#!/usr/bin/env python3
"""Validate engineering documentation only. Does not test the runtime."""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", help="Optional JSON report path relative to repository root"
    )
    args = parser.parse_args()
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    try:
        cat = json.loads((ROOT / "docs/catalog.json").read_text())
        reqs = json.loads((ROOT / "docs/01-requirements/requirements.json").read_text())
        tests = json.loads((ROOT / "docs/05-validation/test-cases.json").read_text())
        backlog = json.loads(
            (ROOT / "docs/04-development/development_backlog.json").read_text()
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {"status": "FAIL", "scope": "documentation_only", "error": str(exc)}
            )
        )
        return 1
    docs = cat["documents"]
    check(len(docs) == 30, "Expected all 30 lifecycle documents")
    check(
        {d["number"] for d in docs} == set(range(1, 31)),
        "Document numbering is incomplete/duplicated",
    )
    docids = {d["id"] for d in docs}
    taskids = {t["id"] for t in backlog["tasks"]}
    testids = {t["id"] for t in tests}
    check(len(docids) == len(docs), "Duplicate document IDs")
    check(len(taskids) == len(backlog["tasks"]), "Duplicate task IDs")
    check(len(testids) == len(tests), "Duplicate test IDs")
    check(len({r["id"] for r in reqs}) == len(reqs), "Duplicate requirement IDs")
    expected_fr = {
        "FR-1.1",
        "FR-1.2",
        "FR-1.3",
        "FR-2.1",
        "FR-2.2",
        "FR-2.3",
        "FR-3.1",
        "FR-3.2",
        "FR-4.1",
        "FR-4.2",
        "FR-4.3",
        "FR-5.1",
        "FR-5.2",
    }
    check(
        {r["id"] for r in reqs if r["id"].startswith("FR-")} == expected_fr,
        "FR list differs from user PRD",
    )
    mapped_tests = set()
    for d in docs:
        p = ROOT / "docs" / d["path"]
        check(p.is_file(), f"Missing document {d['path']}")
        if p.is_file():
            text = p.read_text()
            check(d["id"] in text, f"Document ID not in {p.name}")
            check(d["status"] in text, f"Status missing in {p.name}")
            check(len(text) > 500, f"Document is an empty placeholder: {p.name}")
    for r in reqs:
        for key, valid in [
            ("tasks", taskids),
            ("tests", testids),
            ("design_docs", docids),
        ]:
            check(bool(r[key]), f"{r['id']}: empty {key}")
            check(
                set(r[key]) <= valid, f"{r['id']}: unknown {key}: {set(r[key]) - valid}"
            )
        mapped_tests.update(r["tests"])
        check(
            bool(r.get("acceptance")) and bool(r.get("owner")),
            f"{r['id']}: missing owner/acceptance",
        )
        if r.get("verification_status") in ("pass", "passed", "verified"):
            check(bool(r.get("evidence")), f"{r['id']}: verified without evidence")
    check(
        mapped_tests == testids, f"Unmapped test IDs: {sorted(testids - mapped_tests)}"
    )
    for t in tests:
        check(
            bool(t["stimulus"]) and bool(t["oracle"]),
            f"{t['id']}: missing stimulus/oracle",
        )
        if t["status"] in ("passed", "pass"):
            check(bool(t.get("evidence")), f"{t['id']}: pass without evidence")
    totals = {
        o: sum(t["estimated_person_days"] for t in backlog["tasks"] if t["owner"] == o)
        for o in "ABC"
    }
    check(
        totals == backlog["estimated_days_by_owner"],
        "Owner workload totals inconsistent",
    )
    check(
        sum(totals.values()) == backlog["planned_person_days"],
        "Total workload inconsistent",
    )
    check(
        backlog["planned_person_days"] + backlog["buffer_person_days"] == 120,
        "Capacity differs from 3 people x 8 weeks x 5 days",
    )
    paths = [ROOT / "README.md", ROOT / "CONTRIBUTING.md"]
    paths += [
        p
        for p in (ROOT / "docs").rglob("*.md")
        if not {"archive", "plans"} & set(p.relative_to(ROOT / "docs").parts)
    ]
    paths += list((ROOT / "src").rglob("README.md"))
    paths += [
        ROOT / p / "README.md"
        for p in ["dashboard", "demo", "benchmarks", "config", "policies", "tests"]
    ]
    link_count = 0
    for p in paths:
        if not p.exists():
            errors.append(f"Missing Markdown file: {p}")
            continue
        text = p.read_text()
        check(
            text.count("```") % 2 == 0, f"Unbalanced code fence: {p.relative_to(ROOT)}"
        )
        for target in re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", text):
            target = target.strip().strip("<>")
            if urlsplit(target).scheme or target.startswith("#"):
                continue
            path = unquote(target.split("#", 1)[0])
            if not path:
                continue
            dest = (p.parent / path).resolve()
            check(
                dest.exists(), f"Broken local link in {p.relative_to(ROOT)}: {target}"
            )
            link_count += 1
    report = {
        "status": "PASS" if not errors else "FAIL",
        "scope": "documentation_only",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "lifecycle_documents": len(docs),
        "requirements_and_goals": len(reqs),
        "test_designs": len(tests),
        "work_packages": len(taskids),
        "person_days_by_owner": totals,
        "planned_person_days": sum(totals.values()),
        "buffer_person_days": backlog["buffer_person_days"],
        "local_links_checked": link_count,
        "business_tests_run": 0,
        "benchmark_runs": 0,
        "runtime_implemented": cat["runtime_implemented"],
        "errors": errors,
    }
    if args.output:
        out = ROOT / args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Recover generated docs from 5090 without overwriting unsynchronized local edits."""

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PATHS = [
    "docs/generated",
    "docs/catalog.json",
    "docs/01-requirements/requirements.json",
    "docs/01-requirements/06-requirement-traceability-matrix.md",
    "docs/04-development/development_backlog.json",
    "docs/05-validation/test-cases.json",
    "docs/05-validation/16-test-plan.md",
    "docs/05-validation/18-test-benchmark-report.md",
    "docs/05-validation/public-benchmark-report.md",
    "docs/05-validation/live-benchmark-progress.md",
    "docs/05-validation/vllm-tuning-report.md",
    "docs/05-validation/asb-pilot-progress.md",
]
PATHS += [
    "docs/evidence/" + name
    for name in [
        "runtime-tests.json",
        "coverage-summary.json",
        "runtime-report.json",
        "source-manifest.json",
        "golden-report.json",
        "perf-cpu.json",
        "public-benchmark-report.json",
        "live-mcp.json",
        "live-hooks.json",
        "codex-cli-spike.json",
        "live-benchmark-progress.json",
        "vllm-tuning-report.json",
        "asb-pilot-progress.json",
    ]
]


def main():
    raw = subprocess.check_output(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "5090",
            "tar",
            "-C",
            "/root/autodl-tmp/AgentSentry",
            "-czf",
            "-",
            *PATHS,
        ]
    )
    entries = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for member in archive.getmembers():
            rel = PurePosixPath(member.name)
            if (
                rel.is_absolute()
                or ".." in rel.parts
                or not str(rel).startswith("docs/")
                or not (member.isdir() or member.isfile())
            ):
                raise ValueError("UNSAFE_ARCHIVE_MEMBER")
            if member.isfile():
                entries.append((str(rel), archive.extractfile(member).read()))
    base_path = ROOT / "artifacts/sync-base.json"
    base = json.loads(base_path.read_text()) if base_path.exists() else {}
    # sync-base is a path -> hash mapping, written by sync_server.py.
    conflicts = []
    for relative, data in entries:
        target = ROOT / relative
        if target.is_symlink():
            conflicts.append(relative)
            continue
        if target.exists():
            current = hashlib.sha256(target.read_bytes()).hexdigest()
            if current not in {base.get(relative), hashlib.sha256(data).hexdigest()}:
                conflicts.append(relative)
    if conflicts:
        raise SystemExit(
            "Local changes need review before evidence recovery: "
            + ", ".join(conflicts)
        )
    for relative, data in entries:
        target = ROOT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        base[relative] = hashlib.sha256(data).hexdigest()
    base_path.parent.mkdir(exist_ok=True)
    base_path.write_text(json.dumps(base, indent=2) + "\n")
    print(json.dumps({"recovered_generated_files": len(entries)}))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Reproducible Python token-clone audit, not a plagiarism/originality certificate."""

import argparse
import hashlib
import io
import json
import keyword
import tarfile
import tokenize
from collections import defaultdict
from pathlib import Path


def tokens(raw, normalize_names):
    result = []
    ignored = {
        tokenize.COMMENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENCODING,
        tokenize.ENDMARKER,
    }
    for item in tokenize.tokenize(io.BytesIO(raw).readline):
        if item.type in ignored:
            continue
        value = item.string
        if (
            normalize_names
            and item.type == tokenize.NAME
            and not keyword.iskeyword(value)
        ):
            value = "<identifier>"
        result.append(((item.type, value), item.start[0]))
    return result


def audit(files, window, normalized):
    streams = {name: tokens(raw, normalized) for name, raw in sorted(files.items())}
    matches = defaultdict(list)
    for name, stream in streams.items():
        values = [t[0] for t in stream]
        for offset in range(len(values) - window + 1):
            matches[tuple(values[offset : offset + window])].append((name, offset))
    covered = {name: set() for name in files}
    examples = []
    for occurrences in matches.values():
        if len(occurrences) < 2:
            continue
        accepted = []
        for name, offset in occurrences:
            if any(
                other != name or abs(start - offset) >= window
                for other, start in occurrences
            ):
                covered[name].update(range(offset, offset + window))
                accepted.append({"file": name, "line": streams[name][offset][1]})
        if (
            accepted
            and len(examples) < 12
            and not any(
                e[0]["file"] == accepted[0]["file"]
                and abs(e[0]["line"] - accepted[0]["line"]) < 15
                for e in examples
            )
        ):
            examples.append(accepted[:4])
    total = sum(len(s) for s in streams.values())
    cloned = sum(len(s) for s in covered.values())
    return {
        "minimum_tokens": window,
        "mode": "identifier_normalized" if normalized else "exact",
        "total_tokens": total,
        "clone_covered_tokens": cloned,
        "clone_coverage": cloned / total if total else 0,
        "examples": examples,
        "per_file": {
            n: {"tokens": len(streams[n]), "covered": len(covered[n])}
            for n in sorted(files)
        },
    }


def selected(name):
    path = Path(name)
    return (
        path.suffix == ".py"
        and path.parts[0] in {"src", "benchmarks", "scripts"}
        and "__pycache__" not in path.parts
    )


def summary(files):
    return {
        "files": len(files),
        "file_sha256": {
            n: hashlib.sha256(b).hexdigest() for n, b in sorted(files.items())
        },
        "measurements": [
            audit(files, w, mode) for mode in [False, True] for w in [50, 100, 200]
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-archive", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("docs/evidence/code-duplication.json")
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    current = {
        str(p.relative_to(root)): p.read_bytes()
        for folder in ["src", "benchmarks", "scripts"]
        for p in (root / folder).rglob("*.py")
        if selected(str(p.relative_to(root)))
    }
    report = {
        "method": "Python significant-token contiguous clones; overlapping self matches excluded; strings/numbers preserved",
        "scope": "First-party Python src, benchmarks and scripts. Tests, generated JS, dependencies and upstream artifacts excluded explicitly.",
        "limitations": "Not cross-project plagiarism detection. No Type-III semantic clones or TS/JS scan. Similar boilerplate is counted. No claimed university plagiarism percentage.",
        "current": summary(current),
    }
    if args.baseline_archive:
        with tarfile.open(args.baseline_archive, "r:gz") as archive:
            before = {
                m.name: archive.extractfile(m).read()
                for m in archive.getmembers()
                if m.isfile() and selected(m.name)
            }
        common = set(before) & set(current)
        report.update(
            baseline_archive_sha256=hashlib.sha256(
                args.baseline_archive.read_bytes()
            ).hexdigest(),
            baseline=summary(before),
            common_files_comparison={
                "before": summary({n: before[n] for n in common}),
                "after": summary({n: current[n] for n in common}),
            },
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "files": report["current"]["files"],
                "measurements": [
                    {k: v for k, v in m.items() if k not in {"examples", "per_file"}}
                    for m in report["current"]["measurements"]
                ],
            }
        )
    )


if __name__ == "__main__":
    main()

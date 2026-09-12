#!/usr/bin/env python3
"""Fetch primary benchmark source at immutable GitHub commits; never execute it."""

import argparse
import hashlib
import io
import json
import tarfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

REPOS = {
    "agentdojo": "ethz-spylab/agentdojo",
    "InjecAgent": "uiuc-kang-lab/InjecAgent",
    "ASB": "agiresearch/ASB",
    "MSB": "dongsenzhang/MSB",
    "MPBench": "Digital-Trust-Lab/mp-bench",
    "PIGuard": "leolee99/PIGuard",
}


def fetch(name, root):
    repo = REPOS[name]
    with urllib.request.urlopen(
        "https://api.github.com/repos/" + repo + "/commits/main", timeout=30
    ) as r:
        commit = json.load(r)["sha"]
    url = "https://codeload.github.com/" + repo + "/tar.gz/" + commit
    with urllib.request.urlopen(url, timeout=120) as r:
        raw = r.read(256 * 1024 * 1024 + 1)
    if len(raw) > 256 * 1024 * 1024:
        raise ValueError("SOURCE_ARCHIVE_BUDGET")
    target = root / (name + "-" + commit[:12])
    if not target.exists():
        target.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            total = 0
            for entry in tar:
                parts = PurePosixPath(entry.name).parts
                if (
                    PurePosixPath(entry.name).is_absolute()
                    or ".." in parts
                    or not (entry.isfile() or entry.isdir())
                ):
                    raise ValueError("UNSAFE_SOURCE_ARCHIVE")
                if len(parts) < 2:
                    continue
                path = target.joinpath(*parts[1:])
                if entry.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    total += entry.size
                    if total > 1024 * 1024 * 1024:
                        raise ValueError("SOURCE_EXPANSION_BUDGET")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(tar.extractfile(entry).read())
    record = {
        "benchmark": name,
        "repository": "https://github.com/" + repo,
        "commit": commit,
        "archive_url": url,
        "archive_sha256": hashlib.sha256(raw).hexdigest(),
        "source_dir": str(target),
        "executed": False,
    }
    (target / "agentsentry-source.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("names", nargs="*", choices=list(REPOS))
    p.add_argument("--root", type=Path, default=Path("artifacts/upstream"))
    a = p.parse_args()
    a.root.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(fetch, name, a.root) for name in (a.names or list(REPOS))
        ]
        for f in futures:
            print(json.dumps(f.result()), flush=True)

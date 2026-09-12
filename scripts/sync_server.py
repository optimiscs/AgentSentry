#!/usr/bin/env python3
"""Synchronize reviewed source/docs to 5090 without overwriting unexpected edits."""

import base64
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {
    ".git",
    ".venv",
    ".cache",
    "node_modules",
    "artifacts",
    "runtime-data",
    "models",
    "datasets",
    "__pycache__",
    ".pytest_cache",
    "htmlcov",
    "build",
    "dist",
}
# These files are owned by finite server-side experiments/progress writers.
REMOTE_GENERATED = {
    "docs/evidence/live-benchmark-progress.json",
    "docs/05-validation/live-benchmark-progress.md",
    "docs/evidence/vllm-tuning-report.json",
    "docs/05-validation/vllm-tuning-report.md",
    "docs/evidence/asb-pilot-progress.json",
    "docs/05-validation/asb-pilot-progress.md",
}
REMOTE_CODE = r"""
import json,sys,base64,hashlib,os,tempfile
from pathlib import Path,PurePosixPath
obj=json.load(sys.stdin);root=Path('/root/autodl-tmp/AgentSentry')
changes=[];conflicts=[]
for item in obj['files']:
 rel=PurePosixPath(item['path'])
 if rel.is_absolute() or '..' in rel.parts:raise ValueError('Invalid path')
 path=root/str(rel);raw=base64.b64decode(item['data'])
 if path.is_symlink():conflicts.append(str(rel));continue
 current=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
 if current==item['sha256']:continue
 if current is not None and current!=item.get('expected'):conflicts.append(str(rel));continue
 changes.append((path,raw))
if conflicts:raise RuntimeError('Unexpected server changes: '+json.dumps(conflicts))
for path,raw in changes:
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.sync-',dir=path.parent)
 with os.fdopen(fd,'wb') as f:f.write(raw)
 os.chmod(tmp,0o644);os.replace(tmp,path)
print(json.dumps({'changed_files':len(changes),'verified_files':len(obj['files']),'remote_root':str(root)}))
"""


def main():
    state = ROOT / "artifacts/sync-base.json"
    previous = json.loads(state.read_text()) if state.exists() else {}
    records = []
    current = {k: v for k, v in previous.items() if k in REMOTE_GENERATED}
    for f in sorted(ROOT.rglob("*")):
        rel = f.relative_to(ROOT)
        if (
            not f.is_file()
            or rel.as_posix() in REMOTE_GENERATED
            or EXCLUDE & set(rel.parts)
            or any(p.endswith(".egg-info") for p in rel.parts)
            or f.name in {".coverage"}
        ):
            continue
        raw = f.read_bytes()
        h = hashlib.sha256(raw).hexdigest()
        current[rel.as_posix()] = h
        records.append(
            {
                "path": rel.as_posix(),
                "data": base64.b64encode(raw).decode(),
                "sha256": h,
                "expected": previous.get(rel.as_posix()),
            }
        )
    result = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=12",
            "5090",
            "python3 -c " + shlex.quote(REMOTE_CODE),
        ],
        input=json.dumps({"files": records}),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise SystemExit(
            result.stderr.strip().splitlines()[-1]
            if result.stderr.strip()
            else "SSH synchronization failed"
        )
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps(current, indent=2) + "\n")
    print(result.stdout)


if __name__ == "__main__":
    main()

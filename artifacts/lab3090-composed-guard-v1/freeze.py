"""Freeze the reviewed candidate and a patch against its verified parent."""
import difflib
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL = Path(__file__).resolve().parent
CANDIDATE = ROOT / "artifacts/development/composed-guard-v1"
PARENT = ROOT / "artifacts/development/context-filter-v5"
origin = json.loads((CANDIDATE / "origin-manifest.json").read_text())
names = sorted(set(origin["base_files"]) | {
    "src/agentsentry/context/defense.py",
    "benchmarks/context_options.py",
    "tests/test_context_defense.py",
})
archive_path = CONTROL / "source-candidate.tar.gz"
assert not archive_path.exists(), "FROZEN_ARCHIVE_ALREADY_EXISTS"
files, patches, changed = {}, [], []
for name in names:
    old = (PARENT / name).read_bytes() if name in origin["base_files"] else b""
    if name in origin["base_files"]:
        assert hashlib.sha256(old).hexdigest() == origin["base_files"][name], name
    new = (CANDIDATE / name).read_bytes()
    files[name] = hashlib.sha256(new).hexdigest()
    if old != new:
        changed.append(name)
        patches.extend(difflib.unified_diff(
            old.decode().splitlines(keepends=True), new.decode().splitlines(keepends=True),
            fromfile="a/" + name if name in origin["base_files"] else "/dev/null",
            tofile="b/" + name, n=0,
        ))
manifest = {"status": "FROZEN_DEVELOPMENT_CANDIDATE", "parent_archive_sha256": origin["parent_archive_sha256"], "files": files}
serialized = json.dumps(manifest, indent=2) + "\n"
(CONTROL / "candidate-manifest.json").write_text(serialized)
(CANDIDATE / "candidate-manifest.json").write_text(serialized)
(CONTROL / "changes.patch").write_text("".join(patches))
with tarfile.open(archive_path, "w:gz") as archive:
    for name in names:
        archive.add(CANDIDATE / name, arcname=name, recursive=False)
freeze = {"status": manifest["status"], "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
          "source_files": len(files), "changed_files": changed, "promoted": False,
          "parent_archive_sha256": origin["parent_archive_sha256"], "imports": origin["imports"],
          "hypothesis": origin["hypothesis"], "actor_thinking": False, "guard_thinking": False}
(CONTROL / "freeze.json").write_text(json.dumps(freeze, indent=2) + "\n")
print(json.dumps(freeze))

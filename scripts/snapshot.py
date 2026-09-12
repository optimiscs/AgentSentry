#!/usr/bin/env python3
"""Encrypted cold backups. Stop the single runtime before backup; restore into an empty directory."""

import argparse
import fcntl
import io
import json
import os
import tarfile
from pathlib import Path
from cryptography.fernet import Fernet


def backup(state: Path, output: Path, key_file: Path):
    if output.exists():
        raise ValueError("BACKUP_ALREADY_EXISTS")
    with (state / "runtime.lock").open("a") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if key_file.exists():
            key = key_file.read_bytes().strip()
        else:
            key = Fernet.generate_key()
            fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(key + b"\n")
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w:gz") as tar:
            for name in (
                "active.aspolicy",
                "agentsentry.db",
                "agentsentry.db-wal",
                "agentsentry.db-shm",
                "vault.key",
                "approval.key",
                "operator.token",
                "agent.token",
                "workspace",
                "demo-remote.git",
            ):
                path = state / name
                if path.exists():
                    tar.add(path, arcname=name, recursive=True)
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(Fernet(key).encrypt(data.getvalue()))


def restore(archive: Path, destination: Path, key_file: Path):
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("RESTORE_REQUIRES_EMPTY_DESTINATION")
    data = Fernet(key_file.read_bytes().strip()).decrypt(archive.read_bytes())
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.chmod(0o700)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        # No absolute paths, hardlinks, symlinks, devices, or traversal may be restored.
        members = tar.getmembers()
        for member in members:
            path = Path(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("UNSAFE_BACKUP_MEMBER")
        tar.extractall(destination, members=members, filter="data")
    # The Runtime's fresh epoch also invalidates all restored pending approvals on startup.
    for name in ("vault.key", "approval.key", "operator.token", "agent.token"):
        if (destination / name).exists():
            (destination / name).chmod(0o600)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["backup", "restore"])
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--key-file", type=Path, required=True)
    a = p.parse_args()
    if a.action == "backup":
        backup(a.state, a.archive, a.key_file)
    else:
        restore(a.archive, a.state, a.key_file)
    print(
        json.dumps(
            {"action": a.action, "archive": str(a.archive), "state": str(a.state)}
        )
    )


if __name__ == "__main__":
    main()

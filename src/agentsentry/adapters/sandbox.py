from __future__ import annotations

import ctypes.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .filesystem import BoundaryError


class PythonSandbox:
    """Ephemeral Linux chroot + uid drop + seccomp + CPU/memory/output budgets."""

    def __init__(self, state_dir: Path):
        self.base = state_dir / "sandbox-base"
        self.jobs = state_dir / "sandbox-jobs"
        self.jobs.mkdir(exist_ok=True)
        self.python = Path("/usr/bin/python3").resolve()

    def available(self) -> bool:
        if (
            sys.platform != "linux"
            or os.geteuid() != 0
            or not ctypes.util.find_library("seccomp")
        ):
            return False
        caps = next(
            (
                l.split()[1]
                for l in Path("/proc/self/status").read_text().splitlines()
                if l.startswith("CapEff:")
            ),
            "0",
        )
        return bool(int(caps, 16) & (1 << 18))

    def prepare(self):
        if not self.available():
            raise BoundaryError("SANDBOX_UNAVAILABLE_FAIL_CLOSED")
        if (self.base / ".ready").exists():
            return
        self.base.mkdir(exist_ok=True)

        def copy_binary(src: Path):
            target = self.base / src.relative_to("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(src, target, follow_symlinks=True)
            p = subprocess.run(
                ["ldd", str(src)], capture_output=True, text=True, timeout=10
            )
            for match in re.findall(r"(/[^\s()]+)", p.stdout):
                f = Path(match)
                if f.is_file():
                    dst = self.base / f.relative_to("/")
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if not dst.exists():
                        shutil.copy2(f, dst, follow_symlinks=True)

        copy_binary(self.python)
        version = subprocess.check_output(
            [
                str(self.python),
                "-c",
                'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")',
            ],
            text=True,
        ).strip()
        lib = Path("/usr/lib") / f"python{version}"
        shutil.copytree(
            lib,
            self.base / lib.relative_to("/"),
            dirs_exist_ok=True,
            symlinks=False,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "site-packages",
                "dist-packages",
                "test",
                "tests",
                "ensurepip",
                "idlelib",
                "tkinter",
            ),
        )
        for f in (self.base / lib.relative_to("/")).rglob("*.so"):
            original = Path("/") / f.relative_to(self.base)
            copy_binary(original)
        (self.base / "work").mkdir(exist_ok=True)
        (self.base / "tmp").mkdir(exist_ok=True)
        (self.base / ".ready").write_text("python-chroot-seccomp-1.0")

    def run(self, code: str) -> dict:
        self.prepare()
        with tempfile.TemporaryDirectory(prefix="job-", dir=self.jobs) as job:
            jail = Path(job) / "root"
            shutil.copytree(self.base, jail, copy_function=os.link)
            for name in ["work", "tmp"]:
                os.chown(jail / name, 65534, 65534)
                os.chmod(jail / name, 0o700)
            out_path = Path(job) / "stdout"
            err_path = Path(job) / "stderr"
            worker = Path(__file__).with_name("sandbox_worker.py")
            with out_path.open("wb") as stdout, err_path.open("wb") as stderr:
                proc = subprocess.Popen(
                    [str(self.python), str(worker), str(jail), str(self.python)],
                    stdin=subprocess.PIPE,
                    stdout=stdout,
                    stderr=stderr,
                    env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"},
                    start_new_session=True,
                    close_fds=True,
                )
                try:
                    proc.communicate(json.dumps({"code": code}).encode(), timeout=5)
                except subprocess.TimeoutExpired:
                    import signal

                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                    return {
                        "exit_code": -1,
                        "stdout": out_path.read_bytes()[:65536].decode(
                            errors="replace"
                        ),
                        "stderr": "SANDBOX_TIMEOUT",
                        "isolation": "chroot+uid+seccomp",
                    }
            return {
                "exit_code": proc.returncode,
                "stdout": out_path.read_bytes()[:65536].decode(errors="replace"),
                "stderr": err_path.read_bytes()[:65536].decode(errors="replace"),
                "isolation": "chroot+uid+seccomp",
            }

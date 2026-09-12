from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from agentsentry.schemas import digest


class BoundaryError(ValueError):
    pass


def relative_path(root: Path, value: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or len(value) > 2048:
        raise BoundaryError("INVALID_PATH")
    p = Path(value)
    if p.is_absolute():
        try:
            p = p.relative_to(root)
        except ValueError:
            raise BoundaryError("OUTSIDE_STATIC_BOUNDARY")
    if any(part in {".."} for part in p.parts):
        raise BoundaryError("PATH_TRAVERSAL")
    parts = [part for part in p.parts if part not in {".", ""}]
    if not parts:
        raise BoundaryError("FILE_PATH_REQUIRED")
    return "/".join(parts)


def stamp(st) -> str:
    return digest(
        [st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns]
    )


@contextmanager
def parent_fd(root: Path, relative: str):
    parts = PurePosixPath(relative).parts
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            os.close(fd)
            fd = child
        yield fd, parts[-1]
    finally:
        os.close(fd)


def inspect(root: Path, relative: str) -> str:
    try:
        with parent_fd(root, relative) as (fd, name):
            try:
                st = os.stat(name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                return "missing"
            if not stat.S_ISREG(st.st_mode):
                raise BoundaryError("NOT_REGULAR_FILE")
            return stamp(st)
    except OSError as exc:
        raise BoundaryError("UNSAFE_OR_MISSING_PARENT") from exc


def read(root: Path, relative: str, expected: str, limit: int) -> str:
    with parent_fd(root, relative) as (parent, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode) or stamp(st) != expected:
                raise BoundaryError("RESOURCE_CHANGED")
            if st.st_size > limit:
                raise BoundaryError("FILE_BUDGET_EXCEEDED")
            data = os.read(fd, limit + 1)
            if len(data) > limit:
                raise BoundaryError("FILE_BUDGET_EXCEEDED")
            if stamp(os.fstat(fd)) != expected:
                raise BoundaryError("RESOURCE_CHANGED")
            return data.decode("utf-8", errors="replace")
        finally:
            os.close(fd)


def write(root: Path, relative: str, expected: str, content: str, limit: int) -> dict:
    data = content.encode()
    if len(data) > limit:
        raise BoundaryError("FILE_BUDGET_EXCEEDED")
    with parent_fd(root, relative) as (parent, name):
        flags = os.O_WRONLY | os.O_NOFOLLOW
        if expected == "missing":
            flags |= os.O_CREAT | os.O_EXCL
        fd = os.open(name, flags, 0o600, dir_fd=parent)
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise BoundaryError("NOT_REGULAR_FILE")
            if expected != "missing" and stamp(st) != expected:
                raise BoundaryError("RESOURCE_CHANGED")
            os.ftruncate(fd, 0)
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view) :]
            os.fsync(fd)
            return {"path": relative, "bytes_written": len(data)}
        finally:
            os.close(fd)

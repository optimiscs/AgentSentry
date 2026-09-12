"""Trusted one-shot child. Never import this module in the API process."""

import ctypes
import ctypes.util
import errno
import json
import os
import resource
import sys


def main():
    request = json.loads(sys.stdin.buffer.read(32768))
    code = request["code"]
    if not isinstance(code, str) or len(code) > 16384:
        raise ValueError("CODE_BUDGET_EXCEEDED")
    jail, interpreter = sys.argv[1:3]
    seccomp = ctypes.CDLL(ctypes.util.find_library("seccomp"), use_errno=True)
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    libc = ctypes.CDLL(None, use_errno=True)
    ctx = seccomp.seccomp_init(0x7FFF0000)
    if not ctx:
        raise RuntimeError("SECCOMP_INIT_FAILED")
    for name in [
        "socket",
        "socketpair",
        "connect",
        "bind",
        "listen",
        "accept",
        "accept4",
        "clone",
        "clone3",
        "fork",
        "vfork",
        "ptrace",
        "mount",
        "umount2",
        "unshare",
        "setns",
        "bpf",
        "kexec_load",
        "reboot",
        "open_by_handle_at",
        "chroot",
    ]:
        number = seccomp.seccomp_syscall_resolve_name(name.encode())
        if (
            number >= 0
            and seccomp.seccomp_rule_add(ctx, 0x00050000 | errno.EPERM, number, 0) != 0
        ):
            raise RuntimeError("SECCOMP_RULE_FAILED")
    os.chdir(jail)
    os.chroot(jail)
    os.chdir("/work")
    os.setgroups([])
    os.setgid(65534)
    os.setuid(65534)
    for kind, limit in [
        (resource.RLIMIT_CPU, 2),
        (resource.RLIMIT_AS, 256 * 1024 * 1024),
        (resource.RLIMIT_FSIZE, 65536),
        (resource.RLIMIT_NOFILE, 32),
        (resource.RLIMIT_NPROC, 1),
        (resource.RLIMIT_CORE, 0),
    ]:
        resource.setrlimit(kind, (limit, limit))
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise RuntimeError("NO_NEW_PRIVILEGES_FAILED")
    libc.prctl(4, 0, 0, 0, 0)
    if seccomp.seccomp_load(ctx) != 0:
        raise RuntimeError("SECCOMP_LOAD_FAILED")
    seccomp.seccomp_release(ctx)
    os.execve(
        interpreter,
        [interpreter, "-I", "-S", "-c", code],
        {"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"},
    )


if __name__ == "__main__":
    main()

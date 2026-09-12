from __future__ import annotations

import ipaddress
import re
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from agentsentry.config import Settings
from agentsentry.context.scanner import secret_labels
from agentsentry.intent.contracts import destination_hash
from agentsentry.schemas import ActionIR, Effect, Session, digest

from .filesystem import BoundaryError, inspect, relative_path

TOOL_FIELDS = {
    "fs.read": ({"path"}, {"path"}),
    "fs.write": ({"path", "content"}, {"path", "content"}),
    "http.request": ({"url", "method", "body"}, {"url"}),
    "exec.python": ({"code"}, {"code"}),
    "git.status": (set(), set()),
    "git.diff": (set(), set()),
    "git.commit": ({"message"}, {"message"}),
    "git.push": ({"branch"}, {"branch"}),
    "agent.delegate": ({"task", "scope"}, {"task"}),
    "memory.write": ({"name", "content"}, {"name", "content"}),
    "memory.read": ({"memory_id"}, {"memory_id"}),
    "github.get_issue": ({"number"}, {"number"}),
}
CREDENTIAL = re.compile(
    r"(^|/)(?:\.ssh|\.aws)(?:/|$)|(?:id_rsa|id_ed25519|credentials|private[_-]?key)|(?:^|/)\.env(?:\.|$)",
    re.I,
)


def git(root: Path, *args: str) -> str:
    env = {
        "PATH": "/usr/bin:/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LC_ALL": "C",
    }
    p = subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "protocol.ext.allow=never",
            "-C",
            str(root),
            *args,
        ],
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    if p.returncode:
        raise BoundaryError("GIT_OPERATION_FAILED")
    return p.stdout.strip()


def network_target(settings: Settings, url: str) -> tuple[str, str, list[str]]:
    u = urlsplit(url)
    if (
        u.scheme not in {"http", "https"}
        or not u.hostname
        or u.username
        or u.password
        or u.fragment
    ):
        raise BoundaryError("INVALID_DESTINATION")
    host = u.hostname.lower().rstrip(".")
    try:
        port = u.port or (443 if u.scheme == "https" else 80)
    except ValueError:
        raise BoundaryError("INVALID_PORT")
    if settings.demo:
        if host not in {
            "corp.example.test",
            "unknown.example.test",
            "attacker.example.test",
        } or port not in {80, 443}:
            raise BoundaryError("DEMO_DESTINATION_NOT_REGISTERED")
        return (
            host,
            "TRUSTED" if host in settings.trusted_domains else "UNKNOWN",
            ["demo-sink"],
        )
    if host not in settings.network_allowlist or port not in {80, 443}:
        raise BoundaryError("DESTINATION_OUTSIDE_ALLOWLIST")
    addresses = sorted(
        {row[4][0] for row in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    )
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise BoundaryError("PRIVATE_DESTINATION")
    return host, "TRUSTED" if host in settings.trusted_domains else "UNKNOWN", addresses


class Registry:
    def __init__(self, settings: Settings):
        self.settings = settings

    def normalize(
        self,
        session: Session,
        tool: str,
        args: dict,
        contexts: list[dict],
        action_id: str | None = None,
    ) -> ActionIR:
        labels = set()
        sources = []
        for c in contexts:
            labels.update(c.get("labels", []))
            sources.append(c["chunk_id"])
        labels.update(secret_labels(str(args)))
        base = dict(
            session_id=session.session_id,
            tool=tool,
            effects=[Effect.OTHER],
            resource=tool,
            args_hash=digest(args),
            labels=sorted(labels),
            source_refs=sources,
            agent_depth=session.depth,
            source_type=contexts[-1]["source_type"] if contexts else "USER",
            source_trust="UNTRUSTED" if contexts else "UNKNOWN",
        )
        if action_id:
            base["action_id"] = action_id
        a = ActionIR(**base)
        try:
            if tool not in TOOL_FIELDS:
                raise BoundaryError("UNKNOWN_TOOL")
            allowed, required = TOOL_FIELDS[tool]
            if not required <= set(args) or not set(args) <= allowed:
                raise BoundaryError("INVALID_TOOL_ARGUMENTS")
            if any(not isinstance(v, str) for k, v in args.items() if k != "number"):
                raise BoundaryError("INVALID_TOOL_ARGUMENT_TYPE")
            a.scope_valid = True
            a.scope_allowed = True
            a.resource_class = "PUBLIC"
            if tool.startswith("fs."):
                path = args["path"]
                a.resource_class = (
                    "CREDENTIAL"
                    if CREDENTIAL.search(path)
                    else "SYSTEM"
                    if path.startswith("/etc/")
                    else "REPO"
                )
                relative = relative_path(self.settings.workspace, path)
                a.resource = relative
                a.effects = [
                    Effect.FILE_READ if tool == "fs.read" else Effect.FILE_WRITE
                ]
                # Stat only: sensitive bytes are never read during normalization.
                a.resource_version = inspect(self.settings.workspace, relative)
                a.scope_allowed = self.in_scope(session, relative)
                if (
                    tool == "fs.write"
                    and len(args["content"].encode()) > self.settings.max_file
                ):
                    raise BoundaryError("FILE_BUDGET_EXCEEDED")
                if relative.startswith(".git/") or relative == ".git":
                    raise BoundaryError("GIT_INTERNAL_WRITE_DENIED")
            elif tool == "http.request":
                a.effects = [Effect.NET_EGRESS]
                a.resource = args["url"]
                method = args.get("method", "POST").upper()
                if method not in {"GET", "POST"}:
                    raise BoundaryError("UNSUPPORTED_HTTP_METHOD")
                if len(args.get("body", "").encode()) > self.settings.max_file:
                    raise BoundaryError("BODY_BUDGET_EXCEEDED")
                host, trust, addresses = network_target(self.settings, args["url"])
                a.destination_domain = host
                a.destination_trust = trust
                a.destination_hashes = [destination_hash(args["url"])]
                a.resource_version = digest(addresses)
            elif tool == "exec.python":
                a.effects = [Effect.EXEC]
                a.resource = "sandbox://python"
                a.resource_version = digest(args["code"])
                if len(args["code"]) > 16384:
                    raise BoundaryError("CODE_BUDGET_EXCEEDED")
            elif tool.startswith("git."):
                a.resource = "repo://current"
                a.resource_class = "REPO"
                a.effects = [
                    {
                        "git.status": Effect.FILE_READ,
                        "git.diff": Effect.FILE_READ,
                        "git.commit": Effect.GIT_COMMIT,
                        "git.push": Effect.GIT_PUSH,
                    }[tool]
                ]
                if tool == "git.push":
                    a.effects.append(Effect.NET_EGRESS)
                a.scope_allowed = "." in session.intent.allowed_scopes
                head = git(self.settings.workspace, "rev-parse", "HEAD")
                remote = git(self.settings.workspace, "remote", "get-url", "origin")
                if tool == "git.push":
                    branch = args["branch"]
                    if (
                        not re.fullmatch(r"[A-Za-z][A-Za-z0-9_/-]{0,100}", branch)
                        or ".." in branch
                        or branch.endswith("/")
                    ):
                        raise BoundaryError("INVALID_BRANCH")
                    # This release pushes only to its dedicated local bare demo repository.
                    if (
                        Path(remote).resolve()
                        != (self.settings.state_dir / "demo-remote.git").resolve()
                    ):
                        raise BoundaryError("GIT_REMOTE_NOT_REGISTERED")
                snapshot = {"head": head, "remote": remote}
                if tool == "git.commit":
                    files = git(
                        self.settings.workspace,
                        "ls-files",
                        "-co",
                        "--exclude-standard",
                        "-z",
                    ).split("\x00")
                    if len(files) > 4096:
                        raise BoundaryError("GIT_WORKTREE_BUDGET_EXCEEDED")
                    snapshot["files"] = {
                        f: inspect(
                            self.settings.workspace,
                            relative_path(self.settings.workspace, f),
                        )
                        for f in files
                        if f
                    }
                    snapshot["index"] = inspect(self.settings.workspace, ".git/index")
                a.resource_version = digest(snapshot)
            elif tool == "agent.delegate":
                a.effects = [Effect.DELEGATE]
                a.resource = args.get("scope", ".")
                if session.depth >= self.settings.max_depth:
                    raise BoundaryError("DELEGATION_DEPTH_EXCEEDED")
                a.resource_version = digest(session.intent.model_dump(mode="json"))
            elif tool.startswith("memory."):
                a.effects = [
                    Effect.MEMORY_WRITE
                    if tool == "memory.write"
                    else Effect.MEMORY_READ
                ]
                a.resource = "memory://" + args.get("name", args.get("memory_id", ""))
                a.resource_version = digest(args)
                if tool == "memory.write" and (
                    not args["name"]
                    or len(args["name"]) > 128
                    or len(args["content"]) > 32768
                ):
                    raise BoundaryError("MEMORY_BUDGET_EXCEEDED")
            elif tool == "github.get_issue":
                if not self.settings.demo:
                    raise BoundaryError("DEMO_TOOL_DISABLED")
                if (
                    not isinstance(args["number"], int)
                    or isinstance(args["number"], bool)
                    or args["number"] not in {123, 124}
                ):
                    raise BoundaryError("DEMO_ISSUE_NOT_FOUND")
                a.effects = [Effect.FILE_READ]
                a.resource = f"github://demo/repo/issues/{args['number']}"
                a.resource_version = "fixtures-1.0"
        except (BoundaryError, OSError, ValueError, socket.gaierror) as exc:
            a.adapter_valid = False
            a.adapter_error = (
                str(exc) if isinstance(exc, BoundaryError) else "NORMALIZATION_FAILED"
            )
            if a.adapter_error in {"OUTSIDE_STATIC_BOUNDARY", "PATH_TRAVERSAL"}:
                a.scope_valid = False
        return a

    @staticmethod
    def in_scope(session: Session, relative: str) -> bool:
        return any(
            s == "." or relative == s or relative.startswith(s.rstrip("/") + "/")
            for s in session.intent.allowed_scopes
        )

from __future__ import annotations

import os
import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.fernet import Fernet


@dataclass
class Settings:
    state_dir: Path
    workspace: Path
    policy_path: Path
    project_root: Path = field(default_factory=Path.cwd)
    demo: bool = True
    max_context: int = 65536
    max_file: int = 262144
    max_depth: int = 3
    max_actions: int = 1000
    approval_ttl: int = 600
    retention_days: int = 7
    audit_buffer: int = 256
    allow_low_risk_fail_open: bool = False
    trusted_domains: tuple[str, ...] = ("corp.example.test",)
    network_allowlist: tuple[str, ...] = ()
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    )
    detector_model: str | None = None
    external_mcp: dict = field(default_factory=dict)

    def __post_init__(self):
        self.state_dir = Path(self.state_dir).absolute()
        self.workspace = Path(self.workspace).absolute()
        self.policy_path = Path(self.policy_path).absolute()
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.workspace.mkdir(parents=True, exist_ok=True)
        os.chmod(self.state_dir, 0o700)

    def secret(self, name: str, kind: str = "token") -> str:
        path = self.state_dir / name
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if path.is_symlink():
                raise ValueError("Secret file must not be a symlink")
            return path.read_text().strip()
        value = (
            Fernet.generate_key().decode()
            if kind == "fernet"
            else secrets.token_urlsafe(32)
        )
        with os.fdopen(fd, "w") as f:
            f.write(value + "\n")
        return value

    @classmethod
    def from_env(cls):
        root = Path(os.environ.get("AGENTSENTRY_ROOT", Path.cwd()))
        state = Path(os.environ.get("AGENTSENTRY_STATE_DIR", root / "runtime-data"))
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        policy = Path(os.environ.get("AGENTSENTRY_POLICY", state / "active.aspolicy"))
        if not policy.exists() and "AGENTSENTRY_POLICY" not in os.environ:
            policy.write_text((root / "policies/default.aspolicy").read_text())
            policy.chmod(0o600)
        return cls(
            project_root=root,
            state_dir=state,
            workspace=Path(
                os.environ.get("AGENTSENTRY_WORKSPACE", state / "workspace")
            ),
            policy_path=policy,
            demo=os.environ.get("AGENTSENTRY_DEMO", "1") == "1",
            detector_model=os.environ.get("AGENTSENTRY_DETECTOR_MODEL"),
            external_mcp=json.loads(
                (root / "config/mcp-registrations.json").read_text()
            )
            if (root / "config/mcp-registrations.json").exists()
            else {},
            network_allowlist=tuple(
                filter(
                    None, os.environ.get("AGENTSENTRY_NETWORK_ALLOWLIST", "").split(",")
                )
            ),
        )

import importlib.util
from pathlib import Path
import pytest
from agentsentry.gateway.runtime import Runtime
from agentsentry.schemas import ToolCall
from agentsentry.config import Settings

spec = importlib.util.spec_from_file_location(
    "snapshot", Path(__file__).parents[1] / "scripts/snapshot.py"
)
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


@pytest.mark.case("TC-29")
@pytest.mark.case("TC-41")
def test_backup_restore_preserves_audit_invalidates_approval(settings, tmp_path):
    rt = Runtime(settings)
    s = rt.create_session("review")
    pending = rt.call(
        ToolCall(
            session_id=s.session_id,
            tool="fs.write",
            arguments={"path": "pending.md", "content": "x"},
        )
    )
    archive = tmp_path / "backup.asbackup"
    key = tmp_path / "backup.key"
    with pytest.raises(BlockingIOError):
        snapshot.backup(settings.state_dir, archive, key)
    events = rt.store.events(s.trace_id)
    rt.close()
    snapshot.backup(settings.state_dir, archive, key)
    assert b"CANARY_SECRET" not in archive.read_bytes()
    dst = tmp_path / "restored"
    snapshot.restore(archive, dst, key)
    rt = Runtime(Settings(dst, dst / "workspace", settings.policy_path))
    try:
        assert rt.store.events(s.trace_id) == events
        assert rt.pending() == [] and rt.store.execution_count() == 0
        assert rt.store.action(pending.action.action_id)["status"] == "cancelled"
    finally:
        rt.close()
    with pytest.raises(ValueError):
        snapshot.restore(archive, dst, key)

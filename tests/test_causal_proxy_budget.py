import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("causal_budget", Path(__file__).resolve().parents[1] / "scripts/audit_causal_proxy_budget.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_ablations_preserve_message_roles_and_original_data():
    messages = [{"role": "system", "content": "policy"}, {"role": "user", "content": "task"},
                {"role": "assistant", "content": "read"}, {"role": "tool", "content": "source", "tool_call_id": "x"}]
    batch = dict(audit.variants(messages))
    assert len(batch) == 3
    assert batch["without_user"][1]["content"] == ""
    assert batch["without_tool_3"][3] == {"role": "tool", "content": "", "tool_call_id": "x"}
    batch["full"][0]["content"] = "changed"
    assert messages[0]["content"] == "policy"
    assert batch["without_tool_3"][0]["content"] == "policy"


@pytest.mark.parametrize("messages", [[], [{"role": "system", "content": "x"}],
                                     [{"role": "user", "content": "a"}, {"role": "user", "content": "b"}]])
def test_ambiguous_task_boundary_rejected(messages):
    with pytest.raises(ValueError, match="ORIGINAL_USER"):
        list(audit.variants(messages))


@pytest.mark.parametrize("prefix,completed", [([], [1]), ([1, 2], [1, 2]), ([1, 2], [1, 3, 4])])
def test_template_boundary_mismatch_is_not_scored(prefix, completed):
    with pytest.raises(ValueError, match="TARGET_PREFIX"):
        audit.split_target(prefix, completed)


def test_exact_suffix_is_retained_for_scoring():
    assert audit.split_target([1, 2], [1, 2, 3, 4]) == [3, 4]

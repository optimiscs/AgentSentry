import hashlib
import json
import pytest
from agentsentry.evaluation import summarize, classification_metrics, import_native


@pytest.mark.case("TC-22")
def test_error_is_not_security_success(tmp_path):
    rows = [
        {"id": "1", "state": "ok", "attack": False, "utility": True},
        {"id": "2", "state": "error", "attack": False, "utility": False},
    ]
    p = tmp_path / "native.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    manifest = {
        "benchmark": "synthetic-adapter-contract",
        "benchmark_commit": "fixture-1",
        "model": "fixture",
        "configuration": "test",
        "source_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "field_map": {
            "case_id": "id",
            "status": "state",
            "attack_success": "attack",
            "task_success": "utility",
        },
    }
    records, metrics = import_native(p, manifest)
    assert metrics["errors"] == 1 and not metrics["full_run_valid"]
    assert metrics["asr_all_lower_bound"] == 0 and metrics["asr_all_upper_bound"] == 0.5
    p.write_text("modified")
    with pytest.raises(ValueError, match="SOURCE_HASH"):
        import_native(p, manifest)


@pytest.mark.case("TC-37")
def test_macro_f1_hand_computed():
    metrics = classification_metrics(
        ["ALLOW", "ASK", "BLOCK"],
        ["ALLOW", "ALLOW", "BLOCK"],
        ["ALLOW", "ASK", "BLOCK"],
    )
    assert metrics["macro_f1"] == pytest.approx((2 / 3 + 0 + 1) / 3)
    with pytest.raises(ValueError):
        classification_metrics(["ALLOW"], [], ["ALLOW"])


@pytest.mark.case("TC-22")
def test_duplicate_and_missing_native_outcome():
    with pytest.raises(ValueError):
        summarize([{"case_id": "1", "status": "ok", "attack_success": False}])
    with pytest.raises(ValueError):
        summarize([{"case_id": "1", "status": "error"}] * 2)

import copy
import itertools
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mpbench_lifecycle as lifecycle
import prepare_mpbench


def record(partition="adversarial", **fields):
    return {"case_id": "opaque", "source_partition": partition,
            "labels_and_native_fields": {"expected_memory": "target", "retrieval_query": "follow-up", **fields}}


def test_negative_benign_target_does_not_become_desired_memory():
    c = lifecycle.memory_contract(record("benign", legitimate_memory_write=False))
    assert c["write_objective"] == "NO_MEMORY_WRITE"
    assert c["semantic_target"] == "target" and c["issues"] == []


@pytest.mark.parametrize("raw,objective,adapted", [
    (True, "LEGITIMATE_MEMORY_RETENTION", False),
    ("true", "LEGITIMATE_MEMORY_RETENTION", True),
    ("false", "NO_MEMORY_WRITE", True),
    ("False", "UNKNOWN_BENIGN_WRITE_EXPECTATION", False),
    (1, "UNKNOWN_BENIGN_WRITE_EXPECTATION", False),
    (None, "UNKNOWN_BENIGN_WRITE_EXPECTATION", False),
])
def test_only_documented_boolean_repairs_are_allowed(raw, objective, adapted):
    c = lifecycle.memory_contract(record("benign", legitimate_memory_write=raw))
    assert c["write_objective"] == objective
    assert (c["boolean_adaptation"] is not None) == adapted
    assert c["legitimate_memory_write_raw"] == raw


def test_labels_future_questions_and_targets_do_not_enter_first_session():
    item = {"case_id": "opaque", "user_query": "original", "expected_memory": "leaked",
            "external_content": [{"field": "context", "text": "ordinary", "label": "leaked"}]}
    meta = record(retrieval_query=None, agent_question="must not substitute", trigger_phrase="yes")
    first, second = lifecycle.session_inputs(item, meta)
    assert first == {"case_id": "opaque", "user_query": "original", "external_content": [{"field": "context", "text": "ordinary"}]}
    assert second == {"case_id": "opaque", "user_query": None}
    changed = copy.deepcopy(meta)
    changed["labels_and_native_fields"].update(expected_memory="different", retrieval_query="future", attack_type="new")
    assert lifecycle.session_inputs(item, changed)[0] == first
    first["external_content"][0]["text"] = "changed"
    assert item["external_content"][0]["text"] == "ordinary"


def test_missing_attack_target_and_followup_remain_explicit():
    c = lifecycle.memory_contract(record(expected_memory=" ", retrieval_query=None))
    assert c["issues"] == ["MISSING_MEMORY_TARGET", "MISSING_FOLLOWUP_QUERY"]


def test_conditional_bounds_include_unknown_write_denominator():
    p = lifecycle.attack_rates([{"write": True, "recall": True}, {"write": True, "recall": None},
                                {"write": False, "recall": None}, {"write": None, "recall": None}])
    assert p["asr"] is None and p["rsr"] is None
    assert p["asr_bounds"] == [.5, .75]
    assert p["rsr_bounds"] == [1 / 3, 1]
    assert p["rsr_denominator_bounds"] == [2, 3]


def test_no_write_makes_rsr_undefined_not_perfect_defense():
    p = lifecycle.attack_rates([{"write": False, "recall": None}])
    assert p["asr"] == 0 and p["rsr"] is None and p["rsr_bounds"] == [None, None]


@pytest.mark.parametrize("outcome", [{"write": "false", "recall": None},
                                      {"write": 0, "recall": None},
                                      {"write": False, "recall": True},
                                      {"write": None, "recall": False}])
def test_invalid_or_unconditional_recall_claim_is_rejected(outcome):
    with pytest.raises(ValueError):
        lifecycle.attack_rates([outcome])


def test_bounds_match_exhaustive_completions_of_unknown_outcomes():
    # Independent enumeration checks the conditional-ratio extrema, including
    # worlds with zero positive writes where RSR has no denominator.
    states = [(False, None), (True, False), (True, True), (True, None), (None, None)]
    for observed in itertools.product(states, repeat=3):
        possibilities = [[(False, None), (True, False), (True, True)] if w is None else
                         [(True, False), (True, True)] if w and r is None else [(w, r)] for w, r in observed]
        asrs, rsrs = [], []
        for complete in itertools.product(*possibilities):
            written = sum(w for w, _ in complete)
            asrs.append(written / 3)
            if written:
                rsrs.append(sum(r is True for _, r in complete) / written)
        actual = lifecycle.attack_rates([dict(write=w, recall=r) for w, r in observed])
        assert actual["asr_bounds"] == [min(asrs), max(asrs)]
        assert actual["rsr_bounds"] == ([min(rsrs), max(rsrs)] if rsrs else [None, None])


def test_packet_coverage_integrity_and_no_overwrite(tmp_path):
    source, packet, output = (tmp_path / n for n in ["source", "packet", "output"])
    source.mkdir()
    (source / "agentsentry-source.json").write_text(json.dumps({"commit": prepare_mpbench.COMMIT}))
    for partition, filename in prepare_mpbench.FILES.items():
        (source / filename).write_text(json.dumps({"id": partition, "user_query": "task", "context": "text",
                                                  "legitimate_memory_write": "false"}))
    prepare_mpbench.prepare(source, packet)
    report = lifecycle.prepare(packet, output)
    assert report["input_records"] == 2 and report["boolean_adaptations"] == 2
    assert len((output / "write-inputs.jsonl").read_text().splitlines()) == 2
    with pytest.raises(FileExistsError):
        lifecycle.prepare(packet, output)
    with (packet / "inputs.jsonl").open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="PACKET_CHANGED"):
        lifecycle.prepare(packet, tmp_path / "tampered")

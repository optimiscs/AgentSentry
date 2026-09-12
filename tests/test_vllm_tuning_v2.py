"""Serving experiments must preserve quality jobs and reject partial workloads."""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_vllm_tuning_v2 as tuning


class TuningChecks(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "workload": {
                "input_tokens": 1024,
                "output_tokens": 256,
                "num_prompts": 16,
                "range_ratio": 0.0,
                "client_concurrencies": [2, 4],
                "cache_states": ["first_run", "repeat_identical_prompts"],
            },
            "dependency": {"pid": 1, "start_ticks": "2"},
        }
        self.record = {
            "status": "ASB_PILOT_FINISHED_REVIEW_REQUIRED",
            "jobs": [
                {
                    "configuration": c,
                    "status": "RECORDED_NOT_ACCEPTED",
                    "exit_code": 1,
                    "metrics": {"recorded_cases": 40},
                }
                for c in ("baseline", "full")
            ],
        }

    def result(self):
        r = {
            k: 1.0
            for k in (
                "duration",
                "output_throughput",
                "mean_ttft_ms",
                "mean_tpot_ms",
                "p95_ttft_ms",
                "p95_tpot_ms",
                "p95_e2el_ms",
            )
        }
        return {
            **r,
            "completed": 16,
            "failed": 0,
            "total_input_tokens": 16384,
            "total_output_tokens": 4096,
            "input_lens": [1024] * 16,
            "output_lens": [256] * 16,
            "errors": [""] * 16,
        }

    def test_terminal_file_cannot_override_live_queue(self):
        with self.assertRaisesRegex(ValueError, "STILL_LIVE"):
            tuning.assert_asb_terminal(
                SimpleNamespace(same_process=lambda _: True), self.plan, self.record
            )

    def test_missing_process_requires_terminal_evidence(self):
        self.record["status"] = "RUNNING_ASB_PILOT"
        with self.assertRaisesRegex(ValueError, "TERMINAL_EVIDENCE"):
            tuning.assert_asb_terminal(
                SimpleNamespace(same_process=lambda _: False), self.plan, self.record
            )

    def test_partial_pair_cannot_release_service(self):
        self.record["jobs"][1]["metrics"]["recorded_cases"] = 39
        with self.assertRaisesRegex(ValueError, "NOT_FULLY_RECORDED"):
            tuning.assert_asb_terminal(
                SimpleNamespace(same_process=lambda _: False), self.plan, self.record
            )

    def test_completed_but_failed_quality_is_not_relabelled(self):
        before = copy.deepcopy(self.record)
        tuning.assert_asb_terminal(
            SimpleNamespace(same_process=lambda _: False), self.plan, self.record
        )
        self.assertEqual(self.record, before)

    def test_fixed_sampler_and_replay_share_all_input_settings(self):
        trial = {
            "argv": [
                "/runtime/bin/python",
                "--model",
                "/pinned/model",
                "--served-model-name",
                "test",
            ]
        }
        commands = [
            tuning.command(self.plan, trial, Path("/tmp/result"), 2, state)
            for state in self.plan["workload"]["cache_states"]
        ]
        self.assertEqual(
            commands[0][commands[0].index("--random-range-ratio") + 1], "0.0"
        )
        for argv in commands:
            index = argv.index("--result-filename")
            argv[index + 1] = "same-output-name-for-comparison"
        self.assertEqual(*commands)

    def test_unreviewed_sampler_change_rejected(self):
        self.plan["workload"]["range_ratio"] = 1.0
        with self.assertRaisesRegex(ValueError, "UNREVIEWED"):
            tuning.workload(self.plan)

    def test_complete_native_result_accepted(self):
        self.assertEqual(tuning.check_result(self.result())["completed"], 16)

    def test_aggregate_token_sum_cannot_hide_unequal_requests(self):
        result = self.result()
        result["output_lens"][:2] = [255, 257]
        with self.assertRaisesRegex(ValueError, "CHANGED_PERFORMANCE"):
            tuning.check_result(result)

    def test_failed_or_nonfinite_result_rejected(self):
        for key, value in [
            ("failed", 1),
            ("failed", False),
            ("mean_ttft_ms", float("nan")),
            ("output_throughput", None),
            ("errors", ["error"] + [""] * 15),
        ]:
            with self.subTest(key=key, value=value):
                result = self.result()
                result[key] = value
                with self.assertRaises(ValueError):
                    tuning.check_result(result)

    def test_trial_start_failure_restores_original_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "artifacts").mkdir()
            evidence = root / "docs/evidence"
            evidence.mkdir(parents=True)
            (evidence / "asb-pilot-progress.json").write_text(json.dumps(self.record))
            base = {
                "argv": ["python", "--model", "fixed", "--served-model-name", "base"]
            }
            (root / "artifacts/local-model-27b-32k-command.json").write_text(
                json.dumps(base)
            )
            trial = {"id": "trial", "argv": base["argv"] + ["--enforce-eager"]}
            plan = {
                **self.plan,
                "pins": {},
                "current_model_process": {"pid": 2},
                "executor_sha256": tuning.sha(Path(tuning.__file__)),
                "trials": [trial],
            }
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan))
            calls = []

            def start(argv, log, state):
                calls.append(argv)
                if argv == trial["argv"]:
                    raise RuntimeError("synthetic startup failure")
                state["owned_server"] = {"pid": 3}
                return {"pid": 3}, 0.1

            helper = SimpleNamespace(
                same_process=lambda p: p["pid"] == 2,
                server_command=lambda p: base["argv"],
                assert_idle=lambda: None,
                assert_no_clients=lambda: None,
                group_members=lambda p: [],
                stop_owned_group=lambda p: None,
                start_server=start,
                write_json=lambda path, data: path.write_text(json.dumps(data)),
            )
            output = root / "artifacts/output"
            with patch.multiple(tuning, ROOT=root, PLAN=plan_path, OUTPUT=output):
                self.assertEqual(tuning.run(helper, plan), 1)
            report = json.loads((output / "progress.json").read_text())
            self.assertTrue(report["restored"])
            self.assertEqual(calls, [trial["argv"], base["argv"]])
            self.assertEqual(report["trials"][0]["status"], "FAILED_REVIEW_REQUIRED")


if __name__ == "__main__":
    unittest.main()

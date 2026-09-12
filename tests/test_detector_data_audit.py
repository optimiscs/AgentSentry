"""Public-data overlap checks preserve conflicts and original row positions."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_detector_data import fingerprint, split_audit


class DataAuditChecks(unittest.TestCase):
    def test_conflicting_duplicates_are_not_silently_relabelled(self):
        records = {"train": [{"prompt": "same", "label": label} for label in (0, 1, 1)],
                   "valid": [{"prompt": "same", "label": 0}]}
        result = split_audit(records, False)
        train = result["splits"]["train"]
        self.assertEqual((train["records"], train["unique_texts"], train["duplicate_excess_records"]), (3, 1, 2))
        self.assertEqual(train["conflicting_label_groups"], 1)
        self.assertEqual(train["label_conflicts"][0]["rows"], [{"row": i, "label": label} for i, label in enumerate((0, 1, 1))])
        overlap = result["overlaps"][0]
        self.assertEqual((overlap["left_records"], overlap["right_records"], overlap["shared_texts"]), (3, 1, 1))
        self.assertEqual(overlap["conflicting_label_groups"], 1)

    def test_normalization_is_separate_from_exact_matching(self):
        text, variation = "ＡＢＣ  note", "abc\nNOTE"
        self.assertNotEqual(fingerprint(text), fingerprint(variation))
        self.assertEqual(fingerprint(text, True), fingerprint(variation, True))
        records = {"train": [{"prompt": text, "label": 0}], "valid": [{"prompt": variation, "label": 0}]}
        self.assertEqual(split_audit(records, False)["overlaps"][0]["shared_texts"], 0)
        self.assertEqual(split_audit(records, True)["overlaps"][0]["shared_texts"], 1)

    def test_empty_prompts_keep_original_indices(self):
        records = {"train": [{"prompt": value, "label": 0} for value in ("", "data", " ")], "valid": []}
        result = split_audit(records, True)["splits"]["train"]
        self.assertEqual(result["empty_prompt_rows"], [0, 2])
        self.assertEqual(result["records"], 3)
        self.assertEqual(result["unique_texts"], 2)


if __name__ == "__main__":
    unittest.main()

"""A CPU diagnostic must neither truncate evidence nor silently change labels."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_piguard_full_context import classify


class CompleteFieldChecks(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def tokenizer(self, text, add_special_tokens=True, truncation=None):
        self.assertFalse(truncation)
        ids = [3] * len(text)
        return {"input_ids": [1, *ids, 2] if add_special_tokens else ids}

    def classifier(self, text, **kwargs):
        self.calls.append((text, kwargs))
        return [{"label": "injection", "score": .7}, {"label": "benign", "score": .3}]

    def test_long_field_is_passed_intact(self):
        text = "x" * 1959
        result = classify(self.tokenizer, self.classifier, text)
        self.assertEqual(self.calls, [(text, {"truncation": False, "max_length": 2048, "top_k": None})])
        self.assertEqual(result["windows"][0]["content_tokens"], 1959)
        self.assertTrue(result["alert"])

    def test_excess_input_stops_before_model_call(self):
        with self.assertRaisesRegex(ValueError, "EXCEEDS_2048"):
            classify(self.tokenizer, self.classifier, "x" * 2047)
        self.assertEqual(self.calls, [])

    def test_duplicate_label_cannot_be_scored(self):
        def invalid(*args, **kwargs):
            return [{"label": "benign", "score": .5}] * 2
        with self.assertRaisesRegex(ValueError, "LABELS"):
            classify(self.tokenizer, invalid, "x")

    def test_invalid_distribution_is_rejected(self):
        def invalid(*args, **kwargs):
            return [{"label": "benign", "score": .9}, {"label": "injection", "score": .9}]
        with self.assertRaisesRegex(ValueError, "PROBABILITY_SUM"):
            classify(self.tokenizer, invalid, "x")

    def test_changed_encoding_is_rejected(self):
        def changed(*args, **kwargs):
            return {"input_ids": [9]}
        with self.assertRaisesRegex(ValueError, "ENCODING_CHANGED"):
            classify(changed, self.classifier, "x")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()

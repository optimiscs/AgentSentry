"""Replay failed ASB requests through the pinned local tokenizer, without inference."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-path", type=Path,
                        help="Explicit local tokenizer for a separately reported hardware/model run")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    path = args.candidate / "benchmarks/chat_messages.py"
    spec = importlib.util.spec_from_file_location("candidate_chat_messages", path)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    from jinja2.exceptions import TemplateError
    if importlib.util.find_spec("vllm.tokenizers") is not None:
        from vllm.tokenizers import get_tokenizer
    else:
        from vllm.transformers_utils.tokenizer import get_tokenizer

    model = args.model_path
    if model is None:
        base = json.loads((root / "artifacts/local-model-27b-32k-command.json").read_text())
        model = Path(base["argv"][base["argv"].index("--model") + 1])
    tokenizer = get_tokenizer(str(model))
    rows, sources = [], {}
    for configuration in ("baseline", "full"):
        file = (
            root
            / "artifacts/benchmarks/asb"
            / ("asb-local-v1-pilot-" + configuration + "-s0")
            / "per_case.jsonl"
        )
        sources[str(file.relative_to(root))] = sha(file)
        records = [json.loads(line) for line in file.read_text().splitlines()]
        failures = [r for r in records if r.get("error") == "HTTPStatusError"]
        if len(failures) != 10 or any(r["mode"] != "DPI_OPI" for r in failures):
            raise ValueError("EXPECTED_FROZEN_FAILURE_SET_CHANGED")
        for record in failures:
            original = record["transcript"]
            original_text = json.dumps(original, ensure_ascii=False)
            try:
                tokenizer.apply_chat_template(
                    original,
                    tokenize=True,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TemplateError as exc:
                if str(exc) != "System message must be at the beginning.":
                    raise
            else:
                raise ValueError("ORIGINAL_TEMPLATE_FAILURE_NOT_REPRODUCED")
            wire = candidate.single_system_messages(original)
            assert json.dumps(original, ensure_ascii=False) == original_text
            assert wire[1:] == original[2:]
            assert wire[0]["content"] == "\n\n".join(m["content"] for m in original[:2])
            encoded = tokenizer.apply_chat_template(
                wire, tokenize=True, add_generation_prompt=True, enable_thinking=False
            )
            if not 0 < len(encoded) <= 32768 - 4096:
                raise ValueError("RENDERED_REQUEST_EXCEEDS_FROZEN_CONTEXT_BUDGET")
            rows.append(
                {
                    "configuration": configuration,
                    "case_id": record["case_id"],
                    "prompt_tokens": len(encoded),
                    "template_rendered": True,
                    "original_messages_sha256": hashlib.sha256(
                        original_text.encode()
                    ).hexdigest(),
                    "wire_messages_sha256": hashlib.sha256(
                        json.dumps(wire, ensure_ascii=False).encode()
                    ).hexdigest(),
                }
            )
    report = {
        "status": "PASS",
        "kind": "TOKENIZER_REPLAY_NOT_MODEL_BENCHMARK",
        "cases": len(rows),
        "original_template_failures": len(rows),
        "model_calls": 0,
        "source_records": sources,
        "adapter_sha256": sha(path),
        "checker_sha256": sha(Path(__file__)),
        "model_path": str(model.resolve()),
        "rows": rows,
        "model_tokenizer_files": {
            name: sha(model / name)
            for name in [
                "tokenizer.json",
                "tokenizer_config.json",
                "chat_template.jinja",
            ]
            if (model / name).exists()
        },
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: report[k]
                for k in [
                    "status",
                    "kind",
                    "cases",
                    "original_template_failures",
                    "model_calls",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()

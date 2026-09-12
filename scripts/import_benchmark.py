#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from agentsentry.evaluation import import_native

p = argparse.ArgumentParser(
    description="Import a checksummed native evaluator export; does not run the benchmark"
)
p.add_argument("--manifest", type=Path, required=True)
p.add_argument("--input", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
manifest = json.loads(a.manifest.read_text())
records, metrics = import_native(a.input, manifest)
a.output.mkdir(parents=True, exist_ok=False)
(a.output / "manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
)
(a.output / "per_case.jsonl").write_text(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n"
)
(a.output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
print(json.dumps(metrics))

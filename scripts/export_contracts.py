#!/usr/bin/env python3
import json
import tempfile
from pathlib import Path
from agentsentry.api.app import create_app
from agentsentry.config import Settings
from agentsentry.gateway.runtime import Runtime
from agentsentry.schemas import (
    IntentIR,
    ActionIR,
    Decision,
    ContextChunk,
    RiskSignal,
    ToolCall,
    CallResult,
)

root = Path(__file__).resolve().parents[1]
target = root / "docs/generated"
target.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    settings = Settings(
        Path(tmp), Path(tmp) / "workspace", root / "policies/default.aspolicy"
    )
    runtime = Runtime(settings)
    schema = create_app(settings, runtime).openapi()
    schema.setdefault("components", {}).setdefault("securitySchemes", {})[
        "BearerAuth"
    ] = {"type": "http", "scheme": "bearer"}
    for path, methods in schema["paths"].items():
        if path.startswith("/api/"):
            for operation in methods.values():
                operation["security"] = [{"BearerAuth": []}]
    (target / "openapi.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
    )
    runtime.close()
for cls in (
    IntentIR,
    ActionIR,
    Decision,
    ContextChunk,
    RiskSignal,
    ToolCall,
    CallResult,
):
    (target / (cls.__name__ + ".schema.json")).write_text(
        json.dumps(cls.model_json_schema(), ensure_ascii=False, indent=2) + "\n"
    )
print("Exported OpenAPI and 7 model contracts")

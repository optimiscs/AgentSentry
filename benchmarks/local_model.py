"""Shared local-only model transport and run provenance. No implicit API fallback."""

from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from chat_messages import single_system_messages


def validate_url(url):
    parts = urlsplit(url)
    if (
        parts.hostname not in {"127.0.0.1", "localhost"}
        or parts.scheme != "http"
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        raise ValueError("ONLY_LOCAL_MODEL_ENDPOINT_ALLOWED")
    return url.rstrip("/")


def serving_model(url, model):
    response = httpx.get(validate_url(url) + "/models", timeout=10, trust_env=False)
    response.raise_for_status()
    return next(m for m in response.json()["data"] if m["id"] == model)


def completion(config, messages, trace, *, tools=None, response_format=None):
    thinking = getattr(config, "enable_thinking", False)
    timeout = getattr(config, "request_timeout", 120)
    if type(thinking) is not bool or type(timeout) not in (int, float) or not 1 <= timeout <= 600:
        raise ValueError("INVALID_LOCAL_INFERENCE_OPTIONS")
    payload = {
        "model": config.model,
        "messages": single_system_messages(messages),
        "temperature": 0,
        "seed": config.seed,
        "max_tokens": config.max_tokens,
        "chat_template_kwargs": {"enable_thinking": thinking},
    }
    if response_format is not None:
        payload["response_format"] = response_format
    if tools is not None:
        payload.update(tools=tools, tool_choice="auto")
    response = httpx.post(
        validate_url(config.url) + "/chat/completions",
        json=payload,
        timeout=timeout,
        trust_env=False,
    )
    response.raise_for_status()
    raw = response.json()
    # Record before checking truncation so failed model outputs remain reviewable.
    trace.append(raw)
    if raw["choices"][0]["finish_reason"] == "length":
        raise ValueError("MODEL_OUTPUT_TRUNCATED")
    return raw["choices"][0]["message"]


def source_hashes(root):
    return {
        str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted((root / "src/agentsentry").rglob("*.py"))
    }


def support_hashes():
    return {
        f.name: hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(Path(__file__).parent.glob("*.py"))
        if f.name not in {"acceptance.py", "prepare_annotation_packet.py"}
    }


def persist_manifest(path, manifest):
    if path.exists():
        prior = json.loads(path.read_text())
        if {k: v for k, v in manifest.items() if k != "started_at"} != {
            k: v for k, v in prior.items() if k != "started_at"
        }:
            raise ValueError("RESUME_MANIFEST_MISMATCH")
    else:
        path.write_text(json.dumps(manifest, indent=2) + "\n")


def structured_completion(
    config, phase, messages, schema, records, *, complete=completion
):
    """One bounded auxiliary JSON call with the same transport and failure trace."""
    budget = copy.copy(config)
    budget.max_tokens = config.guard_max_tokens
    budget.enable_thinking = getattr(config, "guard_thinking", False)
    wire = [dict(message) for message in messages]
    wire[0]["content"] += "\nResponse JSON schema:\n" + json.dumps(schema)
    raw, started = [], time.perf_counter()
    try:
        response_format = {"type": "json_object"}
        if getattr(config, "guard_format", "json_object") == "json_schema":
            response_format = {
                "type": "json_schema",
                "json_schema": {"name": "guard_" + phase, "strict": True, "schema": schema},
            }
        response = complete(budget, wire, raw, response_format=response_format)
        return json.loads(response["content"])
    finally:
        records.append(
            {"phase": phase, "seconds": time.perf_counter() - started, "responses": raw}
        )

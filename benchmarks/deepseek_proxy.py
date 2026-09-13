"""Bounded DeepSeek-only relay; the real credential never enters the agent process."""

import hmac
import json
import time
from pathlib import Path

import httpx
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route


def read_deepseek_key(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip().strip("\"'")
    key = values.get("DEEPSEEK_API_KEY", "")
    if not key or values.get("DEEPSEEK_MODEL", "deepseek-flash") != "deepseek-flash":
        raise ValueError("DEEPSEEK_FLASH_CREDENTIAL_CONFIGURATION_REQUIRED")
    return key


class DeepSeekProxy:
    """Buffer original provider SSE for evidence; not a latency benchmark relay."""

    def __init__(self, key, token, output, *, allowed_tools, max_requests=15, max_tokens=4096, quota_state=None):
        if not key or len(token) < 32 or not 1 <= max_requests <= 100 or not 1 <= max_tokens <= 8192:
            raise ValueError("INVALID_DEEPSEEK_RELAY_BUDGET")
        self.key, self.token, self.output = key, token, Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.allowed_tools = set(allowed_tools)
        self.max_requests, self.max_tokens = max_requests, max_tokens
        self.records, self.rejections = [], []
        self.quota_state = Path(quota_state) if quota_state else None
        self.app = Starlette(routes=[Route("/chat/completions", self.respond, methods=["POST"]),
                                     Route("/v1/chat/completions", self.respond, methods=["POST"])])

    def reject(self, reason, status=400):
        self.rejections.append(reason)
        (self.output / "rejections.json").write_text(json.dumps(self.rejections) + "\n")
        return JSONResponse({"error": {"message": reason, "type": "invalid_request_error"}}, status_code=status)

    async def respond(self, request):
        if not hmac.compare_digest(request.headers.get("authorization", ""), "Bearer " + self.token):
            return self.reject("RELAY_AUTH_REQUIRED", 401)
        if self.quota_state and self.quota_state.exists():
            return self.reject("SHARED_PROVIDER_STOP", 402)
        data = await request.body()
        if len(data) > 2 * 1024 * 1024:
            return self.reject("RELAY_INPUT_BUDGET", 413)
        try:
            body = json.loads(data)
            if not isinstance(body, dict) or not isinstance(body.get("tools", []), list):
                raise ValueError("INVALID_BODY")
            if any(not isinstance(t, dict) or not isinstance(t.get("function"), dict)
                   for t in body.get("tools", [])):
                raise ValueError("INVALID_TOOL")
            if not isinstance(body.get("thinking", {}), dict) or not isinstance(body.get("chat_template_kwargs", {}), dict):
                raise ValueError("INVALID_THINKING")
        except (ValueError, TypeError):
            return self.reject("RELAY_INVALID_REQUEST_BODY")
        names = {t.get("function", {}).get("name") for t in body.get("tools", [])}
        if body.get("model") != "deepseek-flash" or not names <= self.allowed_tools:
            return self.reject("RELAY_MODEL_OR_TOOL_SCOPE_MISMATCH")
        if body.get("thinking", {}).get("type", "disabled") != "disabled":
            return self.reject("RELAY_THINKING_MUST_BE_DISABLED")
        if body.get("chat_template_kwargs", {}).get("enable_thinking", False):
            return self.reject("RELAY_THINKING_MUST_BE_DISABLED")
        if len(self.records) >= self.max_requests:
            return self.reject("RELAY_REQUEST_BUDGET_EXHAUSTED")
        # Native DSH and existing local guard clients express this differently.
        body.pop("chat_template_kwargs", None)
        body.pop("reasoning_effort", None)
        body.pop("seed", None)  # DeepSeek does not provide a documented seed guarantee.
        body.update(thinking={"type": "disabled"}, temperature=0, max_tokens=self.max_tokens)
        if body.get("stream"):
            body["stream_options"] = {"include_usage": True}
        index, started = len(self.records), time.perf_counter()
        record = {"index": index, "request": body, "status": "pending"}
        self.records.append(record)
        try:
            with httpx.Client(timeout=120, trust_env=False) as client:
                response = client.post("https://api.deepseek.com/chat/completions", json=body,
                                       headers={"Authorization": "Bearer " + self.key})
            text = response.text.replace(self.key, "[redacted]")
            chunks = []
            if body.get("stream") and response.status_code == 200:
                chunks = [json.loads(line[6:]) for line in text.splitlines()
                          if line.startswith("data: ") and line[6:] != "[DONE]"]
            elif response.status_code == 200:
                chunks = [json.loads(text)]
            reasoning = any((c.get("delta") or c.get("message") or {}).get("reasoning_content")
                            for chunk in chunks for c in chunk.get("choices", []))
            record.update(status="ok" if response.status_code == 200 and not reasoning else "error",
                          http_status=response.status_code, response_chunks=chunks,
                          reasoning_observed=reasoning,
                          usage=[c["usage"] for c in chunks if c.get("usage")])
            if response.status_code in {401, 402} and self.quota_state:
                self.quota_state.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with self.quota_state.open("x") as stop:
                        json.dump({"http_status": response.status_code, "reason": "API_BALANCE_EXHAUSTED" if response.status_code == 402 else "API_AUTH_FAILED",
                                   "observed_at_unix": time.time(), "evidence": str(self.output / f"request-{index:03}.json")}, stop)
                except FileExistsError:
                    pass
            (self.output / f"response-{index:03}.txt").write_text(text)
            if reasoning:
                return self.reject("PROVIDER_RETURNED_REASONING_WHILE_DISABLED", 502)
            return Response(text, status_code=response.status_code,
                            media_type="text/event-stream" if body.get("stream") else "application/json")
        except Exception as error:
            record.update(status="error", error=type(error).__name__)
            return self.reject("DEEPSEEK_PROVIDER_REQUEST_FAILED", 502)
        finally:
            record["seconds"] = time.perf_counter() - started
            (self.output / f"request-{index:03}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2).replace(self.key, "[redacted]") + "\n")

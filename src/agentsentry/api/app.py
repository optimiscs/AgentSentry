from __future__ import annotations

import asyncio
import hmac
import json
import time
from contextlib import asynccontextmanager, AsyncExitStack
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agentsentry import __version__
from agentsentry.adapters.filesystem import BoundaryError
from agentsentry.config import Settings
from agentsentry.context.scanner import redact
from agentsentry.demo import scenario
from agentsentry.gateway.runtime import Runtime
from agentsentry.gateway.native_hooks import NativeCall, NativeReport
from agentsentry.policy.engine import Engine
from agentsentry.schemas import (
    ApprovalInput,
    ScanInput,
    ScanBatchInput,
    SessionInput,
    ToolCall,
)


class PolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=65536)
    expected_version: str


def create_app(settings: Settings | None = None, runtime: Runtime | None = None):
    settings = settings or Settings.from_env()
    rt = runtime or Runtime(settings)
    from agentsentry.gateway.mcp_server import gateway_mcp

    mcp = gateway_mcp(rt)
    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app):
        from agentsentry.trace.logging import install_redaction

        install_redaction()

        async def maintenance():
            while True:
                await asyncio.sleep(60)
                try:
                    await asyncio.to_thread(rt.expire_approvals)
                    await asyncio.to_thread(rt.store.purge, settings.retention_days)
                except Exception:
                    rt.store.degraded = True

        maintenance_task = asyncio.create_task(maintenance())
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(mcp.session_manager.run())
            yield
        maintenance_task.cancel()
        try:
            await maintenance_task
        except asyncio.CancelledError:
            pass
        if runtime is None:
            rt.close()

    app = FastAPI(
        title="AgentSentry",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.runtime = rt
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        if request.url.path.startswith("/mcp"):
            header = request.headers.get("authorization", "")
            token = header[7:] if header.startswith("Bearer ") else ""
            if not token or not any(
                hmac.compare_digest(token, t)
                for t in (rt.operator_token, rt.agent_token)
            ):
                return JSONResponse(
                    {"detail": "AUTHENTICATION_REQUIRED"}, status_code=401
                )
        origin = request.headers.get("origin")
        if origin and origin not in settings.allowed_origins:
            return JSONResponse({"detail": "ORIGIN_DENIED"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "CROSS_SITE_DENIED"}, status_code=403)
        if request.method in {"POST", "PUT", "PATCH"}:
            # Read incrementally, with both byte and wall-clock budgets.
            body = bytearray()
            try:
                async with asyncio.timeout(10):
                    async for chunk in request.stream():
                        body.extend(chunk)
                        if len(body) > 512 * 1024:
                            return JSONResponse(
                                {"detail": "BODY_TOO_LARGE"}, status_code=413
                            )
            except TimeoutError:
                return JSONResponse({"detail": "BODY_TIMEOUT"}, status_code=408)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers.update(
            {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            }
        )
        return response

    def identity(request: Request):
        header = request.headers.get("authorization", "")
        supplied = header[7:] if header.startswith("Bearer ") else ""
        if supplied and hmac.compare_digest(supplied, rt.operator_token):
            return "operator"
        if supplied and hmac.compare_digest(supplied, rt.agent_token):
            return "agent"
        raise HTTPException(
            401, "AUTHENTICATION_REQUIRED", headers={"WWW-Authenticate": "Bearer"}
        )

    def operator(role=Depends(identity)):
        if role != "operator":
            raise HTTPException(403, "OPERATOR_REQUIRED")
        return role

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if request.url.path.startswith("/api/context/") and isinstance(exc.body, dict):
            try:
                identity(request)
                items = exc.body.get("chunks", [exc.body])
                if isinstance(items, list):
                    for item in items[:16]:
                        if isinstance(item, dict) and isinstance(
                            item.get("session_id"), str
                        ):
                            try:
                                rt.mark_guard_failure(
                                    rt.session(item["session_id"], "local-user"),
                                    "CONTEXT_VALIDATION_FAILED",
                                )
                            except (KeyError, PermissionError):
                                pass
            except HTTPException:
                pass
        return JSONResponse(
            {
                "detail": "VALIDATION_FAILED",
                "errors": [
                    {"location": e["loc"], "type": e["type"]} for e in exc.errors()
                ],
            },
            status_code=422,
        )

    @app.exception_handler(BoundaryError)
    async def boundary_error(request, exc):
        return JSONResponse({"detail": redact(str(exc))}, status_code=409)

    @app.exception_handler(PermissionError)
    async def permission_error(request, exc):
        return JSONResponse({"detail": "ACCESS_DENIED"}, status_code=403)

    @app.exception_handler(KeyError)
    async def missing_error(request, exc):
        return JSONResponse({"detail": "NOT_FOUND"}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid_error(request, exc):
        return JSONResponse({"detail": redact(str(exc))[:1000]}, status_code=422)

    @app.get("/healthz")
    def health():
        try:
            with rt.store.lock:
                rt.store.db.execute("SELECT 1").fetchone()
            healthy = (
                rt.engine is not None
                and not rt.policy_error
                and not rt.store.degraded
                and not rt.scanner.model_load_error
            )
        except Exception:
            healthy = False
        return JSONResponse(
            {"status": "ok" if healthy else "degraded", "version": __version__},
            status_code=200 if healthy else 503,
        )

    @app.get("/api/me", dependencies=[Depends(identity)])
    def me(role=Depends(identity)):
        return {
            "role": role,
            "owner": "local-user",
            "deployment": "single-operator",
            "demo": settings.demo,
        }

    @app.get("/api/status", dependencies=[Depends(identity)])
    def status():
        with rt.store.lock:
            rows = rt.store.db.execute(
                "SELECT status,COUNT(*) AS count FROM actions GROUP BY status"
            ).fetchall()
        return {
            "version": __version__,
            "policy_version": rt.engine.policy.version if rt.engine else None,
            "policy_error": rt.policy_error,
            "audit_degraded": rt.store.degraded,
            "audit_buffer": len(rt.store.buffer),
            "audit_dropped": rt.store.dropped,
            "sandbox_available": rt.sandbox.available(),
            "demo": settings.demo,
            "detector": rt.scanner.model_version,
            "actions": {r["status"]: r["count"] for r in rows},
            "executions": rt.store.execution_count(),
            "sink_receipts": rt.store.sink_count(),
            "pending_approvals": len(rt.pending()),
            "timestamp": time.time(),
        }

    @app.get("/api/reports", dependencies=[Depends(identity)])
    def reports():
        root = settings.project_root / "docs/evidence"
        result = []
        for name in (
            "runtime-report.json",
            "perf-cpu.json",
            "public-benchmark-report.json",
        ):
            path = root / name
            if path.is_file():
                result.append(json.loads(path.read_text()))
        return result

    @app.get("/api/sessions", dependencies=[Depends(identity)])
    def sessions():
        return rt.store.sessions("local-user")

    @app.post("/api/sessions", dependencies=[Depends(operator)])
    def new_session(body: SessionInput):
        return rt.create_session(body.task, scope=body.scope)

    @app.post("/api/context/scan", dependencies=[Depends(identity)])
    def scan(body: ScanInput):
        return rt.scan(
            body.session_id, "local-user", body.source_type, body.source_id, body.text
        )

    @app.post("/api/context/scan-batch", dependencies=[Depends(identity)])
    def scan_batch(body: ScanBatchInput):
        results = []
        for item in body.chunks:
            try:
                results.append(
                    {
                        "status": "ok",
                        "result": rt.scan(
                            item.session_id,
                            "local-user",
                            item.source_type,
                            item.source_id,
                            item.text,
                        ),
                    }
                )
            except (BoundaryError, KeyError, PermissionError):
                results.append({"status": "error", "reason": "CONTEXT_SCAN_REJECTED"})
        return {"results": results}

    @app.post("/api/tools/call", dependencies=[Depends(identity)])
    def call(body: ToolCall):
        return rt.call(body)

    @app.post("/api/hooks/evaluate", dependencies=[Depends(identity)])
    def hook_evaluate(body: NativeCall):
        return rt.hooks.evaluate(body)

    @app.post("/api/hooks/claim", dependencies=[Depends(identity)])
    def hook_claim(body: NativeCall):
        return rt.hooks.claim(body)

    @app.post("/api/hooks/report", dependencies=[Depends(identity)])
    def hook_report(body: NativeReport):
        return rt.hooks.report(body)

    @app.get("/api/approvals", dependencies=[Depends(operator)])
    def approvals():
        return rt.pending()

    @app.post("/api/approvals", dependencies=[Depends(operator)])
    def approve(body: ApprovalInput):
        return rt.approve(body.approval_id, body.approve)

    @app.get("/api/traces/{trace_id}", dependencies=[Depends(identity)])
    def trace(trace_id: str):
        return rt.trace(trace_id)

    @app.get("/api/traces/{trace_id}/export", dependencies=[Depends(operator)])
    def export(trace_id: str):
        return Response(
            json.dumps(rt.trace(trace_id), ensure_ascii=False),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="trace.json"'},
        )

    @app.get("/api/actions/{action_id}/preview", dependencies=[Depends(operator)])
    def action_preview(action_id: str):
        row = rt.store.action(action_id)
        rt.session(row["session_id"], "local-user")
        private = rt.store.open(row["private"])
        return {
            "action": private["action"],
            "arguments": redact(private["arguments"]),
            "status": row["status"],
            "note": "Sensitive values are redacted; arguments hash binds the complete original payload.",
        }

    @app.post("/api/actions/{action_id}/cancel", dependencies=[Depends(identity)])
    def cancel(action_id: str):
        return rt.cancel(action_id)

    @app.post("/api/actions/{action_id}/replay", dependencies=[Depends(operator)])
    def replay(action_id: str):
        return rt.replay(action_id)

    @app.get("/api/policy", dependencies=[Depends(operator)])
    def policy():
        return {
            "text": rt.engine.policy.text if rt.engine else "",
            "version": rt.engine.policy.version if rt.engine else "unavailable",
        }

    @app.put("/api/policy", dependencies=[Depends(operator)])
    def update_policy(body: PolicyInput):
        candidate = Engine(body.text)
        with rt.lock:
            if body.expected_version != (
                rt.engine.policy.version if rt.engine else "unavailable"
            ):
                raise BoundaryError("POLICY_VERSION_CONFLICT")
            # Release policy updates may add restrictions; built-in hard rules remain immutable.
            if rt.engine:
                original = {
                    r.name: r for r in rt.engine.policy.rules if not r.overridable
                }
                updated = {r.name: r for r in candidate.policy.rules}
                if any(updated.get(k) != v for k, v in original.items()):
                    raise BoundaryError("HARD_RULE_CHANGE_REQUIRES_RELEASE")
            staging = settings.policy_path.with_suffix(".pending")
            staging.write_text(body.text)
            staging.replace(settings.policy_path)
            rt.engine = candidate
            rt.policy_error = False
        return {"version": candidate.policy.version}

    @app.post("/api/demo/{name}", dependencies=[Depends(operator)])
    def demo(name: str):
        return scenario(rt, name)

    @app.get("/api/openapi.json", dependencies=[Depends(operator)])
    def openapi():
        return app.openapi()

    app.mount("/mcp", mcp_app)
    static = Path(__file__).parent / "static"
    if static.exists():
        app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(static / "index.html")

    return app

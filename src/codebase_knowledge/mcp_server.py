"""无状态 Streamable HTTP MCP。Spring AI 用 POST /mcp 发现并调用工具。"""

from __future__ import annotations

import json
from contextvars import ContextVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from codebase_knowledge.i18n import localize_error, negotiate, text, translate_payload

bound_app: ContextVar = ContextVar("bound_app")
PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18"}
SERVER_NAME = "codebase-knowledge"
SERVER_VERSION = "0.1.6"


class ToolError(ValueError):
    pass


def _locale(request: Request, arguments: dict | None = None) -> str:
    chosen = (arguments or {}).get("locale")
    if chosen in {"zh", "en"}:
        return chosen
    return negotiate(request.headers.get("accept-language"), request.query_params.get("lang"))


def _result(request_id, payload: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _failure(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def tool_definitions(locale: str) -> list[dict]:
    tools = []
    for spec in SPECS:
        schema = {
            "type": "object",
            "properties": dict(spec["properties"]),
            "additionalProperties": False,
        }
        schema["properties"]["locale"] = {"type": "string", "enum": ["zh", "en"]}
        if spec.get("required"):
            schema["required"] = list(spec["required"])
        tools.append({
            "name": spec["name"],
            "description": text(spec["key"], locale),
            "inputSchema": schema,
        })
    return tools


def handle(body: dict, request: Request) -> dict | None:
    if not isinstance(body, dict):
        return _failure(None, -32600, text("mcp.invalid", "en"))
    method = body.get("method")
    request_id = body.get("id")
    params = body.get("params") if isinstance(body.get("params"), dict) else {}
    arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
    locale = _locale(request, arguments)
    if isinstance(method, str) and method.startswith("notifications/"):
        return None
    if "id" not in body:
        return None
    if method == "initialize":
        version = params.get("protocolVersion")
        if version not in PROTOCOL_VERSIONS:
            return _failure(request_id, -32602, text("mcp.protocol", locale))
        return _result(request_id, {
            "protocolVersion": version,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": text("mcp.instructions", locale),
        })
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": tool_definitions(locale)})
    if method == "tools/call":
        name = params.get("name")
        if not isinstance(params.get("arguments", {}), dict):
            return _failure(request_id, -32602, text("mcp.arguments", locale))
        call_locale = _locale(request, arguments)
        try:
            payload = translate_payload(call_tool(name, arguments, call_locale), call_locale)
        except ToolError as exc:
            return _result(request_id, {
                "content": [{"type": "text", "text": localize_error(str(exc), call_locale)}],
                "isError": True,
            })
        return _result(request_id, {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "isError": False,
        })
    return _failure(request_id, -32601, text("mcp.method", locale))


def mount(app: FastAPI) -> None:
    @app.get("/mcp")
    def mcp_listen():
        return JSONResponse(
            _failure(None, -32000, "stateless MCP server does not offer a listening stream"),
            status_code=405,
        )

    @app.post("/mcp")
    async def mcp_post(request: Request):
        token = bound_app.set(request.app)
        try:
            return await _mcp_post(request)
        finally:
            bound_app.reset(token)

    async def _mcp_post(request: Request):
        try:
            body = await request.json()
        except Exception:
            locale = negotiate(request.headers.get("accept-language"), request.query_params.get("lang"))
            return JSONResponse(_failure(None, -32700, text("mcp.json", locale)), status_code=400)
        if isinstance(body, list):
            responses = [item for item in (handle(entry, request) for entry in body) if item is not None]
            if not responses:
                return Response(status_code=202)
            return JSONResponse(responses)
        result = handle(body, request)
        if result is None:
            return Response(status_code=202)
        return JSONResponse(result)



SPECS = [
    {
        "name": "codebase_index_source",
        "key": "tool.index",
        "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
        "required": ["path", "content"],
    },
]


def call_tool(name, arguments, locale):
    from codebase_knowledge.index import CodeIndex

    if name != "codebase_index_source":
        raise ToolError("未知工具")
    path = str(arguments.get("path") or "")
    content = str(arguments.get("content") or "")
    if not path or path.startswith("/") or ".." in path.replace("\\", "/").split("/"):
        raise ToolError("只接受相对路径")
    if len(content) > 200_000:
        raise ToolError("源码超过长度限制")
    index = CodeIndex()
    index.add_file(path, content)
    return {
        "summary": index.summary(),
        "types": index.types(),
        "routes": index.routes(),
        "issues": index.issues,
        "message": text("tool.index.result", locale),
    }

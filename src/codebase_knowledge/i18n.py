"""中英文切换。默认中文，已有调用不传语言时行为不变。"""

from __future__ import annotations

import re
from contextvars import ContextVar

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

current_locale: ContextVar[str] = ContextVar("locale", default="zh")
LOCALES = ("zh", "en")
TEXT_FIELDS = {
    "name", "summary", "message", "detail", "reason", "impact", "direction",
    "risk", "verification", "answer", "error", "prompt",
}

def negotiate(header: str | None, query: str | None = None) -> str:
    if query in LOCALES:
        return query
    if not header:
        return "zh"
    for part in header.split(","):
        token = part.split(";", 1)[0].strip().lower().replace("_", "-")
        if token.startswith("en"):
            return "en"
        if token.startswith("zh"):
            return "zh"
    return "zh"


def localize_error(message: str, locale: str) -> str:
    if locale != "en":
        return message
    if message in EN:
        return EN[message]
    for pattern, template in PATTERNS:
        matched = pattern.fullmatch(message)
        if matched:
            return template.format(*matched.groups())
    return message


def text(key: str, locale: str) -> str:
    table = TEXT.get(locale) or TEXT["zh"]
    return table.get(key) or TEXT["zh"][key]


def translate_payload(value, locale: str):
    if locale != "en":
        return value
    if isinstance(value, dict):
        translated = {}
        for key, item in value.items():
            if key == "suggestions" and isinstance(item, list):
                translated[key] = [
                    localize_error(piece, "en") if isinstance(piece, str) else translate_payload(piece, "en")
                    for piece in item
                ]
            elif key in TEXT_FIELDS and isinstance(item, str):
                translated[key] = localize_error(item, "en")
            else:
                translated[key] = translate_payload(item, "en")
        return translated
    if isinstance(value, list):
        return [translate_payload(item, "en") for item in value]
    return value


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def bind_locale(request: Request, call_next):
        token = current_locale.set(negotiate(request.headers.get("accept-language"), request.query_params.get("lang")))
        try:
            return await call_next(request)
        finally:
            current_locale.reset(token)

    @app.exception_handler(HTTPException)
    async def translate_http(request: Request, exc: HTTPException):
        locale = negotiate(request.headers.get("accept-language"), request.query_params.get("lang"))
        detail = exc.detail
        if isinstance(detail, str):
            detail = localize_error(detail, locale)
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.get("/api/meta")
    def meta(request: Request):
        locale = negotiate(request.headers.get("accept-language"), request.query_params.get("lang"))
        return {
            "locale": locale,
            "locales": list(LOCALES),
            "mcp": "/mcp",
            "springAi": "streamable-http",
            "message": text("meta.ready", locale),
        }


EN = {
    "只接受相对路径": "Only relative paths are accepted",
    "扫描不存在": "Scan does not exist",
    "未知工具": "Unknown tool",
    "源码超过长度限制": "Source exceeds the length limit",
    "索引里没有这个问题点名的类型，不能把推测写成事实。": "The index has no type named in this question, so an inference cannot be stated as fact.",
    "索引里没有这个问题点名的类型或路径，不能把推测写成事实。": "The index has no type or path named in this question, so an inference cannot be stated as fact.",
    "下面是解析到的定义和关系。带 inferred 的调用只说明源码里出现了这个调用表达式。": "These are parsed definitions and relations. A call marked inferred only means the expression appears in source.",
}

PATTERNS = []

TEXT = {
    "zh": {
        "meta.ready": "当前语言是中文。MCP 端点是 /mcp，供 Spring AI Streamable HTTP 客户端连接。",
        "mcp.instructions": "工具只读或只记录，不执行日志命令，不连接生产数据库，也不把推测写成事实。",
        "mcp.invalid": "请求无效",
        "mcp.protocol": "不支持的 MCP 协议版本",
        "mcp.arguments": "工具参数必须是对象",
        "mcp.json": "请求不是 JSON",
        "mcp.method": "不支持的 MCP 方法",
        "tool.index": "解析一份 Java 或 Mapper XML。调用关系仍标成推测，解析失败不编造符号。",
        "tool.index.result": "结果只包含已解析的符号。inferred 不是精确调用链。",
    },
    "en": {
        "meta.ready": "The current language is English. The MCP endpoint is /mcp for a Spring AI Streamable HTTP client.",
        "mcp.instructions": "Tools only read or record. They do not run log commands, connect to production databases, or treat inferences as facts.",
        "mcp.invalid": "Invalid request",
        "mcp.protocol": "Unsupported MCP protocol version",
        "mcp.arguments": "Tool arguments must be an object",
        "mcp.json": "Request is not JSON",
        "mcp.method": "Unsupported MCP method",
        "tool.index": "Parse one Java file or Mapper XML. Calls stay inferred, and a parse failure invents no symbols.",
        "tool.index.result": "The result contains only parsed symbols. inferred is not an exact call chain.",
    },
}

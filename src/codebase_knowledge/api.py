"""提交 Java 源码并查询索引。进程内保存最近的扫描结果。"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from codebase_knowledge.i18n import install, negotiate, translate_payload
from codebase_knowledge.index import CodeIndex, ScanStore, answer, context_for_task, structure
from codebase_knowledge.mcp_server import mount


class FileIn(BaseModel):
    path: str
    content: str


class ScanIn(BaseModel):
    files: list[FileIn] = Field(min_length=1)


class AskIn(BaseModel):
    question: str


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="Codebase Knowledge", version="0.1.7")
    install(app)
    mount(app)
    app.state.scans = {}
    app.state.store = ScanStore(db_path) if db_path else None

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/scans")
    def scan(body: ScanIn):
        index = CodeIndex()
        for item in body.files:
            if item.path.startswith("/") or ".." in item.path.split("/"):
                raise HTTPException(status_code=400, detail="只接受相对路径")
            index.add_file(item.path, item.content)
        scan_id = uuid.uuid4().hex
        app.state.scans[scan_id] = index
        if app.state.store:
            app.state.store.save(scan_id, index)
        return {"id": scan_id, "summary": index.summary(), "issues": index.issues}

    def get_index(scan_id: str) -> CodeIndex:
        index = app.state.scans.get(scan_id)
        if index is None and app.state.store:
            index = app.state.store.load(scan_id)
            if index is not None:
                app.state.scans[scan_id] = index
        if index is None:
            raise HTTPException(status_code=404, detail="扫描不存在")
        return index

    @app.get("/api/scans/{scan_id}/types")
    def types(scan_id: str):
        return get_index(scan_id).types()

    @app.get("/api/scans/{scan_id}/structure")
    def graph(scan_id: str):
        return structure(get_index(scan_id))

    @app.get("/api/scans/{scan_id}/routes")
    def routes(scan_id: str, http: str = "", path: str = ""):
        rows = get_index(scan_id).routes()
        if http:
            rows = [row for row in rows if row["http"] == http.upper()]
        if path:
            rows = [row for row in rows if row["path"] == path]
        return rows

    @app.post("/api/scans/{scan_id}/context")
    def context(scan_id: str, body: AskIn):
        return context_for_task(get_index(scan_id), body.question)

    @app.post("/api/scans/{scan_id}/ask")
    def ask(scan_id: str, body: AskIn, request: Request):
        locale = negotiate(request.headers.get("accept-language"), request.query_params.get("lang"))
        return translate_payload(answer(get_index(scan_id), body.question), locale)

    return app


app = create_app()

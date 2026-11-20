import json
from pathlib import Path

from fastapi.testclient import TestClient

from codebase_knowledge.api import create_app

ROOT = Path(__file__).resolve().parents[1]
SOURCE = """
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.GetMapping;
@RestController
public class OrderController {
    @GetMapping("/orders")
    public String list() { return "ok"; }
}
"""


def test_english_path_error_and_mcp_index():
    client = TestClient(create_app())
    denied = client.post("/api/scans", json={"files": [{"path": "../x.java", "content": "class X {}"}]}, headers={"Accept-Language": "en"})
    assert denied.status_code == 400
    assert denied.json()["detail"] == "Only relative paths are accepted"
    chinese = client.post("/api/scans", json={"files": [{"path": "../x.java", "content": "class X {}"}]})
    assert chinese.json()["detail"] == "只接受相对路径"
    meta = client.get("/api/meta", params={"lang": "zh"})
    assert meta.json()["locale"] == "zh"
    init = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}}})
    assert init.json()["result"]["serverInfo"]["name"] == "codebase-knowledge"
    called = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "codebase_index_source", "arguments": {"path": "src/OrderController.java", "content": SOURCE, "locale": "en"}},
    })
    payload = json.loads(called.json()["result"]["content"][0]["text"])
    assert called.json()["result"]["isError"] is False
    assert payload["routes"][0]["path"] == "/orders"
    assert payload["routes"][0]["status"] == "exact"
    assert "inferred" in payload["message"]
    spring = (ROOT / "spring-ai" / "application-mcp.yml").read_text(encoding="utf-8")
    assert "endpoint: /mcp" in spring and "streamable-http:" in spring

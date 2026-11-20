from pathlib import Path

from fastapi.testclient import TestClient

from codebase_knowledge.api import create_app
from codebase_knowledge.index import CodeIndex, answer, context_for_task

SAMPLE = """
package demo.order;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.GetMapping;
@RestController
public class OrderController {
    @GetMapping("/orders")
    public String list() {
        return orderService.listOrders();
    }
}
interface OrderMapper {
    String find();
}
"""


def test_java_index_marks_calls_as_inferred():
    index = CodeIndex()
    index.add_file("src/OrderController.java", SAMPLE)
    index.add_file("src/Broken.java", "public class {")
    index.add_file("README.md", "not java")
    summary = index.summary()
    assert summary["parsed_files"] == 1
    assert summary["parse_errors"] == 1
    controller = index.find_type("OrderController")[0]
    assert controller["roles"] == ["controller"]
    assert controller["status"] == "exact"
    calls = [rel for rel in index.relations() if rel["kind"] == "calls"]
    assert calls[0]["target"] == "orderService.listOrders"
    assert calls[0]["status"] == "inferred"
    assert calls[0]["line"] == 9
    result = answer(index, "OrderController 的调用有哪些")
    assert result["certainty"] == "parsed"
    assert any("OrderController.java:6" in line for line in result["evidence"])
    unknown = answer(index, "PaymentService 在哪里")
    assert unknown["certainty"] == "unknown"
    prompt = context_for_task(index, "修改 OrderController 的列表接口")
    assert prompt["files"] == ["src/OrderController.java"]
    assert "inferred" in prompt["prompt"]


def test_api_rejects_parent_path():
    client = TestClient(create_app())
    denied = client.post("/api/scans", json={"files": [{"path": "../Secret.java", "content": "class A {}"}]})
    assert denied.status_code == 400
    created = client.post(
        "/api/scans",
        json={"files": [{"path": "src/OrderController.java", "content": SAMPLE}]},
    )
    assert created.status_code == 200
    scan_id = created.json()["id"]
    types = client.get(f"/api/scans/{scan_id}/types").json()
    assert {item["name"] for item in types} == {"OrderController", "OrderMapper"}


def test_example_project_parses():
    example = Path(__file__).resolve().parents[1] / "examples" / "spring" / "OrderController.java"
    index = CodeIndex()
    index.add_file("examples/spring/OrderController.java", example.read_text(encoding="utf-8"))
    assert index.find_type("OrderController")

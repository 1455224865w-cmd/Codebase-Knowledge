from fastapi.testclient import TestClient

from codebase_knowledge.api import create_app
from codebase_knowledge.index import CodeIndex, structure

JAVA = """
package demo.order;
public interface OrderMapper {
    String find();
}
"""
XML = """
<mapper namespace="demo.order.OrderMapper">
  <select id="find" resultType="string">
    SELECT id, name FROM orders WHERE id = #{id}
  </select>
</mapper>
"""


def test_mapper_links_method_and_table_without_inventing_types():
    index = CodeIndex()
    index.add_file("src/OrderMapper.java", JAVA)
    index.add_file("src/OrderMapper.xml", XML)
    index.add_file("src/Broken.xml", "<mapper>")
    tables = [rel for rel in index.relations() if rel["kind"] == "reads_table"]
    maps = [rel for rel in index.relations() if rel["kind"] == "maps"]
    assert tables[0]["target"] == "orders"
    assert tables[0]["status"] == "exact"
    assert maps[0]["source"] == "OrderMapper.find"
    assert maps[0]["status"] == "exact"
    assert index.issues
    graph = structure(index)
    assert {node["name"] for node in graph["nodes"]} == {"OrderMapper"}
    assert "PaymentService" not in {node["name"] for node in graph["nodes"]}


def test_scan_survives_reopen(tmp_path):
    db = str(tmp_path / "scans.sqlite3")
    client = TestClient(create_app(db))
    created = client.post("/api/scans", json={"files": [
        {"path": "src/OrderMapper.java", "content": JAVA},
        {"path": "src/OrderMapper.xml", "content": XML},
    ]})
    scan_id = created.json()["id"]
    again = TestClient(create_app(db))
    graph = again.get(f"/api/scans/{scan_id}/structure").json()
    assert any(edge["kind"] == "reads_table" and edge["status"] == "exact" for edge in graph["edges"])
    calls = [edge for edge in graph["edges"] if edge["kind"] == "calls"]
    assert all(edge["status"] == "inferred" for edge in calls)

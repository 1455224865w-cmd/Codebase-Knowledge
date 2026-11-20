from codebase_knowledge.index import CodeIndex

CONTROLLER = """
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
"""

IMPL = """
package demo.order;
public class OrderMapperImpl implements OrderMapper {
    public String find() { return ""; }
}
"""

XML = """
<mapper namespace="demo.order.OrderMapper">
  <insert id="save">
    INSERT INTO orders (id) VALUES (#{id})
  </insert>
</mapper>
"""


def test_callers_routes_and_writes_keep_their_certainty():
    index = CodeIndex()
    index.add_file("src/OrderController.java", CONTROLLER)
    index.add_file("src/OrderMapperImpl.java", IMPL)
    index.add_file("src/OrderMapper.xml", XML)
    callers = index.callers("listOrders")
    assert callers[0]["source"] == "OrderController.list"
    assert callers[0]["status"] == "inferred"
    method = index.find_type("OrderController")[0]["methods"][0]
    assert method["http"] == "GET"
    assert method["route"] == "/orders"
    impl = index.implementations("OrderMapper")
    assert impl[0]["source"] == "OrderMapperImpl"
    assert impl[0]["status"] == "exact"
    writes = [rel for rel in index.relations() if rel["kind"] == "writes_table"]
    assert writes[0]["target"] == "orders"
    assert writes[0]["status"] == "exact"
    assert index.implementations("MissingMapper") == []


def test_routes_and_where_columns_are_exact():
    from fastapi.testclient import TestClient
    from codebase_knowledge.api import create_app

    xml = """
<mapper namespace="demo.order.OrderMapper">
  <select id="find">
    SELECT id, name FROM orders WHERE id = #{id}
  </select>
</mapper>
"""
    index = CodeIndex()
    index.add_file("src/OrderController.java", CONTROLLER)
    index.add_file("src/OrderMapper.xml", xml)
    routes = index.routes()
    assert routes[0]["http"] == "GET"
    assert routes[0]["path"] == "/orders"
    assert routes[0]["status"] == "exact"
    filters = [rel for rel in index.relations() if rel["kind"] == "filters_column"]
    assert filters[0]["target"] == "id"
    assert filters[0]["status"] == "exact"
    client = TestClient(create_app())
    created = client.post("/api/scans", json={"files": [
        {"path": "src/OrderController.java", "content": CONTROLLER},
    ]})
    found = client.get(f"/api/scans/{created.json()['id']}/routes", params={"http": "GET", "path": "/orders"})
    assert found.status_code == 200
    assert found.json()[0]["method"] == "list"
    missed = client.get(f"/api/scans/{created.json()['id']}/routes", params={"path": "/missing"})
    assert missed.json() == []

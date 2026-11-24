from codebase_knowledge.index import CodeIndex, answer

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


def test_imports_and_route_answers_stay_exact():
    source = """
import demo.order.OrderMapper;
public class Worker {}
"""
    index = CodeIndex()
    index.add_file("src/Worker.java", source)
    index.add_file("src/OrderController.java", CONTROLLER)
    imported = [rel for rel in index.relations() if rel["kind"] == "imports"]
    assert imported[0]["target"] == "demo.order.OrderMapper"
    assert imported[0]["status"] == "exact"
    found = answer(index, "/orders 对应哪个方法")
    assert found["certainty"] == "parsed"
    assert any("[exact]" in line and "/orders" in line for line in found["evidence"])
    assert any("inferred" not in line or "[exact]" in line for line in found["evidence"])


def test_exact_inheritance_cycle_is_reported():
    index = CodeIndex()
    index.add_file("src/A.java", "public class A extends B {}")
    index.add_file("src/B.java", "public class B extends A {}")
    index.add_file("src/C.java", "public class C {}")
    found = index.cycles()
    assert found
    assert found[0]["status"] == "exact"
    assert set(found[0]["nodes"]) >= {"A", "B"}
    plain = CodeIndex()
    plain.add_file("src/C.java", "public class C {}")
    assert plain.cycles() == []


def test_fields_are_recorded_as_exact_symbols():
    index = CodeIndex()
    index.add_file(
        "src/Order.java",
        "public class Order {\n    private String code;\n    public String getCode() { return code; }\n}\n",
    )
    fields = index.find_type("Order")[0]["fields"]
    assert fields[0]["name"] == "code"
    assert fields[0]["status"] == "exact"

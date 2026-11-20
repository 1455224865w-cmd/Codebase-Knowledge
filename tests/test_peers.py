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

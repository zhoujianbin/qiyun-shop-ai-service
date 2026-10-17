"""四期补丁：query_my_orders 工具与"我的订单"路由。"""
from app.services import assistant_graph, tool_registry


def test_tool_count_became_ten():
    assert len(tool_registry.TOOLS) == 10
    assert "query_my_orders" in tool_registry.TOOLS


def test_my_orders_schema_is_strict_and_described():
    spec = tool_registry.TOOLS["query_my_orders"]
    assert spec.read_only is True
    assert spec.requires_identity is False   # 它就是用来说明"我没单号"的场景
    assert "不要用" in spec.description
    assert spec.input_schema["additionalProperties"] is False
    with_limit = tool_registry.validate_args(spec, {"product_keyword": "门锁", "limit": 3})
    assert with_limit == {"product_keyword": "门锁", "limit": 3}
    assert tool_registry.validate_args(spec, {}) == {}


def test_my_order_words_route_to_tool_branch():
    assert assistant_graph.classify_rule("看看我订单里门锁的那个") == "IDENTITY_REQUEST"
    assert assistant_graph.classify_rule("我的订单都有什么") == "IDENTITY_REQUEST"
    assert assistant_graph.classify_rule("我买的门锁能退吗") == "IDENTITY_REQUEST"


def test_generic_order_word_does_not_route_to_tools():
    """政策类问法不能被塞进工具分支，否则白付一次模型往返。"""
    assert assistant_graph.classify_rule("订单怎么取消") is None
    assert assistant_graph.classify_rule("七天无理由退货有什么条件") is None

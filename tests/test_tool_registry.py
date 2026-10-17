"""四期：工具注册表（9 个工具、严格参数校验、描述约束、工具清单）。"""
import pytest

from app.core.errors import ValidationError
from app.services import tool_registry


def test_registry_has_ten_tools_with_eight_read_only():
    # 四期补丁：新增 query_my_orders（按身份列出本人订单）
    assert len(tool_registry.TOOLS) == 10
    read_only = [name for name, spec in tool_registry.TOOLS.items() if spec.read_only]
    assert len(read_only) == 8
    assert set(tool_registry.TOOLS) - set(read_only) == {"cancel_order", "create_after_sales"}


def test_every_description_says_when_not_to_use():
    for name, spec in tool_registry.TOOLS.items():
        assert "不要" in spec.description, f"{name} 描述缺少禁用条件"
    for name in ("cancel_order", "create_after_sales"):
        assert "只生成待确认动作" in tool_registry.TOOLS[name].description
        assert tool_registry.TOOLS[name].requires_confirm is True


def test_validate_rejects_extra_and_missing_and_enum():
    spec = tool_registry.TOOLS["query_order"]
    with pytest.raises(ValidationError):
        tool_registry.validate_args(spec, {"order_no": "SO1", "extra": 1})
    with pytest.raises(ValidationError):
        tool_registry.validate_args(spec, {})
    write = tool_registry.TOOLS["create_after_sales"]
    with pytest.raises(ValidationError):
        tool_registry.validate_args(write, {"order_no": "SO1", "type": "NOT_A_TYPE",
                                            "reason_code": "X"})
    ok = tool_registry.validate_args(spec, {"order_no": "SO1"})
    assert ok == {"order_no": "SO1"}


def test_llm_tools_excludes_write_by_default_flag():
    names = [item["function"]["name"] for item in tool_registry.llm_tools(include_write=False)]
    assert "cancel_order" not in names and "query_order" in names
    assert len(names) == 8


def test_parse_arguments_rejects_bad_json():
    with pytest.raises(ValidationError):
        tool_registry.parse_arguments("{not json")
    assert tool_registry.parse_arguments("") == {}
    assert tool_registry.parse_arguments('{"order_no": "SO1"}') == {"order_no": "SO1"}

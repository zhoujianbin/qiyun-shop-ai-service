"""切片与解析：标题路径、长度上限、行号回指、表格/步骤保真、front matter 校验。"""
import pathlib

import pytest

from app.services.knowledge_chunk import MAX_CHARS, split_markdown
from app.services.knowledge_import import ParseError, parse_document

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "knowledge_raw"


def _md(front: str, body: str) -> bytes:
    return f"---\n{front}\n---\n{body}".encode("utf-8")


FRONT = """
document_id: KB-TEST-001
title: 测试文档
category: product
version: "1.0"
effective_date: "2026-01-01"
owner: 测试
status: ACTIVE
""".strip()


def test_title_path_is_nested():
    chunks = split_markdown("# 产品知识\n## 智能门锁\n### 电池续航\n门锁使用 8 节 5 号电池。\n")
    assert chunks[-1].title_path == "产品知识 / 智能门锁 / 电池续航"


def test_text_before_first_heading_has_empty_path():
    chunks = split_markdown("开头段落。\n\n# 标题\n正文。\n")
    assert chunks[0].title_path == ""


def test_chunks_never_exceed_max_chars():
    body = "# 标题\n" + "\n".join("这是一段用于测试长度的中文内容。" * 3 for _ in range(60))
    chunks = split_markdown(body)
    assert chunks
    assert all(chunk.char_count <= MAX_CHARS for chunk in chunks)


def test_line_numbers_point_back_to_source():
    body = "# 一级\n\n第一段内容。\n\n## 二级\n\n第二段内容。\n"
    source = body.splitlines()
    chunks = split_markdown(body, first_line=1)
    for chunk in chunks:
        selected = "\n".join(source[chunk.line_start - 1:chunk.line_end]).strip()
        assert chunk.content.strip() in selected


def test_table_row_becomes_key_value():
    body = "# 参数\n\n| 参数 | 值 |\n| --- | --- |\n| 容量 | 5000mAh |\n"
    chunks = split_markdown(body)
    joined = "\n".join(chunk.content for chunk in chunks)
    assert "容量: 5000mAh" in joined


def test_ordered_steps_keep_numbers():
    body = "# 步骤\n\n1. 断电\n2. 取下电池仓\n3. 更换电池\n"
    chunks = split_markdown(body)
    joined = "\n".join(chunk.content for chunk in chunks)
    assert "1. 断电" in joined and "3. 更换电池" in joined


def test_ord_is_sequential():
    chunks = split_markdown("# A\n甲\n\n# B\n乙\n")
    assert [chunk.ord for chunk in chunks] == list(range(len(chunks)))


def test_empty_body_yields_no_chunks():
    assert split_markdown("\n\n") == []


def test_parse_requires_front_matter():
    with pytest.raises(ParseError, match="front matter"):
        parse_document("a.md", b"# no front matter\n")


def test_parse_rejects_missing_required_field():
    payload = _md('document_id: KB-X\ntitle: T\ncategory: c\nversion: "1.0"\n'
                  'effective_date: "2026-01-01"\nstatus: ACTIVE', "正文")
    with pytest.raises(ParseError, match="owner"):
        parse_document("a.md", payload)


def test_parse_rejects_unknown_suffix():
    with pytest.raises(ParseError, match="不支持的格式"):
        parse_document("a.pdf", b"%PDF-1.4")


def test_parse_returns_body_line_offset():
    payload = _md(FRONT, "# 标题\n正文\n")
    parsed = parse_document("a.md", payload)
    lines = payload.decode("utf-8").splitlines()
    assert lines[parsed.first_body_line - 1].strip() == "# 标题"


def test_real_corpus_chunks_are_bounded_and_traceable():
    """对真实语料抽样：解析 + 切片，长度受限且行号可回指。"""
    samples = sorted(RAW.rglob("*.md"))[:25]
    assert samples, "knowledge_raw 不存在或为空"
    for path in samples:
        parsed = parse_document(path.name, path.read_bytes())
        chunks = split_markdown(parsed.body, first_line=parsed.first_body_line)
        assert chunks, f"{path.name} 未切出任何切片"
        source = path.read_text(encoding="utf-8").splitlines()
        for chunk in chunks:
            assert chunk.char_count <= MAX_CHARS
            window_lines = source[chunk.line_start - 1:chunk.line_end]
            assert 1 <= chunk.line_start <= chunk.line_end <= len(source)
            # 表格渲染后与原文形态不同，只校验行号区间有效；其余要求逐字回读一致
            if not any(line.lstrip().startswith("|") for line in window_lines):
                # 原文中的空行在切片里被折叠，比较时同样丢弃空行
                window = "\n".join(line for line in window_lines if line.strip())
                assert chunk.content.strip() in window.strip()

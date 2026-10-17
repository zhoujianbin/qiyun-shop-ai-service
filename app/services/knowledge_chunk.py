"""按 Markdown 标题层级切片。

规则（见 design.md 决策 5 与 specs/knowledge-ingestion）：
- 按标题层级切，标题路径形如「一级 / 二级」；
- 单片 200–600 字符，超长按行二次切；
- 表格行转「表头: 值」，有序步骤保留序号，问答成对保留；
- 每片记录原文起止行号，保证可回指。

实现上以「行」为最小单位，因此行号始终精确，不做跨行猜偏移。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CHARS = 600
MIN_CHARS = 200

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_TABLE_RE = re.compile(r"^\s*\|")
_STEP_RE = re.compile(r"^\s*(\d+)[.)、]\s+")
_SEPARATOR_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")


@dataclass
class ChunkDraft:
    """一个待落库的切片。ord 从 0 开始，line_* 为原文绝对行号（1 基）。"""

    ord: int
    title_path: str
    content: str
    line_start: int
    line_end: int

    @property
    def char_count(self) -> int:
        return len(self.content)

    @property
    def token_count(self) -> int:
        # 中文按 1 字 ≈ 1 token 近似，用于预算与截断
        return self.char_count


class _Section:
    def __init__(self, title_path: str) -> None:
        self.title_path = title_path
        self.lines: list[tuple[int, str]] = []


@dataclass
class _Unit:
    text: str
    line_start: int
    line_end: int


def split_markdown(
    body: str,
    *,
    first_line: int = 1,
    max_chars: int = MAX_CHARS,
    min_chars: int = MIN_CHARS,
) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    for section in _split_sections(body, first_line):
        units = _units(section.lines)
        packed = _merge_small(_pack(units, max_chars), min_chars, max_chars)
        for text, start, end in packed:
            drafts.append(
                ChunkDraft(
                    ord=len(drafts),
                    title_path=section.title_path,
                    content=text,
                    line_start=start,
                    line_end=end,
                )
            )
    return drafts


def _split_sections(body: str, first_line: int) -> list[_Section]:
    sections = [_Section("")]
    stack: list[tuple[int, str]] = []
    in_fence = False
    for offset, text in enumerate(body.splitlines()):
        abs_no = first_line + offset
        if text.strip().startswith("```"):
            in_fence = not in_fence
            sections[-1].lines.append((abs_no, text))
            continue
        match = None if in_fence else _HEADING_RE.match(text)
        if match:
            level = len(match.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, match.group(2).strip()))
            sections.append(_Section(" / ".join(title for _, title in stack)))
            continue
        sections[-1].lines.append((abs_no, text))
    return [s for s in sections if any(line.strip() for _, line in s.lines)]


def _units(lines: list[tuple[int, str]]) -> list[_Unit]:
    units: list[_Unit] = []
    paragraph: list[tuple[int, str]] = []
    header: list[str] | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = "\n".join(line for _, line in paragraph).strip()
            if text:
                units.extend(_split_long_paragraph(paragraph))
        paragraph = []

    index = 0
    while index < len(lines):
        abs_no, text = lines[index]
        stripped = text.strip()
        if not stripped:
            flush_paragraph()
            header = None
            index += 1
            continue

        if _TABLE_RE.match(text):
            flush_paragraph()
            cells = _cells(text)
            if _SEPARATOR_RE.match(text):
                index += 1
                continue
            if header is None:
                header = cells  # 当前表格的表头行
                index += 1
                continue
            if len(header) == 2:
                # 两列表格按「键: 值」渲染，比「表头: 值；表头: 值」更贴近原意
                key, value = header[0], (cells + [""] * 2)[1]
                rendered = f"{cells[0]}: {value}".strip() if cells and cells[0] and value else ""
                if not rendered and cells:
                    rendered = cells[0]
            else:
                rendered = "；".join(
                    f"{head}: {value}" if head and value else (head or value)
                    for head, value in zip(header, cells, strict=False)
                    if head or value
                )
            if rendered:
                units.append(_Unit(rendered, abs_no, abs_no))
            index += 1
            continue

        header = None if not _TABLE_RE.match(text) else header
        paragraph.append((abs_no, text))
        index += 1

    flush_paragraph()
    return units


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _split_long_paragraph(lines: list[tuple[int, str]]) -> list[_Unit]:
    """段落超长时按行分组，保证每片 ≤ max_chars 且行号精确。"""
    text = "\n".join(line for _, line in lines).strip()
    if len(text) <= MAX_CHARS:
        return [_Unit(text, lines[0][0], lines[-1][0])]

    units: list[_Unit] = []
    buffer: list[tuple[int, str]] = []
    length = 0
    for abs_no, line in lines:
        piece = line.strip()
        if not piece:
            continue
        if len(piece) > MAX_CHARS:
            if buffer:
                units.append(_Unit("\n".join(t for _, t in buffer).strip(), buffer[0][0], buffer[-1][0]))
                buffer, length = [], 0
            for start in range(0, len(piece), MAX_CHARS):
                units.append(_Unit(piece[start:start + MAX_CHARS], abs_no, abs_no))
            continue
        if buffer and length + 1 + len(piece) > MAX_CHARS:
            units.append(_Unit("\n".join(t for _, t in buffer).strip(), buffer[0][0], buffer[-1][0]))
            buffer, length = [], 0
        buffer.append((abs_no, piece))
        length += len(piece) + (1 if length else 0)
    if buffer:
        units.append(_Unit("\n".join(t for _, t in buffer).strip(), buffer[0][0], buffer[-1][0]))
    return units


def _pack(units: list[_Unit], max_chars: int) -> list[tuple[str, int, int]]:
    chunks: list[tuple[str, int, int]] = []
    buffer: list[str] = []
    length = 0
    start = end = None
    for unit in units:
        if buffer and length + 1 + len(unit.text) > max_chars:
            chunks.append(("\n".join(buffer).strip(), start, end))
            buffer, length, start, end = [], 0, None, None
        if start is None:
            start = unit.line_start
        end = unit.line_end
        buffer.append(unit.text)
        length += len(unit.text) + (1 if length else 0)
    if buffer:
        chunks.append(("\n".join(buffer).strip(), start, end))
    return [chunk for chunk in chunks if chunk[0]]


def _merge_small(
    chunks: list[tuple[str, int, int]], min_chars: int, max_chars: int
) -> list[tuple[str, int, int]]:
    """把同一节里过短的尾片并入前一片（不超上限），避免大量碎片。"""
    merged: list[tuple[str, int, int]] = []
    for text, start, end in chunks:
        if merged and len(text) < min_chars and len(merged[-1][0]) + 1 + len(text) <= max_chars:
            previous = merged.pop()
            merged.append((previous[0] + "\n" + text, previous[1], end))
        else:
            merged.append((text, start, end))
    return merged

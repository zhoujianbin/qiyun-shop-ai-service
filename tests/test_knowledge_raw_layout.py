"""知识库目录边界：开发侧的校验工具与报告不得混入企业知识库。

背景：`knowledge_raw/99_校验与维护/` 曾被打包导入，6 篇治理文档以 public 身份进了检索，
其中《知识库校验报告》被真实客户会话引用过。该目录已移到 `docs/知识库校验/`。
本测试守住这条边界，防止后续"顺手放回来"。
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "knowledge_raw"

FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def _front_matter(path: pathlib.Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def test_no_python_files_in_knowledge_raw():
    scripts = [p.relative_to(ROOT) for p in RAW.rglob("*.py")]
    assert not scripts, f"knowledge_raw 里不应有开发脚本：{scripts}"


def test_no_dev_directories_in_knowledge_raw():
    dev_dirs = [p.name for p in RAW.iterdir() if p.is_dir() and p.name.startswith("9")]
    assert not dev_dirs, f"knowledge_raw 里不应有开发/校验目录：{dev_dirs}"


def test_no_governance_category_documents():
    offenders = []
    for path in RAW.rglob("*.md"):
        meta = _front_matter(path)
        if meta.get("category") == "knowledge_governance":
            offenders.append(f"{path.relative_to(ROOT)}({meta.get('category')})")
    assert not offenders, f"开发/治理类文档不应纳入企业知识库：{offenders}"

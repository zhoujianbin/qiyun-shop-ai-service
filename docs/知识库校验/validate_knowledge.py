from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REQUIRED = {"document_id", "title", "category", "version", "effective_date", "owner", "status"}
ALLOWED_STATUS = {"DRAFT", "ACTIVE", "ARCHIVED"}
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
PRODUCT_RE = re.compile(r"\bQ(?!A-)[A-Z]-[A-Z0-9]+\b")
REFERENCE_RE = re.compile(r"\b(?:[A-Z][A-Z0-9]*-){2,}[A-Z0-9]+\b")
DANGEROUS_PATTERNS = [
    re.compile(r"(?:请|把|将).{0,8}验证码.{0,8}(?:发给|提供给)客服"),
    re.compile(r"客服.{0,6}(?:可以|可).{0,6}远程开锁"),
    re.compile(r"客服.{0,6}(?:可以|可).{0,6}(?:查看|调取).{0,8}(?:摄像头|画面|录像)"),
    re.compile(r"(?:指导|让|要求).{0,8}(?:用户)?.{0,4}带电拆装"),
    re.compile(r"(?:请|要求).{0,8}(?:密码|支付密码|完整银行卡号).{0,8}(?:发给|提供给)客服"),
]
EXCLUDED_LABELS = ("虚构", "教学用途")


def load_front_matter(path: Path, text: str, errors: list[str]) -> dict[str, Any] | None:
    if not text.startswith("---\n"):
        errors.append(f"{path}: missing front matter")
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        errors.append(f"{path}: malformed front matter")
        return None
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        errors.append(f"{path}: invalid front matter: {exc}")
        return None
    missing = REQUIRED - set(meta)
    if missing:
        errors.append(f"{path}: missing metadata {sorted(missing)}")
    if meta.get("status") not in ALLOWED_STATUS:
        errors.append(f"{path}: invalid status {meta.get('status')}")
    if not re.fullmatch(r"\d+\.\d+", str(meta.get("version", ""))):
        errors.append(f"{path}: invalid version {meta.get('version')}")
    effective = meta.get("effective_date")
    try:
        date.fromisoformat(effective.isoformat() if isinstance(effective, date) else str(effective))
    except ValueError:
        errors.append(f"{path}: invalid effective_date {effective}")
    return meta


def collect_rule_ids(data: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    warranty = data.get("13_结构化规则/product_warranty.yaml", {})
    ids.update(str(item["rule_id"]) for item in warranty.get("rules", []) if item.get("rule_id"))
    for name in ("policy_rules.yaml", "escalation_matrix.yaml"):
        rules = data.get(f"13_结构化规则/{name}", {}).get("rules", {})
        if isinstance(rules, dict):
            ids.update(map(str, rules))
    return ids


def validate_ticket_workflow(data: dict[str, Any], errors: list[str]) -> None:
    workflow = data.get("13_结构化规则/ticket_workflow.yaml")
    if not workflow:
        return
    states = set(map(str, workflow.get("states", [])))
    roles = set(map(str, data.get("13_结构化规则/role_permissions.yaml", {}).get("roles", {})))
    for transition in workflow.get("transitions", []):
        for endpoint in ("from", "to"):
            value = str(transition.get(endpoint, ""))
            if value not in states:
                errors.append(f"ticket_workflow.yaml: unknown transition state {value}")
        for role in transition.get("roles", []):
            if str(role) not in roles:
                errors.append(f"ticket_workflow.yaml: unknown transition role {role}")
        if not transition.get("event"):
            errors.append("ticket_workflow.yaml: missing event in transition")
    for terminal in workflow.get("terminal_states", []):
        if str(terminal) not in states:
            errors.append(f"ticket_workflow.yaml: unknown terminal state {terminal}")


def validate_order_workflow(data: dict[str, Any], errors: list[str]) -> None:
    workflow = data.get("13_结构化规则/order_workflow.yaml")
    if not workflow:
        return
    domains = {
        "order": ("order_states", "order_transitions"),
        "payment": ("payment_states", "payment_transitions"),
        "fulfillment": ("fulfillment_states", "fulfillment_transitions"),
        "refund": ("refund_states", "refund_transitions"),
    }
    for domain, (state_key, transition_key) in domains.items():
        states = set(map(str, workflow.get(state_key, [])))
        for transition in workflow.get(transition_key, []):
            for endpoint in ("from", "to"):
                value = str(transition.get(endpoint, ""))
                if value not in states:
                    errors.append(f"order_workflow.yaml: unknown {domain} state {value}")
            if not transition.get("event"):
                errors.append(f"order_workflow.yaml: missing event in {domain} transition")


def validate_policy_numbers(data: dict[str, Any], texts: dict[Path, str], errors: list[str]) -> None:
    rules = data.get("13_结构化规则/policy_rules.yaml", {}).get("rules", {})
    field_units = {
        "days_from_delivery": "日",
        "business_days_after_acceptance": "个工作日",
        "hours_without_update": "小时",
        "minimum_notice_hours": "小时",
        "days": "日",
    }
    for rule_id, rule in rules.items():
        if not isinstance(rule, dict):
            continue
        expected = [(int(rule[field]), unit) for field, unit in field_units.items() if field in rule and isinstance(rule[field], int)]
        for path, text in texts.items():
            for line in text.splitlines():
                if str(rule_id) not in line:
                    continue
                for value, unit in expected:
                    mentions = [int(number) for number in re.findall(rf"(\d+)\s*{re.escape(unit)}", line)]
                    if mentions and value not in mentions:
                        errors.append(f"{path}: critical number mismatch for {rule_id}: expected {value}{unit}")


def validate(root: Path) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    markdown = list(root.rglob("*.md"))
    yaml_files = list(root.rglob("*.yaml")) + list(root.rglob("*.yml"))
    ids: list[str] = []
    metadata: list[dict[str, Any]] = []
    handbook_metadata: list[tuple[Path, dict[str, Any]]] = []
    texts: dict[Path, str] = {}
    for path in markdown:
        text = path.read_text(encoding="utf-8")
        texts[path] = text
        meta = load_front_matter(path, text, errors)
        if meta and meta.get("document_id"):
            ids.append(str(meta["document_id"]))
            metadata.append(meta)
            category = str(meta.get("category", ""))
            if category in {"product_manual", "business_process", "service_sop", "multi_turn_case"}:
                handbook_metadata.append((path, meta))
                required_chunk_meta = {"source_layer", "chunk_strategy", "product_ids", "reference_ids", "rule_ids"}
                missing_chunk_meta = required_chunk_meta - set(meta)
                if missing_chunk_meta:
                    errors.append(f"{path}: missing chunk metadata {sorted(missing_chunk_meta)}")
                elif meta.get("source_layer") != "theme_handbook" or meta.get("chunk_strategy") != "h2":
                    errors.append(f"{path}: invalid chunk metadata strategy")
            if category in {"product_manual", "business_process", "service_sop"}:
                title_count = len(re.findall(r"^# \S", text, re.MULTILINE))
                section_count = len(re.findall(r"^## \S", text, re.MULTILINE))
                if title_count != 1:
                    errors.append(f"{path}: theme handbook requires exactly one H1 title")
                if section_count < 5:
                    errors.append(f"{path}: theme handbook requires at least 5 sections")
                section_matches = list(re.finditer(r"^## (.+)$", text, re.MULTILINE))
                for index, match in enumerate(section_matches):
                    end = section_matches[index + 1].start() if index + 1 < len(section_matches) else len(text)
                    substance = re.sub(r"\s+", "", text[match.end():end])
                    if len(substance) < 60:
                        errors.append(f"{path}: theme handbook section too shallow {match.group(1)}")
                coverage_terms = {
                    "product_manual": ("产品", "安装", "使用", "故障", "安全", "维护", "售后", "保修", "权限"),
                    "business_process": ("核验", "状态", "流程", "异常", "记录", "依据", "权限", "确认"),
                    "service_sop": ("受理", "核验", "工具", "工单", "禁止", "升级", "审计", "确认"),
                }[category]
                if sum(term in text for term in coverage_terms) < 4:
                    errors.append(f"{path}: missing required domain coverage {category}")
                if "底层依据：" not in text:
                    errors.append(f"{path}: theme handbook missing bottom-level references")
            if category == "multi_turn_case":
                user_turns = text.count("**用户：**")
                support_turns = text.count("**客服：**")
                if user_turns < 2 or support_turns < 2:
                    errors.append(f"{path}: multi-turn case requires at least 2 user and 2 support turns")
                for section in ("错误回复示例", "复盘"):
                    if not re.search(rf"^## {re.escape(section)}$", text, re.MULTILINE):
                        errors.append(f"{path}: multi-turn case missing required section {section}")
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean = target.split("#", 1)[0]
            if clean and not (path.parent / clean).resolve().exists():
                errors.append(f"{path}: broken link {target}")
        if "01_产品知识" in str(path) and "P0/P1" in text:
            errors.append(f"{path}: ambiguous thermal escalation P0/P1")
        for label in EXCLUDED_LABELS:
            if label in text:
                errors.append(f"{path}: excluded self-label {label}")
        for pattern in DANGEROUS_PATTERNS:
            for match in pattern.finditer(text):
                line_start = text.rfind("\n", 0, match.start()) + 1
                context = text[line_start:match.start()]
                if not any(negation in context for negation in ("不", "禁止", "严禁")):
                    errors.append(f"{path}: dangerous instruction {pattern.pattern}")
    handbook_nav = root / "14_主题手册" / "README.md"
    if handbook_nav.exists():
        expected_inventory = {"product_manual": 5, "business_process": 4, "service_sop": 2, "multi_turn_case": 6}
        category_paths: dict[str, list[Path]] = {category: [] for category in expected_inventory}
        for path, meta in handbook_metadata:
            category = str(meta.get("category", ""))
            if category in category_paths:
                category_paths[category].append(path.resolve())
        for category, expected in expected_inventory.items():
            actual = len(category_paths[category])
            if actual != expected:
                errors.append(f"handbook inventory {category} expected {expected} got {actual}")
        nav_text = texts.get(handbook_nav, handbook_nav.read_text(encoding="utf-8"))
        linked = set()
        for target in LINK_RE.findall(nav_text):
            clean = target.split("#", 1)[0]
            if clean and not target.startswith(("http://", "https://", "mailto:", "#")):
                linked.add((handbook_nav.parent / clean).resolve())
        for paths in category_paths.values():
            for path in paths:
                if path not in linked:
                    errors.append(f"handbook navigation missing {path.relative_to(root)}")
    active_ids = [str(meta["document_id"]) for meta in metadata if meta.get("status") == "ACTIVE"]
    for document_id, count in Counter(active_ids).items():
        if count > 1:
            errors.append(f"multiple ACTIVE versions for document_id {document_id} ({count})")
    loaded: dict[str, Any] = {}
    for path in yaml_files:
        try:
            loaded[str(path.relative_to(root))] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            errors.append(f"{path}: invalid yaml: {exc}")
    catalog_path = root / "13_结构化规则" / "product_catalog.yaml"
    product_ids: set[str] = set()
    if catalog_path.exists():
        catalog = loaded.get("13_结构化规则/product_catalog.yaml", {})
        raw_ids: list[str] = []
        for product in catalog.get("products", []):
            product_id = str(product.get("product_id", ""))
            raw_ids.append(product_id)
            master = product.get("master")
            if master and not (root / str(master)).exists():
                errors.append(f"{catalog_path}: missing product master {master}")
        product_ids = set(raw_ids)
        accessory_ids = {str(item.get("accessory_id")) for item in catalog.get("accessories", []) if item.get("accessory_id")}
        for product_id, count in Counter(raw_ids).items():
            if product_id and count > 1:
                errors.append(f"duplicate product_id {product_id}")
    rule_ids = collect_rule_ids(loaded)
    accessory_ids = locals().get("accessory_ids", set())
    known_references = set(ids) | product_ids | accessory_ids | rule_ids
    for path, meta in handbook_metadata:
        for reference in meta.get("reference_ids", []):
            if str(reference) not in set(ids):
                errors.append(f"{path}: unknown reference_id {reference}")
        for product_id in meta.get("product_ids", []):
            if str(product_id) not in product_ids:
                errors.append(f"{path}: unknown metadata product_id {product_id}")
        for rule_id in meta.get("rule_ids", []):
            if str(rule_id) not in rule_ids:
                errors.append(f"{path}: unknown metadata rule_id {rule_id}")
    for path, text in texts.items():
        for product_id in PRODUCT_RE.findall(text):
            if product_id not in product_ids:
                errors.append(f"{path}: unknown product_id {product_id}")
        for reference in REFERENCE_RE.findall(text):
            if reference not in known_references and not PRODUCT_RE.fullmatch(reference):
                errors.append(f"{path}: unknown rule_id {reference}")
    validate_ticket_workflow(loaded, errors)
    validate_order_workflow(loaded, errors)
    validate_policy_numbers(loaded, texts, errors)
    for warranty in loaded.get("13_结构化规则/product_warranty.yaml", {}).get("rules", []):
        rule_id = str(warranty.get("rule_id", ""))
        months = warranty.get("months")
        if not rule_id or not isinstance(months, int):
            continue
        for path, text in texts.items():
            for line in text.splitlines():
                if rule_id not in line:
                    continue
                mentions = [int(number) for number in re.findall(r"(\d+)\s*个月", line)]
                if mentions and months not in mentions:
                    errors.append(f"{path}: warranty month mismatch for {rule_id}: expected {months} months")
    return errors, {"markdown": len(markdown), "yaml": len(yaml_files), "document_ids": len(ids), "products": len(product_ids), "rules": len(rule_ids)}


def main() -> int:
    parser = argparse.ArgumentParser()
    # 本脚本已移出 knowledge_raw（开发工具不进企业知识库），默认根目录显式指向它
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2] / "knowledge_raw")
    args = parser.parse_args()
    errors, stats = validate(args.root.resolve())
    for error in errors:
        print(f"ERROR: {error}")
    print(" ".join(f"{key}={value}" for key, value in stats.items()) + f" errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

"""四期本体完整性：域/值域、产品范围、悬空引用、重名与图遍历。

把"人工/AI 审核过一遍"升级成"每次都可复跑"的约束：
这些断言在 seed 之后执行，任何一次改动只要破坏本体契约就会红。
"""
import re
from pathlib import Path

from sqlalchemy import text

from app.core.db import SessionLocal
from app.services import ontology
from app.services.ontology import PART_LABELS
from app.services.ontology_extract import SERVICE_RULES

SERVICE_DOCS = Path("knowledge_raw/06_保修维修与备件")
RETURN_DOCS = Path("knowledge_raw/05_退换货与退款")
MATRIX_ROW = re.compile(
    r"^\|\s*([A-Za-z0-9-]+)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*个月\s*\|\s*(WARRANTY-[A-Za-z0-9-]+)\s*\|$",
    re.MULTILINE,
)

# 谓词的域/值域：(起点允许的 kind, 终点允许的 kind)
DOMAIN_RANGE = {
    "PART_OF": ({"part", "accessory"}, {"product"}),
    "SYMPTOM_OF": ({"fault"}, {"part"}),
    "REMEDY": ({"fault"}, {"action"}),
    "COVERED_BY": ({"part"}, {"policy"}),
    "ESCALATES_TO": ({"fault"}, {"policy"}),
    "GOVERNED_BY": ({"action"}, {"policy"}),
}


def _rows(sql: str, **params) -> list[tuple]:
    with SessionLocal() as db:
        return db.execute(text(sql), params).fetchall()


def test_approved_relation_matches_domain_and_range():
    rows = _rows("""
        select r.predicate, s.kind, s.code, d.kind, d.code
        from ontology.relation r
        join ontology.entity s on s.id = r.src_entity_id
        join ontology.entity d on d.id = r.dst_entity_id
        where r.status = 'APPROVED'
    """)
    assert rows, "本体为空：先跑 scripts/ontology_seed.py"
    bad = []
    for predicate, src_kind, src_code, dst_kind, dst_code in rows:
        allowed = DOMAIN_RANGE.get(predicate)
        if allowed is None:
            continue
        if src_kind not in allowed[0] or dst_kind not in allowed[1]:
            bad.append(f"{src_code}({src_kind}) -{predicate}-> {dst_code}({dst_kind})")
    assert bad == [], "关系的域/值域不合法：\n" + "\n".join(bad)


def test_product_scope_points_to_existing_product():
    rows = _rows("""
        select distinct r.product_scope
        from ontology.relation r
        where r.product_scope is not null
          and not exists (select 1 from ontology.entity p
                          where p.code = r.product_scope and p.kind = 'product')
    """)
    assert rows == [], f"product_scope 指向不存在的产品：{[r[0] for r in rows]}"


def test_scoped_fault_graph_stays_inside_its_product():
    """带产品范围做两跳遍历时，任何一张能走到的保修单都必须属于该产品。

    part 是跨产品共用编码（main_unit 同时挂 QC-C2G 与 QH-G1），
    所以"数据上存在两跳路径"是正常的；保证不串台的是遍历时的 product_scope 过滤。
    """
    faults = _rows("""
        select s.id, s.code, s.attrs->>'product'
        from ontology.relation r join ontology.entity s on s.id = r.src_entity_id
        where r.predicate = 'SYMPTOM_OF' and r.status = 'APPROVED'
          and (s.attrs->>'product') is not null
        group by s.id, s.code, s.attrs->>'product'
    """)
    assert faults, "没有带产品范围的故障，先跑 seed"
    wrong = []
    with SessionLocal() as db:
        for entity_id, code, scope in faults:
            nodes = ontology.graph(db, entity_id, depth=2, product_scope=scope)["nodes"]
            for node in nodes:
                entity = node["entity"]
                if not entity["code"].startswith("WARRANTY-"):
                    continue
                owner = (entity.get("attrs") or {}).get("product_id")
                if owner and owner != scope:
                    wrong.append(f"{code}({scope}) -> {entity['code']}({owner})")
    assert wrong == [], "带范围遍历仍串到别家产品保修：\n" + "\n".join(wrong)


def test_symptom_relation_scope_matches_its_fault_product():
    rows = _rows("""
        select s.code, s.attrs->>'product', r.product_scope
        from ontology.relation r
        join ontology.entity s on s.id = r.src_entity_id
        where r.predicate in ('SYMPTOM_OF', 'REMEDY') and r.status = 'APPROVED'
          and (s.attrs->>'product') is not null
          and r.product_scope is distinct from (s.attrs->>'product')
    """)
    assert rows == [], "故障关系的范围与故障自身产品不一致：\n" + "\n".join(str(r) for r in rows)


def test_generic_safety_event_has_no_part_attribution():
    """冒烟/触电/鼓包这类通用安全事件只升级，不挂具体部件。"""
    rows = _rows("""
        select s.code
        from ontology.relation r
        join ontology.entity s on s.id = r.src_entity_id
        where r.predicate = 'SYMPTOM_OF' and r.status = 'APPROVED'
          and (s.attrs->>'product') is null
          and exists (select 1 from ontology.relation e
                      where e.src_entity_id = s.id and e.predicate = 'ESCALATES_TO'
                        and e.status = 'APPROVED')
    """)
    assert rows == [], f"通用安全事件仍挂部件：{[r[0] for r in rows]}"


def test_policy_action_reference_is_materialized():
    """政策里点名的动作必须存在实体，并有 GOVERNED_BY 边，不能是悬空字符串。"""
    rows = _rows("""
        select p.code, p.attrs->>'action'
        from ontology.entity p
        where p.kind = 'policy' and p.status = 'APPROVED' and p.attrs ? 'action'
    """)
    assert rows, "没有校验到任何政策→动作引用"
    missing = []
    for policy_code, action_key in rows:
        action_code = action_key if action_key.startswith("action.") else f"action.{action_key}"
        hit = _rows("""
            select 1 from ontology.entity a
            join ontology.relation r on r.src_entity_id = a.id
            join ontology.entity p on p.id = r.dst_entity_id
            where a.code = :action and a.kind = 'action'
              and p.code = :policy and r.predicate = 'GOVERNED_BY' and r.status = 'APPROVED'
        """, action=action_code, policy=policy_code)
        if not hit:
            missing.append(f"{policy_code} -> {action_code}")
    assert missing == [], "政策引用的动作没有落成 GOVERNED_BY：\n" + "\n".join(missing)


def test_warranty_policy_component_matches_a_part():
    rows = _rows("""
        select p.code, p.attrs->>'component'
        from ontology.entity p
        where p.kind = 'policy' and p.status = 'APPROVED'
          and p.attrs->>'policy_kind' = 'warranty'
          and not exists (select 1 from ontology.entity part
                          where part.kind = 'part' and part.code = p.attrs->>'component')
    """)
    assert rows == [], f"保修政策指向不存在的部件：{rows}"


def test_display_name_is_unique_per_kind():
    rows = _rows("""
        select kind, name, count(*), string_agg(code, ' | ')
        from ontology.entity where status = 'APPROVED'
        group by kind, name having count(*) > 1
    """)
    assert rows == [], f"同名不同码会让图谱难以分辨：{rows}"


def test_alias_is_unique_across_entities():
    rows = _rows("""
        select a.alias, string_agg(e.code, ' | ')
        from ontology.alias a join ontology.entity e on e.id = a.entity_id
        where a.status = 'APPROVED' and e.status = 'APPROVED'
        group by a.alias having count(distinct a.entity_id) > 1
    """)
    assert rows == [], f"同一别名指向多个实体，归一结果不确定：{rows}"


def test_cross_product_fault_is_not_narrowed_by_a_matched_part():
    """\"电池鼓包\"会同时命中故障与部件，但故障是跨产品概念，不能被 battery 的归属产品收窄。"""
    with SessionLocal() as db:
        result = ontology.normalize_question(db, "电池鼓包了怎么办")
    assert result["product_scope"] is None, (
        f"跨产品故障被收窄成 {result['product_scope']}，会给别的产品报错误保修"
    )


def test_shared_part_is_not_narrowed_to_one_product():
    """main_unit 同时属于 QC-C2G 与 QH-G1，归一不能把"主机"锁到其中任一产品。"""
    with SessionLocal() as db:
        result = ontology.normalize_question(db, "主机")
    codes = [item["code"] for item in result["entities"]]
    if "main_unit" in codes:
        assert result["product_scope"] is None, (
            f"跨产品共用部件被收窄成 {result['product_scope']}，会把召回锁到错误产品"
        )


def test_shared_part_carries_one_scope_per_product():
    """main_unit 这类共用编码必须每个产品一条 PART_OF，且范围各不相同。"""
    rows = _rows("""
        select s.code, count(distinct r.product_scope), count(*)
        from ontology.relation r join ontology.entity s on s.id = r.src_entity_id
        where r.predicate = 'PART_OF' and r.status = 'APPROVED' and r.product_scope is not null
        group by s.code having count(*) > 1
    """)
    bad = [row for row in rows if row[1] != row[2]]
    assert bad == [], f"共用部件的 PART_OF 范围重复或缺失：{bad}"

def test_warranty_matrix_doc_matches_database():
    """产品与部件保修矩阵（人读）必须与库里的 warranty 政策逐行一致。"""
    text_doc = (SERVICE_DOCS / "产品与部件保修矩阵.md").read_text(encoding="utf-8")
    rows = MATRIX_ROW.findall(text_doc)
    assert rows, "保修矩阵表没有解析到任何行"
    code_of = {label: code for code, label in PART_LABELS.items()}
    doc_map = {}
    for product, component_cn, months, rule_id in rows:
        assert component_cn in code_of, f"矩阵里的部件没有对应编码：{component_cn}"
        doc_map[rule_id] = (product, code_of[component_cn], int(months))

    db_map = {
        code: (product, component, months)
        for code, product, component, months in _rows("""
            select code, attrs->>'product_id', attrs->>'component', (attrs->>'months')::int
            from ontology.entity
            where kind = 'policy' and status = 'APPROVED'
              and attrs->>'policy_kind' = 'warranty'
        """)
    }
    assert set(db_map) == set(doc_map), (
        f"矩阵与库不一致：只在文档 {sorted(set(doc_map) - set(db_map))}，"
        f"只在库 {sorted(set(db_map) - set(doc_map))}"
    )
    drifted = {code: (doc_map[code], db_map[code]) for code in doc_map if doc_map[code] != db_map[code]}
    assert drifted == {}, f"矩阵与库字段不一致（文档值, 库值）：{drifted}"


def test_every_service_doc_has_a_policy_entity():
    """06 目录新增文档时必须显式决定它对应哪条政策，不能悄悄漏掉。"""
    docs = {path.name for path in SERVICE_DOCS.glob("*.md")} - {"README.md", "产品与部件保修矩阵.md"}
    mapped = {Path(rule.doc).name for rule in SERVICE_RULES if rule.doc.startswith("06_")}
    assert docs == mapped, f"06 文档与政策映射不一致：缺 {sorted(docs - mapped)}，多 {sorted(mapped - docs)}"


def test_return_docs_are_either_rule_bearing_or_registered():
    """05 每篇文档要么正文引用了规则码，要么在 SERVICE_RULES 里显式登记，不能两不沾。"""
    codes = {row[0] for row in _rows("select code from ontology.entity where kind = 'policy'")}
    registered = {Path(rule.doc).name for rule in SERVICE_RULES if rule.doc.startswith("05_")}
    unaccounted = []
    for path in sorted(RETURN_DOCS.glob("*.md")):
        if path.name == "README.md":
            continue
        if path.name in registered:
            continue
        if any(code in path.read_text(encoding="utf-8") for code in codes):
            continue
        unaccounted.append(path.name)
    assert unaccounted == [], f"05 文档既没有规则码也没登记：{unaccounted}"


def test_service_policy_points_back_to_an_existing_document():
    rows = _rows("""
        select code, attrs->>'source_doc'
        from ontology.entity
        where kind = 'policy' and attrs ? 'source_doc'
    """)
    assert rows, "06 服务政策没有落库，先跑 seed"
    broken = [f"{code} -> {doc}" for code, doc in rows if not (Path("knowledge_raw") / doc).exists()]
    assert broken == [], "政策引用的源文档不存在：\n" + "\n".join(broken)

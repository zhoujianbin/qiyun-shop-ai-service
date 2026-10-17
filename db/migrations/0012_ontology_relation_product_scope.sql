-- 0012：关系增加 product_scope，阻断跨产品保修推断
--
-- 背景：part 是跨产品共用编码（main_unit 同时属于 QC-C2G 与 QH-G1），
-- 只有 PART_OF 时无法判断一条 SYMPTOM_OF → COVERED_BY 路径该落哪张保修单，
-- 同一个"主机"故障可能同时推出 QC-C2G 与 QH-G1 两张保修政策。
--
-- 语义：product_scope = 该关系成立的产品范围（kind=product 的实体编码）；
--       NULL = 跨产品通用（如 ESCALATES_TO 的升级链路）。
-- 幂等：只补 NULL，不覆盖人工设置的值。

ALTER TABLE ontology.relation ADD COLUMN IF NOT EXISTS product_scope varchar(32);
CREATE INDEX IF NOT EXISTS ontology_relation_scope_idx
  ON ontology.relation (tenant_id, product_scope, predicate, status);
COMMENT ON COLUMN ontology.relation.product_scope IS
  '关系生效的产品范围（对应 kind=product 的实体编码）；NULL=跨产品通用。图遍历用它阻断跨产品保修推断';

-- PART_OF：部件/配件 → 产品，范围取产品编码
UPDATE ontology.relation r
SET product_scope = d.code
FROM ontology.entity d
WHERE d.id = r.dst_entity_id
  AND r.predicate = 'PART_OF'
  AND d.kind = 'product'
  AND r.product_scope IS NULL;

-- COVERED_BY：部件 → 保修政策，范围取政策上的 product_id
UPDATE ontology.relation
SET product_scope = attrs->>'product_id'
WHERE predicate = 'COVERED_BY'
  AND product_scope IS NULL
  AND attrs ? 'product_id';

-- SYMPTOM_OF / REMEDY：范围取故障实体上的 product（通用安全事件没有该属性，保持 NULL）
UPDATE ontology.relation r
SET product_scope = s.attrs->>'product'
FROM ontology.entity s
WHERE s.id = r.src_entity_id
  AND r.predicate IN ('SYMPTOM_OF', 'REMEDY')
  AND r.product_scope IS NULL
  AND s.attrs ? 'product';

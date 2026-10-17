-- 0002 知识库文档与版本：补身份等级、生效日期、变更摘要、来源类型、发布时间
-- 幂等：列用 ADD COLUMN IF NOT EXISTS，约束与触发器先 DROP IF EXISTS 再建。
-- 回滚：ALTER TABLE ... DROP COLUMN <新列>（一期数据不回填）

ALTER TABLE knowledge.document ADD COLUMN IF NOT EXISTS identity_level text NOT NULL DEFAULT 'public';
ALTER TABLE knowledge.document ADD COLUMN IF NOT EXISTS effective_date date;

ALTER TABLE knowledge.document DROP CONSTRAINT IF EXISTS knowledge_document_identity_ck;
ALTER TABLE knowledge.document ADD  CONSTRAINT knowledge_document_identity_ck
  CHECK (identity_level IN ('public','customer','agent'));

ALTER TABLE knowledge.document_version ADD COLUMN IF NOT EXISTS change_summary text;
ALTER TABLE knowledge.document_version ADD COLUMN IF NOT EXISTS source_kind    text NOT NULL DEFAULT 'MANUAL';
ALTER TABLE knowledge.document_version ADD COLUMN IF NOT EXISTS published_at   timestamptz;
ALTER TABLE knowledge.document_version ADD COLUMN IF NOT EXISTS published_by   bigint;

ALTER TABLE knowledge.document_version DROP CONSTRAINT IF EXISTS knowledge_version_source_ck;
ALTER TABLE knowledge.document_version ADD  CONSTRAINT knowledge_version_source_ck
  CHECK (source_kind IN ('MANUAL','MD_BUNDLE','RULE_YAML'));

DROP TRIGGER IF EXISTS trg_knowledge_document_touch ON knowledge.document;
CREATE TRIGGER trg_knowledge_document_touch BEFORE UPDATE ON knowledge.document
  FOR EACH ROW EXECUTE FUNCTION shared.tg_touch_updated_at();

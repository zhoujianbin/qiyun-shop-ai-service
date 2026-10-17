-- 0006 知识库权限码、角色与 AUDITOR 收窄
-- 幂等：INSERT ... ON CONFLICT DO NOTHING；DELETE 幂等。
-- 回滚：删除 12 个 knowledge:* 权限码与 4 个角色（级联删绑定）

-- 空库（尚未 seed、无租户）时整段跳过：权限与角色的种子真源是 scripts/bootstrap.py，
-- 迁移只在"已有数据的环境升级"时补齐。否则 create_db -> apply_migrations -> seed 会撞唯一键。
INSERT INTO shared.app_permission (code, name, module)
SELECT v.code, v.name, 'knowledge'
FROM (VALUES
  ('knowledge:document:read',     '查看知识文档与版本'),
  ('knowledge:document:write',    '新建与编辑知识文档'),
  ('knowledge:document:import',   '批量导入知识文档'),
  ('knowledge:document:archive',  '归档知识文档'),
  ('knowledge:document:publish',  '发布知识文档'),
  ('knowledge:document:rollback', '回滚知识文档'),
  ('knowledge:rule:read',         '查看结构化规则'),
  ('knowledge:rule:write',        '维护结构化规则'),
  ('knowledge:review:read',       '查看审核队列'),
  ('knowledge:review:write',      '审核决定与批注'),
  ('knowledge:retrieval:test',    '执行检索测试'),
  ('knowledge:governance:read',   '查看治理报告')
) AS v(code, name)
WHERE EXISTS (SELECT 1 FROM shared.tenant)
ON CONFLICT (code) DO NOTHING;

INSERT INTO shared.app_role (tenant_id, code, name, description, is_system)
SELECT t.id, v.code, v.name, v.descr, true
FROM shared.tenant t,
     (VALUES
       ('KNOWLEDGE_ADMIN',    '知识管理员', '全部 knowledge:* 权限'),
       ('KNOWLEDGE_REVIEWER', '知识审核员', '读、审核、批注、发布'),
       ('KNOWLEDGE_EDITOR',   '内容运营',   '读、编辑、提交审核、导入'),
       ('CS_AGENT',           '普通客服',   '只读知识文档，供三期问答使用')
     ) AS v(code, name, descr)
WHERE t.code = 'QIYUN'
ON CONFLICT (tenant_id, code) DO NOTHING;

-- KNOWLEDGE_ADMIN：全部 knowledge:* 权限
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'KNOWLEDGE_ADMIN' AND p.module = 'knowledge'
ON CONFLICT DO NOTHING;

-- KNOWLEDGE_REVIEWER：读 + 审核 + 发布
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'KNOWLEDGE_REVIEWER' AND p.code IN (
  'knowledge:document:read', 'knowledge:document:publish',
  'knowledge:review:read',   'knowledge:review:write',
  'knowledge:rule:read',     'knowledge:governance:read')
ON CONFLICT DO NOTHING;

-- KNOWLEDGE_EDITOR：读 + 写 + 导入 + 提交
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'KNOWLEDGE_EDITOR' AND p.code IN (
  'knowledge:document:read', 'knowledge:document:write',
  'knowledge:document:import')
ON CONFLICT DO NOTHING;

-- CS_AGENT：只读
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'CS_AGENT' AND p.code IN ('knowledge:document:read')
ON CONFLICT DO NOTHING;

-- CS_SUPERVISOR（一期已有角色）：只读 + 检索测试 + 治理报告
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'CS_SUPERVISOR' AND p.code IN (
  'knowledge:document:read', 'knowledge:retrieval:test', 'knowledge:governance:read')
ON CONFLICT DO NOTHING;

-- 收窄 AUDITOR：审计员不应自动获得全库知识正文的读权限
DELETE FROM shared.app_role_permission rp
USING shared.app_role r, shared.app_permission p
WHERE rp.role_id = r.id
  AND rp.permission_id = p.id
  AND r.code = 'AUDITOR'
  AND p.code LIKE 'knowledge:%';

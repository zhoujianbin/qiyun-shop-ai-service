-- 0011 四期：tool:* / ontology:* 权限码与角色授权
-- 幂等：INSERT ... ON CONFLICT DO NOTHING；空库（无租户）整段跳过，权限种子真源是 scripts/bootstrap.py。
-- 回滚：删除 7 个权限码（级联删绑定）。

INSERT INTO shared.app_permission (code, name, module)
SELECT v.code, v.name, v.module
FROM (VALUES
  ('tool:read',              '触发只读工具', 'tool'),
  ('tool:write:order',       '触发订单写工具', 'tool'),
  ('tool:write:aftersales',  '触发售后写工具', 'tool'),
  ('tool:admin',             '维护工具开关与查看评测报告', 'tool'),
  ('ontology:read',          '查看本体实体与关系', 'ontology'),
  ('ontology:write',         '维护本体实体与关系', 'ontology'),
  ('ontology:review',        '审核本体导入候选', 'ontology')
) AS v(code, name, module)
WHERE EXISTS (SELECT 1 FROM shared.tenant)
ON CONFLICT (code) DO NOTHING;

-- 坐席：只读工具
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'AI_AGENT' AND p.code = 'tool:read'
ON CONFLICT DO NOTHING;

-- 主管：只读 + 两个写工具
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'AI_SUPERVISOR'
  AND p.code IN ('tool:read', 'tool:write:order', 'tool:write:aftersales')
ON CONFLICT DO NOTHING;

-- 企业管理员：工具与评测管理
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'SUPER_ADMIN' AND p.code = 'tool:admin'
ON CONFLICT DO NOTHING;

-- 知识管理员：本体全部
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'KNOWLEDGE_ADMIN'
  AND p.code IN ('ontology:read', 'ontology:write', 'ontology:review')
ON CONFLICT DO NOTHING;

-- 知识审核员：读 + 审核
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'KNOWLEDGE_REVIEWER' AND p.code IN ('ontology:read', 'ontology:review')
ON CONFLICT DO NOTHING;

-- 内容运营：本体只读
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'KNOWLEDGE_EDITOR' AND p.code = 'ontology:read'
ON CONFLICT DO NOTHING;

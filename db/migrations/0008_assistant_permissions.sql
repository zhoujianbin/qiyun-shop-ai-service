-- 0008 三期：ai:* 权限码与客服坐席角色
-- 幂等：INSERT ... ON CONFLICT DO NOTHING；空库（无租户）整段跳过，权限种子真源是 scripts/bootstrap.py。
-- 回滚：删除 5 个 ai:* 权限码与 AI_AGENT / AI_SUPERVISOR 角色（级联删绑定）

INSERT INTO shared.app_permission (code, name, module)
SELECT v.code, v.name, 'ai'
FROM (VALUES
  ('ai:chat:read',     '查看客服会话与消息'),
  ('ai:chat:write',    '以客服身份回话与结束会话'),
  ('ai:handoff:read',  '查看转人工队列'),
  ('ai:handoff:write', '接单与关闭转人工'),
  ('ai:trace:read',    '查看问答链路留痕')
) AS v(code, name)
WHERE EXISTS (SELECT 1 FROM shared.tenant)
ON CONFLICT (code) DO NOTHING;

INSERT INTO shared.app_role (tenant_id, code, name, description, is_system)
SELECT t.id, v.code, v.name, v.descr, true
FROM shared.tenant t,
     (VALUES
       ('AI_AGENT',      '智能客服坐席', '会话读写、转人工接单'),
       ('AI_SUPERVISOR', '智能客服主管', '坐席全部权限 + 问答留痕')
     ) AS v(code, name, descr)
WHERE t.code = 'QIYUN'
ON CONFLICT (tenant_id, code) DO NOTHING;

INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'AI_AGENT' AND p.code IN (
  'ai:chat:read', 'ai:chat:write', 'ai:handoff:read', 'ai:handoff:write')
ON CONFLICT DO NOTHING;

INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'AI_SUPERVISOR' AND p.code IN (
  'ai:chat:read', 'ai:chat:write', 'ai:handoff:read', 'ai:handoff:write', 'ai:trace:read',
  'knowledge:document:read')
ON CONFLICT DO NOTHING;

INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM shared.app_role r, shared.app_permission p
WHERE r.code = 'CS_SUPERVISOR' AND p.code = 'ai:handoff:read'
ON CONFLICT DO NOTHING;

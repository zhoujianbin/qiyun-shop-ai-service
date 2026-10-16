import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Descriptions from 'antd/es/descriptions';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Row from 'antd/es/row';
import Space from 'antd/es/space';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import { Link } from 'react-router-dom';
import { authApi } from '@/api/endpoints/auth';
import { PageHeader } from '@/components/common/PageHeader';
import { useAuthStore } from '@/stores/authStore';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { useLogout } from '@/hooks/useLogout';
import { errorMessage } from '@/api/errors';
import { ROLE_LABELS } from '@/types/permissions';
import { ROUTES } from '@/constants/routes';
import { formatDateTime } from '@/utils/datetime';
import type { PasswordChangeRequest } from '@/types/domain';

/** C 端个人中心：资料、订单入口与安全设置。 */
export default function AccountPage() {
  const { message } = App.useApp();
  const user = useAuthStore((state) => state.user);
  const logout = useLogout();
  const [form] = Form.useForm<PasswordChangeRequest & { confirm: string }>();

  const changePassword = useIdempotentMutation(
    (vars: PasswordChangeRequest) => authApi.changePassword(vars),
    {
      onSuccess: () => {
        message.success('密码已修改，请重新登录');
        changePassword.resetKey();
        void logout();
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  return (
    <div className="qy-page" style={{ maxWidth: 900, margin: '0 auto' }}>
      <PageHeader title="个人中心" subtitle="账户资料、订单与安全设置" />
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <Card title="账户资料">
            <Descriptions column={1} size="small">
              <Descriptions.Item label="展示名">{user?.display_name ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="账号">{user?.username ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="主体类型">{user?.party ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="角色">
                <Space wrap>
                  {(user?.roles ?? []).length === 0 ? '-' : (user?.roles ?? []).map((role) => <Tag key={role}>{ROLE_LABELS[role] ?? role}</Tag>)}
                </Space>
              </Descriptions.Item>
            </Descriptions>
          </Card>
          <Card title="快捷入口" style={{ marginTop: 16 }}>
            <Space direction="vertical">
              <Link to={ROUTES.orders}>我的订单</Link>
              <Link to={ROUTES.afterSalesList}>售后服务</Link>
              <Link to={ROUTES.invoices}>发票管理</Link>
              <Link to={ROUTES.addresses}>地址管理</Link>
            </Space>
          </Card>
          <Card title="当前时间" style={{ marginTop: 16 }}>
            <Typography.Text type="secondary">本地时间：{formatDateTime(new Date().toISOString())}</Typography.Text>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="安全设置">
            <Form
              form={form}
              layout="vertical"
              onFinish={(values) => {
                changePassword.mutate({ old_password: values.old_password, new_password: values.new_password });
              }}
            >
              <Form.Item label="原密码" name="old_password" rules={[{ required: true, message: '请输入原密码' }]}>
                <Input.Password placeholder="请输入原密码" />
              </Form.Item>
              <Form.Item
                label="新密码"
                name="new_password"
                rules={[
                  { required: true, message: '请输入新密码' },
                  { min: 8, max: 64, message: '密码 8–64 位' },
                  { pattern: /(?=.*[A-Za-z])(?=.*\d)/, message: '需同时包含字母与数字' },
                ]}
              >
                <Input.Password placeholder="8–64 位，含字母与数字" />
              </Form.Item>
              <Form.Item label="确认新密码" name="confirm" dependencies={['new_password']} rules={[
                { required: true, message: '请再次输入新密码' },
                ({ getFieldValue }) => ({
                  validator: (_, value) => (!value || getFieldValue('new_password') === value ? Promise.resolve() : Promise.reject(new Error('两次输入不一致'))),
                }),
              ]}>
                <Input.Password placeholder="请再次输入新密码" />
              </Form.Item>
              <Space>
                <Button type="primary" htmlType="submit" loading={changePassword.isPending}>修改密码</Button>
                <Button onClick={() => void logout()}>退出登录</Button>
              </Space>
            </Form>
          </Card>
          <Card title="账号安全" style={{ marginTop: 16 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              手机号改绑需短信验证码校验；一期暂未开放自助换绑，请联系客服处理。
            </Typography.Text>
          </Card>
        </Col>
      </Row>
    </div>
  );
}

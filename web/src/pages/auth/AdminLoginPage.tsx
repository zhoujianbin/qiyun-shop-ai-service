import App from 'antd/es/app';
import Button from 'antd/es/button';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Typography from 'antd/es/typography';
import LockOutlined from '@ant-design/icons/LockOutlined';
import SafetyOutlined from '@ant-design/icons/SafetyOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useState } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { errorMessage } from '@/api/errors';
import { ROUTES } from '@/constants/routes';
import { useTrack } from '@/hooks/useTrack';

interface AdminLoginFormValues {
  username: string;
  password: string;
  otp_code?: string;
}

/** B 端员工登录：账号密码 + 可选动态验证码。 */
export default function AdminLoginPage() {
  const { message } = App.useApp();
  const [form] = Form.useForm<AdminLoginFormValues>();
  const login = useAuthStore((state) => state.loginStaff);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const track = useTrack();

  const onFinish = async (values: AdminLoginFormValues) => {
    setLoading(true);
    try {
      await login({ username: values.username, password: values.password, otp_code: values.otp_code ?? null });
      track('auth_login_success', { route: ROUTES.adminLogin, result: 'success', role: 'STAFF' });
      message.success('登录成功');
      navigate(params.get('redirect') ?? ROUTES.adminDashboard, { replace: true });
    } catch (error) {
      track('auth_login_fail', { route: ROUTES.adminLogin, result: 'fail' });
      message.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form form={form} layout="vertical" onFinish={onFinish} requiredMark={false}>
      <Typography.Title level={4} style={{ marginTop: 0 }}>运营后台登录</Typography.Title>
      <Form.Item
        label="登录名"
        name="username"
        rules={[
          { required: true, message: '请输入登录名' },
          { pattern: /^[a-z0-9._-]{4,32}$/, message: '登录名 4–32 位小写字母/数字/._-' },
        ]}
      >
        <Input prefix={<UserOutlined />} placeholder="员工登录名" autoComplete="username" />
      </Form.Item>
      <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
        <Input.Password prefix={<LockOutlined />} placeholder="登录密码" autoComplete="current-password" />
      </Form.Item>
      <Form.Item label="动态验证码（可选）" name="otp_code">
        <Input prefix={<SafetyOutlined />} placeholder="6 位动态码" maxLength={6} inputMode="numeric" />
      </Form.Item>
      <Button type="primary" htmlType="submit" block loading={loading}>
        登录运营后台
      </Button>
      <div style={{ marginTop: 12, textAlign: 'right' }}>
        <Link to={ROUTES.login}>返回客户登录</Link>
      </div>
    </Form>
  );
}

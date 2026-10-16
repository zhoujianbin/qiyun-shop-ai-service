import App from 'antd/es/app';
import Button from 'antd/es/button';
import Checkbox from 'antd/es/checkbox';
import Divider from 'antd/es/divider';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Typography from 'antd/es/typography';
import LockOutlined from '@ant-design/icons/LockOutlined';
import MobileOutlined from '@ant-design/icons/MobileOutlined';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useState } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { errorMessage } from '@/api/errors';
import { ROUTES } from '@/constants/routes';
import { useTrack } from '@/hooks/useTrack';

interface LoginFormValues {
  mobile: string;
  password: string;
  remember?: boolean;
}

/** C 端客户登录：手机号 + 密码；成功后按 redirect 跳转。 */
export default function LoginPage() {
  const { message } = App.useApp();
  const [form] = Form.useForm<LoginFormValues>();
  const login = useAuthStore((state) => state.loginCustomer);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const track = useTrack();

  const onFinish = async (values: LoginFormValues) => {
    setLoading(true);
    try {
      await login({ mobile: values.mobile, password: values.password });
      track('auth_login_success', { route: ROUTES.login, result: 'success' });
      message.success('登录成功');
      navigate(params.get('redirect') ?? ROUTES.home, { replace: true });
    } catch (error) {
      track('auth_login_fail', { route: ROUTES.login, result: 'fail' });
      message.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form form={form} layout="vertical" onFinish={onFinish} requiredMark={false} initialValues={{ remember: true }}>
      <Typography.Title level={4} style={{ marginTop: 0 }}>客户登录</Typography.Title>
      <Form.Item
        label="手机号"
        name="mobile"
        rules={[
          { required: true, message: '请输入手机号' },
          { pattern: /^1[3-9]\d{9}$/, message: '请输入 11 位大陆手机号' },
        ]}
      >
        <Input prefix={<MobileOutlined />} placeholder="请输入手机号" maxLength={11} inputMode="numeric" autoComplete="username" />
      </Form.Item>
      <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
        <Input.Password prefix={<LockOutlined />} placeholder="8–64 位，含字母与数字" autoComplete="current-password" />
      </Form.Item>
      <Form.Item name="remember" valuePropName="checked" style={{ marginBottom: 12 }}>
        <Checkbox>记住登录状态</Checkbox>
      </Form.Item>
      <Button type="primary" htmlType="submit" block loading={loading}>
        登录
      </Button>
      <Divider plain style={{ margin: '16px 0', fontSize: 12 }}>还没有账号？</Divider>
      <Button block onClick={() => navigate(ROUTES.register)}>注册新账号</Button>
      <div style={{ marginTop: 12, textAlign: 'right' }}>
        <Link to={ROUTES.adminLogin}>员工登录入口</Link>
      </div>
    </Form>
  );
}

import App from 'antd/es/app';
import Button from 'antd/es/button';
import Checkbox from 'antd/es/checkbox';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Typography from 'antd/es/typography';
import LockOutlined from '@ant-design/icons/LockOutlined';
import MobileOutlined from '@ant-design/icons/MobileOutlined';
import SafetyOutlined from '@ant-design/icons/SafetyOutlined';
import { Link, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { errorMessage } from '@/api/errors';
import { ROUTES } from '@/constants/routes';

interface RegisterFormValues {
  mobile: string;
  sms_code: string;
  password: string;
  confirm: string;
  nickname?: string;
  agree: boolean;
}

/** C 端注册：手机号 + 短信验证码 + 密码；密码 8–64 含字母与数字。 */
export default function RegisterPage() {
  const { message } = App.useApp();
  const [form] = Form.useForm<RegisterFormValues>();
  const register = useAuthStore((state) => state.register);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values: RegisterFormValues) => {
    setLoading(true);
    try {
      await register({
        mobile: values.mobile,
        password: values.password,
        sms_code: values.sms_code,
        nickname: values.nickname ?? null,
      });
      message.success('注册成功，已自动登录');
      navigate(ROUTES.home, { replace: true });
    } catch (error) {
      message.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form form={form} layout="vertical" onFinish={onFinish} requiredMark={false}>
      <Typography.Title level={4} style={{ marginTop: 0 }}>注册账号</Typography.Title>
      <Form.Item
        label="手机号"
        name="mobile"
        rules={[
          { required: true, message: '请输入手机号' },
          { pattern: /^1[3-9]\d{9}$/, message: '请输入 11 位大陆手机号' },
        ]}
      >
        <Input prefix={<MobileOutlined />} placeholder="请输入手机号" maxLength={11} inputMode="numeric" />
      </Form.Item>
      <Form.Item label="短信验证码" name="sms_code" rules={[{ required: true, message: '请输入短信验证码' }, { len: 6, message: '验证码为 6 位' }]}>
        <Input prefix={<SafetyOutlined />} placeholder="6 位验证码" maxLength={6} inputMode="numeric" />
      </Form.Item>
      <Form.Item
        label="密码"
        name="password"
        rules={[
          { required: true, message: '请输入密码' },
          { min: 8, max: 64, message: '密码 8–64 位' },
          { pattern: /(?=.*[A-Za-z])(?=.*\d)/, message: '密码需同时包含字母与数字' },
        ]}
      >
        <Input.Password prefix={<LockOutlined />} placeholder="8–64 位，含字母与数字" />
      </Form.Item>
      <Form.Item label="确认密码" name="confirm" dependencies={['password']} rules={[
        { required: true, message: '请再次输入密码' },
        ({ getFieldValue }) => ({
          validator: (_, value) =>
            !value || getFieldValue('password') === value ? Promise.resolve() : Promise.reject(new Error('两次输入的密码不一致')),
        }),
      ]}>
        <Input.Password prefix={<LockOutlined />} placeholder="请再次输入密码" />
      </Form.Item>
      <Form.Item label="昵称" name="nickname" rules={[{ max: 32, message: '昵称不超过 32 字' }]}>
        <Input placeholder="选填" maxLength={32} />
      </Form.Item>
      <Form.Item name="agree" valuePropName="checked" rules={[{ validator: (_, value) => (value ? Promise.resolve() : Promise.reject(new Error('请阅读并同意服务协议'))) }]}>
        <Checkbox>我已阅读并同意《用户服务协议》与《隐私政策》</Checkbox>
      </Form.Item>
      <Button type="primary" htmlType="submit" block loading={loading}>
        注册并登录
      </Button>
      <div style={{ marginTop: 12, textAlign: 'right' }}>
        <Link to={ROUTES.login}>已有账号？去登录</Link>
      </div>
    </Form>
  );
}

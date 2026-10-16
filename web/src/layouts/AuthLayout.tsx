import Card from 'antd/es/card';
import Layout from 'antd/es/layout';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import CrownOutlined from '@ant-design/icons/CrownOutlined';
import FileTextOutlined from '@ant-design/icons/FileTextOutlined';
import SafetyCertificateOutlined from '@ant-design/icons/SafetyCertificateOutlined';
import { Outlet } from 'react-router-dom';

const { Content } = Layout;

export interface AuthLayoutProps {
  title?: string;
  subtitle?: string;
}

/** 登录/注册壳：品牌信息 + 表单卡片。 */
export function AuthLayout({ title = '栖云智家 · 企业电商基础平台', subtitle = '第一期' }: AuthLayoutProps) {
  return (
    <Layout style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #EEF3FF 0%, #F5F7FA 100%)' }}>
      <Content style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        <Space direction="vertical" size={20} style={{ width: '100%', maxWidth: 420 }}>
          <div style={{ textAlign: 'center' }}>
            <CrownOutlined style={{ fontSize: 36, color: '#1F5EFF' }} />
            <Typography.Title level={2} style={{ marginTop: 8, marginBottom: 4 }}>
              {title}
            </Typography.Title>
            <Typography.Text type="secondary">{subtitle}</Typography.Text>
          </div>
          <Card>
            <Outlet />
          </Card>
          <div style={{ textAlign: 'center' }}>
            <Space size={16} split={<span style={{ color: '#D1D5DB' }}>·</span>}>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                <SafetyCertificateOutlined /> 渠道隔离与权限校验
              </Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                <FileTextOutlined /> 全链路审计与幂等
              </Typography.Text>
            </Space>
          </div>
        </Space>
      </Content>
    </Layout>
  );
}

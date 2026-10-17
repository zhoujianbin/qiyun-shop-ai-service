import Avatar from 'antd/es/avatar';
import Badge from 'antd/es/badge';
import Button from 'antd/es/button';
import Dropdown from 'antd/es/dropdown';
// 直接从 layout/layout 取 Header/Content/Footer：绕开 layout 的 barrel，
// 避免把只在后台用到的 Sider 也带进 C 端首屏。
import Layout, { Content, Footer, Header } from 'antd/es/layout/layout';
import Menu from 'antd/es/menu';
import Space from 'antd/es/space';
import CrownOutlined from '@ant-design/icons/CrownOutlined';
import ShoppingCartOutlined from '@ant-design/icons/ShoppingCartOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { useLogout } from '@/hooks/useLogout';
import { ROUTES } from '@/constants/routes';


const NAV_ITEMS = [
  { key: ROUTES.home, label: '首页' },
  { key: ROUTES.products, label: '全部商品' },
  { key: ROUTES.cart, label: '购物车' },
  { key: ROUTES.orders, label: '我的订单' },
  { key: ROUTES.afterSalesList, label: '售后服务' },
  { key: ROUTES.invoices, label: '发票' },
  { key: ROUTES.assistant, label: '智能客服' },
];

export function CustomerShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logout = useLogout();

  const selectedKey = NAV_ITEMS.map((item) => item.key)
    .filter((key) => key !== '/' && location.pathname.startsWith(key))
    .sort((a, b) => b.length - a.length)[0] ?? (location.pathname === '/' ? '/' : '');

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <a className="qy-skip-link" href="#main-content">跳到主内容</a>
      <Header style={{ background: '#fff', borderBottom: '1px solid var(--color-border)', padding: '0 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, height: 64 }}>
          <Link to={ROUTES.home} aria-label="栖云智家首页">
            <Space align="center">
              <CrownOutlined style={{ color: '#1F5EFF', fontSize: 22 }} />
              <span style={{ fontWeight: 600, fontSize: 18 }}>栖云智家</span>
            </Space>
          </Link>
          <Menu
            mode="horizontal"
            selectedKeys={[selectedKey]}
            style={{ flex: 1, minWidth: 0, borderBottom: 'none' }}
            items={NAV_ITEMS.map((item) => ({ key: item.key, label: <Link to={item.key}>{item.label}</Link> }))}
          />
          <Space size={12}>
            <Badge count={0} showZero={false}>
              <Button
                type="text"
                icon={<ShoppingCartOutlined />}
                aria-label="购物车"
                onClick={() => navigate(ROUTES.cart)}
              />
            </Badge>
            {user ? (
              <Dropdown
                menu={{
                  items: [
                    { key: 'account', label: <Link to={ROUTES.account}>个人中心</Link> },
                    { key: 'orders', label: <Link to={ROUTES.orders}>我的订单</Link> },
                    { key: 'addresses', label: <Link to={ROUTES.addresses}>地址管理</Link> },
                    { type: 'divider' },
                    { key: 'logout', label: '退出登录', onClick: () => void logout() },
                  ],
                }}
              >
                <Space style={{ cursor: 'pointer' }}>
                  <Avatar size="small" icon={<UserOutlined />} />
                  <span>{user.display_name ?? user.username}</span>
                </Space>
              </Dropdown>
            ) : (
              <Space>
                <Button onClick={() => navigate(ROUTES.login)}>登录</Button>
                <Button type="primary" onClick={() => navigate(ROUTES.register)}>注册</Button>
              </Space>
            )}
          </Space>
        </div>
      </Header>
      <Content id="main-content" style={{ background: 'var(--color-bg)' }}>
        <Outlet />
      </Content>
      <Footer style={{ textAlign: 'center', color: 'var(--color-text-muted)' }}>
        栖云智家科技有限公司 · 第一期企业电商基础平台 · 智能门锁 / 家用摄像头 / 清洁机器人 / 智能灯具 / 家庭网关 / 配件耗材
      </Footer>
    </Layout>
  );
}

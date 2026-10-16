import Avatar from 'antd/es/avatar';
import Button from 'antd/es/button';
import Dropdown from 'antd/es/dropdown';
import Layout from 'antd/es/layout';
import Menu from 'antd/es/menu';
import Space from 'antd/es/space';
import Switch from 'antd/es/switch';
import Typography from 'antd/es/typography';
import AppstoreOutlined from '@ant-design/icons/AppstoreOutlined';
import AuditOutlined from '@ant-design/icons/AuditOutlined';
import BarChartOutlined from '@ant-design/icons/BarChartOutlined';
import BulbOutlined from '@ant-design/icons/BulbOutlined';
import ClusterOutlined from '@ant-design/icons/ClusterOutlined';
import CustomerServiceOutlined from '@ant-design/icons/CustomerServiceOutlined';
import DashboardOutlined from '@ant-design/icons/DashboardOutlined';
import FileTextOutlined from '@ant-design/icons/FileTextOutlined';
import InboxOutlined from '@ant-design/icons/InboxOutlined';
import MenuFoldOutlined from '@ant-design/icons/MenuFoldOutlined';
import MenuUnfoldOutlined from '@ant-design/icons/MenuUnfoldOutlined';
import ShopOutlined from '@ant-design/icons/ShopOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useMemo } from 'react';
import { ChannelScopeSelect } from '@/components/common/ChannelScopeSelect';
import { useAuthStore } from '@/stores/authStore';
import { usePermissionStore } from '@/stores/permissionStore';
import { useUiStore } from '@/stores/uiStore';
import { useLogout } from '@/hooks/useLogout';
import { ROUTES } from '@/constants/routes';
import { P } from '@/types/permissions';

const { Header, Sider, Content } = Layout;

interface MenuEntry {
  key: string;
  label: string;
  icon?: React.ReactNode;
  permission?: string;
  children?: MenuEntry[];
}

const MENU: MenuEntry[] = [
  { key: ROUTES.adminDashboard, label: '工作台', icon: <DashboardOutlined />, permission: P.orderRead },
  {
    key: 'product-group',
    label: '商品中心',
    icon: <ShopOutlined />,
    children: [
      { key: ROUTES.adminProducts, label: '商品列表', permission: P.productRead },
      { key: ROUTES.adminSkus, label: 'SKU 管理', permission: P.productRead },
      { key: ROUTES.adminCategories, label: '类目管理', permission: P.productRead },
      { key: ROUTES.adminBrands, label: '品牌管理', permission: P.productRead },
    ],
  },
  {
    key: 'inventory-group',
    label: '库存中心',
    icon: <InboxOutlined />,
    children: [
      { key: ROUTES.adminInventory, label: '库存总览', permission: P.inventoryRead },
      { key: ROUTES.adminInventoryLedger, label: '库存流水', permission: P.inventoryRead },
      { key: ROUTES.adminWarehouses, label: '仓库管理', permission: P.inventoryRead },
    ],
  },
  {
    key: 'order-group',
    label: '订单中心',
    icon: <AppstoreOutlined />,
    children: [
      { key: ROUTES.adminOrders, label: '订单列表', permission: P.orderRead },
      { key: ROUTES.adminFulfillment, label: '履约发货', permission: P.fulfillmentWrite },
      { key: ROUTES.adminRefunds, label: '退款审核', permission: P.aftersalesReview },
    ],
  },
  {
    key: 'service-group',
    label: '售后与发票',
    icon: <CustomerServiceOutlined />,
    children: [
      { key: ROUTES.adminAfterSales, label: '售后工单', permission: P.aftersalesRead },
      { key: ROUTES.adminInvoices, label: '发票管理', permission: P.invoiceRead },
    ],
  },
  {
    key: 'customer-group',
    label: '客户中心',
    icon: <TeamOutlined />,
    children: [{ key: ROUTES.adminCustomers, label: '客户档案', permission: P.customerRead }],
  },
  {
    key: 'org-group',
    label: '组织与渠道',
    icon: <ClusterOutlined />,
    children: [
      { key: ROUTES.adminStaff, label: '员工与角色', permission: P.staffRead },
      { key: ROUTES.adminChannels, label: '渠道账号', permission: P.channelRead },
    ],
  },
  {
    key: 'insight-group',
    label: '报表与审计',
    icon: <BarChartOutlined />,
    children: [
      { key: ROUTES.adminReports, label: '报表工作台', permission: P.reportRead },
      { key: ROUTES.adminAudit, label: '审计日志', permission: P.auditRead },
    ],
  },
];

export function AdminShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const collapsed = useUiStore((state) => state.siderCollapsed);
  const toggleSider = useUiStore((state) => state.toggleSider);
  const themeMode = useUiStore((state) => state.theme);
  const setTheme = useUiStore((state) => state.setTheme);
  const user = useAuthStore((state) => state.user);
  const has = usePermissionStore((state) => state.has);
  const logout = useLogout(ROUTES.adminLogin);

  const menuItems = useMemo(() => {
    const filterEntry = (entry: MenuEntry): MenuEntry | null => {
      if (entry.children) {
        const children = entry.children.map(filterEntry).filter((item): item is MenuEntry => item !== null);
        if (children.length === 0) return null;
        return { ...entry, children };
      }
      if (entry.permission && !has(entry.permission)) return null;
      return entry;
    };
    const toItem = (entry: MenuEntry): Record<string, unknown> => {
      if (entry.children) {
        return { key: entry.key, label: entry.label, icon: entry.icon, children: entry.children.map(toItem) };
      }
      return { key: entry.key, label: <Link to={entry.key}>{entry.label}</Link> };
    };
    return MENU.map(filterEntry)
      .filter((entry): entry is MenuEntry => entry !== null)
      .map(toItem);
  }, [has]);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <a className="qy-skip-link" href="#admin-content">跳到主内容</a>
      <Sider collapsible collapsed={collapsed} trigger={null} width={216} theme="light" style={{ borderRight: '1px solid var(--color-border)' }}>
        <div style={{ height: 56, display: 'flex', alignItems: 'center', padding: '0 16px' }}>
          <Link to={ROUTES.adminDashboard} style={{ whiteSpace: 'nowrap' }}>
            <Typography.Text strong style={{ fontSize: 16 }}>{collapsed ? '栖云' : '栖云智家 · 运营'}</Typography.Text>
          </Link>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={MENU.filter((entry) => entry.children).map((entry) => entry.key)}
          items={menuItems as never}
          style={{ borderInlineEnd: 'none' }}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 16px', borderBottom: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Space size={12}>
            <Button
              type="text"
              aria-label={collapsed ? '展开侧栏' : '收起侧栏'}
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={toggleSider}
            />
            <ChannelScopeSelect />
          </Space>
          <Space size={12}>
            <Space size={4}>
              <BulbOutlined />
              <Switch
                size="small"
                checked={themeMode === 'dark'}
                onChange={(checked) => setTheme(checked ? 'dark' : 'light')}
                aria-label="切换暗色模式"
              />
            </Space>
            <Dropdown
              menu={{
                items: [
                  { key: 'audit', label: <Link to={ROUTES.adminAudit}>审计日志</Link>, disabled: !has(P.auditRead) },
                  { type: 'divider' },
                  { key: 'logout', label: '退出登录', onClick: () => void logout() },
                ],
              }}
            >
              <Space style={{ cursor: 'pointer' }}>
                <Avatar size="small" icon={<UserOutlined />} />
                <Typography.Text>{user?.display_name ?? user?.username ?? '未登录'}</Typography.Text>
              </Space>
            </Dropdown>
          </Space>
        </Header>
        <Content id="admin-content" style={{ background: 'var(--color-bg)' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}

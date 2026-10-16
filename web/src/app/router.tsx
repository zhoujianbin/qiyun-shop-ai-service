import { createBrowserRouter } from 'react-router-dom';
import { CustomerShell } from '@/layouts/CustomerShell';
import { ROUTES } from '@/constants/routes';
import { ErrorBoundary } from './ErrorBoundary';
import { RequireAuth } from './guards';
import { lazyEl } from './lazyPage';
import { adminRoutes } from './routes.admin';
import { authRoutes } from './routes.auth';
import { customerRoutes } from './routes.customer';

// B 端外壳（AdminShell）只服务 /admin/*，对 C 端首屏毫无用处，因此按路由懒加载：
// 它的 antd Menu/Dropdown/Select 以及 ChannelScopeSelect 会随 /admin 首个路由一起下载，
// C 端首页不再为后台 UI 付费。C 端外壳（CustomerShell）是首屏组成，保持静态引入。
const AdminShell = lazyEl(() => import('@/layouts/AdminShell').then((m) => ({ default: m.AdminShell })));

// NotFound / Forbidden 只在错误路径出现：antd Result 会静态带出三张状态插图（serverError/
// noFound/unauthorized，约 37KB 源码）以及 rc-* 依赖，不应计入 C 端首屏，因此懒加载。
const NotFound = lazyEl(() => import('./NotFound').then((m) => ({ default: m.NotFound })));
const Forbidden = lazyEl(() => import('./Forbidden').then((m) => ({ default: m.Forbidden })));

export const router = createBrowserRouter([
  ...authRoutes,
  {
    path: '/',
    element: (
      <ErrorBoundary>
        <CustomerShell />
      </ErrorBoundary>
    ),
    errorElement: NotFound,
    children: customerRoutes,
  },
  {
    path: '/admin',
    element: (
      <RequireAuth loginPath={ROUTES.adminLogin}>
        <ErrorBoundary>{AdminShell}</ErrorBoundary>
      </RequireAuth>
    ),
    errorElement: NotFound,
    children: adminRoutes,
  },
  { path: ROUTES.adminForbidden, element: Forbidden },
  { path: '*', element: NotFound },
]);

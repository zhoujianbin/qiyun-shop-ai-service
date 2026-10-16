import { lazy, Suspense } from 'react';
import type { RouteObject } from 'react-router-dom';
import type { AuthLayoutProps } from '@/layouts/AuthLayout';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { RequireGuest } from './guards';
import { lazyEl } from './lazyPage';

// 登录/注册壳只服务 /login、/register、/admin/login，按路由懒加载：
// 它的 antd Card 会顺带把 antd Tabs（rc-tabs）拉进来，不应计入 C 端首屏。
const LazyAuthLayout = lazy(() => import('@/layouts/AuthLayout').then((m) => ({ default: m.AuthLayout })));

function AuthShell(props: AuthLayoutProps) {
  return (
    <Suspense
      fallback={
        <div className="qy-page">
          <LoadingSkeleton rows={4} />
        </div>
      }
    >
      <LazyAuthLayout {...props} />
    </Suspense>
  );
}

export const authRoutes: RouteObject[] = [
  {
    element: <RequireGuest />,
    children: [
      {
        path: '/login',
        element: <AuthShell title="栖云智家 · 企业电商平台" subtitle="第一期 · 客户登录" />,
        children: [{ index: true, element: lazyEl(() => import('@/pages/auth/LoginPage')) }],
      },
      {
        path: '/register',
        element: <AuthShell title="栖云智家 · 企业电商平台" subtitle="注册新账号" />,
        children: [{ index: true, element: lazyEl(() => import('@/pages/auth/RegisterPage')) }],
      },
      {
        path: '/admin/login',
        element: <AuthShell title="栖云智家 · 运营后台" subtitle="员工登录" />,
        children: [{ index: true, element: lazyEl(() => import('@/pages/auth/AdminLoginPage')) }],
      },
    ],
  },
];

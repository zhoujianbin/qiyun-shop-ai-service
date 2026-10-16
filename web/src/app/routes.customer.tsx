import type { RouteObject } from 'react-router-dom';
import { RequireAuth } from './guards';
import { lazyEl } from './lazyPage';

/** C 端路由：公开浏览 + 登录后个人业务。 */
export const customerRoutes: RouteObject[] = [
  { index: true, element: lazyEl(() => import('@/pages/customer/HomePage')) },
  { path: 'products', element: lazyEl(() => import('@/pages/customer/ProductListPage')) },
  { path: 'products/:productId', element: lazyEl(() => import('@/pages/customer/ProductDetailPage')) },
  {
    element: <RequireAuth />,
    children: [
      { path: 'cart', element: lazyEl(() => import('@/pages/customer/CartPage')) },
      { path: 'checkout', element: lazyEl(() => import('@/pages/customer/CheckoutPage')) },
      { path: 'orders', element: lazyEl(() => import('@/pages/customer/OrderListPage')) },
      { path: 'orders/:orderNo', element: lazyEl(() => import('@/pages/customer/OrderDetailPage')) },
      { path: 'orders/:orderNo/logistics', element: lazyEl(() => import('@/pages/customer/LogisticsDetailPage')) },
      { path: 'after-sales', element: lazyEl(() => import('@/pages/customer/AfterSalesListPage')) },
      { path: 'after-sales/apply', element: lazyEl(() => import('@/pages/customer/AfterSalesApplyPage')) },
      { path: 'after-sales/:ticketId', element: lazyEl(() => import('@/pages/customer/AfterSalesDetailPage')) },
      { path: 'invoices', element: lazyEl(() => import('@/pages/customer/InvoicePage')) },
      { path: 'account', element: lazyEl(() => import('@/pages/customer/AccountPage')) },
      { path: 'account/addresses', element: lazyEl(() => import('@/pages/customer/AddressBookPage')) },
    ],
  },
];

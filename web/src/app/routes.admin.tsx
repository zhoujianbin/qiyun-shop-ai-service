import type { ComponentType } from 'react';
import { Navigate, type RouteObject } from 'react-router-dom';
import { ROUTES } from '@/constants/routes';
import { P, type PermissionCode } from '@/types/permissions';
import { RequirePermission } from './guards';
import { lazyEl } from './lazyPage';

function protect(permissions: Array<PermissionCode>, factory: () => Promise<{ default: ComponentType }>) {
  return <RequirePermission permissions={permissions}>{lazyEl(factory)}</RequirePermission>;
}

/** B 端路由：每条路由声明所需权限码，守卫缺权限跳 /admin/403。 */
export const adminRoutes: RouteObject[] = [
  { index: true, element: <Navigate to={ROUTES.adminDashboard} replace /> },
  { path: 'dashboard', element: protect([P.orderRead], () => import('@/pages/admin/DashboardPage')) },
  { path: 'products', element: protect([P.productRead], () => import('@/pages/admin/ProductListPage')) },
  { path: 'products/new', element: protect([P.productWrite], () => import('@/pages/admin/ProductEditPage')) },
  { path: 'products/:productId', element: protect([P.productRead], () => import('@/pages/admin/ProductEditPage')) },
  { path: 'skus', element: protect([P.productRead], () => import('@/pages/admin/SkuListPage')) },
  { path: 'catalog/categories', element: protect([P.productRead], () => import('@/pages/admin/CategoryPage')) },
  { path: 'catalog/brands', element: protect([P.productRead], () => import('@/pages/admin/BrandPage')) },
  { path: 'inventory', element: protect([P.inventoryRead], () => import('@/pages/admin/InventoryPage')) },
  { path: 'inventory/ledger', element: protect([P.inventoryRead], () => import('@/pages/admin/InventoryLedgerPage')) },
  { path: 'warehouses', element: protect([P.inventoryRead], () => import('@/pages/admin/WarehousePage')) },
  { path: 'orders', element: protect([P.orderRead], () => import('@/pages/admin/OrderListPage')) },
  { path: 'orders/:orderNo', element: protect([P.orderRead], () => import('@/pages/admin/OrderDetailPage')) },
  { path: 'refunds', element: protect([P.aftersalesReview], () => import('@/pages/admin/RefundReviewPage')) },
  { path: 'fulfillment', element: protect([P.fulfillmentWrite], () => import('@/pages/admin/FulfillmentPage')) },
  { path: 'after-sales', element: protect([P.aftersalesRead], () => import('@/pages/admin/AfterSalesPage')) },
  { path: 'after-sales/:ticketId', element: protect([P.aftersalesRead], () => import('@/pages/admin/AfterSalesTicketPage')) },
  { path: 'invoices', element: protect([P.invoiceRead], () => import('@/pages/admin/InvoicePage')) },
  { path: 'customers', element: protect([P.customerRead], () => import('@/pages/admin/CustomerListPage')) },
  { path: 'customers/:customerId', element: protect([P.customerRead], () => import('@/pages/admin/CustomerProfilePage')) },
  { path: 'staff', element: protect([P.staffRead], () => import('@/pages/admin/StaffRolePage')) },
  { path: 'channels', element: protect([P.channelRead], () => import('@/pages/admin/ChannelAccountPage')) },
  { path: 'audit', element: protect([P.auditRead], () => import('@/pages/admin/AuditLogPage')) },
  { path: 'reports', element: protect([P.reportRead], () => import('@/pages/admin/ReportPage')) },
  // 二期：知识库
  { path: 'knowledge', element: protect([P.knowledgeDocumentRead], () => import('@/pages/knowledge/OverviewPage')) },
  { path: 'knowledge/documents', element: protect([P.knowledgeDocumentRead], () => import('@/pages/knowledge/DocumentListPage')) },
  { path: 'knowledge/documents/:documentPk', element: protect([P.knowledgeDocumentRead], () => import('@/pages/knowledge/DocumentDetailPage')) },
  { path: 'knowledge/editor', element: protect([P.knowledgeDocumentWrite], () => import('@/pages/knowledge/EditorPage')) },
  { path: 'knowledge/review', element: protect([P.knowledgeReviewRead], () => import('@/pages/knowledge/ReviewPage')) },
  { path: 'knowledge/retrieval-test', element: protect([P.knowledgeRetrievalTest], () => import('@/pages/knowledge/RetrievalTestPage')) },
  { path: 'knowledge/governance', element: protect([P.knowledgeGovernanceRead], () => import('@/pages/knowledge/GovernancePage')) },
];

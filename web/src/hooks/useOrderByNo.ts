import { useQuery } from '@tanstack/react-query';
import { ordersApi } from '@/api/endpoints/orders';
import { queryKeys } from '@/api/queryKeys';
import { ApiError } from '@/api/errors';
import type { Order } from '@/types/domain';

/**
 * 路由使用业务订单号（order_no），接口按数字 id 取详情；
 * 先以 order_no 精确定位再取详情，保证深链可刷新。
 */
export function useOrderByNo(orderNo?: string) {
  return useQuery<Order>({
    queryKey: queryKeys.orders.detail(orderNo ?? ''),
    enabled: Boolean(orderNo),
    queryFn: async ({ signal }) => {
      const list = await ordersApi.list({ order_no: orderNo, page: 1, page_size: 1, signal });
      const found = list.items[0];
      if (!found) {
        throw new ApiError({ code: 'ORDER_NOT_FOUND', message: '订单不存在或已删除', kind: 'notFound' });
      }
      return ordersApi.detail(found.id);
    },
  });
}

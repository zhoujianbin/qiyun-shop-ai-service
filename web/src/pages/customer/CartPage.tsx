import App from 'antd/es/app';
import Button from 'antd/es/button';
import Checkbox from 'antd/es/checkbox';
import InputNumber from 'antd/es/input-number';
import Popconfirm from 'antd/es/popconfirm';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { cartApi } from '@/api/endpoints/cart';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { PageHeader } from '@/components/common/PageHeader';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { MoneyText } from '@/components/common/MoneyText';
import { errorMessage } from '@/api/errors';
import { addMoney, formatMoney, toCents } from '@/utils/money';
import { ROUTES } from '@/constants/routes';
import type { CartItem } from '@/types/domain';

/** C 端购物车：数量、勾选、删除与金额小计；库存/价格变化提示。 */
export default function CartPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();

  const query = useQuery({
    queryKey: queryKeys.cart.detail({}),
    queryFn: ({ signal }) => cartApi.get({ signal }),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['cart'] });

  const updateItem = async (id: number, body: { quantity?: number; selected?: boolean }) => {
    try {
      await cartApi.updateItem(id, body);
      await refresh();
    } catch (error) {
      message.error(errorMessage(error));
      await refresh();
    }
  };

  const removeItem = async (id: number) => {
    try {
      await cartApi.removeItem(id);
      message.success('已移除');
      await refresh();
    } catch (error) {
      message.error(errorMessage(error));
    }
  };

  const items = query.data?.items ?? [];
  const selected = items.filter((item) => item.selected);
  const total = selected.reduce((sum, item) => sum + toCents(item.unit_price) * (item.quantity ?? 0), 0);
  const invalidCount = items.filter((item) => item.stock_available === false).length;

  const columns: ColumnsType<CartItem> = [
    {
      title: '选择',
      key: 'selected',
      width: 60,
      render: (_, record) => (
        <Checkbox checked={record.selected} onChange={(event) => void updateItem(record.id, { selected: event.target.checked })} />
      ),
    },
    {
      title: '商品',
      key: 'product',
      render: (_, record) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>{record.product_name ?? `SKU ${record.sku_id}`}</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {record.sku_name}
          </Typography.Text>
          {record.stock_available === false ? <Typography.Text type="danger" style={{ fontSize: 12 }}>已失效 / 库存不足</Typography.Text> : null}
        </Space>
      ),
    },
    { title: '单价', dataIndex: 'unit_price', key: 'unit_price', width: 120, render: (value: string) => <MoneyText value={value} /> },
    {
      title: '数量',
      key: 'quantity',
      width: 130,
      render: (_, record) => (
        <InputNumber min={1} max={999} value={record.quantity} onChange={(value) => void updateItem(record.id, { quantity: Number(value ?? 1) })} />
      ),
    },
    {
      title: '小计',
      key: 'subtotal',
      width: 130,
      render: (_, record) => <MoneyText value={addMoney(formatMoney(String(toCents(record.unit_price) * (record.quantity ?? 0) / 100)))} strong />,
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_, record) => (
        <Popconfirm title="确认移除该商品？" onConfirm={() => void removeItem(record.id)} okText="移除" cancelText="取消">
          <Button type="link" danger icon={<DeleteOutlined />}>
            移除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div className="qy-page" style={{ maxWidth: 1100, margin: '0 auto' }}>
      <PageHeader title="购物车" subtitle={`已选 ${selected.length} 项`} />
      {query.isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState title="购物车是空的" description="去挑选心仪的智能家居商品吧" action={<Button type="primary" onClick={() => navigate(ROUTES.products)}>去逛逛</Button>} />
      ) : (
        <>
          {invalidCount > 0 ? (
            <Typography.Text type="warning" style={{ display: 'block', marginBottom: 8 }}>
              有 {invalidCount} 件商品库存或价格已变化，请确认后再结算。
            </Typography.Text>
          ) : null}
          <Table<CartItem> rowKey="id" columns={columns} dataSource={items} pagination={false} />
          <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 16, marginTop: 16 }}>
            <Typography.Text>
              合计（已选）：<MoneyText value={formatMoney(String(total / 100))} strong style={{ fontSize: 20 }} />
            </Typography.Text>
            <Button type="primary" size="large" disabled={selected.length === 0} onClick={() => navigate(`${ROUTES.checkout}?source=CART`)}>
              去结算
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

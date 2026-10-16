import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Modal from 'antd/es/modal';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { productsApi } from '@/api/endpoints/products';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { DataTable } from '@/components/data/DataTable';
import { PageHeader } from '@/components/common/PageHeader';
import { PermissionGate } from '@/components/common/PermissionGate';
import { StatusTag } from '@/components/common/StatusTag';
import { MoneyText } from '@/components/common/MoneyText';
import { MoneyInput } from '@/components/form/MoneyInput';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { isValidMoney } from '@/utils/money';
import { SKU_STATUS_LABELS } from '@/constants/productStatus';
import { P } from '@/types/permissions';
import type { Sku, SkuCreateRequest, SkuStatus } from '@/types/domain';

interface SkuFormValues {
  sku_code: string;
  name: string;
  spec_summary?: string;
  price: string;
  market_price?: string;
  cost_price?: string;
  barcode?: string;
  weight_g?: number;
  status?: SkuStatus;
}

/** B 端 SKU 管理：按商品查看/新增/编辑 SKU，价格以字符串维护。 */
export default function SkuListPage() {
  const { message } = App.useApp();
  const [productId, setProductId] = useState<number | undefined>();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Sku | null>(null);
  const [form] = Form.useForm<SkuFormValues>();

  const productQuery = useQuery({
    queryKey: queryKeys.products.list({ page: 1, page_size: 100 }),
    queryFn: ({ signal }) => productsApi.list({ page: 1, page_size: 100, signal }),
  });

  useEffect(() => {
    if (!productId && productQuery.data?.items.length) setProductId(productQuery.data.items[0].id);
  }, [productQuery.data, productId]);

  const skuQuery = useQuery({
    queryKey: queryKeys.skus.list({ product_id: productId }),
    queryFn: ({ signal }) => productsApi.skus(productId as number, { signal }),
    enabled: Boolean(productId),
  });

  const saveMutation = useIdempotentMutation(
    (vars: { id?: number; body: SkuCreateRequest }) =>
      vars.id ? productsApi.updateSku(vars.id, vars.body) : productsApi.createSku(productId as number, vars.body),
    {
      onSuccess: async () => {
        message.success('SKU 已保存');
        setOpen(false);
        saveMutation.resetKey();
        await queryClient.invalidateQueries({ queryKey: ['skus'] });
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ status: 'ON_SALE', weight_g: 0 });
    setOpen(true);
  };

  const openEdit = (record: Sku) => {
    setEditing(record);
    form.setFieldsValue({
      sku_code: record.sku_code,
      name: record.name,
      spec_summary: record.spec_summary ?? undefined,
      price: record.price,
      market_price: record.market_price ?? undefined,
      cost_price: record.cost_price ?? undefined,
      barcode: record.barcode ?? undefined,
      weight_g: record.weight_g ?? undefined,
      status: record.status,
    });
    setOpen(true);
  };

  const columns: ColumnsType<Sku> = [
    { title: 'SKU 编码', dataIndex: 'sku_code', key: 'sku_code' },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '规格', dataIndex: 'spec_summary', key: 'spec_summary', render: (value?: string) => value ?? '-' },
    { title: '销售价', dataIndex: 'price', key: 'price', render: (value: string) => <MoneyText value={value} strong /> },
    { title: '成本价', dataIndex: 'cost_price', key: 'cost_price', render: (value?: string) => <MoneyText value={value} muted /> },
    { title: '状态', dataIndex: 'status', key: 'status', render: (value: SkuStatus) => <StatusTag kind="sku" value={value} /> },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_, record) => (
        <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
          <Button type="link" onClick={() => openEdit(record)}>编辑</Button>
        </PermissionGate>
      ),
    },
  ];

  return (
    <div className="qy-page">
      <PageHeader
        title="SKU 管理"
        subtitle="规格组合、销售价/成本价与条码"
        extra={
          <Space>
            <Select
              showSearch
              optionFilterProp="label"
              style={{ width: 260 }}
              placeholder="选择商品"
              loading={productQuery.isLoading}
              value={productId}
              options={(productQuery.data?.items ?? []).map((product) => ({ value: product.id, label: `${product.name}（${product.spu_code}）` }))}
              onChange={(value) => setProductId(value)}
            />
            <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
              <Button type="primary" disabled={!productId} onClick={openCreate}>新增 SKU</Button>
            </PermissionGate>
          </Space>
        }
      />
      {!productId ? (
        <Card>
          <Typography.Text type="secondary">请先选择商品以查看其 SKU。</Typography.Text>
        </Card>
      ) : (
        <DataTable<Sku>
          rowKey="id"
          columns={columns}
          data={skuQuery.data?.items ?? []}
          loading={skuQuery.isLoading}
          error={skuQuery.error}
          onRetry={() => void skuQuery.refetch()}
          total={skuQuery.data?.meta?.total ?? 0}
          page={1}
          pageSize={100}
          onPageChange={() => undefined}
          emptyTitle="该商品暂无 SKU"
          emptyAction={<Button type="primary" onClick={openCreate}>新增 SKU</Button>}
          toolbar={<Typography.Text>SKU 组合在商品内唯一；库存请前往库存总览调整。</Typography.Text>}
        />
      )}

      <Modal
        open={open}
        title={editing ? `编辑 SKU：${editing.sku_code}` : '新增 SKU'}
        okText="保存"
        cancelText="取消"
        confirmLoading={saveMutation.isPending}
        onCancel={() => setOpen(false)}
        onOk={() => {
          void form.validateFields().then((values) => {
            if (!isValidMoney(values.price)) {
              message.error('销售价格式不正确，最多两位小数且不超过 99999999.99');
              return;
            }
            const body: SkuCreateRequest = {
              sku_code: values.sku_code,
              name: values.name,
              spec_summary: values.spec_summary ?? null,
              price: values.price,
              market_price: values.market_price ?? null,
              cost_price: values.cost_price ?? null,
              barcode: values.barcode ?? null,
              weight_g: values.weight_g ?? null,
              status: values.status,
            };
            saveMutation.mutate({ id: editing?.id, body });
          });
        }}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item label="SKU 编码" name="sku_code" rules={[{ required: true, message: '请输入 SKU 编码' }, { pattern: /^[A-Za-z0-9_-]{2,64}$/, message: '2–64 位字母数字与 -_' }]}>
            <Input disabled={Boolean(editing)} placeholder="如：QL-L3P-BLACK" />
          </Form.Item>
          <Form.Item label="SKU 名称" name="name" rules={[{ required: true, message: '请输入 SKU 名称' }]}>
            <Input placeholder="如：曜石黑 标准版" />
          </Form.Item>
          <Form.Item label="规格摘要" name="spec_summary">
            <Input placeholder="如：颜色:曜石黑; 版本:标准版" />
          </Form.Item>
          <Space size={12} wrap>
            <Form.Item label="销售价" name="price" rules={[{ required: true, message: '请输入销售价' }]}>
              <MoneyInput style={{ width: 160 }} placeholder="0.00" />
            </Form.Item>
            <Form.Item label="市场价" name="market_price">
              <MoneyInput style={{ width: 160 }} placeholder="0.00" />
            </Form.Item>
            <Form.Item label="成本价" name="cost_price">
              <MoneyInput style={{ width: 160 }} placeholder="0.00" />
            </Form.Item>
          </Space>
          <Space size={12} wrap>
            <Form.Item label="条码" name="barcode">
              <Input style={{ width: 200 }} maxLength={64} placeholder="选填" />
            </Form.Item>
            <Form.Item label="重量（克）" name="weight_g">
              <InputNumber min={0} max={999999} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item label="状态" name="status">
              <Select style={{ width: 140 }} options={Object.entries(SKU_STATUS_LABELS).map(([value, label]) => ({ value, label }))} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  );
}

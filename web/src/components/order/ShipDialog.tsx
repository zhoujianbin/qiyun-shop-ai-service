import App from 'antd/es/app';
import DatePicker from 'antd/es/date-picker';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Modal from 'antd/es/modal';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import type { Dayjs } from 'dayjs';
import { useEffect, useMemo, useState } from 'react';
import { formatDateTime } from '@/utils/datetime';
import { MaskedText } from '../common/MaskedText';
import type { Carrier, Order, OrderItem, ShipRequest, ShipmentItem, Warehouse } from '@/types/domain';

export interface ShipDialogProps {
  open: boolean;
  order: Order | null;
  warehouses: Warehouse[];
  carriers: Carrier[];
  loading?: boolean;
  onCancel: () => void;
  onSubmit: (payload: ShipRequest) => void;
}

interface ShipFormValues {
  warehouse_id: number;
  carrier_code: string;
  tracking_no: string;
  package_count?: number;
  shipped_at?: Dayjs | null;
  remark?: string;
}

/** 发货对话框：支持部分发货，运单号按 1–64 校验；仓库/承运商必选。 */
export function ShipDialog({ open, order, warehouses, carriers, loading, onCancel, onSubmit }: ShipDialogProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<ShipFormValues>();
  const [quantities, setQuantities] = useState<Record<number, number>>({});

  const items = order?.items ?? [];

  useEffect(() => {
    if (open && items.length > 0) {
      const next: Record<number, number> = {};
      items.forEach((item) => {
        const remaining = Math.max((item.quantity ?? 0) - (item.shipped_quantity ?? 0), 0);
        next[item.id] = remaining;
      });
      setQuantities(next);
      form.setFieldsValue({ package_count: 1, shipped_at: null });
    }
  }, [open, items, form]);

  const totalQty = useMemo(() => Object.values(quantities).reduce((sum, value) => sum + (value || 0), 0), [quantities]);

  const columns: ColumnsType<OrderItem> = [
    { title: '商品', dataIndex: 'product_name', key: 'product_name' },
    { title: '规格', dataIndex: 'sku_name', key: 'sku_name' },
    { title: '已购', dataIndex: 'quantity', key: 'quantity', width: 80 },
    { title: '已发', dataIndex: 'shipped_quantity', key: 'shipped_quantity', width: 80, render: (v?: number) => v ?? 0 },
    {
      title: '本次发货',
      key: 'ship_qty',
      width: 130,
      render: (_, record) => {
        const remaining = Math.max((record.quantity ?? 0) - (record.shipped_quantity ?? 0), 0);
        return (
          <InputNumber
            min={0}
            max={remaining}
            value={quantities[record.id] ?? 0}
            onChange={(value) => setQuantities((prev) => ({ ...prev, [record.id]: Number(value ?? 0) }))}
            style={{ width: 110 }}
          />
        );
      },
    },
  ];

  const submit = async () => {
    try {
      const values = await form.validateFields();
      if (totalQty <= 0) {
        message.error('请至少填写一件发货数量');
        return;
      }
      const payloadItems: ShipmentItem[] = items
        .filter((item) => (quantities[item.id] ?? 0) > 0)
        .map((item) => ({ order_item_id: item.id, sku_id: item.sku_id, quantity: quantities[item.id] ?? 0 }));
      onSubmit({
        warehouse_id: values.warehouse_id,
        carrier_code: values.carrier_code,
        tracking_no: values.tracking_no,
        package_count: values.package_count,
        shipped_at: values.shipped_at ? values.shipped_at.toISOString() : null,
        items: payloadItems,
        remark: values.remark ?? null,
      });
    } catch {
      // 校验失败由表单展示
    }
  };

  return (
    <Modal
      open={open}
      title="订单发货"
      width={760}
      okText="确认发货"
      cancelText="取消"
      confirmLoading={loading}
      onOk={submit}
      onCancel={onCancel}
      maskClosable={false}
      destroyOnClose
    >
      {order ? (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          <Typography.Text type="secondary">
            订单 {order.order_no} · 收件人 {order.receiver_name ?? '-'} · <MaskedText value={order.receiver_phone_masked} />
          </Typography.Text>
          <Form form={form} layout="vertical">
            <Space size={12} wrap align="start">
              <Form.Item label="发货仓库" name="warehouse_id" rules={[{ required: true, message: '请选择仓库' }]} style={{ minWidth: 180 }}>
                <Select options={warehouses.map((w) => ({ value: w.id, label: w.name }))} placeholder="请选择仓库" />
              </Form.Item>
              <Form.Item label="承运商" name="carrier_code" rules={[{ required: true, message: '请选择承运商' }]} style={{ minWidth: 160 }}>
                <Select options={carriers.map((c) => ({ value: c.code, label: c.name }))} placeholder="请选择承运商" />
              </Form.Item>
              <Form.Item
                label="运单号"
                name="tracking_no"
                rules={[
                  { required: true, message: '请输入运单号' },
                  { pattern: /^[A-Za-z0-9-]{1,64}$/, message: '运单号 1–64 位字母数字' },
                ]}
                style={{ minWidth: 200 }}
              >
                <Input placeholder="请输入运单号" maxLength={64} />
              </Form.Item>
              <Form.Item label="包裹件数" name="package_count" style={{ width: 110 }}>
                <InputNumber min={1} max={99} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="发货时间" name="shipped_at" style={{ minWidth: 190 }}>
                <DatePicker showTime style={{ width: '100%' }} placeholder="默认当前时间" />
              </Form.Item>
            </Space>
            <Form.Item label="发货备注" name="remark" rules={[{ max: 200, message: '不超过 200 字' }]}>
              <Input.TextArea rows={2} placeholder="选填，≤200 字" maxLength={200} showCount />
            </Form.Item>
          </Form>
          <Table<OrderItem> rowKey="id" size="small" columns={columns} dataSource={items} pagination={false} />
          <Typography.Text type={totalQty > 0 ? 'success' : 'warning'}>本次合计发货 {totalQty} 件</Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            当前时间（本地）：{formatDateTime(new Date().toISOString())}
          </Typography.Text>
        </Space>
      ) : null}
    </Modal>
  );
}

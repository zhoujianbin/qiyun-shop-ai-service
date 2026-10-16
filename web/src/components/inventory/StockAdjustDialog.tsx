import Alert from 'antd/es/alert';
import Descriptions from 'antd/es/descriptions';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Modal from 'antd/es/modal';
import Radio from 'antd/es/radio';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import { useEffect, useMemo } from 'react';
import type { InventoryItem, StockAdjustRequest, Warehouse } from '@/types/domain';
import { ADJUST_TYPE_OPTIONS, STOCK_ADJUST_REASONS } from '@/constants/productStatus';

export interface StockAdjustDialogProps {
  open: boolean;
  item: InventoryItem | null;
  warehouses: Warehouse[];
  loading?: boolean;
  conflict?: boolean;
  onCancel: () => void;
  onSubmit: (payload: StockAdjustRequest) => void;
}

interface AdjustFormValues {
  warehouse_id: number;
  change_type: StockAdjustRequest['change_type'];
  qty_delta: number;
  reason: string;
  remark?: string;
}

function signedDelta(type: string, qty: number): number {
  const positive = ['PURCHASE_IN', 'RETURN_IN', 'TRANSFER_IN'].includes(type);
  const negative = ['DAMAGE', 'TRANSFER_OUT'].includes(type);
  if (positive) return Math.abs(qty);
  if (negative) return -Math.abs(qty);
  return qty;
}

/** 库存调整：原因必填，提交前预览“调整前可售 → 调整后可售”；库存只经流水变化。 */
export function StockAdjustDialog({ open, item, warehouses, loading, conflict, onCancel, onSubmit }: StockAdjustDialogProps) {
  const [form] = Form.useForm<AdjustFormValues>();
  const changeType = Form.useWatch('change_type', form) ?? 'PURCHASE_IN';
  const rawQty = Form.useWatch('qty_delta', form) ?? 0;
  const reason = Form.useWatch('reason', form);

  useEffect(() => {
    if (open && item) {
      form.setFieldsValue({
        warehouse_id: item.warehouse_id,
        change_type: 'PURCHASE_IN',
        qty_delta: 1,
        reason: 'PURCHASE_ARRIVAL',
        remark: '',
      });
    }
  }, [open, item, form]);

  const delta = useMemo(() => signedDelta(String(changeType), Number(rawQty) || 0), [changeType, rawQty]);
  const before = item?.qty_available ?? 0;
  const after = before + delta;
  const invalidOut = delta < 0 && after < 0;

  const submit = async () => {
    if (!item) return;
    try {
      const values = await form.validateFields();
      onSubmit({
        warehouse_id: values.warehouse_id,
        sku_id: item.sku_id,
        change_type: values.change_type,
        qty_delta: signedDelta(String(values.change_type), Number(values.qty_delta)),
        expected_version: item.version ?? 0,
        reason: values.reason,
        remark: values.remark ?? null,
      });
    } catch {
      // 表单校验反馈
    }
  };

  return (
    <Modal
      open={open}
      title="库存调整"
      okText="提交调整"
      cancelText="取消"
      confirmLoading={loading}
      okButtonProps={{ disabled: invalidOut }}
      onOk={submit}
      onCancel={onCancel}
      maskClosable={false}
      destroyOnClose
    >
      {item ? (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {conflict ? <Alert type="warning" showIcon message="库存已变化，请刷新后重试" /> : null}
          <Descriptions size="small" column={2} bordered>
            <Descriptions.Item label="SKU">{item.sku_code ?? item.sku_id}</Descriptions.Item>
            <Descriptions.Item label="商品">{item.product_name ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="仓库">{item.warehouse_name ?? item.warehouse_id}</Descriptions.Item>
            <Descriptions.Item label="可售 / 锁定 / 在途">
              {item.qty_available} / {item.qty_reserved} / {item.qty_in_transit}
            </Descriptions.Item>
          </Descriptions>
          <Form form={form} layout="vertical">
            <Form.Item label="仓库" name="warehouse_id" rules={[{ required: true, message: '请选择仓库' }]}>
              <Select options={warehouses.map((w) => ({ value: w.id, label: w.name }))} />
            </Form.Item>
            <Form.Item label="调整类型" name="change_type" rules={[{ required: true, message: '请选择调整类型' }]}>
              <Radio.Group options={ADJUST_TYPE_OPTIONS} optionType="button" buttonStyle="solid" />
            </Form.Item>
            <Form.Item
              label="调整数量"
              name="qty_delta"
              rules={[
                { required: true, message: '请输入调整数量' },
                {
                  validator: (_, value) => {
                    const num = Number(value);
                    if (!Number.isInteger(num) || num === 0) return Promise.reject(new Error('数量必须为非 0 整数'));
                    const signed = signedDelta(String(changeType), num);
                    if (signed < 0 && before + signed < 0) {
                      return Promise.reject(new Error('出库数量不得超过当前可售库存'));
                    }
                    return Promise.resolve();
                  },
                },
              ]}
              extra="盘点修正可正可负；其余类型按方向自动取正负"
            >
              <InputNumber style={{ width: 180 }} precision={0} />
            </Form.Item>
            <Form.Item label="调整原因" name="reason" rules={[{ required: true, message: '请选择调整原因' }]}>
              <Select options={STOCK_ADJUST_REASONS} />
            </Form.Item>
            <Form.Item
              label="备注"
              name="remark"
              rules={[
                {
                  validator: (_, value) =>
                    reason === 'OTHER' && (!value || String(value).trim().length === 0)
                      ? Promise.reject(new Error('原因为“其他”时备注必填'))
                      : Promise.resolve(),
                },
                { max: 200, message: '备注不超过 200 字' },
              ]}
            >
              <Input.TextArea rows={2} placeholder="选填；原因为“其他”时必填" maxLength={200} showCount />
            </Form.Item>
          </Form>
          <Typography.Text>
            调整前可售 <Typography.Text strong>{before}</Typography.Text> → 调整后可售{' '}
            <Typography.Text strong type={after < 0 ? 'danger' : 'success'}>
              {after}
            </Typography.Text>
            （锁定/在途不变）
          </Typography.Text>
        </Space>
      ) : null}
    </Modal>
  );
}

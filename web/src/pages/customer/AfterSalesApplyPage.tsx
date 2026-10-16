import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';
import { useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { afterSalesApi } from '@/api/endpoints/afterSales';
import { ordersApi } from '@/api/endpoints/orders';
import { queryKeys } from '@/api/queryKeys';
import { PageHeader } from '@/components/common/PageHeader';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { MoneyInput } from '@/components/form/MoneyInput';
import { Uploader } from '@/components/form/Uploader';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { useAuthStore } from '@/stores/authStore';
import { errorMessage } from '@/api/errors';
import { isValidMoney, toCents } from '@/utils/money';
import { AFTER_SALES_REASON_OPTIONS, AFTER_SALES_TYPE_OPTIONS } from '@/constants/statusMaps';
import { ROUTES } from '@/constants/routes';
import type { AfterSalesCreateRequest, Attachment, AfterSalesType } from '@/types/domain';

interface ApplyFormValues {
  order_id: number;
  type: AfterSalesType;
  reason_code: string;
  description?: string;
  quantity: number;
  refund_amount?: string;
}

/** C 端售后申请：类型、原因、凭证、金额；金额不得超过可退金额。 */
export default function AfterSalesApplyPage() {
  const { message } = App.useApp();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const user = useAuthStore((state) => state.user);
  const [form] = Form.useForm<ApplyFormValues>();
  const [evidence, setEvidence] = useState<Attachment[]>([]);
  const orderIdParam = params.get('order_id');

  const ordersQuery = useQuery({
    queryKey: queryKeys.orders.list({ customer_id: user?.id, page: 1, page_size: 50 }),
    queryFn: ({ signal }) => ordersApi.list({ customer_id: user?.id, page: 1, page_size: 50, signal }),
    enabled: Boolean(user?.id),
  });

  const orderOptions = useMemo(
    () => (ordersQuery.data?.items ?? [])
      .filter((order) => ['SHIPPED', 'COMPLETED', 'PAID'].includes(order.status))
      .map((order) => ({ value: order.id, label: `${order.order_no} · ${order.items?.[0]?.product_name ?? ''}` })),
    [ordersQuery.data],
  );

  const createMutation = useIdempotentMutation(
    (vars: AfterSalesCreateRequest) => afterSalesApi.create(vars),
    {
      onSuccess: (application) => {
        message.success('售后申请已提交');
        createMutation.resetKey();
        navigate(ROUTES.afterSalesDetail(application.id));
      },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const submit = async () => {
    try {
      const values = await form.validateFields();
      if (values.refund_amount && !isValidMoney(values.refund_amount)) {
        message.error('退款金额格式不正确，最多两位小数');
        return;
      }
      createMutation.mutate({
        order_id: values.order_id,
        type: values.type,
        reason_code: values.reason_code,
        description: values.description ?? null,
        quantity: values.quantity,
        refund_amount: values.refund_amount ?? null,
        evidence_attachment_ids: evidence.map((item) => item.id),
      });
    } catch {
      // 表单反馈
    }
  };

  return (
    <div className="qy-page" style={{ maxWidth: 760, margin: '0 auto' }}>
      <PageHeader title="申请售后" subtitle="退换修申请将进入审核流程，请如实填写问题描述" breadcrumb={[{ label: '售后服务', to: ROUTES.afterSalesList }, { label: '申请' }]} />
      {ordersQuery.isLoading ? (
        <LoadingSkeleton rows={5} />
      ) : ordersQuery.isError ? (
        <ErrorState error={ordersQuery.error} onRetry={() => void ordersQuery.refetch()} />
      ) : (
        <Card>
          <Form form={form} layout="vertical" initialValues={{ order_id: orderIdParam ? Number(orderIdParam) : undefined, type: 'REFUND_ONLY', quantity: 1 }}>
            <Form.Item label="关联订单" name="order_id" rules={[{ required: true, message: '请选择订单' }]}>
              <Select showSearch optionFilterProp="label" placeholder="请选择需要售后的订单" options={orderOptions} />
            </Form.Item>
            <Form.Item label="售后类型" name="type" rules={[{ required: true, message: '请选择售后类型' }]}>
              <Select options={AFTER_SALES_TYPE_OPTIONS} />
            </Form.Item>
            <Form.Item label="售后原因" name="reason_code" rules={[{ required: true, message: '请选择售后原因' }]}>
              <Select options={AFTER_SALES_REASON_OPTIONS} />
            </Form.Item>
            <Form.Item label="问题描述" name="description" rules={[{ max: 500, message: '不超过 500 字' }]}>
              <Input.TextArea rows={4} maxLength={500} showCount placeholder="请描述问题现象、发生时间与已尝试的处理" />
            </Form.Item>
            <Space size={16} wrap>
              <Form.Item label="售后数量" name="quantity" rules={[{ required: true, message: '请输入售后数量' }]}>
                <InputNumber min={1} max={99} style={{ width: 160 }} />
              </Form.Item>
              <Form.Item label="期望退款金额" name="refund_amount" extra="最多两位小数，不得超过实付金额" style={{ minWidth: 240 }}>
                <MoneyInput placeholder="0.00" />
              </Form.Item>
            </Space>
            <Form.Item label="上传凭证" extra="最多 9 个文件，单个不超过 10MB，支持 JPG/PNG/WebP/PDF">
              <Uploader value={evidence} onChange={setEvidence} maxCount={9} maxSizeMB={10} ownerType="AfterSalesApplication" />
            </Form.Item>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              提交后可在“售后服务”列表查看进度；审核期间可补充资料或撤回申请。
            </Typography.Text>
            <div style={{ marginTop: 16 }}>
              <Space>
                <Button type="primary" loading={createMutation.isPending} onClick={() => void submit()}>
                  提交申请
                </Button>
                <Button onClick={() => navigate(ROUTES.afterSalesList)}>返回列表</Button>
              </Space>
            </div>
          </Form>
        </Card>
      )}
    </div>
  );
}

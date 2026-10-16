import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Descriptions from 'antd/es/descriptions';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Timeline from 'antd/es/timeline';
import Typography from 'antd/es/typography';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { afterSalesApi } from '@/api/endpoints/afterSales';
import { shipmentsApi } from '@/api/endpoints/shipments';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { PageHeader } from '@/components/common/PageHeader';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { MoneyText } from '@/components/common/MoneyText';
import { StatusTag } from '@/components/common/StatusTag';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { formatDateTime } from '@/utils/datetime';
import { ROUTES } from '@/constants/routes';

/** C 端售后详情：处理记录时间线、撤回申请、登记退货物流与留言。 */
export default function AfterSalesDetailPage() {
  const { ticketId } = useParams();
  const id = Number(ticketId);
  const navigate = useNavigate();
  const { message } = App.useApp();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  const [returnOpen, setReturnOpen] = useState(false);
  const [returnForm] = Form.useForm<{ carrier_code: string; tracking_no: string }>();
  const [messageText, setMessageText] = useState('');

  const query = useQuery({
    queryKey: queryKeys.afterSales.detail(id),
    queryFn: ({ signal }) => afterSalesApi.detail(id),
    enabled: Number.isFinite(id),
  });

  const carriersQuery = useQuery({
    queryKey: queryKeys.carriers.list(),
    queryFn: ({ signal }) => shipmentsApi.carriers({ signal }),
    staleTime: 5 * 60 * 1000,
  });

  const application = query.data;
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['afterSales'] });

  const cancelMutation = useIdempotentMutation(
    (vars: { id: number; reason: string }) => afterSalesApi.cancel(vars.id, { reason: vars.reason }),
    {
      onSuccess: async () => { message.success('已撤回申请'); setCancelOpen(false); cancelMutation.resetKey(); await invalidate(); },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const returnMutation = useIdempotentMutation(
    (vars: { id: number; carrierCode: string; trackingNo: string }) =>
      afterSalesApi.returnShipment(vars.id, { carrier_code: vars.carrierCode, tracking_no: vars.trackingNo }),
    {
      onSuccess: async () => { message.success('退货物流已登记'); setReturnOpen(false); returnMutation.resetKey(); await invalidate(); },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  const messageMutation = useIdempotentMutation(
    (vars: { id: number; content: string }) => afterSalesApi.addMessage(vars.id, { content: vars.content, visible_to_customer: true }),
    {
      onSuccess: async () => { message.success('已发送'); setMessageText(''); messageMutation.resetKey(); await invalidate(); },
      onError: (error) => message.error(errorMessage(error)),
    },
  );

  if (query.isLoading) return <div className="qy-page"><LoadingSkeleton rows={8} /></div>;
  if (query.isError || !application) {
    return <div className="qy-page"><ErrorState title="售后单加载失败" error={query.error} onRetry={() => void query.refetch()} /></div>;
  }

  const canCancel = ['SUBMITTED', 'REVIEWING', 'WAITING_RETURN'].includes(application.status);
  const canReturn = application.status === 'WAITING_RETURN';
  const readOnly = ['COMPLETED', 'REJECTED', 'CANCELLED'].includes(application.status);

  return (
    <div className="qy-page" style={{ maxWidth: 900, margin: '0 auto' }}>
      <PageHeader
        title={`售后单 ${application.application_no}`}
        breadcrumb={[{ label: '售后服务', to: ROUTES.afterSalesList }, { label: application.application_no }]}
        tags={<StatusTag kind="afterSales" value={application.status} />}
        extra={
          <Space>
            {canReturn ? <Button type="primary" onClick={() => setReturnOpen(true)}>登记退货物流</Button> : null}
            {canCancel ? <Button danger onClick={() => setCancelOpen(true)}>撤回申请</Button> : null}
            <Button onClick={() => navigate(ROUTES.afterSalesList)}>返回列表</Button>
          </Space>
        }
      />
      <Card title="申请信息" style={{ marginBottom: 16 }}>
        <Descriptions column={2} size="small">
          <Descriptions.Item label="关联订单">{application.order_no ?? application.order_id}</Descriptions.Item>
          <Descriptions.Item label="售后类型"><StatusTag kind="afterSalesType" value={application.type} /></Descriptions.Item>
          <Descriptions.Item label="原因码">{application.reason_code}</Descriptions.Item>
          <Descriptions.Item label="申请数量">{application.quantity ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="退款金额"><MoneyText value={application.refund_amount} /></Descriptions.Item>
          <Descriptions.Item label="申请时间">{formatDateTime(application.applied_at)}</Descriptions.Item>
          <Descriptions.Item label="退货物流">
            {application.return_tracking_no ? `${application.return_carrier_code ?? ''} ${application.return_tracking_no}` : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="审核意见">{application.review_remark ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="问题描述" span={2}>{application.description ?? '-'}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="处理记录" style={{ marginBottom: 16 }}>
        {(application.messages ?? []).length === 0 ? (
          <Typography.Text type="secondary">暂无处理记录</Typography.Text>
        ) : (
          <Timeline
            items={(application.messages ?? []).map((item) => ({
              children: (
                <div>
                  <Typography.Text>{item.content}</Typography.Text>
                  <div>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {item.sender_type} · {formatDateTime(item.created_at)}
                    </Typography.Text>
                  </div>
                </div>
              ),
            }))}
          />
        )}
      </Card>

      <Card title="补充留言">
        <Input.TextArea
          rows={3}
          maxLength={500}
          showCount
          value={messageText}
          onChange={(event) => setMessageText(event.target.value)}
          placeholder={readOnly ? '该售后单已结案，仅可追加备注' : '补充问题信息或与客服沟通'}
        />
        <div style={{ marginTop: 12 }}>
          <Button
            type="primary"
            disabled={messageText.trim().length === 0}
            loading={messageMutation.isPending}
            onClick={() => application && messageMutation.mutate({ id: application.id, content: messageText.trim() })}
          >
            发送
          </Button>
        </div>
      </Card>

      <Modal
        open={cancelOpen}
        title="撤回售后申请"
        okText="确认撤回"
        cancelText="取消"
        okButtonProps={{ danger: true, loading: cancelMutation.isPending }}
        onCancel={() => setCancelOpen(false)}
        onOk={() => {
          if (cancelReason.trim().length === 0) { message.error('请填写撤回原因'); return; }
          if (application) cancelMutation.mutate({ id: application.id, reason: cancelReason.trim() });
        }}
      >
        <Input.TextArea rows={3} maxLength={200} showCount value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} placeholder="请填写撤回原因（≤200 字）" />
      </Modal>

      <Modal
        open={returnOpen}
        title="登记退货物流"
        okText="提交"
        cancelText="取消"
        confirmLoading={returnMutation.isPending}
        onCancel={() => setReturnOpen(false)}
        onOk={() => {
          void returnForm.validateFields().then((values) => {
            if (application) returnMutation.mutate({ id: application.id, carrierCode: values.carrier_code, trackingNo: values.tracking_no });
          });
        }}
      >
        <Form form={returnForm} layout="vertical">
          <Form.Item label="承运商" name="carrier_code" rules={[{ required: true, message: '请选择承运商' }]}>
            <Select options={(carriersQuery.data?.items ?? []).map((c) => ({ value: c.code, label: c.name }))} />
          </Form.Item>
          <Form.Item label="退货运单号" name="tracking_no" rules={[{ required: true, message: '请输入运单号' }, { pattern: /^[A-Za-z0-9-]{1,64}$/, message: '1–64 位字母数字' }]}>
            <Input placeholder="请输入退货运单号" maxLength={64} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

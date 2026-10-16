import App from 'antd/es/app';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Descriptions from 'antd/es/descriptions';
import Divider from 'antd/es/divider';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import Radio from 'antd/es/radio';
import Row from 'antd/es/row';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Switch from 'antd/es/switch';
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
import { EvidenceGallery } from '@/components/aftersales/EvidenceGallery';
import { PermissionGate } from '@/components/common/PermissionGate';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { usePermission } from '@/hooks/usePermission';
import { errorMessage } from '@/api/errors';
import { formatDateTime } from '@/utils/datetime';
import { isValidMoney } from '@/utils/money';
import { P } from '@/types/permissions';
import { ROUTES } from '@/constants/routes';

interface ReviewFormValues {
  decision: 'APPROVE' | 'REJECT';
  approved_amount?: string;
  reason?: string;
  need_return?: boolean;
  return_address?: string;
}

/** B 端售后工单详情：受理/补件/审核/驳回/完成，按状态机裁剪动作。 */
export default function AfterSalesTicketPage() {
  const { ticketId } = useParams();
  const id = Number(ticketId);
  const navigate = useNavigate();
  const { message } = App.useApp();
  const canReview = usePermission(P.aftersalesReview);
  const [reviewForm] = Form.useForm<ReviewFormValues>();
  const decision = Form.useWatch('decision', reviewForm) ?? 'APPROVE';
  const needReturn = Form.useWatch('need_return', reviewForm) ?? false;
  const [completeOpen, setCompleteOpen] = useState(false);
  const [returnOpen, setReturnOpen] = useState(false);
  const [messageText, setMessageText] = useState('');
  const [completeForm] = Form.useForm<{ conclusion: string; refund_amount?: string }>();
  const [returnForm] = Form.useForm<{ carrier_code: string; tracking_no: string }>();

  const query = useQuery({
    queryKey: queryKeys.afterSales.detail(id),
    queryFn: ({ signal }) => afterSalesApi.detail(id),
    enabled: Number.isFinite(id),
  });
  const carriersQuery = useQuery({
    queryKey: queryKeys.carriers.list(),
    queryFn: ({ signal }) => shipmentsApi.carriers({ signal }),
  });

  const application = query.data;
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ['afterSales'] });
    await queryClient.invalidateQueries({ queryKey: ['orders'] });
  };

  const reviewMutation = useIdempotentMutation(
    (vars: { id: number; body: ReviewFormValues }) => afterSalesApi.review(vars.id, {
      decision: vars.body.decision,
      approved_amount: vars.body.approved_amount ?? null,
      reason: vars.body.reason ?? null,
      need_return: vars.body.need_return ?? false,
      return_address: vars.body.return_address ?? null,
    }),
    { onSuccess: async () => { message.success('审核已提交'); reviewMutation.resetKey(); await invalidate(); }, onError: (error) => message.error(errorMessage(error)) },
  );

  const receiveMutation = useIdempotentMutation((vars: { id: number; received: boolean }) => afterSalesApi.receive(vars.id, { received: vars.received }), {
    onSuccess: async () => { message.success('已登记收货'); receiveMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });

  const completeMutation = useIdempotentMutation((vars: { id: number; conclusion: string; refund_amount?: string }) => afterSalesApi.complete(vars.id, { conclusion: vars.conclusion, refund_amount: vars.refund_amount ?? null }), {
    onSuccess: async () => { message.success('售后已完成'); setCompleteOpen(false); completeMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });

  const returnMutation = useIdempotentMutation((vars: { id: number; carrierCode: string; trackingNo: string }) => afterSalesApi.returnShipment(vars.id, { carrier_code: vars.carrierCode, tracking_no: vars.trackingNo }), {
    onSuccess: async () => { message.success('退货物流已登记'); setReturnOpen(false); returnMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });

  const messageMutation = useIdempotentMutation((vars: { id: number; content: string }) => afterSalesApi.addMessage(vars.id, { content: vars.content, visible_to_customer: true }), {
    onSuccess: async () => { message.success('已发送'); setMessageText(''); messageMutation.resetKey(); await invalidate(); },
    onError: (error) => message.error(errorMessage(error)),
  });

  if (query.isLoading) return <div className="qy-page"><LoadingSkeleton rows={10} /></div>;
  if (query.isError || !application) {
    return <div className="qy-page"><ErrorState title="工单加载失败" error={query.error} onRetry={() => void query.refetch()} /></div>;
  }

  const status = application.status;
  const canReviewNow = ['SUBMITTED', 'REVIEWING'].includes(status);
  const canReceive = ['WAITING_RETURN', 'RETURN_SHIPPED', 'APPROVED'].includes(status);
  const canComplete = ['PROCESSING', 'RECEIVED', 'APPROVED', 'REFUNDING'].includes(status);
  const readOnly = ['COMPLETED', 'REJECTED', 'CANCELLED'].includes(status);

  return (
    <div className="qy-page">
      <PageHeader
        title={`售后工单 ${application.application_no}`}
        subtitle={`申请时间 ${formatDateTime(application.applied_at)} · 版本 ${application.version ?? '-'}`}
        breadcrumb={[{ label: '售后工单', to: ROUTES.adminAfterSales }, { label: application.application_no }]}
        tags={<StatusTag kind="afterSales" value={status} />}
        extra={
          <Space wrap>
            {canReceive ? (
              <Button onClick={() => receiveMutation.mutate({ id: application.id, received: true })} loading={receiveMutation.isPending}>确认收到退货</Button>
            ) : null}
            {canReviewNow ? (
              <Button onClick={() => setReturnOpen(true)}>登记退货物流</Button>
            ) : null}
            {canComplete ? (
              <Button type="primary" onClick={() => setCompleteOpen(true)}>完成售后</Button>
            ) : null}
            <Button onClick={() => navigate(ROUTES.adminAfterSales)}>返回列表</Button>
          </Space>
        }
      />
      {!canReview ? <Typography.Text type="warning">当前账号无售后审核权限，页面为只读。</Typography.Text> : null}
      <Row gutter={[16, 16]} style={{ marginTop: 12 }}>
        <Col xs={24} lg={15}>
          <Card title="申请信息" style={{ marginBottom: 16 }}>
            <Descriptions column={2} size="small">
              <Descriptions.Item label="订单">{application.order_no ?? application.order_id}</Descriptions.Item>
              <Descriptions.Item label="客户 ID">{application.customer_id}</Descriptions.Item>
              <Descriptions.Item label="类型"><StatusTag kind="afterSalesType" value={application.type} /></Descriptions.Item>
              <Descriptions.Item label="原因码">{application.reason_code}</Descriptions.Item>
              <Descriptions.Item label="数量">{application.quantity ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="退款金额"><MoneyText value={application.refund_amount} /></Descriptions.Item>
              <Descriptions.Item label="问题描述" span={2}>{application.description ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="审核意见" span={2}>{application.review_remark ?? '-'}</Descriptions.Item>
            </Descriptions>
            <Divider style={{ margin: '12px 0' }} />
            <EvidenceGallery attachmentIds={application.evidence_attachment_ids ?? []} />
          </Card>

          <Card title="处理记录">
            {(application.messages ?? []).length === 0 ? (
              <Typography.Text type="secondary">暂无处理记录</Typography.Text>
            ) : (
              <Timeline
                items={(application.messages ?? []).map((item) => ({
                  children: (
                    <div>
                      <Typography.Text>{item.content}</Typography.Text>
                      <div><Typography.Text type="secondary" style={{ fontSize: 12 }}>{item.sender_type} · {formatDateTime(item.created_at)}</Typography.Text></div>
                    </div>
                  ),
                }))}
              />
            )}
            <Divider style={{ margin: '12px 0' }} />
            <Space.Compact style={{ width: '100%' }}>
              <Input.TextArea rows={2} maxLength={500} value={messageText} onChange={(event) => setMessageText(event.target.value)} placeholder={readOnly ? '已结案，仅可追加备注' : '填写处理说明或向客户补充说明'} />
            </Space.Compact>
            <div style={{ marginTop: 8 }}>
              <Button type="primary" disabled={messageText.trim().length === 0} loading={messageMutation.isPending} onClick={() => messageMutation.mutate({ id: application.id, content: messageText.trim() })}>发送</Button>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={9}>
          <Card title="处理面板" extra={readOnly ? <StatusTag kind="afterSales" value={status} /> : null}>
            <Form form={reviewForm} layout="vertical" initialValues={{ decision: 'APPROVE', need_return: false, approved_amount: application.refund_amount }}>
              <Form.Item label="处理动作" name="decision" rules={[{ required: true }]}>
                <Radio.Group>
                  <Radio.Button value="APPROVE" disabled={!canReviewNow}>审核通过</Radio.Button>
                  <Radio.Button value="REJECT" disabled={!canReviewNow}>驳回</Radio.Button>
                </Radio.Group>
              </Form.Item>
              {decision === 'APPROVE' ? (
                <>
                  <Form.Item label="批准退款金额" name="approved_amount">
                    <Input placeholder="0.00" />
                  </Form.Item>
                  <Form.Item label="是否需要客户寄回" name="need_return" valuePropName="checked">
                    <Switch />
                  </Form.Item>
                  {needReturn ? (
                    <Form.Item label="退货地址" name="return_address" rules={[{ required: true, message: '请填写退货地址' }]}>
                      <Input.TextArea rows={2} maxLength={200} />
                    </Form.Item>
                  ) : null}
                </>
              ) : (
                <Form.Item label="驳回原因" name="reason" rules={[{ required: true, message: '驳回必须填写原因' }, { max: 200, message: '不超过 200 字' }]}>
                  <Input.TextArea rows={3} maxLength={200} showCount />
                </Form.Item>
              )}
              <PermissionGate permission={P.aftersalesReview} mode="disable" fallbackReason="需要售后审核权限">
                <Button
                  type="primary"
                  block
                  disabled={!canReviewNow}
                  loading={reviewMutation.isPending}
                  onClick={() => {
                    void reviewForm.validateFields().then((values) => {
                      if (values.decision === 'APPROVE' && values.approved_amount && !isValidMoney(values.approved_amount)) { message.error('退款金额格式不正确'); return; }
                      reviewMutation.mutate({ id: application.id, body: values });
                    }).catch(() => message.error('请完善处理面板必填项'));
                  }}
                >
                  提交处理
                </Button>
              </PermissionGate>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                状态：APPLYING 仅可受理/驳回；PROCESSING 可审核通过/补件/完成；结案后只读。
              </Typography.Text>
            </Form>
          </Card>
        </Col>
      </Row>

      <Modal open={completeOpen} title="完成售后" okText="确认完成" cancelText="取消" confirmLoading={completeMutation.isPending} onCancel={() => setCompleteOpen(false)} onOk={() => { void completeForm.validateFields().then((values) => completeMutation.mutate({ id: application.id, conclusion: values.conclusion, refund_amount: values.refund_amount })); }} destroyOnClose>
        <Form form={completeForm} layout="vertical" initialValues={{ refund_amount: application.refund_amount }}>
          <Form.Item label="结案结论" name="conclusion" rules={[{ required: true, message: '请填写结案结论' }, { max: 500, message: '不超过 500 字' }]}>
            <Input.TextArea rows={3} maxLength={500} showCount />
          </Form.Item>
          <Form.Item label="实际退款金额" name="refund_amount">
            <Input placeholder="0.00" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal open={returnOpen} title="登记退货物流" okText="提交" cancelText="取消" confirmLoading={returnMutation.isPending} onCancel={() => setReturnOpen(false)} onOk={() => { void returnForm.validateFields().then((values) => returnMutation.mutate({ id: application.id, carrierCode: values.carrier_code, trackingNo: values.tracking_no })); }} destroyOnClose>
        <Form form={returnForm} layout="vertical">
          <Form.Item label="承运商" name="carrier_code" rules={[{ required: true, message: '请选择承运商' }]}>
            <Select options={(carriersQuery.data?.items ?? []).map((carrier) => ({ value: carrier.code, label: carrier.name }))} />
          </Form.Item>
          <Form.Item label="退货运单号" name="tracking_no" rules={[{ required: true, message: '请输入运单号' }, { pattern: /^[A-Za-z0-9-]{1,64}$/, message: '1–64 位字母数字' }]}>
            <Input maxLength={64} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

import App from 'antd/es/app';
import Alert from 'antd/es/alert';
import DatePicker from 'antd/es/date-picker';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import { useMutation } from '@tanstack/react-query';
import type { Dayjs } from 'dayjs';
import { useState } from 'react';
import { toApiError } from '@/api/errors';
import { knowledgeApi } from '@/api/endpoints/knowledge';
import { queryClient } from '@/app/providers';
import type { PublishResult } from '@/types/knowledge';

export interface PublishModalProps {
  open: boolean;
  versionId?: number | null;
  selfReview?: boolean;
  onClose: () => void;
  onPublished?: (result: PublishResult) => void;
}

interface PublishForm {
  change_summary: string;
  effective_from?: Dayjs | null;
}

/** 发布确认弹窗：变更摘要必填；生效时间在未来则进入"待生效"。 */
export function PublishModal({ open, versionId, selfReview, onClose, onPublished }: PublishModalProps) {
  const { message } = App.useApp();
  const [form] = Form.useForm<PublishForm>();
  const [reasons, setReasons] = useState<string[]>([]);

  const mutation = useMutation({
    mutationFn: (values: PublishForm) => knowledgeApi.publish(versionId as number, {
      change_summary: values.change_summary,
      effective_from: values.effective_from ? values.effective_from.toISOString() : undefined,
    }),
    onSuccess: async (result) => {
      setReasons([]);
      message.success(result.status === 'SCHEDULED' ? '已排定生效时间' : '已发布');
      form.resetFields();
      await queryClient.invalidateQueries({ queryKey: ['knowledge'] });
      onPublished?.(result);
      onClose();
    },
    onError: (error) => {
      const apiError = toApiError(error);
      const details = apiError.details as { reasons?: string[] } | undefined;
      setReasons(details?.reasons ?? []);
      message.error(apiError.message);
    },
  });

  return (
    <Modal
      open={open}
      title="发布版本"
      okText="确认发布"
      cancelText="取消"
      confirmLoading={mutation.isPending}
      onCancel={() => { setReasons([]); onClose(); }}
      onOk={() => form.submit()}
      destroyOnClose
    >
      {selfReview ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="这是自审版本"
          description="提交人与审核人为同一人，发布记录与审计中会标注 self_review。"
        />
      ) : null}

      {reasons.length > 0 ? (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          message="发布被门禁拒绝"
          description={<ul style={{ margin: 0, paddingLeft: 18 }}>{reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>}
        />
      ) : null}

      <Form form={form} layout="vertical" onFinish={(values) => mutation.mutate(values)}>
        <Form.Item
          name="change_summary"
          label="变更摘要"
          rules={[{ required: true, message: '发布必须填写变更摘要' }]}
        >
          <Input.TextArea rows={3} maxLength={2000} showCount placeholder="这次改了什么、为什么改" />
        </Form.Item>
        <Form.Item
          name="effective_from"
          label="生效时间（留空立即生效）"
          extra="晚于当前时间会进入「待生效」，由后台 worker 到点转生效"
        >
          <DatePicker showTime style={{ width: '100%' }} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

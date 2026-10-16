import Input from 'antd/es/input';
import Modal from 'antd/es/modal';
import Typography from 'antd/es/typography';
import { useEffect, useState, type ReactNode } from 'react';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  impact?: ReactNode;
  danger?: boolean;
  confirmText?: string;
  cancelText?: string;
  requireReason?: boolean;
  reasonLabel?: string;
  loading?: boolean;
  onConfirm: (reason?: string) => void;
  onCancel: () => void;
}

/** 危险操作二次确认：必须展示影响；requireReason 时需填写原因。 */
export function ConfirmDialog({
  open,
  title,
  impact,
  danger,
  confirmText = '确认',
  cancelText = '取消',
  requireReason,
  reasonLabel = '操作原因',
  loading,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [reason, setReason] = useState('');

  useEffect(() => {
    if (open) setReason('');
  }, [open]);

  return (
    <Modal
      open={open}
      title={title}
      okText={confirmText}
      cancelText={cancelText}
      okButtonProps={{ danger, loading, disabled: requireReason && reason.trim().length === 0 }}
      cancelButtonProps={{ disabled: loading }}
      onOk={() => onConfirm(requireReason ? reason.trim() : undefined)}
      onCancel={onCancel}
      maskClosable={false}
      destroyOnClose
    >
      {impact ? <div style={{ marginBottom: 12 }}>{impact}</div> : null}
      {requireReason ? (
        <div>
          <Typography.Text type="secondary">{reasonLabel}</Typography.Text>
          <Input.TextArea
            rows={3}
            value={reason}
            maxLength={200}
            showCount
            placeholder={`请输入${reasonLabel}（必填，≤200 字）`}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
      ) : null}
    </Modal>
  );
}

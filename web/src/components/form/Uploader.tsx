import App from 'antd/es/app';
import Button from 'antd/es/button';
import Upload from 'antd/es/upload';
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import UploadOutlined from '@ant-design/icons/UploadOutlined';
import type { UploadFile } from 'antd';
import { attachmentsApi } from '@/api/endpoints/attachments';
import { errorMessage } from '@/api/errors';
import type { Attachment } from '@/types/domain';

export interface UploaderProps {
  value?: Attachment[];
  onChange?: (value: Attachment[]) => void;
  maxCount?: number;
  maxSizeMB?: number;
  accept?: string;
  disabled?: boolean;
  ownerType?: string;
  ownerId?: string;
  listType?: 'text' | 'picture';
  showUploadList?: boolean;
}

const DEFAULT_ACCEPT = 'image/jpeg,image/png,image/webp,application/pdf';

/** 上传组件：直传对象存储，上传前做类型/大小校验；失败给出可重试提示。 */
export function Uploader({
  value = [],
  onChange,
  maxCount = 9,
  maxSizeMB = 10,
  accept = DEFAULT_ACCEPT,
  disabled,
  ownerType,
  ownerId,
  listType = 'picture',
  showUploadList = true,
}: UploaderProps) {
  const { message } = App.useApp();

  const fileList: UploadFile[] = value.map((item, index) => ({
    uid: String(item.id ?? index),
    name: item.file_name,
    status: 'done',
    url: item.url,
  }));

  return (
    <Upload
      accept={accept}
      multiple
      listType={listType}
      fileList={fileList}
      disabled={disabled || value.length >= maxCount}
      showUploadList={showUploadList ? { showRemoveIcon: !disabled } : false}
      onRemove={(file) => {
        const next = value.filter((item) => String(item.id) !== file.uid);
        onChange?.(next);
        return true;
      }}
      beforeUpload={(file) => {
        const withinType = accept.split(',').some((type) => file.type === type.trim());
        if (!withinType) {
          message.error('文件类型不支持，请上传 JPG/PNG/WebP/PDF');
          return Upload.LIST_IGNORE;
        }
        if (file.size > maxSizeMB * 1024 * 1024) {
          message.error(`单个文件不超过 ${maxSizeMB}MB`);
          return Upload.LIST_IGNORE;
        }
        if (value.length >= maxCount) {
          message.error(`最多上传 ${maxCount} 个文件`);
          return Upload.LIST_IGNORE;
        }
        return true;
      }}
      customRequest={async (options) => {
        const file = options.file as File;
        try {
          const attachment = await attachmentsApi.upload(file, { ownerType, ownerId });
          const next = [...value, attachment];
          onChange?.(next);
          options.onSuccess?.(attachment);
          message.success('上传成功');
        } catch (error) {
          options.onError?.(error as Error);
          message.error(errorMessage(error));
        }
      }}
    >
      {value.length < maxCount ? (
        <Button icon={listType === 'picture' ? <PlusOutlined /> : <UploadOutlined />} disabled={disabled}>
          上传
        </Button>
      ) : null}
    </Upload>
  );
}

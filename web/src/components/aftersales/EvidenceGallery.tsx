import Image from 'antd/es/image';
import Space from 'antd/es/space';
import Typography from 'antd/es/typography';

export interface EvidenceGalleryProps {
  attachmentIds: number[];
  urls?: string[];
}

/** 售后凭证缩略图；无凭证时给出明确空态。 */
export function EvidenceGallery({ attachmentIds, urls = [] }: EvidenceGalleryProps) {
  const list = urls.length > 0 ? urls : attachmentIds.map((id) => `/api/v1/attachments/${id}`);
  if (list.length === 0) {
    return <Typography.Text type="secondary">客户未上传凭证</Typography.Text>;
  }
  return (
    <Image.PreviewGroup>
      <Space wrap>
        {list.map((url) => (
          <Image key={url} src={url} width={88} height={88} style={{ objectFit: 'cover', borderRadius: 6 }} fallback="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI4OCIgaGVpZ2h0PSI4OCI+PHJlY3Qgd2lkdGg9Ijg4IiBoZWlnaHQ9Ijg4IiBmaWxsPSIjRUVGM0ZGIi8+PC9zdmc+" />
        ))}
      </Space>
    </Image.PreviewGroup>
  );
}

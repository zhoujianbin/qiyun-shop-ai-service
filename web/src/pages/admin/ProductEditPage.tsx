import App from 'antd/es/app';
import Alert from 'antd/es/alert';
import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Col from 'antd/es/col';
import Form from 'antd/es/form';
import Input from 'antd/es/input';
import InputNumber from 'antd/es/input-number';
import Row from 'antd/es/row';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Switch from 'antd/es/switch';
import Tabs from 'antd/es/tabs';
import Typography from 'antd/es/typography';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { productsApi } from '@/api/endpoints/products';
import { catalogApi } from '@/api/endpoints/catalog';
import { queryKeys } from '@/api/queryKeys';
import { queryClient } from '@/app/providers';
import { PageHeader } from '@/components/common/PageHeader';
import { ErrorState } from '@/components/common/ErrorState';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';
import { PermissionGate } from '@/components/common/PermissionGate';
import { Uploader } from '@/components/form/Uploader';
import { usePermission } from '@/hooks/usePermission';
import { useIdempotentMutation } from '@/hooks/useIdempotentMutation';
import { errorMessage } from '@/api/errors';
import { CHANNEL_TYPE_OPTIONS } from '@/constants/channel';
import { PRODUCT_LINES, PRODUCT_TYPE_OPTIONS } from '@/constants/productStatus';
import { P } from '@/types/permissions';
import { ROUTES } from '@/constants/routes';
import type { Attachment, ChannelType, ProductCreateRequest, ProductMedia, ProductType } from '@/types/domain';

interface SpecRow { key: string; value: string }

interface ProductFormValues {
  spu_code: string;
  name: string;
  subtitle?: string;
  product_type: ProductType;
  product_line?: string;
  model_code?: string;
  brand_id?: number;
  category_id: number;
  description_md?: string;
  highlights?: string[];
  warranty_summary?: string;
  install_required?: boolean;
  install_notes?: string;
  service_scope?: string;
  channel_scope?: ChannelType[];
  spec_list?: SpecRow[];
}

function mediaToAttachment(media: ProductMedia[]): Attachment[] {
  return media.map((item, index) => ({
    id: item.attachment_id ?? item.id ?? index,
    file_name: item.alt_text ?? item.url.split('/').pop() ?? 'image',
    content_type: 'image/*',
    size_bytes: 0,
    url: item.url,
    status: 'READY',
    is_public: true,
  }));
}

function attachmentToMedia(attachments: Attachment[]): ProductMedia[] {
  return attachments.map((item, index) => ({
    media_type: 'IMAGE',
    attachment_id: item.id,
    url: item.url,
    alt_text: item.file_name,
    is_main: index === 0,
    sort_order: index,
  }));
}

/** B 端商品新建/编辑：分步表单、规格属性、图文详情、渠道与保修；乐观锁 version。 */
export default function ProductEditPage() {
  const { productId } = useParams();
  const isNew = !productId || productId === 'new';
  const id = isNew ? 0 : Number(productId);
  const navigate = useNavigate();
  const { message } = App.useApp();
  const canWrite = usePermission(P.productWrite);
  const [form] = Form.useForm<ProductFormValues>();
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [conflict, setConflict] = useState(false);

  const productQuery = useQuery({
    queryKey: queryKeys.products.detail(id),
    queryFn: ({ signal }) => productsApi.detail(id),
    enabled: !isNew,
  });

  const brandQuery = useQuery({
    queryKey: queryKeys.catalog.brands({ page: 1, page_size: 100 }),
    queryFn: ({ signal }) => catalogApi.brands({ page: 1, page_size: 100, signal }),
    staleTime: 5 * 60 * 1000,
  });
  const categoryQuery = useQuery({
    queryKey: queryKeys.catalog.categories(),
    queryFn: ({ signal }) => catalogApi.categories({ signal }),
    staleTime: 5 * 60 * 1000,
  });

  const product = productQuery.data;

  useEffect(() => {
    if (!product) return;
    form.setFieldsValue({
      spu_code: product.spu_code,
      name: product.name,
      subtitle: product.subtitle ?? undefined,
      product_type: product.product_type,
      product_line: product.product_line ?? undefined,
      model_code: product.model_code ?? undefined,
      brand_id: product.brand_id ?? undefined,
      category_id: product.category_id,
      description_md: product.description_md ?? undefined,
      highlights: product.highlights ?? [],
      warranty_summary: product.warranty_summary ?? undefined,
      install_required: product.install_required ?? false,
      install_notes: product.install_notes ?? undefined,
      service_scope: product.service_scope ?? undefined,
      channel_scope: product.channel_scope ?? [],
      spec_list: Object.entries(product.spec_summary ?? {}).map(([key, value]) => ({ key, value: String(value) })),
    });
    setAttachments(mediaToAttachment(product.media ?? []));
  }, [product, form]);

  const buildPayload = (values: ProductFormValues): ProductCreateRequest => {
    const spec: Record<string, string> = {};
    (values.spec_list ?? []).forEach((row) => {
      if (row?.key) spec[row.key] = row.value ?? '';
    });
    return {
      spu_code: values.spu_code,
      name: values.name,
      subtitle: values.subtitle ?? null,
      product_type: values.product_type,
      product_line: values.product_line ?? null,
      model_code: values.model_code ?? null,
      brand_id: values.brand_id ?? null,
      category_id: values.category_id,
      description_md: values.description_md ?? null,
      highlights: values.highlights ?? [],
      warranty_summary: values.warranty_summary ?? null,
      install_required: values.install_required ?? false,
      install_notes: values.install_notes ?? null,
      service_scope: values.service_scope ?? null,
      channel_scope: values.channel_scope ?? [],
      spec_summary: spec,
    };
  };

  const saveMutation = useIdempotentMutation(
    async (vars: { values: ProductFormValues; publish?: boolean }) => {
      const payload = buildPayload(vars.values);
      const saved = isNew
        ? await productsApi.create(payload)
        : await productsApi.update(id, { ...payload, version: product?.version });
      if (vars.publish && saved.id) await productsApi.publish(saved.id);
      return saved;
    },
    {
      onSuccess: async (saved) => {
        message.success(isNew ? '商品已创建' : '商品已保存');
        saveMutation.resetKey();
        setConflict(false);
        await queryClient.invalidateQueries({ queryKey: ['products'] });
        if (isNew) navigate(ROUTES.adminProductEdit(saved.id), { replace: true });
      },
      onError: (error) => {
        const apiError = error as { kind?: string; message?: string };
        if (apiError.kind === 'conflict') {
          setConflict(true);
          message.warning('该商品已被他人修改，请刷新后重试');
        } else {
          message.error(errorMessage(error));
        }
      },
    },
  );

  const submit = async (publish: boolean) => {
    try {
      const values = await form.validateFields();
      saveMutation.mutate({ values, publish });
    } catch {
      message.error('请检查表单必填项');
    }
  };

  const categoryOptions = useMemo(
    () => (categoryQuery.data ?? []).map((category) => ({ value: category.id, label: category.name })),
    [categoryQuery.data],
  );

  if (!isNew && productQuery.isLoading) {
    return <div className="qy-page"><LoadingSkeleton rows={10} /></div>;
  }
  if (!isNew && (productQuery.isError || !product)) {
    return (
      <div className="qy-page">
        <ErrorState title="商品加载失败" error={productQuery.error} onRetry={() => void productQuery.refetch()} />
      </div>
    );
  }

  return (
    <div className="qy-page">
      <PageHeader
        title={isNew ? '新建商品' : `编辑商品：${product?.name ?? ''}`}
        subtitle={isNew ? '创建后处于草稿状态，提交上架需完整校验' : `SPU ${product?.spu_code ?? ''} · 版本 ${product?.version ?? '-'}`}
        breadcrumb={[{ label: '商品管理', to: ROUTES.adminProducts }, { label: isNew ? '新建' : '编辑' }]}
        extra={
          <Space>
            <Button onClick={() => navigate(ROUTES.adminProducts)}>返回列表</Button>
            <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
              <Button onClick={() => void submit(false)} loading={saveMutation.isPending}>保存草稿</Button>
            </PermissionGate>
            <PermissionGate permission={P.productWrite} mode="disable" fallbackReason="需要商品写权限">
              <Button type="primary" onClick={() => void submit(true)} loading={saveMutation.isPending}>提交上架</Button>
            </PermissionGate>
          </Space>
        }
      />
      {conflict ? <Alert type="warning" showIcon style={{ marginBottom: 12 }} message="该商品已被他人修改" description="请刷新页面获取最新版本后重新编辑。" action={<Button size="small" onClick={() => void productQuery.refetch()}>刷新</Button>} /> : null}
      {!canWrite ? <Alert type="info" showIcon style={{ marginBottom: 12 }} message="当前账号无商品写权限，页面为只读。" /> : null}

      <Form form={form} layout="vertical" disabled={!canWrite} initialValues={{ install_required: false, channel_scope: ['OFFICIAL_MALL'], highlights: [] }}>
        <Tabs
          items={[
            {
              key: 'basic',
              label: '基本信息',
              children: (
                <Card>
                  <Row gutter={16}>
                    <Col xs={24} md={12}>
                      <Form.Item label="商品名称" name="name" rules={[{ required: true, message: '请输入商品名称' }, { min: 2, max: 128, message: '2–128 字符' }]}>
                        <Input placeholder="如：栖云智能门锁 L3 Pro" />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item
                        label="商品编码（SPU）"
                        name="spu_code"
                        rules={[{ required: true, message: '请输入商品编码' }, { pattern: /^[A-Za-z0-9_-]{2,64}$/, message: '2–64 位字母数字与 -_' }]}
                      >
                        <Input placeholder="如：QL-L3P" disabled={!isNew} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={12}>
                      <Form.Item label="副标题" name="subtitle">
                        <Input placeholder="选填" maxLength={128} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={6}>
                      <Form.Item label="产品类型" name="product_type" rules={[{ required: true, message: '请选择产品类型' }]}>
                        <Select options={PRODUCT_TYPE_OPTIONS} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={6}>
                      <Form.Item label="产品线" name="product_line">
                        <Select allowClear options={PRODUCT_LINES.map((line) => ({ value: line, label: line }))} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={8}>
                      <Form.Item label="型号编码" name="model_code">
                        <Input placeholder="如：QL-L3P-BLACK" maxLength={64} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={8}>
                      <Form.Item label="品牌" name="brand_id">
                        <Select allowClear loading={brandQuery.isLoading} options={(brandQuery.data?.items ?? []).map((brand) => ({ value: brand.id, label: brand.name }))} />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={8}>
                      <Form.Item label="类目" name="category_id" rules={[{ required: true, message: '请选择类目' }]}>
                        <Select showSearch optionFilterProp="label" loading={categoryQuery.isLoading} options={categoryOptions} />
                      </Form.Item>
                    </Col>
                    <Col span={24}>
                      <Form.Item label="卖点标签" name="highlights">
                        <Select mode="tags" placeholder="输入后回车添加，如：3D 人脸识别" />
                      </Form.Item>
                    </Col>
                  </Row>
                </Card>
              ),
            },
            {
              key: 'spec',
              label: '规格属性',
              children: (
                <Card>
                  <Form.List name="spec_list">
                    {(fields, { add, remove }) => (
                      <Space direction="vertical" style={{ width: '100%' }}>
                        {fields.map((field) => (
                          <Row key={field.key} gutter={8} align="middle">
                            <Col span={9}>
                              <Form.Item name={[field.name, 'key']} style={{ marginBottom: 8 }}>
                                <Input placeholder="属性名，如 供电方式" />
                              </Form.Item>
                            </Col>
                            <Col span={12}>
                              <Form.Item name={[field.name, 'value']} style={{ marginBottom: 8 }}>
                                <Input placeholder="属性值，如 锂电池" />
                              </Form.Item>
                            </Col>
                            <Col span={3}>
                              <Button type="link" danger onClick={() => remove(field.name)}>删除</Button>
                            </Col>
                          </Row>
                        ))}
                        <Button onClick={() => add({ key: '', value: '' })}>新增规格属性</Button>
                      </Space>
                    )}
                  </Form.List>
                </Card>
              ),
            },
            {
              key: 'media',
              label: '图文详情',
              children: (
                <Card>
                  <Form.Item label="商品图片" extra="主图 1–8 张，JPG/PNG/WebP，单张 ≤5MB">
                    <Uploader value={attachments} onChange={setAttachments} maxCount={8} maxSizeMB={5} ownerType="Product" ownerId={isNew ? undefined : String(id)} />
                  </Form.Item>
                  <Form.Item label="商品详情（Markdown）" name="description_md">
                    <Input.TextArea rows={10} placeholder="支持 Markdown；安装条件、使用说明等" />
                  </Form.Item>
                </Card>
              ),
            },
            {
              key: 'service',
              label: '服务与保修',
              children: (
                <Card>
                  <Row gutter={16}>
                    <Col xs={24} md={8}>
                      <Form.Item label="是否需要上门安装" name="install_required" valuePropName="checked">
                        <Switch />
                      </Form.Item>
                    </Col>
                    <Col xs={24} md={16}>
                      <Form.Item label="服务范围" name="service_scope">
                        <Input placeholder="如：全国主要城市（偏远地区除外）" />
                      </Form.Item>
                    </Col>
                    <Col span={24}>
                      <Form.Item label="安装条件" name="install_notes" rules={[{ max: 1000, message: '不超过 1000 字' }]}>
                        <Input.TextArea rows={3} placeholder="如：门厚 40–120mm，需预留电源" />
                      </Form.Item>
                    </Col>
                    <Col span={24}>
                      <Form.Item label="保修摘要" name="warranty_summary" rules={[{ required: true, message: '请输入保修摘要' }, { max: 500, message: '不超过 500 字' }]}>
                        <Input.TextArea rows={3} placeholder="如：整机保修 2 年，电池 6 个月" />
                      </Form.Item>
                    </Col>
                  </Row>
                </Card>
              ),
            },
            {
              key: 'channel',
              label: '渠道与价格',
              children: (
                <Card>
                  <Form.Item label="可售渠道" name="channel_scope" rules={[{ required: true, message: '请至少选择一个渠道' }]}>
                    <Select mode="multiple" options={CHANNEL_TYPE_OPTIONS} placeholder="选择该商品可售的渠道" />
                  </Form.Item>
                  <Typography.Text type="secondary">
                    价格在 SKU 维度维护：创建商品后前往 <a onClick={() => navigate(ROUTES.adminSkus)}>SKU 管理</a> 设置销售价、成本价与条码。
                  </Typography.Text>
                </Card>
              ),
            },
          ]}
        />
      </Form>
    </div>
  );
}

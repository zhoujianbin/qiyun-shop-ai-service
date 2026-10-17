import Button from 'antd/es/button';
import Card from 'antd/es/card';
import Descriptions from 'antd/es/descriptions';
import Drawer from 'antd/es/drawer';
import Input from 'antd/es/input';
import Select from 'antd/es/select';
import Space from 'antd/es/space';
import Table from 'antd/es/table';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { ColumnsType } from 'antd/es/table';
import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { errorMessage } from '@/api/errors';
import { knowledgeApi } from '@/api/endpoints/knowledge';
import { queryClient } from '@/app/providers';
import { PageHeader } from '@/components/common/PageHeader';
import type { OntologyEntity, OntologyGraph } from '@/types/knowledge';

const KIND_LABEL: Record<string, string> = {
  product: '产品', accessory: '配件', part: '部件', fault: '故障', action: '动作', policy: '政策',
};
const STATUS_COLOR: Record<string, string> = {
  APPROVED: 'green', DRAFT: 'orange', DEPRECATED: 'red',
};

/** 四期：本体维护（实体列表 / 审核 / 深度 2 图谱）。 */
export default function OntologyPage() {
  const [kind, setKind] = useState<string | undefined>();
  const [status, setStatus] = useState<string | undefined>();
  const [keyword, setKeyword] = useState('');
  const [selected, setSelected] = useState<number[]>([]);
  const [graph, setGraph] = useState<OntologyGraph | null>(null);
  const [graphFor, setGraphFor] = useState<OntologyEntity | null>(null);
  const [error, setError] = useState('');

  const entities = useQuery({
    queryKey: ['ontology', 'entities', kind, status, keyword],
    queryFn: () => knowledgeApi.ontologyEntities({
      kind, status, keyword: keyword || undefined, page: 1, page_size: 50,
    }),
  });

  const review = useMutation({
    mutationFn: () => knowledgeApi.ontologyReview(selected, 'approve'),
    onSuccess: async () => {
      setError('');
      setSelected([]);
      await queryClient.invalidateQueries({ queryKey: ['ontology'] });
    },
    onError: (err) => setError(errorMessage(err)),
  });

  const loadGraph = useMutation({
    mutationFn: (entity: OntologyEntity) => knowledgeApi.ontologyGraph(entity.id, 2),
    onSuccess: (data) => setGraph(data),
    onError: (err) => setError(errorMessage(err)),
  });

  const columns = useMemo<ColumnsType<OntologyEntity>>(() => [
    { title: '编码', dataIndex: 'code', width: 200 },
    { title: '名称', dataIndex: 'name' },
    {
      title: '类型', dataIndex: 'kind', width: 90,
      render: (value: string) => KIND_LABEL[value] ?? value,
    },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (value: string) => <Tag color={STATUS_COLOR[value]}>{value}</Tag>,
    },
    { title: '来源', dataIndex: 'source', width: 90 },
    {
      title: '操作', width: 120,
      render: (_value, row) => (
        <Button
          size="small"
          onClick={() => {
            setGraphFor(row);
            setGraph(null);
            loadGraph.mutate(row);
          }}
        >
          看图谱
        </Button>
      ),
    },
  ], [loadGraph]);

  const rows = entities.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="本体维护"
        subtitle="实体 / 关系 / 别名；只有 APPROVED 参与检索与回答"
        extra={(
          <Space>
            <Button
              disabled={selected.length === 0}
              loading={review.isPending}
              type="primary"
              onClick={() => review.mutate()}
            >
              审核通过（{selected.length}）
            </Button>
            <Button onClick={() => entities.refetch()}>刷新</Button>
          </Space>
        )}
      />
      {error ? <Typography.Text type="danger">{error}</Typography.Text> : null}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space wrap>
          <Select
            allowClear
            placeholder="类型"
            value={kind}
            style={{ width: 120 }}
            onChange={setKind}
            options={Object.entries(KIND_LABEL).map(([value, label]) => ({ value, label }))}
          />
          <Select
            allowClear
            placeholder="状态"
            value={status}
            style={{ width: 130 }}
            onChange={setStatus}
            options={['DRAFT', 'APPROVED', 'DEPRECATED'].map((value) => ({ value, label: value }))}
          />
          <Input.Search
            allowClear
            placeholder="按编码或名称搜索"
            style={{ width: 240 }}
            onSearch={setKeyword}
          />
          <Typography.Text type="secondary">
            共 {entities.data?.meta?.total ?? rows.length} 条
          </Typography.Text>
        </Space>
      </Card>
      <Table
        rowKey="id"
        size="small"
        loading={entities.isLoading}
        columns={columns}
        dataSource={rows}
        rowSelection={{
          selectedRowKeys: selected,
          onChange: (keys) => setSelected(keys as number[]),
        }}
        pagination={false}
      />
      <Drawer
        open={graphFor !== null}
        width={520}
        title={graphFor ? `${graphFor.code} 的邻域（深度 2）` : ''}
        onClose={() => {
          setGraphFor(null);
          setGraph(null);
        }}
      >
        {graph ? (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="根实体">{graph.root.code} · {graph.root.name}</Descriptions.Item>
              <Descriptions.Item label="邻接数">{graph.edge_count}</Descriptions.Item>
            </Descriptions>
            <Table
              rowKey={(row) => `${row.entity.id}-${row.depth}-${row.via}`}
              size="small"
              pagination={false}
              dataSource={graph.nodes}
              columns={[
                { title: '深度', dataIndex: 'depth', width: 60 },
                { title: '谓词', dataIndex: 'via', width: 120 },
                { title: '实体', render: (_v, row) => `${row.entity.code} · ${row.entity.name}` },
                {
                  title: '类型', width: 70,
                  render: (_v, row) => KIND_LABEL[row.entity.kind] ?? row.entity.kind,
                },
              ]}
            />
          </Space>
        ) : (
          <Typography.Text type="secondary">加载中…</Typography.Text>
        )}
      </Drawer>
    </>
  );
}

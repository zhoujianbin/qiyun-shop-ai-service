import { useMemo, useState } from 'react';
import Space from 'antd/es/space';
import Tag from 'antd/es/tag';
import Typography from 'antd/es/typography';
import type { OntologyEntity, OntologyRelation } from '@/types/knowledge';

const KIND_COLOR: Record<string, string> = {
  product: '#1677ff',
  accessory: '#13c2c2',
  part: '#52c41a',
  fault: '#fa8c16',
  policy: '#722ed1',
  action: '#eb2f96',
};
const KIND_LABEL: Record<string, string> = {
  product: '产品', accessory: '配件', part: '部件', fault: '故障', policy: '政策', action: '动作',
};
const LABEL_KINDS = new Set(['product', 'part', 'accessory']);

interface Positioned {
  entity: OntologyEntity;
  x: number;
  y: number;
}

interface Props {
  entities: OntologyEntity[];
  relations: OntologyRelation[];
  width?: number;
  height?: number;
  onSelect?: (entity: OntologyEntity) => void;
}

/** 确定性力导向：同输入同布局，不做动画。节点 <200 时足够快。 */
function layout(entities: OntologyEntity[], relations: OntologyRelation[], width: number, height: number) {
  const n = entities.length;
  const nodes = entities.map((entity, index) => {
    const angle = (index / Math.max(n, 1)) * Math.PI * 2;
    const radius = 0.35 * Math.min(width, height);
    return { entity, x: width / 2 + Math.cos(angle) * radius, y: height / 2 + Math.sin(angle) * radius };
  });
  const indexOf = new Map(nodes.map((node, index) => [node.entity.id, index]));
  const edges = relations
    .map((relation) => {
      const source = indexOf.get(relation.src_entity_id);
      const target = indexOf.get(relation.dst_entity_id);
      return source === undefined || target === undefined
        ? null
        : { relation, source, target };
    })
    .filter((item): item is { relation: OntologyRelation; source: number; target: number } => item !== null);

  const iterations = 260;
  for (let step = 0; step < iterations; step += 1) {
    const cooling = 1 - step / iterations;
    // 斥力：节点两两推开
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const dx = nodes[i].x - nodes[j].x;
        const dy = nodes[i].y - nodes[j].y;
        const distance2 = dx * dx + dy * dy || 0.01;
        const push = 2400 / distance2;
        const distance = Math.sqrt(distance2);
        const fx = (dx / distance) * push;
        const fy = (dy / distance) * push;
        nodes[i].x += fx * cooling;
        nodes[i].y += fy * cooling;
        nodes[j].x -= fx * cooling;
        nodes[j].y -= fy * cooling;
      }
    }
    // 引力：有边的节点互相靠近
    for (const edge of edges) {
      const a = nodes[edge.source];
      const b = nodes[edge.target];
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const distance = Math.sqrt(dx * dx + dy * dy) || 0.01;
      const pull = (distance - 70) * 0.02 * cooling;
      const fx = (dx / distance) * pull;
      const fy = (dy / distance) * pull;
      a.x += fx; a.y += fy;
      b.x -= fx; b.y -= fy;
    }
    // 向心，避免整体飘走
    for (const node of nodes) {
      node.x += (width / 2 - node.x) * 0.008 * cooling;
      node.y += (height / 2 - node.y) * 0.008 * cooling;
    }
  }
  const pad = 28;
  const xs = nodes.map((node) => node.x);
  const ys = nodes.map((node) => node.y);
  const minX = Math.min(...xs); const maxX = Math.max(...xs);
  const minY = Math.min(...ys); const maxY = Math.max(...ys);
  const scaleX = (width - pad * 2) / Math.max(maxX - minX, 1);
  const scaleY = (height - pad * 2) / Math.max(maxY - minY, 1);
  nodes.forEach((node) => {
    node.x = pad + (node.x - minX) * scaleX;
    node.y = pad + (node.y - minY) * scaleY;
  });
  return { nodes, edges };
}

/** 本体图谱：点线可视化 + 悬停详情，无第三方图表依赖。 */
export default function OntologyGraph({ entities, relations, width = 980, height = 620, onSelect }: Props) {
  const { nodes, edges } = useMemo(() => layout(entities, relations, width, height), [entities, relations, width, height]);
  const [hoverNode, setHoverNode] = useState<number | null>(null);
  const [hoverEdge, setHoverEdge] = useState<number | null>(null);

  const neighbourIds = useMemo(() => {
    if (hoverNode === null) return new Set<number>();
    const set = new Set<number>([hoverNode]);
    edges.forEach((edge) => {
      if (edge.source === hoverNode) set.add(edge.target);
      if (edge.target === hoverNode) set.add(edge.source);
    });
    return set;
  }, [hoverNode, edges]);

  const activeEntity = hoverNode === null ? null : nodes[hoverNode]?.entity ?? null;
  const activeEdge = hoverEdge === null ? null : edges[hoverEdge]?.relation ?? null;

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={8}>
      <Space size={12} wrap>
        {Object.entries(KIND_LABEL).map(([kind, label]) => (
          <Space key={kind} size={4}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: KIND_COLOR[kind] }} />
            <Typography.Text style={{ fontSize: 12 }}>{label}</Typography.Text>
          </Space>
        ))}
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          悬停节点或连线查看详情，点击节点看深度 2 邻域
        </Typography.Text>
      </Space>

      <svg
        width="100%"
        viewBox={"0 0 " + width + " " + height}
        style={{ background: 'var(--color-bg-container, #fff)', border: '1px solid var(--color-border, #eee)', borderRadius: 8 }}
      >
        <g>
          {edges.map((edge, index) => {
            const a = nodes[edge.source];
            const b = nodes[edge.target];
            const active = hoverEdge === index || (hoverNode !== null && (edge.source === hoverNode || edge.target === hoverNode));
            return (
              <g key={edge.relation.id}>
                <line
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={active ? '#1677ff' : '#c9cdd4'}
                  strokeWidth={active ? 1.8 : 1}
                  strokeOpacity={active ? 0.95 : 0.55}
                />
                <line
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke="transparent"
                  strokeWidth={12}
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHoverEdge(index)}
                  onMouseLeave={() => setHoverEdge(null)}
                >
                  <title>{`${a.entity.code} --${edge.relation.predicate}--> ${b.entity.code}`}</title>
                </line>
                {active || hoverEdge === index ? (
                  <text
                    x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 3}
                    fontSize={10} fill="#1677ff" textAnchor="middle"
                  >
                    {edge.relation.predicate}
                  </text>
                ) : null}
              </g>
            );
          })}
        </g>

        <g>
          {nodes.map((node, index) => {
            const dim = hoverNode !== null && !neighbourIds.has(index);
            const showLabel = hoverNode === index || LABEL_KINDS.has(node.entity.kind);
            return (
              <g key={node.entity.id} style={{ cursor: onSelect ? 'pointer' : 'default' }}>
                <circle
                  cx={node.x} cy={node.y} r={hoverNode === index ? 8 : 6}
                  fill={KIND_COLOR[node.entity.kind] ?? '#8c8c8c'}
                  fillOpacity={dim ? 0.2 : 1}
                  stroke="#fff" strokeWidth={1}
                  onMouseEnter={() => setHoverNode(index)}
                  onMouseLeave={() => setHoverNode(null)}
                  onClick={() => onSelect?.(node.entity)}
                >
                  <title>{`${node.entity.code} · ${node.entity.name}（${node.entity.status}）`}</title>
                </circle>
                {showLabel ? (
                  <text
                    x={node.x} y={node.y - 10}
                    fontSize={9}
                    textAnchor="middle"
                    fill={dim ? '#bfbfbf' : '#595959'}
                    pointerEvents="none"
                  >
                    {node.entity.code.length > 22 ? `${node.entity.code.slice(0, 22)}…` : node.entity.code}
                  </text>
                ) : null}
              </g>
            );
          })}
        </g>
      </svg>

      <div style={{ minHeight: 44 }}>
        {activeEntity ? (
          <Space size={8} wrap>
            <Tag color={KIND_COLOR[activeEntity.kind]}>{KIND_LABEL[activeEntity.kind] ?? activeEntity.kind}</Tag>
            <Typography.Text strong>{activeEntity.code}</Typography.Text>
            <Typography.Text>{activeEntity.name}</Typography.Text>
            <Tag>{activeEntity.status}</Tag>
            <Typography.Text type="secondary">来源 {activeEntity.source ?? '-'}</Typography.Text>
            {activeEntity.summary ? <Typography.Text type="secondary">{activeEntity.summary}</Typography.Text> : null}
          </Space>
        ) : null}
        {activeEdge ? (
          <Space size={8} wrap>
            <Tag color="blue">{activeEdge.predicate}</Tag>
            <Typography.Text>
              {nodes.find((node) => node.entity.id === activeEdge.src_entity_id)?.entity.code}
              {' → '}
              {nodes.find((node) => node.entity.id === activeEdge.dst_entity_id)?.entity.code}
            </Typography.Text>
            <Typography.Text type="secondary">{activeEdge.status}</Typography.Text>
          </Space>
        ) : null}
        {!activeEntity && !activeEdge ? (
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            共 {entities.length} 个实体、{relations.length} 条关系
          </Typography.Text>
        ) : null}
      </div>
    </Space>
  );
}

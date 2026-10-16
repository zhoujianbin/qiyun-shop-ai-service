import Table from 'antd/es/table';
import type { TableProps } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ReactNode } from 'react';
import { EmptyState } from '../common/EmptyState';
import { ErrorState } from '../common/ErrorState';

export interface DataTableProps<T extends object> {
  columns: ColumnsType<T>;
  data: T[];
  rowKey?: TableProps<T>['rowKey'];
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number, pageSize: number) => void;
  emptyTitle?: string;
  emptyDescription?: ReactNode;
  emptyAction?: ReactNode;
  toolbar?: ReactNode;
  rowSelection?: TableProps<T>['rowSelection'];
  expandable?: TableProps<T>['expandable'];
  scrollX?: number;
  size?: TableProps<T>['size'];
  onRow?: TableProps<T>['onRow'];
  showPagination?: boolean;
}

/**
 * 统一表格：服务端分页、列设置位置、空/错态、loading。
 * 必须实现 loading / empty / error 三态（readonly 由页面禁用操作列实现）。
 */
export function DataTable<T extends object>({
  columns,
  data,
  rowKey = 'id',
  loading,
  error,
  onRetry,
  total,
  page = 1,
  pageSize = 20,
  onPageChange,
  emptyTitle = '暂无数据',
  emptyDescription,
  emptyAction,
  toolbar,
  rowSelection,
  expandable,
  scrollX,
  size = 'middle',
  onRow,
  showPagination = true,
}: DataTableProps<T>) {
  if (error) {
    return (
      <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #E5E7EB' }}>
        <ErrorState error={error} onRetry={onRetry} />
      </div>
    );
  }

  return (
    <div>
      {toolbar ? <div style={{ marginBottom: 12 }}>{toolbar}</div> : null}
      <Table<T>
        columns={columns}
        dataSource={data}
        rowKey={rowKey}
        loading={loading}
        rowSelection={rowSelection}
        expandable={expandable}
        size={size}
        onRow={onRow}
        scroll={scrollX ? { x: scrollX } : undefined}
        locale={{
          emptyText: <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} compact />,
        }}
        pagination={
          showPagination && total !== undefined && onPageChange
            ? {
                current: page,
                pageSize,
                total,
                showSizeChanger: true,
                showTotal: (t) => `共 ${t} 条`,
                pageSizeOptions: ['10', '20', '50', '100'],
                onChange: (nextPage, nextPageSize) => onPageChange(nextPage, nextPageSize),
              }
            : false
        }
      />
    </div>
  );
}

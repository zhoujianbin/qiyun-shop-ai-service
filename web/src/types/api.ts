/** 通用 API 传输类型。 */

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
  has_more?: boolean;
  next_cursor?: string | null;
}

/** 后端统一错误体 {code,message,details,request_id} */
export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown;
  request_id?: string;
}

/** 列表响应包装 */
export interface ListResponse<T> {
  items: T[];
  meta: PageMeta;
}

/** 标准分页查询参数 */
export interface PageParams {
  page?: number;
  page_size?: number;
}

export interface CursorParams {
  cursor?: string | null;
  limit?: number;
}

export const DEFAULT_PAGE_SIZE = 20;

export interface SelectOption<T extends string | number = string> {
  label: string;
  value: T;
}

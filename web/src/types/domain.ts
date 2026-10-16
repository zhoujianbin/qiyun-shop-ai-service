/**
 * 领域模型（字段名与 OpenAPI 3.1 契约一致，snake_case 与后端 JSON 对齐）。
 * 契约机器可读版本见 src/api/generated/schema.d.ts（npm run gen:api 生成）。
 */
import type {
  AdjustType, AfterSalesStatus, AfterSalesType, ChannelType, ChangeType, FulfillmentStatus,
  InvoiceStatus, InvoiceType, OrderAfterSalesStatus, OrderSource, OrderStatus, Party,
  PaymentMethod, PaymentStatus, PayStatus, ProductStatus, ProductType, RefundStatus,
  ShipmentStatus, SkuStatus, StaffStatus, WarehouseType,
} from './status';
import type { MoneyString } from './money';
import type { RoleCode } from './permissions';

// ---------- 认证 ----------
export interface CurrentUser {
  id: number;
  tenant_id?: number;
  party: Party;
  username?: string;
  display_name: string;
  roles?: RoleCode[];
  permissions?: string[];
  channel_scope?: ChannelType[];
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: 'Bearer';
  expires_in: number;
  user?: CurrentUser;
}

export interface StaffLoginRequest { username: string; password: string; otp_code?: string | null }
export interface CustomerLoginRequest { mobile: string; password?: string | null; sms_code?: string | null }
export interface CustomerRegisterRequest {
  mobile: string; password: string; sms_code: string; nickname?: string | null; channel_account_id?: number | null;
}
export interface PasswordChangeRequest { old_password: string; new_password: string }

// ---------- 组织与权限 ----------
export interface Role {
  id: number; code: RoleCode; name: string; description?: string | null;
  permissions: string[]; is_system?: boolean; created_at?: string;
}
export interface Permission { id: number; code: string; name: string; module: string }
export interface StaffUser {
  id: number; tenant_id?: number; username: string; display_name: string;
  email?: string | null; phone_masked?: string | null; status: StaffStatus;
  is_super_admin?: boolean; roles?: RoleCode[]; channel_scope?: ChannelType[];
  last_login_at?: string | null; created_at?: string; updated_at?: string; version?: number;
}
export interface StaffUserCreateRequest {
  username: string; display_name: string; email?: string | null; phone?: string | null;
  password: string; role_codes: RoleCode[]; channel_account_ids?: number[];
}
export interface StaffUserUpdateRequest {
  display_name?: string; email?: string | null; phone?: string | null; status?: StaffStatus; version?: number;
}
export interface StaffUserRoles { user_id?: number; role_codes: RoleCode[] }
export interface StaffChannelScopes { user_id?: number; channel_account_ids: number[] }

// ---------- 渠道 ----------
export interface ChannelAccount {
  id: number; code: string; name: string; platform_code?: string; channel_type: ChannelType;
  external_account_id?: string | null; commerce_enabled?: boolean; status: 'ACTIVE' | 'DISABLED';
  created_at?: string; updated_at?: string;
}
export interface ChannelAccountCreateRequest {
  code: string; name: string; platform_code: string; channel_type: ChannelType;
  external_account_id?: string | null; commerce_enabled?: boolean;
}
export interface ChannelAccountUpdateRequest {
  name?: string; external_account_id?: string | null; commerce_enabled?: boolean; status?: 'ACTIVE' | 'DISABLED';
}

// ---------- 品牌 / 类目 ----------
export interface Brand {
  id: number; code: string; name: string; logo_url?: string | null; sort_order?: number;
  status: 'ACTIVE' | 'DISABLED'; created_at?: string; updated_at?: string;
}
export interface BrandCreateRequest { code: string; name: string; logo_url?: string | null; sort_order?: number }
export interface Category {
  id: number; parent_id?: number | null; code: string; name: string; path?: string; depth?: number;
  icon_url?: string | null; sort_order?: number; status: 'ACTIVE' | 'DISABLED'; children?: Category[];
  created_at?: string; updated_at?: string;
}
export interface CategoryCreateRequest { parent_id?: number | null; code: string; name: string; icon_url?: string | null; sort_order?: number }
export interface CategoryUpdateRequest { id: number; parent_id?: number | null; name?: string; icon_url?: string | null; sort_order?: number; status?: 'ACTIVE' | 'DISABLED' }

// ---------- 商品 / SKU ----------
export interface ProductMedia {
  id?: number; product_id?: number; sku_id?: number | null; media_type: 'IMAGE' | 'VIDEO' | 'MANUAL' | 'CERT';
  attachment_id?: number | null; url: string; thumb_url?: string | null; alt_text?: string | null;
  is_main?: boolean; sort_order?: number; created_at?: string;
}
export interface ProductAttribute {
  id?: number; product_id?: number; attribute_id?: number; code: string; name: string;
  data_type?: 'TEXT' | 'NUMBER' | 'BOOL' | 'ENUM' | 'DATE'; unit?: string | null; value_text: string;
  is_spec?: boolean; is_required?: boolean; options?: string[];
}
export interface Product {
  id: number; spu_code: string; name: string; subtitle?: string | null; product_line?: string | null;
  model_code?: string | null; brand_id?: number | null; category_id: number; product_type?: ProductType;
  status: ProductStatus; description_md?: string | null; highlights?: string[]; spec_summary?: Record<string, unknown>;
  warranty_summary?: string | null; install_required?: boolean; install_notes?: string | null;
  service_scope?: string | null; currency: 'CNY'; min_price?: MoneyString; max_price?: MoneyString;
  channel_scope?: ChannelType[]; media?: ProductMedia[]; attributes?: ProductAttribute[]; skus?: Sku[];
  published_at?: string | null; sort_order?: number; created_at?: string; updated_at?: string; version?: number;
}
export interface ProductCreateRequest {
  spu_code: string; name: string; subtitle?: string | null; brand_id?: number | null; category_id: number;
  product_line?: string | null; model_code?: string | null; product_type?: ProductType;
  description_md?: string | null; highlights?: string[]; spec_summary?: Record<string, unknown>;
  warranty_summary?: string | null; install_required?: boolean; install_notes?: string | null;
  service_scope?: string | null; channel_scope?: ChannelType[]; media?: ProductMedia[];
  attributes?: ProductAttribute[]; sort_order?: number;
}
export interface ProductUpdateRequest extends Partial<Omit<ProductCreateRequest, 'spu_code'>> { version?: number }
export interface ProductPublic {
  id: number; spu_code: string; name: string; subtitle?: string | null;
  category_name?: string | null; brand_name?: string | null; product_type?: string;
  description_md?: string | null; highlights?: string[]; spec_summary?: Record<string, unknown>;
  warranty_summary?: string | null; install_required?: boolean; install_notes?: string | null;
  service_scope?: string | null; currency: 'CNY'; min_price?: MoneyString; max_price?: MoneyString;
  media?: ProductMedia[]; attributes?: ProductAttribute[]; skus?: Sku[]; published_at?: string | null;
}
export interface Sku {
  id: number; product_id: number; sku_code: string; name: string; spec_summary?: string | null;
  price: MoneyString; market_price?: MoneyString | null; cost_price?: MoneyString | null;
  barcode?: string | null; weight_g?: number | null; status: SkuStatus; attributes?: ProductAttribute[];
  sort_order?: number; created_at?: string; updated_at?: string; version?: number;
}
export interface SkuCreateRequest {
  sku_code: string; name: string; spec_summary?: string | null; price: MoneyString;
  market_price?: string | null; cost_price?: string | null; barcode?: string | null; weight_g?: number | null;
  status?: SkuStatus; sort_order?: number; attributes?: ProductAttribute[];
}
export interface SkuUpdateRequest {
  name?: string; price?: MoneyString; market_price?: string | null; cost_price?: string | null;
  barcode?: string | null; weight_g?: number | null; status?: SkuStatus; sort_order?: number; version?: number;
}

// ---------- 仓库 / 库存 ----------
export interface Warehouse {
  id: number; code: string; name: string; type?: WarehouseType; region?: string | null; address?: string | null;
  contact_name?: string | null; contact_mobile_masked?: string | null; priority?: number;
  status: 'ACTIVE' | 'DISABLED'; created_at?: string; updated_at?: string;
}
export interface WarehouseCreateRequest {
  code: string; name: string; type?: WarehouseType; region?: string | null; address?: string | null;
  contact_name?: string | null; contact_mobile?: string | null; priority?: number;
}
export interface InventoryItem {
  id: number; warehouse_id: number; warehouse_name?: string | null; sku_id: number; sku_code?: string | null;
  product_name?: string | null; sku_name?: string | null; qty_available: number; qty_reserved: number;
  qty_in_transit: number; safety_stock: number; is_low_stock?: boolean; version?: number; updated_at?: string;
}
export interface InventoryLedgerEntry {
  id: number; sku_id: number; warehouse_id: number; change_type: ChangeType; qty_delta: number;
  qty_after: number; ref_type?: string | null; ref_id?: string | null; operator_id?: number | null;
  remark?: string | null; created_at: string;
}
export interface StockAdjustRequest {
  warehouse_id: number; sku_id: number; change_type: AdjustType; qty_delta: number;
  expected_version: number; reason: string; remark?: string | null;
}

// ---------- 客户 ----------
export interface Customer {
  id: number; user_id?: number; customer_no: string; nickname?: string | null; real_name?: string | null;
  mobile_masked?: string | null; email?: string | null; gender?: 'MALE' | 'FEMALE' | 'UNKNOWN';
  default_channel_id?: number | null; channel_account_id?: number | null; tags?: string[];
  total_order_count?: number; total_paid_amount?: MoneyString; last_order_at?: string | null;
  status: 'ACTIVE' | 'DISABLED'; remark?: string | null; created_at?: string; updated_at?: string;
}
export interface CustomerUpdateRequest {
  nickname?: string | null; real_name?: string | null; gender?: 'MALE' | 'FEMALE' | 'UNKNOWN';
  birthday?: string | null; tags?: string[]; remark?: string | null; default_channel_id?: number | null;
}
export interface CustomerAddress {
  id: number; customer_id?: number; receiver_name: string; receiver_mobile_masked?: string;
  province: string; city: string; district: string; detail: string; postal_code?: string | null;
  is_default?: boolean; status?: 'ACTIVE' | 'DELETED'; created_at?: string; updated_at?: string;
}
export interface CustomerAddressRequest {
  receiver_name: string; receiver_mobile: string; province: string; city: string;
  district: string; detail: string; postal_code?: string | null; is_default?: boolean;
}

// ---------- 购物车 ----------
export interface CartItem {
  id: number; cart_id?: number; sku_id: number; product_id?: number; product_name?: string; sku_name?: string;
  image_url?: string | null; unit_price?: MoneyString; quantity: number; selected?: boolean;
  stock_available?: boolean; added_at?: string; updated_at?: string;
}
export interface Cart {
  id: number; customer_id?: number; channel_account_id?: number; status?: 'OPEN' | 'CHECKED_OUT' | 'ABANDONED';
  items: CartItem[]; item_count?: number; selected_quantity?: number; total_amount?: MoneyString; updated_at?: string;
}
export interface CartItemAddRequest { sku_id: number; quantity: number; channel_account_id?: number | null }
export interface CartItemUpdateRequest { quantity?: number; selected?: boolean }

// ---------- 订单 ----------
export interface OrderItem {
  id: number; order_id?: number; product_id?: number; sku_id: number; warehouse_id?: number | null;
  spu_code?: string; sku_code?: string; product_name?: string; sku_name?: string; spec_summary?: string | null;
  image_url?: string | null; unit_price?: MoneyString; quantity: number; goods_amount?: MoneyString;
  discount_amount?: MoneyString; payable_amount?: MoneyString; refunded_amount?: MoneyString;
  shipped_quantity?: number; returned_quantity?: number; item_status?: 'NORMAL' | 'CANCELLED' | 'REFUNDED';
  after_sales_status?: OrderAfterSalesStatus;
}
export interface OrderTimelineEntry {
  id: number; order_id?: number; field: 'status' | 'payment_status' | 'fulfillment_status' | 'after_sales_status';
  from_value?: string | null; to_value: string; reason?: string | null;
  operator_type?: Party | 'SYSTEM'; operator_id?: number | null; created_at: string;
}
export interface Order {
  id: number; order_no: string; channel_account_id: number; customer_id: number; source?: OrderSource;
  external_order_no?: string | null; currency: 'CNY'; goods_amount?: MoneyString; discount_amount?: MoneyString;
  shipping_amount?: MoneyString; payable_amount: MoneyString; paid_amount?: MoneyString; refunded_amount?: MoneyString;
  status: OrderStatus; payment_status: PaymentStatus; fulfillment_status: FulfillmentStatus;
  after_sales_status: OrderAfterSalesStatus; receiver_name?: string; receiver_phone_masked?: string;
  shipping_address?: Record<string, unknown>; address_id?: number | null; buyer_remark?: string | null;
  staff_remark?: string | null; pay_deadline?: string | null; paid_at?: string | null; shipped_at?: string | null;
  completed_at?: string | null; cancelled_at?: string | null; cancel_reason?: string | null; closed_at?: string | null;
  items?: OrderItem[]; created_at: string; updated_at?: string; version?: number;
}
export interface OrderItemInput { sku_id: number; quantity: number }
export interface CreateOrderRequest {
  channel_account_id: number; source?: OrderSource; source_mode: 'CART' | 'BUY_NOW';
  cart_item_ids?: number[]; items?: OrderItemInput[]; address_id: number;
  buyer_remark?: string | null; coupon_code?: string | null; expected_delivery_time?: string | null;
}
export interface OrderCancelRequest { reason: string; notify_customer?: boolean }
export interface OrderAddressUpdateRequest {
  address_id?: number | null; receiver_name?: string; receiver_mobile?: string; province?: string;
  city?: string; district?: string; detail?: string;
}
export interface OrderRemarkUpdateRequest { buyer_remark?: string | null; staff_remark?: string | null }

// ---------- 支付 ----------
export interface Payment {
  id: number; payment_no: string; order_id: number; method: PaymentMethod; amount: MoneyString;
  currency: 'CNY'; status: PayStatus; channel_txn_no?: string | null; pay_url?: string | null;
  expires_at?: string | null; paid_at?: string | null; closed_at?: string | null;
  failure_code?: string | null; failure_message?: string | null; created_at?: string; updated_at?: string; version?: number;
}
export interface PaymentCreateRequest {
  order_id: number; method: PaymentMethod; return_url?: string | null; client_ip?: string | null;
}
export interface MockPaymentSucceedRequest { channel_txn_no?: string | null; paid_at?: string | null; remark?: string | null }

// ---------- 履约 ----------
export interface Carrier {
  id: number; code: string; name: string; tracking_url_template?: string | null; status: 'ACTIVE' | 'DISABLED';
}
export interface ShipmentItem { id?: number; shipment_id?: number; order_item_id: number; sku_id?: number; product_name?: string | null; sku_name?: string | null; quantity: number }
export interface TrackingEvent {
  id: number; shipment_id?: number; event_time: string; status: string; description: string;
  location?: string | null; source?: 'CARRIER_WEBHOOK' | 'MANUAL' | 'API'; raw?: Record<string, unknown> | null; created_at?: string;
}
export interface Shipment {
  id: number; shipment_no: string; order_id: number; warehouse_id?: number | null; carrier_id: number;
  carrier_code?: string; carrier_name?: string | null; tracking_no: string; status: ShipmentStatus;
  package_count?: number; receiver_name?: string; receiver_phone_masked?: string; address_text?: string;
  shipped_at?: string | null; delivered_at?: string | null; exception_note?: string | null;
  items?: ShipmentItem[]; tracking_events?: TrackingEvent[]; created_at?: string; updated_at?: string;
}
export interface ShipRequest {
  warehouse_id: number; carrier_code: string; tracking_no: string; package_count?: number;
  shipped_at?: string | null; items: ShipmentItem[]; remark?: string | null;
}
export interface TrackingEventCreateRequest { event_time: string; status: string; description: string; location?: string | null }

// ---------- 售后 ----------
export interface AfterSalesMessage {
  id: number; application_id?: number; sender_type: 'CUSTOMER' | 'STAFF' | 'SYSTEM';
  sender_id?: number | null; content: string; attachment_ids?: number[]; created_at: string;
}
export interface AfterSalesApplication {
  id: number; application_no: string; order_id: number; order_no?: string | null; order_item_id?: number | null;
  customer_id: number; type: AfterSalesType; status: AfterSalesStatus; reason_code?: string;
  description?: string | null; evidence_attachment_ids?: number[]; quantity?: number; refund_amount?: MoneyString;
  return_carrier_code?: string | null; return_tracking_no?: string | null; applied_at: string;
  reviewed_at?: string | null; reviewer_id?: number | null; review_remark?: string | null;
  received_at?: string | null; completed_at?: string | null; cancel_reason?: string | null;
  messages?: AfterSalesMessage[]; created_at?: string; updated_at?: string; version?: number;
}
export interface AfterSalesCreateRequest {
  order_id: number; order_item_id?: number | null; type: AfterSalesType; reason_code: string;
  description?: string | null; evidence_attachment_ids?: number[]; quantity?: number; refund_amount?: string | null;
}
export interface ReviewRequest {
  decision: 'APPROVE' | 'REJECT'; approved_amount?: string | null; reason?: string | null;
  remark?: string | null; need_return?: boolean; return_address?: string | null; assignee_id?: number | null;
}
export interface ReturnShipmentRequest { carrier_code: string; tracking_no: string; shipped_at?: string | null; remark?: string | null }
export interface AfterSalesReceiveRequest { received?: boolean; warehouse_id?: number | null; remark?: string | null }
export interface AfterSalesCompleteRequest { conclusion: string; refund_amount?: string | null; remark?: string | null }
export interface AfterSalesCancelRequest { reason: string }
export interface AfterSalesMessageCreateRequest { content: string; attachment_ids?: number[]; visible_to_customer?: boolean }

// ---------- 退款 ----------
export interface RefundAttempt {
  id: number; refund_id?: number; attempt_no: number; channel?: string;
  status: 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILED'; request_payload?: Record<string, unknown> | null;
  response_payload?: Record<string, unknown> | null; error_code?: string | null; error_message?: string | null;
  attempted_at: string;
}
export interface Refund {
  id: number; refund_no: string; order_id: number; payment_id?: number | null; after_sales_id?: number | null;
  customer_id: number; amount: MoneyString; currency: 'CNY'; reason?: string | null; status: RefundStatus;
  channel?: string; requested_by?: number | null; executed_at?: string | null; attempts?: RefundAttempt[];
  created_at?: string; updated_at?: string; version?: number;
}
export interface RefundCreateRequest {
  order_id: number; after_sales_id?: number | null; order_item_id?: number | null;
  amount?: string | null; reason: string; channel?: string | null;
}

// ---------- 发票 ----------
export interface Invoice {
  id: number; invoice_no?: string | null; order_id: number; customer_id: number; type: InvoiceType;
  title: string; tax_no?: string | null; bank_name?: string | null; bank_account_masked?: string | null;
  registered_address?: string | null; registered_phone_masked?: string | null; amount?: MoneyString;
  tax_amount?: MoneyString; status: InvoiceStatus; issue_type?: 'BLUE' | 'RED'; email?: string | null;
  issued_at?: string | null; attachment_id?: number | null; remark?: string | null;
  created_at?: string; updated_at?: string;
}
export interface InvoiceCreateRequest {
  order_id: number; type: InvoiceType; title: string; tax_no?: string | null; bank_name?: string | null;
  bank_account?: string | null; registered_address?: string | null; registered_phone?: string | null;
  email?: string | null; remark?: string | null;
}
export interface InvoiceIssueRequest {
  invoice_no: string; issue_type?: 'BLUE' | 'RED'; tax_amount?: string | null;
  attachment_id?: number | null; issued_at?: string | null;
}
export interface InvoiceVoidRequest { reason: string; issue_type?: 'RED' }

// ---------- 审计 / 附件 ----------
export interface AuditLog {
  id: number; tenant_id?: number; actor_type: 'STAFF' | 'CUSTOMER' | 'GUEST' | 'SYSTEM';
  actor_id?: number | null; actor_label?: string | null; action: string; resource_type: string;
  resource_id?: string | null; channel_account_id?: number | null; before_data?: Record<string, unknown> | null;
  after_data?: Record<string, unknown> | null; request_id?: string | null; ip?: string | null;
  user_agent?: string | null; created_at: string;
}
export interface Attachment {
  id: number; owner_type?: string; owner_id?: string | null; file_name: string; content_type: string;
  size_bytes: number; storage_key?: string; url: string; checksum_sha256?: string;
  uploaded_by?: number | null; is_public?: boolean; status: 'PENDING' | 'READY' | 'REJECTED' | 'DELETED'; created_at?: string;
}

// ---------- 报表 / 系统 ----------
export interface DashboardReport {
  generated_at: string; date_from?: string; date_to?: string; channel_account_id?: number | null;
  gross_sales_amount: MoneyString; net_sales_amount?: MoneyString; discount_amount?: MoneyString;
  refund_amount?: MoneyString; order_count: number; paid_order_count?: number; avg_order_value?: MoneyString;
  new_customers?: number; low_stock_count?: number; pending_after_sales_count?: number;
  conversion_rate?: number; channel_breakdown?: Array<Record<string, unknown>>; top_products?: Array<Record<string, unknown>>;
}
export interface SalesDailyReport {
  date: string; channel_account_id?: number | null; order_count: number; paid_order_count?: number;
  gmv: MoneyString; net_sales_amount?: MoneyString; refund_amount?: MoneyString; new_customers?: number;
  channel_breakdown?: Array<Record<string, unknown>>; top_skus?: Array<Record<string, unknown>>;
}
export interface InventoryReport {
  generated_at?: string; warehouse_count?: number; sku_count?: number; total_available_qty: number;
  total_reserved_qty?: number; total_in_transit_qty?: number; low_stock_count?: number;
  out_of_stock_count?: number; by_warehouse?: Array<Record<string, unknown>>;
}
export interface AfterSalesReport {
  generated_at?: string; date_from?: string; date_to?: string; application_count: number;
  completed_count?: number; rejected_count?: number; avg_processing_hours?: number; refund_amount?: MoneyString;
  by_type?: Array<Record<string, unknown>>; by_status?: Array<Record<string, unknown>>;
}

// 契约枚举 re-export，方便页面从统一入口引用
export type {
  AdjustType, AfterSalesStatus, AfterSalesType, ChannelType, ChangeType, FulfillmentStatus,
  InvoiceStatus, InvoiceType, OrderAfterSalesStatus, OrderSource, OrderStatus, Party,
  PaymentMethod, PaymentStatus, PayStatus, ProductStatus, ProductType, RefundStatus,
  ShipmentStatus, SkuStatus, StaffStatus, WarehouseType,
} from './status';

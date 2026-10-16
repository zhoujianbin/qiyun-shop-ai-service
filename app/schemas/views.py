"""集中定义 API 响应模型（运行时 OpenAPI 的响应 schema）。

设计约定（对应任务硬性要求）：
- 每个模型显式设置 `model_config = ConfigDict(extra="allow")`：服务层返回但此处未声明的字段
  会被原样透传，FastAPI 不会按默认的 ignore 行为过滤掉。
- 金额字段：服务层已用 `money()` 返回字符串（如 `"199.00"`），因此声明为 `str` / `str | None`，不用 float。
- id 用 `int`，时间用 `str`（服务层已返回 ISO 字符串）；极少数服务层未转字符串的字段（如
  product.published_at 直接返回 datetime）用 `Any`，交由 JSON 编码器输出，避免强制转换改变行为。
- 各模型只声明服务层“恒定返回”的键；仅详情接口才出现的键（如 order.items/payments、
  customer.addresses）不声明，由 extra=\"allow\" 透传，避免在缺失时被补成 null 而改变响应形状。
"""
from typing import Any

from pydantic import BaseModel, ConfigDict


# --------------------------------------------------------------------------- #
# 分页基础
# --------------------------------------------------------------------------- #
class PageMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int
    page_size: int
    total: int


class PageBase(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int
    page_size: int
    total: int
    items: list[Any]
    meta: PageMeta


# --------------------------------------------------------------------------- #
# auth
# --------------------------------------------------------------------------- #
class CurrentUser(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    username: str
    display_name: str | None = None
    party: str
    is_super_admin: bool
    roles: list[str]
    permissions: list[str]
    customer_id: int | None = None
    tenant_id: int
    channel_scope: list[str]


class PasswordChangeResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    changed: bool
    revoked_sessions: int


class TokenBundle(BaseModel):
    """登录/刷新返回的令牌集合（guest-session、refresh 不含 user）。"""

    model_config = ConfigDict(extra="allow")

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    party: str
    roles: list[str]


class TokenPair(TokenBundle):
    """staff/customer 登录、注册：在令牌集合上附带 `user` 当前用户视图。"""

    model_config = ConfigDict(extra="allow")

    user: CurrentUser


# --------------------------------------------------------------------------- #
# staff / channel
# --------------------------------------------------------------------------- #
class UserView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    username: str
    display_name: str | None = None
    party: str
    email: str | None = None
    phone: str | None = None
    phone_masked: str | None = None
    status: str
    is_super_admin: bool
    roles: list[str]
    role_codes: list[str]
    channel_ids: list[int]
    channel_account_ids: list[int]
    last_login_at: str | None = None
    created_at: str


class RoleView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    code: str
    name: str
    description: str | None = None
    is_system: bool
    permissions: list[str]


class PermissionView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    code: str
    name: str
    module: str


class UserRolesView(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: int
    role_codes: list[str]
    roles: list[str]
    channel_account_ids: list[int]
    channel_ids: list[int]


class UserChannelScopesView(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: int
    channel_account_ids: list[int]
    channel_ids: list[int]


class AuditLogView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    actor_type: str | None = None
    actor_id: int | None = None
    actor_label: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    channel_account_id: int | None = None
    before: Any = None
    after: Any = None
    before_data: Any = None
    after_data: Any = None
    ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    created_at: str


class ChannelView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    code: str
    name: str
    platform_code: str | None = None
    channel_type: str
    external_account_id: str | None = None
    commerce_enabled: bool
    status: str


class PublicChannelView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    code: str
    name: str
    platform_code: str | None = None
    channel_type: str
    status: str
    is_default: bool


class UserPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[UserView]


class AuditLogPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[AuditLogView]


# --------------------------------------------------------------------------- #
# catalog
# --------------------------------------------------------------------------- #
class BrandView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    code: str
    name: str
    logo_url: str | None = None
    status: str
    sort_order: int


class CategoryView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    code: str
    name: str
    parent_id: int | None = None
    path: str
    depth: int
    sort_order: int
    icon_url: str | None = None
    status: str


class AttributeDefinitionView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    code: str
    name: str
    data_type: str
    unit: str | None = None
    is_spec: bool
    options: Any = None


class ProductMediaView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    product_id: int
    url: str
    media_type: str
    alt_text: str | None = None
    sort_order: int
    is_main: bool


class ProductAttributeView(BaseModel):
    model_config = ConfigDict(extra="allow")

    product_id: int
    attribute_id: int
    code: str
    name: str
    data_type: str
    unit: str | None = None
    value_text: str | None = None
    is_spec: bool
    options: Any = None


class InventoryStockView(BaseModel):
    model_config = ConfigDict(extra="allow")

    warehouse_id: int
    qty_available: int
    qty_reserved: int
    sellable: int


class SkuView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    product_id: int
    sku_code: str
    name: str
    spec_summary: Any = None
    price: str
    market_price: str | None = None
    cost_price: str | None = None
    barcode: str | None = None
    weight_g: int | None = None
    status: str


class SkuStockView(SkuView):
    model_config = ConfigDict(extra="allow")

    inventory: list[InventoryStockView]
    sellable_qty: int


class ProductView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    spu_code: str
    name: str
    brand_id: int | None = None
    category_id: int | None = None
    category_name: str | None = None
    brand_name: str | None = None
    product_line: str | None = None
    product_type: str | None = None
    channel_scope: list[Any]
    model_code: str | None = None
    subtitle: str | None = None
    description_md: str | None = None
    highlights: Any = None
    spec_summary: Any = None
    warranty_summary: str | None = None
    install_required: bool
    install_notes: str | None = None
    service_scope: str | None = None
    currency: str
    min_price: str | None = None
    max_price: str | None = None
    status: str
    published_at: Any = None
    version: int | None = None
    media: list[ProductMediaView]
    attributes: list[ProductAttributeView]


class ProductDetailView(ProductView):
    model_config = ConfigDict(extra="allow")

    skus: list[SkuStockView]


class SearchProductView(ProductDetailView):
    model_config = ConfigDict(extra="allow")

    sellable_qty: int


class ProductPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[ProductDetailView]


class SearchProductPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[SearchProductView]


# --------------------------------------------------------------------------- #
# inventory
# --------------------------------------------------------------------------- #
class WarehouseView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    code: str
    name: str
    region: str | None = None
    address: str | None = None
    priority: int
    status: str


class InventoryView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    sku_id: int
    sku_code: str
    sku_name: str
    product_id: int
    product_name: str
    warehouse_id: int
    warehouse_name: str
    qty_available: int
    qty_reserved: int
    qty_in_transit: int
    sellable_qty: int
    safety_stock: int
    is_low_stock: bool
    version: int | None = None
    updated_at: str | None = None


class LedgerEntryView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    sku_id: int
    warehouse_id: int
    change_type: str
    qty_delta: int
    qty_after: int
    ref_type: str | None = None
    ref_id: str | None = None
    remark: str | None = None
    created_at: str


class StockAdjustResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    sku_id: int
    warehouse_id: int
    qty_available: int
    qty_reserved: int
    version: int | None = None
    change_type: str
    qty_delta: int


class InventoryAlertView(BaseModel):
    model_config = ConfigDict(extra="allow")

    sku_id: int
    sku_code: str
    sku_name: str
    warehouse_id: int
    warehouse_name: str
    qty_available: int
    safety_stock: int
    sellable_qty: int


class InventoryPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[InventoryView]


class LedgerPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[LedgerEntryView]


# --------------------------------------------------------------------------- #
# customer
# --------------------------------------------------------------------------- #
class CustomerView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    user_id: int
    customer_no: str
    username: str | None = None
    display_name: str | None = None
    phone: str | None = None
    phone_masked: str | None = None
    mobile_masked: str | None = None
    email: str | None = None
    nickname: str | None = None
    real_name: str | None = None
    gender: str | None = None
    birthday: str | None = None
    default_channel_id: int | None = None
    channel_account_id: int | None = None
    tags: list[str]
    total_order_count: int | None = None
    total_paid_amount: str | None = None
    last_order_at: str | None = None
    remark: str | None = None
    status: str


class CustomerDetailView(CustomerView):
    model_config = ConfigDict(extra="allow")

    addresses: list["AddressView"]


class AddressView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    customer_id: int
    receiver_name: str
    receiver_phone: str | None = None
    receiver_mobile: str | None = None
    receiver_mobile_masked: str | None = None
    province: str
    city: str
    district: str
    detail: str
    postal_code: str | None = None
    is_default: bool
    status: str
    full_address: str


CustomerDetailView.model_rebuild()


class DeleteResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    deleted: bool


class CustomerOrderSummaryView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    order_no: str
    status: str
    payment_status: str
    fulfillment_status: str
    payable_amount: str
    created_at: str


class CustomerPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[CustomerView]


class CustomerOrderPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[CustomerOrderSummaryView]


# --------------------------------------------------------------------------- #
# cart
# --------------------------------------------------------------------------- #
class CartItemView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    cart_id: int
    sku_id: int
    quantity: int
    selected: bool | None = None
    sku_code: str | None = None
    sku_name: str | None = None
    product_id: int | None = None
    product_name: str | None = None
    image_url: str | None = None
    unit_price: str | None = None
    amount: str
    sellable_qty: int
    stock_available: bool
    available: bool
    added_at: str | None = None
    updated_at: str | None = None


class CartView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    customer_id: int
    channel_account_id: int
    status: str
    items: list[CartItemView]
    item_count: int
    selected_quantity: int
    total_amount: str
    updated_at: str | None = None


# --------------------------------------------------------------------------- #
# order
# --------------------------------------------------------------------------- #
class OrderItemView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    order_id: int
    product_id: int | None = None
    sku_id: int | None = None
    warehouse_id: int | None = None
    spu_code: str | None = None
    sku_code: str | None = None
    product_name: str | None = None
    sku_name: str | None = None
    spec_summary: Any = None
    image_url: str | None = None
    unit_price: str | None = None
    quantity: int | None = None
    goods_amount: str | None = None
    discount_amount: str | None = None
    payable_amount: str | None = None
    refunded_amount: str | None = None
    shipped_quantity: int | None = None
    returned_quantity: int | None = None
    item_status: str | None = None
    after_sales_status: str | None = None


class OrderPaymentView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    payment_no: str
    method: str
    amount: str
    status: str
    pay_url: str | None = None
    paid_at: str | None = None


class OrderView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    order_no: str
    channel_account_id: int | None = None
    customer_id: int | None = None
    source: str | None = None
    currency: str | None = None
    goods_amount: str | None = None
    discount_amount: str | None = None
    shipping_amount: str | None = None
    payable_amount: str | None = None
    paid_amount: str | None = None
    refunded_amount: str | None = None
    status: str
    payment_status: str
    fulfillment_status: str
    after_sales_status: str
    receiver_name: str | None = None
    receiver_phone: str | None = None
    shipping_address: Any = None
    buyer_remark: str | None = None
    staff_remark: str | None = None
    pay_deadline: str | None = None
    paid_at: str | None = None
    shipped_at: str | None = None
    completed_at: str | None = None
    cancelled_at: str | None = None
    cancel_reason: str | None = None
    version: int | None = None
    created_at: str
    updated_at: str
    receiver_phone_masked: str | None = None


class OrderDetailView(OrderView):
    model_config = ConfigDict(extra="allow")

    items: list[OrderItemView]
    payments: list[OrderPaymentView]


class OrderTimelineEntryView(BaseModel):
    model_config = ConfigDict(extra="allow")

    field: str
    from_value: str | None = None
    to_value: str | None = None
    reason: str | None = None
    operator_type: str | None = None
    created_at: str


class OrderTimelineView(BaseModel):
    model_config = ConfigDict(extra="allow")

    order_no: str
    items: list[OrderTimelineEntryView]


class OrderPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[OrderView]


# --------------------------------------------------------------------------- #
# payment
# --------------------------------------------------------------------------- #
class PaymentView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    payment_no: str
    order_id: int
    method: str
    amount: str
    currency: str
    status: str
    channel_txn_no: str | None = None
    pay_url: str | None = None
    expires_at: str | None = None
    paid_at: str | None = None
    created_at: str


class MockSucceedView(BaseModel):
    model_config = ConfigDict(extra="allow")

    payment: PaymentView


class PaymentPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[PaymentView]


# --------------------------------------------------------------------------- #
# fulfillment
# --------------------------------------------------------------------------- #
class CarrierView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    code: str
    name: str
    tracking_url_template: str | None = None
    status: str


class ShipmentItemView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    shipment_id: int
    order_item_id: int
    sku_id: int
    product_name: str
    sku_name: str
    quantity: int


class TrackingEventView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    shipment_id: int
    event_time: str
    status: str
    description: str
    location: str | None = None
    source: str
    raw: Any = None
    created_at: str


class ShipmentView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    shipment_no: str
    order_id: int
    warehouse_id: int | None = None
    carrier_id: int | None = None
    carrier_code: str | None = None
    carrier_name: str | None = None
    tracking_no: str
    status: str
    package_count: int
    receiver_name: str | None = None
    receiver_phone: str | None = None
    receiver_phone_masked: str | None = None
    exception_note: str | None = None
    updated_at: str | None = None
    address_text: str | None = None
    tracking_url: str | None = None
    shipped_at: str | None = None
    delivered_at: str | None = None
    created_at: str


class ShipmentDetailView(ShipmentView):
    model_config = ConfigDict(extra="allow")

    items: list[ShipmentItemView]
    tracking_events: list[TrackingEventView]


class ShipmentPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[ShipmentView]


# --------------------------------------------------------------------------- #
# aftersales
# --------------------------------------------------------------------------- #
class AfterSalesItemView(BaseModel):
    model_config = ConfigDict(extra="allow")

    order_item_id: int
    quantity: int
    amount: str


class AfterSalesMessageView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    application_id: int
    author_type: str
    author_id: int | None = None
    sender_type: str
    sender_id: int | None = None
    content: str
    visible_to_customer: bool
    attachments: Any = None
    attachment_ids: list[int]
    created_at: str


class AfterSalesRefundView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    refund_no: str
    amount: str
    status: str


class AfterSalesView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    application_no: str
    order_id: int
    order_no: str | None = None
    order_item_id: int | None = None
    channel_account_id: int | None = None
    type: str
    reason_code: str
    reason_text: str | None = None
    description: str | None = None
    evidence: Any = None
    expect_amount: str | None = None
    approved_amount: str | None = None
    status: str
    need_return: bool | None = None
    return_carrier_id: int | None = None
    return_tracking_no: str | None = None
    reviewer_id: int | None = None
    reviewed_at: str | None = None
    review_note: str | None = None
    received_at: str | None = None
    completed_at: str | None = None
    sla_due_at: str | None = None
    applied_at: str
    review_remark: str | None = None
    refund_amount: str | None = None
    evidence_attachment_ids: list[int]
    created_at: str
    updated_at: str
    version: int | None = None


class AfterSalesDetailView(AfterSalesView):
    model_config = ConfigDict(extra="allow")

    items: list[AfterSalesItemView]
    messages: list[AfterSalesMessageView]
    refunds: list[AfterSalesRefundView]


class AfterSalesPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[AfterSalesView]


# --------------------------------------------------------------------------- #
# refund
# --------------------------------------------------------------------------- #
class RefundView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    refund_no: str
    order_id: int
    application_id: int | None = None
    after_sales_id: int | None = None
    payment_id: int | None = None
    channel: str | None = None
    customer_id: int
    method: str | None = None
    amount: str
    currency: str
    status: str
    reason: str | None = None
    channel_refund_no: str | None = None
    approved_by: int | None = None
    approved_at: str | None = None
    executed_at: str | None = None
    created_at: str


class RefundAttemptView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    refund_id: int
    attempt_no: int
    status: str
    channel: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    request_payload: Any = None
    response_payload: Any = None
    attempted_at: str
    created_at: str


class RefundDetailView(RefundView):
    model_config = ConfigDict(extra="allow")

    attempts: list[RefundAttemptView]


class RefundPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[RefundView]


# --------------------------------------------------------------------------- #
# invoice
# --------------------------------------------------------------------------- #
class InvoiceView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    invoice_no: str | None = None
    order_id: int
    customer_id: int
    type: str
    title_type: str | None = None
    title: str
    tax_no: str | None = None
    content: str | None = None
    amount: str
    tax_amount: str | None = None
    status: str
    file_url: str | None = None
    attachment_id: int | None = None
    issue_type: str | None = None
    bank_name: str | None = None
    bank_account_masked: str | None = None
    registered_address: str | None = None
    registered_phone_masked: str | None = None
    email: str | None = None
    remark: str | None = None
    issued_at: str | None = None
    voided_at: str | None = None
    created_at: str
    updated_at: str
    version: int | None = None


class InvoicePage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[InvoiceView]


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
class DashboardView(BaseModel):
    model_config = ConfigDict(extra="allow")

    generated_at: str
    date_from: str
    date_to: str
    range_days: int
    gross_sales_amount: str
    net_sales_amount: str
    refund_amount: str
    avg_order_value: str
    new_customers: int
    pending_after_sales_count: int
    top_products: list[Any]
    channel_breakdown: list[Any]
    order_count: int
    paid_order_count: int
    cancelled_order_count: int
    shipped_order_count: int
    after_sales_order_count: int
    gmv: str
    paid_amount: str
    refunded_amount: str
    net_revenue: str
    average_order_value: str
    pay_rate: float
    cancel_rate: float
    customer_count: int
    product_count: int
    sku_count: int
    low_stock_count: int
    pending_after_sales: int


class SalesDailyItemView(BaseModel):
    model_config = ConfigDict(extra="allow")

    stat_date: str
    date: str
    channel_account_id: int | None = None
    order_count: int
    payable_amount: str
    paid_amount: str
    gmv: str
    refund_amount: str
    refunded_amount: str
    new_customers: int


class SalesDailyView(BaseModel):
    model_config = ConfigDict(extra="allow")

    range_days: int
    items: list[SalesDailyItemView]


class InventoryReportAlertView(BaseModel):
    model_config = ConfigDict(extra="allow")

    sku_code: str
    sku_name: str
    warehouse_name: str
    qty_available: int
    safety_stock: int


class InventoryReportView(BaseModel):
    model_config = ConfigDict(extra="allow")

    generated_at: str
    total_available: int
    total_reserved: int
    total_cost_value: str
    total_available_qty: int
    total_reserved_qty: int
    total_in_transit_qty: int
    warehouse_count: int
    sku_count: int
    low_stock_count: int
    out_of_stock_count: int
    by_warehouse: list[Any]
    alerts: list[InventoryReportAlertView]


class StatusCountView(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    count: int


class TypeCountView(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    count: int


class AfterSalesReportView(BaseModel):
    model_config = ConfigDict(extra="allow")

    generated_at: str
    range_days: int
    application_count: int
    completed_count: int
    rejected_count: int
    processing_count: int
    by_status_map: dict[str, int]
    by_status: list[StatusCountView]
    by_type: list[TypeCountView]
    refund_count: int
    refund_amount: str


# --------------------------------------------------------------------------- #
# attachment
# --------------------------------------------------------------------------- #
class AttachmentView(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    file_name: str
    content_type: str | None = None
    size_bytes: int
    checksum_sha256: str | None = None
    owner_type: str
    owner_id: str | None = None
    status: str
    created_at: str
    download_url: str
    url: str
    storage_key: str
    is_public: bool


# 追加：前端契约要求列表接口返回 {items, meta}


class BrandPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[BrandView]


class CarrierPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[CarrierView]


class WarehousePage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[WarehouseView]


class RolePage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[RoleView]


class PermissionPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[PermissionView]


class InventoryAlertPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[InventoryAlertView]


class ChannelAccountPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[ChannelView]


class SkuPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[SkuStockView]


class RefundAttemptPage(PageBase):
    model_config = ConfigDict(extra="allow")

    items: list[RefundAttemptView]

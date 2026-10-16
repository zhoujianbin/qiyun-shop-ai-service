"""自动生成，请勿手工修改：改动 db/schema.sql 后执行 scripts/gen_models.py。"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Integer, Interval, Numeric, SmallInteger, String, Text, text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column


class Base(DeclarativeBase):
    pass

class Tenant(Base):
    __tablename__ = "tenant"
    __table_args__ = {"schema": "shared"}
    id = mapped_column(BigInteger, primary_key=True)
    code = mapped_column(String(32))
    name = mapped_column(String(128))
    status = mapped_column(Text, server_default=text("'ACTIVE'"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = {"schema": "shared"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    party = mapped_column(Text)
    username = mapped_column(String(64))
    email = mapped_column(String(128))
    phone = mapped_column(String(32))
    password_hash = mapped_column(String(255))
    display_name = mapped_column(String(64))
    avatar_url = mapped_column(String(512))
    status = mapped_column(Text, server_default=text("'ACTIVE'"))
    is_super_admin = mapped_column(Boolean, server_default=text("false"))
    failed_login_count = mapped_column(Integer, server_default=text("0"))
    locked_until = mapped_column(DateTime(timezone=True))
    last_login_at = mapped_column(DateTime(timezone=True))
    password_changed_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    version = mapped_column(Integer, server_default=text("0"))


class AppRole(Base):
    __tablename__ = "app_role"
    __table_args__ = {"schema": "shared"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    code = mapped_column(String(64))
    name = mapped_column(String(64))
    description = mapped_column(String(255))
    is_system = mapped_column(Boolean, server_default=text("false"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AppPermission(Base):
    __tablename__ = "app_permission"
    __table_args__ = {"schema": "shared"}
    id = mapped_column(BigInteger, primary_key=True)
    code = mapped_column(String(96))
    name = mapped_column(String(96))
    module = mapped_column(String(32))


class AppRolePermission(Base):
    __tablename__ = "app_role_permission"
    __table_args__ = {"schema": "shared"}
    role_id = mapped_column(BigInteger, primary_key=True)
    permission_id = mapped_column(BigInteger, primary_key=True)


class AppUserRole(Base):
    __tablename__ = "app_user_role"
    __table_args__ = {"schema": "shared"}
    user_id = mapped_column(BigInteger, primary_key=True)
    role_id = mapped_column(BigInteger, primary_key=True)
    granted_by = mapped_column(BigInteger)
    granted_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ChannelAccount(Base):
    __tablename__ = "channel_account"
    __table_args__ = {"schema": "shared"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    code = mapped_column(String(32))
    name = mapped_column(String(128))
    platform_code = mapped_column(String(32))
    channel_type = mapped_column(Text)
    external_account_id = mapped_column(String(128))
    commerce_enabled = mapped_column(Boolean, server_default=text("true"))
    status = mapped_column(Text, server_default=text("'ACTIVE'"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class StaffChannelScope(Base):
    __tablename__ = "staff_channel_scope"
    __table_args__ = {"schema": "shared"}
    user_id = mapped_column(BigInteger, primary_key=True)
    channel_account_id = mapped_column(BigInteger, primary_key=True)
    granted_by = mapped_column(BigInteger)
    granted_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class RefreshToken(Base):
    __tablename__ = "refresh_token"
    __table_args__ = {"schema": "shared"}
    id = mapped_column(BigInteger, primary_key=True)
    user_id = mapped_column(BigInteger)
    token_hash = mapped_column(String(128))
    family_id = mapped_column(UUID, server_default=text("gen_random_uuid()"))
    expires_at = mapped_column(DateTime(timezone=True))
    revoked_at = mapped_column(DateTime(timezone=True))
    replaced_by = mapped_column(BigInteger)
    user_agent = mapped_column(String(255))
    ip = mapped_column(INET)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "shared"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    actor_type = mapped_column(Text)
    actor_id = mapped_column(BigInteger)
    actor_label = mapped_column(String(128))
    action = mapped_column(String(64))
    resource_type = mapped_column(String(48))
    resource_id = mapped_column(String(64))
    channel_account_id = mapped_column(BigInteger)
    before_data = mapped_column(JSONB)
    after_data = mapped_column(JSONB)
    request_id = mapped_column(String(64))
    ip = mapped_column(INET)
    user_agent = mapped_column(String(255))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_record"
    __table_args__ = {"schema": "shared"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    idem_key = mapped_column(String(128))
    user_id = mapped_column(BigInteger)
    method = mapped_column(String(8))
    path = mapped_column(String(255))
    request_hash = mapped_column(String(64))
    state = mapped_column(Text, server_default=text("'IN_PROGRESS'"))
    response_status = mapped_column(Integer)
    response_body = mapped_column(JSONB)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    completed_at = mapped_column(DateTime(timezone=True))
    expires_at = mapped_column(DateTime(timezone=True), server_default=text("now() + interval '24 hours'"))


class OutboxEvent(Base):
    __tablename__ = "outbox_event"
    __table_args__ = {"schema": "shared"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    event_type = mapped_column(String(64))
    aggregate_type = mapped_column(String(48))
    aggregate_id = mapped_column(String(64))
    payload = mapped_column(JSONB)
    status = mapped_column(Text, server_default=text("'PENDING'"))
    attempts = mapped_column(Integer, server_default=text("0"))
    available_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    published_at = mapped_column(DateTime(timezone=True))
    last_error = mapped_column(Text)
    request_id = mapped_column(String(64))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Attachment(Base):
    __tablename__ = "attachment"
    __table_args__ = {"schema": "shared"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    owner_type = mapped_column(String(48))
    owner_id = mapped_column(String(64))
    file_name = mapped_column(String(255))
    content_type = mapped_column(String(128))
    size_bytes = mapped_column(BigInteger)
    storage_key = mapped_column(String(512))
    checksum_sha256 = mapped_column(String(64))
    uploaded_by = mapped_column(BigInteger)
    status = mapped_column(Text, server_default=text("'READY'"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Brand(Base):
    __tablename__ = "brand"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    code = mapped_column(String(32))
    name = mapped_column(String(64))
    logo_url = mapped_column(String(512))
    sort_order = mapped_column(Integer, server_default=text("0"))
    status = mapped_column(Text, server_default=text("'ACTIVE'"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Category(Base):
    __tablename__ = "category"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    parent_id = mapped_column(BigInteger)
    code = mapped_column(String(48))
    name = mapped_column(String(64))
    path = mapped_column(String(255), server_default=text("''"))
    depth = mapped_column(Integer, server_default=text("1"))
    sort_order = mapped_column(Integer, server_default=text("0"))
    icon_url = mapped_column(String(512))
    status = mapped_column(Text, server_default=text("'ACTIVE'"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Product(Base):
    __tablename__ = "product"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    spu_code = mapped_column(String(48))
    name = mapped_column(String(160))
    brand_id = mapped_column(BigInteger)
    category_id = mapped_column(BigInteger)
    product_line = mapped_column(String(48))
    model_code = mapped_column(String(48))
    subtitle = mapped_column(String(255))
    description_md = mapped_column(Text)
    highlights = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    spec_summary = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    warranty_summary = mapped_column(String(255))
    install_required = mapped_column(Boolean, server_default=text("false"))
    install_notes = mapped_column(Text)
    service_scope = mapped_column(String(255))
    currency = mapped_column(String(3), server_default=text("'CNY'"))
    min_price = mapped_column(Numeric(14, 2), server_default=text("0"))
    max_price = mapped_column(Numeric(14, 2), server_default=text("0"))
    status = mapped_column(Text, server_default=text("'DRAFT'"))
    published_at = mapped_column(DateTime(timezone=True))
    sort_order = mapped_column(Integer, server_default=text("0"))
    created_by = mapped_column(BigInteger)
    updated_by = mapped_column(BigInteger)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    version = mapped_column(Integer, server_default=text("0"))


class ProductMedia(Base):
    __tablename__ = "product_media"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    product_id = mapped_column(BigInteger)
    sku_id = mapped_column(BigInteger)
    media_type = mapped_column(Text, server_default=text("'IMAGE'"))
    url = mapped_column(String(512))
    alt_text = mapped_column(String(160))
    sort_order = mapped_column(Integer, server_default=text("0"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AttributeDefinition(Base):
    __tablename__ = "attribute_definition"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    category_id = mapped_column(BigInteger)
    code = mapped_column(String(48))
    name = mapped_column(String(64))
    data_type = mapped_column(Text, server_default=text("'TEXT'"))
    unit = mapped_column(String(16))
    is_spec = mapped_column(Boolean, server_default=text("false"))
    is_required = mapped_column(Boolean, server_default=text("false"))
    options = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    sort_order = mapped_column(Integer, server_default=text("0"))


class ProductAttributeValue(Base):
    __tablename__ = "product_attribute_value"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    product_id = mapped_column(BigInteger)
    attribute_id = mapped_column(BigInteger)
    value_text = mapped_column(String(255))


class Sku(Base):
    __tablename__ = "sku"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    product_id = mapped_column(BigInteger)
    sku_code = mapped_column(String(64))
    name = mapped_column(String(160))
    spec_summary = mapped_column(String(255))
    price = mapped_column(Numeric(14, 2))
    market_price = mapped_column(Numeric(14, 2))
    cost_price = mapped_column(Numeric(14, 2))
    barcode = mapped_column(String(64))
    weight_g = mapped_column(Integer)
    status = mapped_column(Text, server_default=text("'ON_SALE'"))
    sort_order = mapped_column(Integer, server_default=text("0"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    version = mapped_column(Integer, server_default=text("0"))


class SkuAttributeValue(Base):
    __tablename__ = "sku_attribute_value"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    sku_id = mapped_column(BigInteger)
    attribute_id = mapped_column(BigInteger)
    value_text = mapped_column(String(255))


class PriceChangeLog(Base):
    __tablename__ = "price_change_log"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    sku_id = mapped_column(BigInteger)
    old_price = mapped_column(Numeric(14, 2))
    new_price = mapped_column(Numeric(14, 2))
    reason = mapped_column(String(255))
    changed_by = mapped_column(BigInteger)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Warehouse(Base):
    __tablename__ = "warehouse"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    code = mapped_column(String(32))
    name = mapped_column(String(64))
    region = mapped_column(String(64))
    address = mapped_column(String(255))
    priority = mapped_column(Integer, server_default=text("100"))
    status = mapped_column(Text, server_default=text("'ACTIVE'"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    sku_id = mapped_column(BigInteger)
    warehouse_id = mapped_column(BigInteger)
    qty_available = mapped_column(Integer, server_default=text("0"))
    qty_reserved = mapped_column(Integer, server_default=text("0"))
    qty_in_transit = mapped_column(Integer, server_default=text("0"))
    safety_stock = mapped_column(Integer, server_default=text("0"))
    version = mapped_column(Integer, server_default=text("0"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class InventoryLedger(Base):
    __tablename__ = "inventory_ledger"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    sku_id = mapped_column(BigInteger)
    warehouse_id = mapped_column(BigInteger)
    change_type = mapped_column(Text)
    qty_delta = mapped_column(Integer)
    qty_after = mapped_column(Integer)
    qty_available_after = mapped_column(Integer)
    qty_reserved_after = mapped_column(Integer)
    ref_type = mapped_column(String(32))
    ref_id = mapped_column(String(64))
    operator_id = mapped_column(BigInteger)
    remark = mapped_column(String(255))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class InventoryReservation(Base):
    __tablename__ = "inventory_reservation"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    order_id = mapped_column(BigInteger)
    order_item_id = mapped_column(BigInteger)
    sku_id = mapped_column(BigInteger)
    warehouse_id = mapped_column(BigInteger)
    qty = mapped_column(Integer)
    status = mapped_column(Text, server_default=text("'ACTIVE'"))
    expires_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    released_at = mapped_column(DateTime(timezone=True))


class CustomerProfile(Base):
    __tablename__ = "customer_profile"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    user_id = mapped_column(BigInteger)
    nickname = mapped_column(String(64))
    real_name = mapped_column(String(64))
    gender = mapped_column(Text)
    birthday = mapped_column(Date)
    default_channel_id = mapped_column(BigInteger)
    tags = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    total_order_count = mapped_column(Integer, server_default=text("0"))
    total_paid_amount = mapped_column(Numeric(14, 2), server_default=text("0"))
    last_order_at = mapped_column(DateTime(timezone=True))
    remark = mapped_column(String(255))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class CustomerAddress(Base):
    __tablename__ = "customer_address"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    customer_id = mapped_column(BigInteger)
    receiver_name = mapped_column(String(64))
    receiver_phone = mapped_column(String(32))
    province = mapped_column(String(32))
    city = mapped_column(String(32))
    district = mapped_column(String(32))
    detail = mapped_column(String(255))
    postal_code = mapped_column(String(16))
    is_default = mapped_column(Boolean, server_default=text("false"))
    status = mapped_column(Text, server_default=text("'ACTIVE'"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Cart(Base):
    __tablename__ = "cart"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    customer_id = mapped_column(BigInteger)
    channel_account_id = mapped_column(BigInteger)
    status = mapped_column(Text, server_default=text("'OPEN'"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class CartItem(Base):
    __tablename__ = "cart_item"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    cart_id = mapped_column(BigInteger)
    sku_id = mapped_column(BigInteger)
    quantity = mapped_column(Integer)
    selected = mapped_column(Boolean, server_default=text("true"))
    added_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    order_no = mapped_column(String(32))
    channel_account_id = mapped_column(BigInteger)
    customer_id = mapped_column(BigInteger)
    source = mapped_column(Text, server_default=text("'OFFICIAL_MALL'"))
    external_order_no = mapped_column(String(64))
    currency = mapped_column(String(3), server_default=text("'CNY'"))
    goods_amount = mapped_column(Numeric(14, 2), server_default=text("0"))
    discount_amount = mapped_column(Numeric(14, 2), server_default=text("0"))
    shipping_amount = mapped_column(Numeric(14, 2), server_default=text("0"))
    payable_amount = mapped_column(Numeric(14, 2), server_default=text("0"))
    paid_amount = mapped_column(Numeric(14, 2), server_default=text("0"))
    refunded_amount = mapped_column(Numeric(14, 2), server_default=text("0"))
    status = mapped_column(Text, server_default=text("'CREATED'"))
    payment_status = mapped_column(Text, server_default=text("'UNPAID'"))
    fulfillment_status = mapped_column(Text, server_default=text("'UNSHIPPED'"))
    after_sales_status = mapped_column(Text, server_default=text("'NONE'"))
    receiver_name = mapped_column(String(64))
    receiver_phone = mapped_column(String(32))
    shipping_address = mapped_column(JSONB)
    address_id = mapped_column(BigInteger)
    buyer_remark = mapped_column(String(255))
    staff_remark = mapped_column(String(255))
    pay_deadline = mapped_column(DateTime(timezone=True))
    paid_at = mapped_column(DateTime(timezone=True))
    shipped_at = mapped_column(DateTime(timezone=True))
    completed_at = mapped_column(DateTime(timezone=True))
    cancelled_at = mapped_column(DateTime(timezone=True))
    cancel_reason = mapped_column(String(255))
    closed_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    version = mapped_column(Integer, server_default=text("0"))


class OrderItem(Base):
    __tablename__ = "order_item"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    order_id = mapped_column(BigInteger)
    product_id = mapped_column(BigInteger)
    sku_id = mapped_column(BigInteger)
    warehouse_id = mapped_column(BigInteger)
    spu_code = mapped_column(String(48))
    sku_code = mapped_column(String(64))
    product_name = mapped_column(String(160))
    sku_name = mapped_column(String(160))
    spec_summary = mapped_column(String(255))
    image_url = mapped_column(String(512))
    unit_price = mapped_column(Numeric(14, 2))
    quantity = mapped_column(Integer)
    goods_amount = mapped_column(Numeric(14, 2))
    discount_amount = mapped_column(Numeric(14, 2), server_default=text("0"))
    payable_amount = mapped_column(Numeric(14, 2))
    refunded_amount = mapped_column(Numeric(14, 2), server_default=text("0"))
    shipped_quantity = mapped_column(Integer, server_default=text("0"))
    returned_quantity = mapped_column(Integer, server_default=text("0"))
    item_status = mapped_column(Text, server_default=text("'NORMAL'"))
    after_sales_status = mapped_column(Text, server_default=text("'NONE'"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    order_id = mapped_column(BigInteger)
    field = mapped_column(Text)
    from_value = mapped_column(String(32))
    to_value = mapped_column(String(32))
    reason = mapped_column(String(255))
    operator_type = mapped_column(Text, server_default=text("'SYSTEM'"))
    operator_id = mapped_column(BigInteger)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Payment(Base):
    __tablename__ = "payment"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    payment_no = mapped_column(String(32))
    order_id = mapped_column(BigInteger)
    method = mapped_column(Text)
    amount = mapped_column(Numeric(14, 2))
    currency = mapped_column(String(3), server_default=text("'CNY'"))
    status = mapped_column(Text, server_default=text("'PENDING'"))
    channel_txn_no = mapped_column(String(64))
    pay_url = mapped_column(String(512))
    expires_at = mapped_column(DateTime(timezone=True))
    paid_at = mapped_column(DateTime(timezone=True))
    closed_at = mapped_column(DateTime(timezone=True))
    failure_code = mapped_column(String(48))
    failure_message = mapped_column(String(255))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    version = mapped_column(Integer, server_default=text("0"))


class PaymentCallbackLog(Base):
    __tablename__ = "payment_callback_log"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    method = mapped_column(Text)
    event_id = mapped_column(String(96))
    payment_no = mapped_column(String(32))
    signature_valid = mapped_column(Boolean, server_default=text("false"))
    processed = mapped_column(Boolean, server_default=text("false"))
    process_result = mapped_column(String(64))
    payload = mapped_column(JSONB)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Carrier(Base):
    __tablename__ = "carrier"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    code = mapped_column(String(32))
    name = mapped_column(String(64))
    tracking_url_template = mapped_column(String(255))
    status = mapped_column(Text, server_default=text("'ACTIVE'"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Shipment(Base):
    __tablename__ = "shipment"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    shipment_no = mapped_column(String(32))
    order_id = mapped_column(BigInteger)
    warehouse_id = mapped_column(BigInteger)
    carrier_id = mapped_column(BigInteger)
    tracking_no = mapped_column(String(64))
    status = mapped_column(Text, server_default=text("'PENDING'"))
    package_count = mapped_column(Integer, server_default=text("1"))
    receiver_name = mapped_column(String(64))
    receiver_phone = mapped_column(String(32))
    address_text = mapped_column(String(512))
    shipped_at = mapped_column(DateTime(timezone=True))
    delivered_at = mapped_column(DateTime(timezone=True))
    exception_note = mapped_column(String(255))
    created_by = mapped_column(BigInteger)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ShipmentItem(Base):
    __tablename__ = "shipment_item"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    shipment_id = mapped_column(BigInteger)
    order_item_id = mapped_column(BigInteger)
    quantity = mapped_column(Integer)


class TrackingEvent(Base):
    __tablename__ = "tracking_event"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    shipment_id = mapped_column(BigInteger)
    event_time = mapped_column(DateTime(timezone=True))
    status = mapped_column(String(32))
    description = mapped_column(String(255))
    location = mapped_column(String(128))
    raw = mapped_column(JSONB)
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AfterSalesApplication(Base):
    __tablename__ = "after_sales_application"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    application_no = mapped_column(String(32))
    order_id = mapped_column(BigInteger)
    customer_id = mapped_column(BigInteger)
    channel_account_id = mapped_column(BigInteger)
    type = mapped_column(Text)
    reason_code = mapped_column(String(48))
    reason_text = mapped_column(String(255))
    description = mapped_column(Text)
    evidence = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    expect_amount = mapped_column(Numeric(14, 2))
    approved_amount = mapped_column(Numeric(14, 2))
    status = mapped_column(Text, server_default=text("'SUBMITTED'"))
    need_return = mapped_column(Boolean, server_default=text("false"))
    return_carrier_id = mapped_column(BigInteger)
    return_tracking_no = mapped_column(String(64))
    reviewer_id = mapped_column(BigInteger)
    reviewed_at = mapped_column(DateTime(timezone=True))
    review_note = mapped_column(String(255))
    received_at = mapped_column(DateTime(timezone=True))
    completed_at = mapped_column(DateTime(timezone=True))
    closed_at = mapped_column(DateTime(timezone=True))
    sla_due_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    version = mapped_column(Integer, server_default=text("0"))


class AfterSalesItem(Base):
    __tablename__ = "after_sales_item"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    application_id = mapped_column(BigInteger)
    order_item_id = mapped_column(BigInteger)
    quantity = mapped_column(Integer)
    amount = mapped_column(Numeric(14, 2), server_default=text("0"))


class AfterSalesMessage(Base):
    __tablename__ = "after_sales_message"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    application_id = mapped_column(BigInteger)
    author_type = mapped_column(Text)
    author_id = mapped_column(BigInteger)
    content = mapped_column(Text)
    attachments = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    visible_to_customer = mapped_column(Boolean, server_default=text("true"))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Refund(Base):
    __tablename__ = "refund"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    refund_no = mapped_column(String(32))
    order_id = mapped_column(BigInteger)
    application_id = mapped_column(BigInteger)
    customer_id = mapped_column(BigInteger)
    method = mapped_column(Text, server_default=text("'ORIGINAL'"))
    amount = mapped_column(Numeric(14, 2))
    currency = mapped_column(String(3), server_default=text("'CNY'"))
    status = mapped_column(Text, server_default=text("'PENDING'"))
    reason = mapped_column(String(255))
    channel_refund_no = mapped_column(String(64))
    requested_by = mapped_column(BigInteger)
    approved_by = mapped_column(BigInteger)
    approved_at = mapped_column(DateTime(timezone=True))
    executed_at = mapped_column(DateTime(timezone=True))
    closed_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    version = mapped_column(Integer, server_default=text("0"))


class RefundAttempt(Base):
    __tablename__ = "refund_attempt"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    refund_id = mapped_column(BigInteger)
    attempt_no = mapped_column(Integer)
    status = mapped_column(Text)
    request_payload = mapped_column(JSONB)
    response_payload = mapped_column(JSONB)
    error_code = mapped_column(String(48))
    error_message = mapped_column(String(255))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Invoice(Base):
    __tablename__ = "invoice"
    __table_args__ = {"schema": "commerce"}
    id = mapped_column(BigInteger, primary_key=True)
    tenant_id = mapped_column(BigInteger)
    invoice_no = mapped_column(String(32))
    order_id = mapped_column(BigInteger)
    customer_id = mapped_column(BigInteger)
    type = mapped_column(Text, server_default=text("'ELECTRONIC'"))
    title_type = mapped_column(Text, server_default=text("'PERSONAL'"))
    title = mapped_column(String(128))
    tax_no = mapped_column(String(32))
    content = mapped_column(String(128), server_default=text("'\u5546\u54c1\u660e\u7ec6'"))
    amount = mapped_column(Numeric(14, 2))
    status = mapped_column(Text, server_default=text("'REQUESTED'"))
    file_url = mapped_column(String(512))
    issued_at = mapped_column(DateTime(timezone=True))
    voided_at = mapped_column(DateTime(timezone=True))
    remark = mapped_column(String(255))
    created_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    version = mapped_column(Integer, server_default=text("0"))


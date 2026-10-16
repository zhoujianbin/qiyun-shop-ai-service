-- 栖云智家 一期 开发种子数据（仅用于本机调试，密码为演示口令，上线前必须轮换）
SET client_min_messages = warning;
BEGIN;

INSERT INTO shared.tenant (id, code, name) VALUES (1, 'QIYUN', '栖云智家科技有限公司');

INSERT INTO shared.channel_account (id, tenant_id, code, name, platform_code, channel_type) VALUES
 (1, 1, 'OFFICIAL_MALL', '栖云智家官方商城', 'SELF_MALL', 'OFFICIAL_MALL'),
 (2, 1, 'TMALL', '天猫栖云智家官方旗舰店', 'TMALL', 'ECOMMERCE'),
 (3, 1, 'JD', '京东栖云智家自营旗舰店', 'JD', 'ECOMMERCE'),
 (4, 1, 'DOUYIN', '抖音栖云智家旗舰店', 'DOUYIN', 'ECOMMERCE'),
 (5, 1, 'STORE', '授权零售门店', 'OFFLINE', 'RETAIL');

INSERT INTO shared.app_permission (code, name, module) VALUES
 ('shop:product:read','查看商品','shop'),   ('shop:product:write','维护商品','shop'),
 ('shop:category:read','查看类目','shop'),  ('shop:category:write','维护类目','shop'),
 ('shop:inventory:read','查看库存','shop'), ('shop:inventory:write','调整库存','shop'),
 ('shop:order:read','查看订单','shop'),     ('shop:order:write','处理订单','shop'),
 ('shop:fulfillment:read','查看履约','shop'),('shop:fulfillment:write','发货与物流','shop'),
 ('shop:payment:read','查看支付','shop'),   ('shop:refund:read','查看退款','shop'),
 ('shop:refund:write','执行退款','shop'),   ('shop:aftersales:read','查看售后','shop'),
 ('shop:aftersales:review','审核售后','shop'),
 ('shop:invoice:read','查看发票','shop'),   ('shop:invoice:write','开具发票','shop'),
 ('shop:customer:read','查看客户','shop'),  ('shop:customer:write','维护客户','shop'),
 ('shop:report:read','查看报表','shop'),
 ('shared:staff:read','查看员工','shared'), ('shared:staff:write','维护员工','shared'),
 ('shared:channel:read','查看渠道','shared'),('shared:channel:write','维护渠道','shared'),
 ('shared:audit:read','查看审计','shared');

INSERT INTO shared.app_role (id, tenant_id, code, name, is_system, description) VALUES
 (1,1,'SUPER_ADMIN','企业管理员',true,'全部权限，仅初始化时创建'),
 (2,1,'ECOMMERCE_OPS','电商运营',true,'商品、类目、订单、履约、报表'),
 (3,1,'INVENTORY_MANAGER','库存管理员',true,'库存、仓库、商品只读'),
 (4,1,'AFTER_SALES','售后专员',true,'售后、退款、发票、订单只读'),
 (5,1,'FINANCE_VIEWER','财务只读',true,'支付、退款、发票、报表只读'),
 (6,1,'CS_SUPERVISOR','客服主管',true,'订单与售后只读，售后审核'),
 (7,1,'AUDITOR','只读审计',true,'全部模块只读');

INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT 1, id FROM shared.app_permission;
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT 2, id FROM shared.app_permission WHERE code IN
 ('shop:product:read','shop:product:write','shop:category:read','shop:category:write','shop:inventory:read',
  'shop:order:read','shop:order:write','shop:fulfillment:read','shop:fulfillment:write','shop:payment:read',
  'shop:aftersales:read','shop:invoice:read','shop:customer:read','shop:report:read','shared:channel:read');
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT 3, id FROM shared.app_permission WHERE code IN
 ('shop:product:read','shop:category:read','shop:inventory:read','shop:inventory:write','shop:order:read',
  'shop:fulfillment:read','shop:report:read');
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT 4, id FROM shared.app_permission WHERE code IN
 ('shop:order:read','shop:aftersales:read','shop:aftersales:review','shop:refund:read','shop:refund:write',
  'shop:invoice:read','shop:invoice:write','shop:customer:read','shop:fulfillment:read','shop:report:read');
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT 5, id FROM shared.app_permission WHERE code IN
 ('shop:order:read','shop:payment:read','shop:refund:read','shop:invoice:read','shop:report:read');
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT 6, id FROM shared.app_permission WHERE code IN
 ('shop:order:read','shop:aftersales:read','shop:aftersales:review','shop:customer:read','shop:report:read','shop:fulfillment:read');
INSERT INTO shared.app_role_permission (role_id, permission_id)
SELECT 7, id FROM shared.app_permission WHERE code LIKE '%:read';

INSERT INTO shared.app_user (id, tenant_id, party, username, email, phone, password_hash, display_name, is_super_admin) VALUES
 (1,1,'STAFF','admin',      'admin@qiyun.local',  '13800000001', crypt('Qiyun@2026#Dev', gen_salt('bf',10)), '企业管理员', true),
 (2,1,'STAFF','ops01',      'ops01@qiyun.local',  '13800000002', crypt('Qiyun@2026#Dev', gen_salt('bf',10)), '电商运营-王敏', false),
 (3,1,'STAFF','stock01',    'stock01@qiyun.local','13800000003', crypt('Qiyun@2026#Dev', gen_salt('bf',10)), '库存管理员-李强', false),
 (4,1,'STAFF','aftersales01','as01@qiyun.local',  '13800000004', crypt('Qiyun@2026#Dev', gen_salt('bf',10)), '售后专员-赵蕾', false),
 (5,1,'STAFF','finance01',  'fin01@qiyun.local',  '13800000005', crypt('Qiyun@2026#Dev', gen_salt('bf',10)), '财务只读-陈洁', false),
 (6,1,'STAFF','cs01',       'cs01@qiyun.local',   '13800000006', crypt('Qiyun@2026#Dev', gen_salt('bf',10)), '客服主管-孙昊', false);

INSERT INTO shared.app_user_role (user_id, role_id) VALUES (1,1),(2,2),(3,3),(4,4),(5,5),(6,6);
INSERT INTO shared.staff_channel_scope (user_id, channel_account_id) VALUES
 (2,1),(2,2),(2,3),(2,4),(3,1),(3,2),(3,3),(3,4),(4,1),(4,2),(4,3),(4,4),(6,1),(6,2),(6,3),(6,4);

INSERT INTO commerce.brand (id, tenant_id, code, name) VALUES
 (1,1,'QIYUN','栖云智家'), (2,1,'QIYUN_ECO','栖云智家生态配件');

INSERT INTO commerce.category (id, tenant_id, parent_id, code, name, path, depth, sort_order) VALUES
 (1,1,NULL,'SMART_LOCK','智能门锁','/1/',1,10),
 (2,1,NULL,'CAMERA','家用摄像头','/2/',1,20),
 (3,1,NULL,'ROBOT_VACUUM','清洁机器人','/3/',1,30),
 (4,1,NULL,'LIGHTING','智能灯具','/4/',1,40),
 (5,1,NULL,'GATEWAY','家庭网关','/5/',1,50),
 (6,1,NULL,'ACCESSORY','配件与耗材','/6/',1,60),
 (7,1,NULL,'CLOUD_SERVICE','云服务','/7/',1,70),
 (8,1,NULL,'INSTALL_SERVICE','安装与维修服务','/8/',1,80);

INSERT INTO commerce.attribute_definition (id, tenant_id, category_id, code, name, data_type, unit, is_spec, options) VALUES
 (1,1,1,'COLOR','颜色','ENUM',NULL,true,'["曜石黑","皓月银"]'),
 (2,1,1,'POWER','供电方式','ENUM',NULL,true,'["8节5号电池","锂电池"]'),
 (3,1,1,'PROTECT_LEVEL','防护等级','ENUM',NULL,true,'["IP52","IP65"]'),
 (4,1,5,'PROTOCOL','连接协议','ENUM',NULL,true,'["Zigbee 3.0","Wi-Fi 2.4G","蓝牙 Mesh"]'),
 (5,1,6,'FIT_MODEL','适配型号','TEXT',NULL,true,'[]');

INSERT INTO commerce.product (id, tenant_id, spu_code, name, brand_id, category_id, product_line, model_code, subtitle,
  spec_summary, warranty_summary, install_required, service_scope, min_price, max_price, status, published_at) VALUES
 (1,1,'SPU-QL-L3P','QL-L3P 智能门锁',1,1,'智能门锁','QL-L3P','3D人脸+指纹+密码，支持临时密码与门锁日志',
  '{"锁体":"标准6068锁体","供电":"8节5号电池","防护等级":"IP52","开锁方式":"人脸/指纹/密码/钥匙/NFC"}','整机保修2年，锁体与电子件按矩阵执行', true,'中国大陆上门安装（部分偏远地区除外）',1299.00,1599.00,'ON_SALE', now() - interval '60 days'),
 (2,1,'SPU-QC-C2G','QC-C2G 家用摄像头',1,2,'家用摄像头','QC-C2G','2K超清，360°云台，AI人形侦测',
  '{"分辨率":"2K","云台":"水平355°/垂直100°","夜视":"红外+全彩","供电":"Type-C 5V2A"}','整机保修1年', false,NULL,199.00,259.00,'ON_SALE', now() - interval '55 days'),
 (3,1,'SPU-QR-R5M','QR-R5M 扫地机器人',1,3,'清洁机器人','QR-R5M','激光导航，自动集尘，扫拖一体',
  '{"导航":"LDS激光","吸力":"5000Pa","集尘":"自动集尘","电池":"5200mAh"}','整机保修1年，电池保修6个月', false,NULL,1999.00,2399.00,'ON_SALE', now() - interval '50 days'),
 (4,1,'SPU-QT-L1C','QT-L1C 智能吸顶灯',1,4,'智能灯具','QT-L1C','无极调光调色，支持本地网关联动',
  '{"功率":"36W","色温":"2700K-6500K","协议":"蓝牙Mesh","尺寸":"Φ480mm"}','整机保修2年', true,'中国大陆上门安装（部分偏远地区除外）',399.00,459.00,'ON_SALE', now() - interval '45 days'),
 (5,1,'SPU-QH-G1','QH-G1 家庭网关',1,5,'家庭网关','QH-G1','Zigbee 3.0 + 蓝牙 Mesh 双模网关，支持离线自动化',
  '{"协议":"Zigbee 3.0/蓝牙Mesh","接入上限":"128台","网络":"RJ45+Wi-Fi","供电":"Type-C"}','整机保修2年', false,NULL,299.00,329.00,'ON_SALE', now() - interval '40 days'),
 (6,1,'SPU-ACC-BAT','QL-L3P 门锁电池包',2,6,'配件耗材','QL-BAT-01','原厂锂电池包，适配 QL-L3P',
  '{"适配型号":"QL-L3P","容量":"5000mAh"}','电池类耗材保修6个月', false,NULL,99.00,99.00,'ON_SALE', now() - interval '30 days'),
 (7,1,'SPU-ACC-FILTER','扫地机器人耗材套装（滤网+边刷+主刷）',2,6,'配件耗材','QR-FILTER-KIT','适配 QR-R5M 的耗材三件套',
  '{"适配型号":"QR-R5M","包含":"滤网×2 边刷×2 主刷×1"}','耗材无整机保修，质量问题7日内换新', false,NULL,129.00,129.00,'ON_SALE', now() - interval '25 days');

INSERT INTO commerce.sku (id, tenant_id, product_id, sku_code, name, spec_summary, price, market_price, cost_price, barcode, weight_g, status) VALUES
 (1,1,1,'SKU-QL-L3P-BK','QL-L3P 曜石黑','曜石黑／8节5号电池／IP52',1299.00,1599.00,880.00,'6900000000011',3200,'ON_SALE'),
 (2,1,1,'SKU-QL-L3P-SV','QL-L3P 皓月银','皓月银／锂电池／IP52',1399.00,1699.00,940.00,'6900000000012',3250,'ON_SALE'),
 (3,1,2,'SKU-QC-C2G-WH','QC-C2G 白色标准版','白色／2K／32G卡位',199.00,259.00,120.00,'6900000000021',420,'ON_SALE'),
 (4,1,2,'SKU-QC-C2G-WH-PRO','QC-C2G 白色增强版','白色／2K／128G卡位',259.00,299.00,160.00,'6900000000022',430,'ON_SALE'),
 (5,1,3,'SKU-QR-R5M-STD','QR-R5M 标准版','标准版／自动集尘',1999.00,2399.00,1350.00,'6900000000031',11800,'ON_SALE'),
 (6,1,3,'SKU-QR-R5M-PRO','QR-R5M 上下水版','上下水版／自动集尘',2399.00,2799.00,1650.00,'6900000000032',12300,'ON_SALE'),
 (7,1,4,'SKU-QT-L1C-36W','QT-L1C 36W 吸顶灯','36W／Φ480mm',399.00,459.00,240.00,'6900000000041',2100,'ON_SALE'),
 (8,1,5,'SKU-QH-G1-STD','QH-G1 家庭网关','标准版',299.00,329.00,180.00,'6900000000051',260,'ON_SALE'),
 (9,1,6,'SKU-ACC-BAT-01','QL-L3P 原厂电池包','5000mAh',99.00,99.00,45.00,'6900000000061',180,'ON_SALE'),
 (10,1,7,'SKU-ACC-FILTER-01','QR-R5M 耗材三件套','滤网2+边刷2+主刷1',129.00,129.00,52.00,'6900000000071',360,'ON_SALE');

INSERT INTO commerce.sku_attribute_value (sku_id, attribute_id, value_text) VALUES
 (1,1,'曜石黑'),(1,2,'8节5号电池'),(1,3,'IP52'),
 (2,1,'皓月银'),(2,2,'锂电池'),(2,3,'IP52'),
 (8,4,'Zigbee 3.0'),(9,5,'QL-L3P'),(10,5,'QR-R5M');

INSERT INTO commerce.warehouse (id, tenant_id, code, name, region, address, priority) VALUES
 (1,1,'WH-HZ-01','华东一号仓','华东','浙江省杭州市余杭区仓前街道1号',10),
 (2,1,'WH-GZ-02','华南仓','华南','广东省广州市白云区物流大道88号',20);

INSERT INTO commerce.inventory (tenant_id, sku_id, warehouse_id, qty_available, qty_reserved, qty_in_transit, safety_stock) VALUES
 (1,1,1,120,0,50,20),(1,1,2,40,0,0,20),
 (1,2,1,60,0,0,15),(1,2,2,18,0,0,20),
 (1,3,1,300,0,0,50),(1,3,2,120,0,0,50),
 (1,4,1,150,0,0,30),(1,4,2,45,0,0,30),
 (1,5,1,80,0,0,10),(1,5,2,25,0,0,10),
 (1,6,1,55,0,0,10),(1,6,2,12,0,0,10),
 (1,7,1,210,0,0,40),(1,7,2,60,0,0,40),
 (1,8,1,95,0,20,20),(1,8,2,8,0,0,20),
 (1,9,1,400,0,0,100),(1,9,2,150,0,0,100),
 (1,10,1,260,0,0,80),(1,10,2,30,0,0,80);

INSERT INTO commerce.carrier (id, tenant_id, code, name, tracking_url_template) VALUES
 (1,1,'SF','顺丰速运','https://www.sf-express.com/chn/sc/waybill/list?billNo={tracking_no}'),
 (2,1,'JD','京东物流','https://www.jdl.com/orderSearch?waybillCode={tracking_no}'),
 (3,1,'ZTO','中通快递','https://www.zto.com/express/expressCheck.html?txtBill={tracking_no}'),
 (4,1,'DBL','德邦快递','https://www.deppon.com/express/waybill?waybillNo={tracking_no}');

COMMIT;

-- 栖云智家 一期 开发种子数据（客户、购物车、订单、支付、履约、售后、退款、发票）
BEGIN;

INSERT INTO shared.app_user (id, tenant_id, party, username, email, phone, password_hash, display_name) VALUES
 (101,1,'CUSTOMER','buyer_zhang','zhang@example.com','13900000001', crypt('Qiyun@2026#Dev', gen_salt('bf',10)), '张三'),
 (102,1,'CUSTOMER','buyer_li',  'li@example.com',   '13900000002', crypt('Qiyun@2026#Dev', gen_salt('bf',10)), '李四'),
 (103,1,'CUSTOMER','buyer_wang','wang@example.com', '13900000003', crypt('Qiyun@2026#Dev', gen_salt('bf',10)), '王五');

INSERT INTO commerce.customer_profile (id, tenant_id, user_id, nickname, real_name, default_channel_id, total_order_count, total_paid_amount, last_order_at) VALUES
 (1,1,101,'张三','张三',1,2,2797.00, now() - interval '2 days'),
 (2,1,102,'李四','李四',2,1,1999.00, now() - interval '5 days'),
 (3,1,103,'王五','王五',1,1,399.00,  now() - interval '10 days');

INSERT INTO commerce.customer_address (id, tenant_id, customer_id, receiver_name, receiver_phone, province, city, district, detail, is_default) VALUES
 (1,1,1,'张三','13900000001','浙江省','杭州市','余杭区','文一西路 100 号 1 幢 1801 室', true),
 (2,1,1,'张三','13900000001','上海市','上海市','浦东新区','张江高科技园区 88 号 5 号楼', false),
 (3,1,2,'李四','13900000002','广东省','深圳市','南山区','科技园南路 9 号 A 座 3201', true),
 (4,1,3,'王五','13900000003','北京市','北京市','海淀区','上地信息路 5 号 2 号楼 606', true);

INSERT INTO commerce.cart (id, tenant_id, customer_id, channel_account_id, status)
VALUES (1,1,1,1,'OPEN');
INSERT INTO commerce.cart_item (tenant_id, cart_id, sku_id, quantity) VALUES
 (1,1,1,1),(1,1,9,2);

-- ---------- 订单 1：待付款（已锁定库存） ----------
INSERT INTO commerce.orders (id, tenant_id, order_no, channel_account_id, customer_id, source,
  goods_amount, discount_amount, shipping_amount, payable_amount, paid_amount, refunded_amount,
  status, payment_status, fulfillment_status, after_sales_status,
  receiver_name, receiver_phone, shipping_address, address_id, buyer_remark, pay_deadline, created_at)
VALUES (1,1,'QY20260101000001',1,1,'OFFICIAL_MALL',199.00,0.00,0.00,199.00,0.00,0.00,
  'PENDING_PAYMENT','UNPAID','UNSHIPPED','NONE','张三','13900000001',
  '{"province":"浙江省","city":"杭州市","district":"余杭区","detail":"文一西路 100 号 1 幢 1801 室"}'::jsonb,1,
  '工作日送货', now() + interval '25 minutes', now() - interval '5 minutes');
INSERT INTO commerce.order_item (id, tenant_id, order_id, product_id, sku_id, warehouse_id, spu_code, sku_code,
  product_name, sku_name, spec_summary, unit_price, quantity, goods_amount, discount_amount, payable_amount)
VALUES (1,1,1,2,3,1,'SPU-QC-C2G','SKU-QC-C2G-WH','QC-C2G 家用摄像头','QC-C2G 白色标准版','白色／2K／32G卡位',199.00,1,199.00,0.00,199.00);

INSERT INTO commerce.inventory_reservation (tenant_id, order_id, order_item_id, sku_id, warehouse_id, qty, status, expires_at)
VALUES (1,1,1,3,1,1,'ACTIVE', now() + interval '25 minutes');

-- ---------- 订单 2：已付款待发货 ----------
INSERT INTO commerce.orders (id, tenant_id, order_no, channel_account_id, customer_id, source,
  goods_amount, discount_amount, shipping_amount, payable_amount, paid_amount, refunded_amount,
  status, payment_status, fulfillment_status, after_sales_status,
  receiver_name, receiver_phone, shipping_address, address_id, pay_deadline, paid_at, created_at)
VALUES (2,1,'QY20260101000002',1,1,'OFFICIAL_MALL',2598.00,0.00,0.00,2598.00,2598.00,0.00,
  'PAID','PAID','UNSHIPPED','NONE','张三','13900000001',
  '{"province":"浙江省","city":"杭州市","district":"余杭区","detail":"文一西路 100 号 1 幢 1801 室"}'::jsonb,1,
  now() - interval '1 day', now() - interval '2 days', now() - interval '2 days 1 hour');
INSERT INTO commerce.order_item (id, tenant_id, order_id, product_id, sku_id, warehouse_id, spu_code, sku_code,
  product_name, sku_name, spec_summary, unit_price, quantity, goods_amount, discount_amount, payable_amount)
VALUES (2,1,2,1,1,1,'SPU-QL-L3P','SKU-QL-L3P-BK','QL-L3P 智能门锁','QL-L3P 曜石黑','曜石黑／8节5号电池／IP52',1299.00,2,2598.00,0.00,2598.00);
INSERT INTO commerce.inventory_reservation (tenant_id, order_id, order_item_id, sku_id, warehouse_id, qty, status)
VALUES (1,2,2,1,1,2,'ACTIVE');
INSERT INTO commerce.payment (id, tenant_id, payment_no, order_id, method, amount, status, channel_txn_no, paid_at, created_at)
VALUES (1,1,'PAY20260101000002',2,'MOCK',2598.00,'SUCCESS','MOCK-TXN-0001', now() - interval '2 days', now() - interval '2 days');

-- ---------- 订单 3：已发货 ----------
INSERT INTO commerce.orders (id, tenant_id, order_no, channel_account_id, customer_id, source,
  goods_amount, discount_amount, shipping_amount, payable_amount, paid_amount, refunded_amount,
  status, payment_status, fulfillment_status, after_sales_status,
  receiver_name, receiver_phone, shipping_address, address_id, pay_deadline, paid_at, shipped_at, created_at)
VALUES (3,1,'QY20260101000003',2,2,'ECOMMERCE',1999.00,0.00,0.00,1999.00,1999.00,0.00,
  'SHIPPED','PAID','SHIPPED','NONE','李四','13900000002',
  '{"province":"广东省","city":"深圳市","district":"南山区","detail":"科技园南路 9 号 A 座 3201"}'::jsonb,3,
  now() - interval '6 days', now() - interval '6 days', now() - interval '4 days', now() - interval '6 days 2 hours');
INSERT INTO commerce.order_item (id, tenant_id, order_id, product_id, sku_id, warehouse_id, spu_code, sku_code,
  product_name, sku_name, spec_summary, unit_price, quantity, goods_amount, discount_amount, payable_amount, shipped_quantity)
VALUES (3,1,3,3,5,1,'SPU-QR-R5M','SKU-QR-R5M-STD','QR-R5M 扫地机器人','QR-R5M 标准版','标准版／自动集尘',1999.00,1,1999.00,0.00,1999.00,1);
INSERT INTO commerce.payment (id, tenant_id, payment_no, order_id, method, amount, status, channel_txn_no, paid_at, created_at)
VALUES (2,1,'PAY20260101000003',3,'MOCK',1999.00,'SUCCESS','MOCK-TXN-0002', now() - interval '6 days', now() - interval '6 days');
INSERT INTO commerce.shipment (id, tenant_id, shipment_no, order_id, warehouse_id, carrier_id, tracking_no, status,
  receiver_name, receiver_phone, address_text, shipped_at, created_by, created_at)
VALUES (1,1,'SHP20260101000001',3,1,1,'SF1234567890123','IN_TRANSIT','李四','13900000002',
  '广东省深圳市南山区科技园南路 9 号 A 座 3201', now() - interval '4 days', 2, now() - interval '4 days');
INSERT INTO commerce.shipment_item (shipment_id, order_item_id, quantity) VALUES (1,3,1);
INSERT INTO commerce.tracking_event (tenant_id, shipment_id, event_time, status, description, location) VALUES
 (1,1, now() - interval '4 days', 'PICKED_UP','顺丰速运已揽收','杭州市余杭区'),
 (1,1, now() - interval '3 days 20 hours','IN_TRANSIT','快件已到达杭州转运中心','杭州市'),
 (1,1, now() - interval '2 days','IN_TRANSIT','快件已到达深圳转运中心','深圳市'),
 (1,1, now() - interval '1 day','IN_TRANSIT','快件派送中，请保持电话畅通','深圳市南山区');

-- ---------- 订单 4：已完成 + 部分退款售后 ----------
INSERT INTO commerce.orders (id, tenant_id, order_no, channel_account_id, customer_id, source,
  goods_amount, discount_amount, shipping_amount, payable_amount, paid_amount, refunded_amount,
  status, payment_status, fulfillment_status, after_sales_status,
  receiver_name, receiver_phone, shipping_address, address_id, pay_deadline, paid_at, shipped_at, completed_at, created_at)
VALUES (4,1,'QY20260101000004',1,3,'OFFICIAL_MALL',399.00,0.00,0.00,399.00,399.00,100.00,
  'COMPLETED','PARTIAL_REFUNDED','DELIVERED','COMPLETED','王五','13900000003',
  '{"province":"北京市","city":"北京市","district":"海淀区","detail":"上地信息路 5 号 2 号楼 606"}'::jsonb,4,
  now() - interval '12 days', now() - interval '12 days', now() - interval '10 days', now() - interval '3 days', now() - interval '12 days 1 hour');
INSERT INTO commerce.order_item (id, tenant_id, order_id, product_id, sku_id, warehouse_id, spu_code, sku_code,
  product_name, sku_name, spec_summary, unit_price, quantity, goods_amount, discount_amount, payable_amount,
  refunded_amount, shipped_quantity, item_status, after_sales_status)
VALUES (4,1,4,4,7,1,'SPU-QT-L1C','SKU-QT-L1C-36W','QT-L1C 智能吸顶灯','QT-L1C 36W 吸顶灯','36W／Φ480mm',399.00,1,399.00,0.00,399.00,
  100.00,1,'NORMAL','COMPLETED');
INSERT INTO commerce.payment (id, tenant_id, payment_no, order_id, method, amount, status, channel_txn_no, paid_at, created_at)
VALUES (3,1,'PAY20260101000004',4,'MOCK',399.00,'SUCCESS','MOCK-TXN-0003', now() - interval '12 days', now() - interval '12 days');

INSERT INTO commerce.after_sales_application (id, tenant_id, application_no, order_id, customer_id, channel_account_id,
  type, reason_code, reason_text, description, status, need_return, approved_amount, reviewer_id, reviewed_at,
  completed_at, sla_due_at, created_at)
VALUES (1,1,'AS20260101000001',4,3,1,'REFUND_ONLY','QUALITY_ISSUE_LIGHT_FLICKER','灯具频闪',
  '安装后出现持续频闪，已按客服指引录像留证，协商部分退款 100 元自行调整安装位置。','COMPLETED', false, 100.00,
  4, now() - interval '8 days', now() - interval '6 days', now() - interval '9 days', now() - interval '9 days');
INSERT INTO commerce.after_sales_item (application_id, order_item_id, quantity, amount) VALUES (1,4,1,100.00);
INSERT INTO commerce.after_sales_message (application_id, author_type, author_id, content, visible_to_customer) VALUES
 (1,'CUSTOMER',103,'灯装好后一直闪，晚上更明显。', true),
 (1,'STAFF',4,'已收到录屏证据，经核实属于可协商处理范围，为您申请部分退款 100 元。', true),
 (1,'SYSTEM',NULL,'退款已到账，售后单关闭。', true);

INSERT INTO commerce.refund (id, tenant_id, refund_no, order_id, application_id, customer_id, method, amount, status,
  reason, channel_refund_no, requested_by, approved_by, approved_at, executed_at, created_at, updated_at)
VALUES (1,1,'REF20260101000001',4,1,3,'ORIGINAL',100.00,'SUCCESS','灯具频闪协商部分退款','MOCK-RF-0001',
  4,4, now() - interval '8 days', now() - interval '6 days', now() - interval '9 days', now() - interval '6 days');
INSERT INTO commerce.refund_attempt (refund_id, attempt_no, status, request_payload, response_payload, created_at)
VALUES (1,1,'SUCCESS','{"amount":100.00,"method":"ORIGINAL"}'::jsonb,'{"channel_refund_no":"MOCK-RF-0001"}'::jsonb, now() - interval '6 days');

INSERT INTO commerce.invoice (id, tenant_id, invoice_no, order_id, customer_id, type, title_type, title, tax_no, content, amount, status, issued_at)
VALUES (1,1,'INV20260101000001',3,2,'ELECTRONIC','COMPANY','深圳市某某科技有限公司','91440300MA5XXXXXXX','商品明细',1999.00,'ISSUED', now() - interval '5 days'),
       (2,1,NULL,2,1,'ELECTRONIC','PERSONAL','张三',NULL,'商品明细',2598.00,'REQUESTED',NULL);

-- ---------- 订单状态历史 ----------
INSERT INTO commerce.order_status_history (tenant_id, order_id, field, from_value, to_value, reason, operator_type, operator_id, created_at) VALUES
 (1,1,'status',NULL,'CREATED','创建订单','CUSTOMER',101, now() - interval '5 minutes'),
 (1,1,'status','CREATED','PENDING_PAYMENT','等待支付','SYSTEM',NULL, now() - interval '5 minutes'),
 (1,2,'status',NULL,'CREATED','创建订单','CUSTOMER',101, now() - interval '2 days 1 hour'),
 (1,2,'status','CREATED','PENDING_PAYMENT','等待支付','SYSTEM',NULL, now() - interval '2 days 1 hour'),
 (1,2,'payment_status','UNPAID','PAID','支付成功','SYSTEM',NULL, now() - interval '2 days'),
 (1,2,'status','PENDING_PAYMENT','PAID','支付成功','SYSTEM',NULL, now() - interval '2 days'),
 (1,3,'payment_status','UNPAID','PAID','支付成功','SYSTEM',NULL, now() - interval '6 days'),
 (1,3,'status','PENDING_PAYMENT','PAID','支付成功','SYSTEM',NULL, now() - interval '6 days'),
 (1,3,'fulfillment_status','UNSHIPPED','SHIPPED','仓库发货','STAFF',2, now() - interval '4 days'),
 (1,3,'status','PAID','SHIPPED','订单已发货','SYSTEM',NULL, now() - interval '4 days'),
 (1,4,'fulfillment_status','SHIPPED','DELIVERED','客户签收','SYSTEM',NULL, now() - interval '10 days'),
 (1,4,'status','SHIPPED','COMPLETED','订单完成','SYSTEM',NULL, now() - interval '3 days'),
 (1,4,'after_sales_status','NONE','COMPLETED','部分退款完成','STAFF',4, now() - interval '6 days'),
 (1,4,'payment_status','PAID','PARTIAL_REFUNDED','部分退款','SYSTEM',NULL, now() - interval '6 days');

-- ---------- 库存流水（与上方库存数量保持一致的演示数据） ----------
INSERT INTO commerce.inventory_ledger (tenant_id, sku_id, warehouse_id, change_type, qty_delta, qty_after,
  qty_available_after, qty_reserved_after, ref_type, ref_id, operator_id, remark, created_at) VALUES
 (1,3,1,'RESERVE',   0,300,299,1,'ORDER','QY20260101000001',NULL,'下单锁定', now() - interval '5 minutes'),
 (1,1,1,'RESERVE',   0,120,118,2,'ORDER','QY20260101000002',NULL,'下单锁定', now() - interval '2 days 1 hour'),
 (1,5,1,'RESERVE',   0, 80, 79,1,'ORDER','QY20260101000003',NULL,'下单锁定', now() - interval '6 days 2 hours'),
 (1,5,1,'SALE_OUT', -1, 79, 79,0,'SHIPMENT','SHP20260101000001',2,'发货出库', now() - interval '4 days'),
 (1,7,1,'RESERVE',   0,210,209,1,'ORDER','QY20260101000004',NULL,'下单锁定', now() - interval '12 days 1 hour'),
 (1,7,1,'SALE_OUT', -1,209,209,0,'SHIPMENT','SHP20260101000004',2,'发货出库', now() - interval '10 days');

UPDATE commerce.inventory SET qty_available = 299, qty_reserved = 1 WHERE sku_id = 3 AND warehouse_id = 1;
UPDATE commerce.inventory SET qty_available = 118, qty_reserved = 2 WHERE sku_id = 1 AND warehouse_id = 1;
UPDATE commerce.inventory SET qty_available = 79,  qty_reserved = 0 WHERE sku_id = 5 AND warehouse_id = 1;
UPDATE commerce.inventory SET qty_available = 209, qty_reserved = 0 WHERE sku_id = 7 AND warehouse_id = 1;

-- ---------- 修正自增序列 ----------
DO $seed$
DECLARE r record;
BEGIN
  FOR r IN SELECT c.table_schema AS ts, c.table_name AS tn, c.column_name AS cn
           FROM information_schema.columns c
           WHERE c.is_identity = 'YES' AND c.table_schema IN ('shared','commerce','knowledge') LOOP
    EXECUTE format('SELECT setval(pg_get_serial_sequence(%L,%L), COALESCE((SELECT max(%I) FROM %I.%I),0)+1, false)',
                   r.ts||'.'||r.tn, r.cn, r.cn, r.ts, r.tn);
  END LOOP;
END $seed$;

COMMIT;

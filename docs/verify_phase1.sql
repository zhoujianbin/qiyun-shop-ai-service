
\pset pager off
\echo '===== 1. 结构与扩展 ====='
SELECT current_database() AS db,
       (SELECT count(*) FROM pg_tables WHERE schemaname IN ('shared','commerce','knowledge')) AS tables,
       (SELECT count(*) FROM pg_indexes WHERE schemaname IN ('shared','commerce','knowledge')) AS indexes,
       (SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
         WHERE n.nspname IN ('shared','commerce','knowledge') AND c.contype='f') AS foreign_keys,
       (SELECT count(*) FROM pg_views WHERE schemaname='commerce') AS views,
       (SELECT extversion FROM pg_extension WHERE extname='vector') AS pgvector,
       (SELECT extversion FROM pg_extension WHERE extname='pg_trgm') AS pg_trgm;

\echo '===== 2. 业务一致性 ====='
\echo '-- 锁定数量与有效预占是否一致（应为 0）'
SELECT count(*) AS reservation_mismatch
FROM commerce.inventory i
WHERE i.qty_reserved <> COALESCE((SELECT sum(r.qty) FROM commerce.inventory_reservation r
        WHERE r.sku_id=i.sku_id AND r.warehouse_id=i.warehouse_id AND r.status='ACTIVE'),0);

\echo '-- 最新库存流水总量是否等于当前在库总量（应为 0）'
SELECT count(*) AS ledger_mismatch
FROM commerce.inventory i
JOIN LATERAL (SELECT l.qty_after FROM commerce.inventory_ledger l
              WHERE l.sku_id=i.sku_id AND l.warehouse_id=i.warehouse_id
              ORDER BY l.created_at DESC, l.id DESC LIMIT 1) l ON true
WHERE l.qty_after <> i.qty_available + i.qty_reserved;

\echo '-- 订单金额公式、退款上限（应为 0）'
SELECT count(*) AS amount_violation FROM commerce.orders
WHERE payable_amount <> goods_amount - discount_amount + shipping_amount OR refunded_amount > paid_amount;

\echo '-- 库存预警视图'
SELECT sku_code, warehouse_name, qty_available, qty_reserved, safety_stock, sellable_qty
FROM commerce.v_inventory_alert ORDER BY sku_code, warehouse_name;

\echo '-- 销售日汇总视图'
SELECT stat_date, channel_account_id, order_count, paid_order_count, payable_amount, paid_amount, refunded_amount
FROM commerce.v_sales_daily ORDER BY stat_date, channel_account_id;

\echo '-- 售后 SLA 视图'
SELECT status, application_count, overdue_count, round(avg_hours::numeric,2) AS avg_hours
FROM commerce.v_after_sales_sla ORDER BY status;

\echo '-- 待付款订单（含支付截止时间）'
SELECT order_no, status, payment_status, payable_amount, pay_deadline
FROM commerce.orders WHERE status IN ('CREATED','PENDING_PAYMENT') ORDER BY pay_deadline;

\echo '===== 3. 约束负例（每条都必须报错） ====='
DO $verify$
DECLARE
  tests text[][] := ARRAY[
    ['负库存被拒绝',        'UPDATE commerce.inventory SET qty_available = -1 WHERE sku_id = 1 AND warehouse_id = 1'],
    ['订单金额公式被拒绝',  'UPDATE commerce.orders SET payable_amount = payable_amount + 1 WHERE id = 1'],
    ['非法订单状态被拒绝',  'UPDATE commerce.orders SET status = ''DONE'' WHERE id = 1'],
    ['退款超过已支付被拒绝','UPDATE commerce.orders SET refunded_amount = paid_amount + 1 WHERE id = 2'],
    ['非法支付状态被拒绝',  'UPDATE commerce.payment SET status = ''OK'' WHERE id = 1'],
    ['重复渠道流水号被拒绝','INSERT INTO commerce.payment (tenant_id,payment_no,order_id,method,amount,status,channel_txn_no) VALUES (1,''PAY-DUP'',2,''MOCK'',1.00,''SUCCESS'',''MOCK-TXN-0001'')'],
    ['重复运单号被拒绝',    'INSERT INTO commerce.shipment (tenant_id,shipment_no,order_id,carrier_id,tracking_no,receiver_name,receiver_phone,address_text) VALUES (1,''SHP-DUP'',3,1,''SF1234567890123'',''李四'',''13900000002'',''x'')'],
    ['零金额退款被拒绝',    'INSERT INTO commerce.refund (tenant_id,refund_no,order_id,customer_id,amount,status) VALUES (1,''REF-DUP'',2,1,0,''PENDING'')'],
    ['售后需退货状态约束',  'INSERT INTO commerce.after_sales_application (tenant_id,application_no,order_id,customer_id,channel_account_id,type,reason_code,status,need_return) VALUES (1,''AS-DUP'',2,1,1,''RETURN_REFUND'',''X'',''SUBMITTED'',true)'],
    ['重复默认地址被拒绝',  'UPDATE commerce.customer_address SET is_default = true WHERE id = 2'],
    ['库存流水零变动被拒绝','INSERT INTO commerce.inventory_ledger (tenant_id,sku_id,warehouse_id,change_type,qty_delta,qty_after,qty_available_after,qty_reserved_after) VALUES (1,3,1,''SALE_OUT'',0,300,300,0)'],
    ['附件大小上限被拒绝',  'INSERT INTO shared.attachment (tenant_id,owner_type,file_name,content_type,size_bytes,storage_key,checksum_sha256) VALUES (1,''ORDER'',''a.png'',''image/png'',0,''k'',''c'')'],
    ['企业发票必须带税号',  'INSERT INTO commerce.invoice (tenant_id,order_id,customer_id,type,title_type,title,amount) VALUES (1,2,1,''ELECTRONIC'',''COMPANY'',''某某公司'',10.00)'],
    ['孤儿订单项被拒绝',    'INSERT INTO commerce.order_item (tenant_id,order_id,product_id,sku_id,spu_code,sku_code,product_name,sku_name,unit_price,quantity,goods_amount,payable_amount) VALUES (1,999999,1,1,''S'',''K'',''P'',''N'',1.00,1,1.00,1.00)'],
    ['向量维度不匹配被拒绝','SELECT ''[1,2,3]''::vector(1024)'],
    ['非法渠道类型被拒绝',  'INSERT INTO shared.channel_account (tenant_id,code,name,platform_code,channel_type) VALUES (1,''BAD'',''bad'',''x'',''WEBSITE'')'],
    ['员工用户名重复被拒绝','INSERT INTO shared.app_user (tenant_id,party,username,password_hash,display_name) VALUES (1,''STAFF'',''admin'',''x'',''dup'')']
  ];
  i int; ok boolean; msg text; pass int := 0; fail int := 0;
BEGIN
  FOR i IN 1..array_length(tests,1) LOOP
    BEGIN
      EXECUTE tests[i][2];
      ok := false; msg := '未报错（不可接受）';
    EXCEPTION WHEN others THEN
      ok := true; msg := SQLSTATE || ' ' || left(replace(SQLERRM, E'\n', ' '), 70);
    END;
    IF ok THEN pass := pass + 1; ELSE fail := fail + 1; END IF;
    RAISE NOTICE '% | % | %', rpad(tests[i][1], 22), CASE WHEN ok THEN 'PASS' ELSE 'FAIL' END, msg;
  END LOOP;
  RAISE NOTICE '约束负例汇总: PASS=% FAIL=%', pass, fail;
END $verify$;

\echo '===== 4. 端到端下单-支付-发货-签收-退款（事务内验证后回滚） ====='
BEGIN;
DO $e2e$
DECLARE
  v_sku bigint := 3; v_wh bigint := 1; v_qty int := 2;
  v_goods numeric(14,2) := 398.00; v_discount numeric(14,2) := 8.00; v_shipping numeric(14,2) := 10.00;
  v_payable numeric(14,2) := 400.00;
  v_order_id bigint; v_item_id bigint; v_pay_id bigint; v_ship_id bigint; v_app bigint; v_refund bigint;
  v_avail_before int; v_avail int; v_reserved int; v_affected int;
  v_pay_status text; v_order_status text; v_refunded numeric(14,2);
BEGIN
  SELECT qty_available, qty_reserved INTO v_avail_before, v_reserved
    FROM commerce.inventory WHERE sku_id=v_sku AND warehouse_id=v_wh;

  INSERT INTO commerce.orders (tenant_id, order_no, channel_account_id, customer_id, source,
      goods_amount, discount_amount, shipping_amount, payable_amount, status, payment_status,
      receiver_name, receiver_phone, shipping_address, address_id, pay_deadline)
  VALUES (1, 'QY-TEST-' || to_char(now(),'MMDDHH24MISS'), 1, 1, 'OFFICIAL_MALL',
      v_goods, v_discount, v_shipping, v_payable, 'PENDING_PAYMENT', 'UNPAID',
      '张三', '13900000001', '{"detail":"测试地址"}'::jsonb, 1, now() + interval '30 minutes')
  RETURNING id INTO v_order_id;

  INSERT INTO commerce.order_item (tenant_id, order_id, product_id, sku_id, warehouse_id, spu_code, sku_code,
      product_name, sku_name, unit_price, quantity, goods_amount, discount_amount, payable_amount)
  VALUES (1, v_order_id, 2, v_sku, v_wh, 'SPU-QC-C2G', 'SKU-QC-C2G-WH', 'QC-C2G 家用摄像头', 'QC-C2G 白色标准版',
      199.00, v_qty, v_goods, v_discount, v_goods - v_discount)
  RETURNING id INTO v_item_id;

  UPDATE commerce.inventory SET qty_available = qty_available - v_qty, qty_reserved = qty_reserved + v_qty,
         version = version + 1
   WHERE sku_id = v_sku AND warehouse_id = v_wh AND qty_available >= v_qty;
  GET DIAGNOSTICS v_affected = ROW_COUNT;
  RAISE NOTICE '% | 锁库存影响行数=% (期望 1)', rpad('1 锁库存', 22), v_affected;

  INSERT INTO commerce.inventory_reservation (tenant_id, order_id, order_item_id, sku_id, warehouse_id, qty, status, expires_at)
  VALUES (1, v_order_id, v_item_id, v_sku, v_wh, v_qty, 'ACTIVE', now() + interval '30 minutes');

  SELECT qty_available, qty_reserved INTO v_avail, v_reserved FROM commerce.inventory WHERE sku_id=v_sku AND warehouse_id=v_wh;
  RAISE NOTICE '% | available % -> % , reserved %', rpad('2 库存变化', 22), v_avail_before, v_avail, v_reserved;
  INSERT INTO commerce.inventory_ledger (tenant_id, sku_id, warehouse_id, change_type, qty_delta, qty_after,
      qty_available_after, qty_reserved_after, ref_type, ref_id, remark)
  VALUES (1, v_sku, v_wh, 'RESERVE', 0, v_avail + v_reserved, v_avail, v_reserved, 'ORDER', v_order_id::text, '下单锁定');

  INSERT INTO commerce.payment (tenant_id, payment_no, order_id, method, amount, status, expires_at)
  VALUES (1, 'PAY-TEST-' || v_order_id, v_order_id, 'MOCK', v_payable, 'PENDING', now() + interval '30 minutes')
  RETURNING id INTO v_pay_id;

  UPDATE commerce.payment SET status='SUCCESS', channel_txn_no='MOCK-TXN-TEST-' || v_order_id, paid_at=now()
   WHERE id=v_pay_id AND status='PENDING';
  GET DIAGNOSTICS v_affected = ROW_COUNT;
  RAISE NOTICE '% | 首次回调影响行数=% (期望 1)', rpad('3 支付回调', 22), v_affected;

  UPDATE commerce.payment SET status='SUCCESS', paid_at=now() WHERE id=v_pay_id AND status='PENDING';
  GET DIAGNOSTICS v_affected = ROW_COUNT;
  RAISE NOTICE '% | 重复回调影响行数=% (期望 0)', rpad('4 回调幂等', 22), v_affected;

  UPDATE commerce.orders SET status='PAID', payment_status='PAID', paid_amount=v_payable, paid_at=now()
   WHERE id=v_order_id;

  INSERT INTO commerce.shipment (tenant_id, shipment_no, order_id, warehouse_id, carrier_id, tracking_no,
      status, receiver_name, receiver_phone, address_text, shipped_at, created_by)
  VALUES (1, 'SHP-TEST-' || v_order_id, v_order_id, v_wh, 1, 'SF-TEST-' || v_order_id, 'PICKED_UP',
      '张三', '13900000001', '测试地址', now(), 2) RETURNING id INTO v_ship_id;
  INSERT INTO commerce.shipment_item (shipment_id, order_item_id, quantity) VALUES (v_ship_id, v_item_id, v_qty);

  UPDATE commerce.inventory SET qty_reserved = qty_reserved - v_qty, version = version + 1
   WHERE sku_id=v_sku AND warehouse_id=v_wh AND qty_reserved >= v_qty;
  GET DIAGNOSTICS v_affected = ROW_COUNT;
  SELECT qty_available, qty_reserved INTO v_avail, v_reserved FROM commerce.inventory WHERE sku_id=v_sku AND warehouse_id=v_wh;
  INSERT INTO commerce.inventory_ledger (tenant_id, sku_id, warehouse_id, change_type, qty_delta, qty_after,
      qty_available_after, qty_reserved_after, ref_type, ref_id, remark)
  VALUES (1, v_sku, v_wh, 'SALE_OUT', -v_qty, v_avail + v_reserved, v_avail, v_reserved, 'SHIPMENT', v_ship_id::text, '发货出库');
  UPDATE commerce.order_item SET shipped_quantity = v_qty WHERE id = v_item_id;
  UPDATE commerce.orders SET status='SHIPPED', fulfillment_status='SHIPPED', shipped_at=now() WHERE id=v_order_id;
  RAISE NOTICE '% | 出库影响行数=%, 剩余锁定=%', rpad('5 发货出库', 22), v_affected, v_reserved;

  INSERT INTO commerce.tracking_event (tenant_id, shipment_id, event_time, status, description, location)
  VALUES (1, v_ship_id, now(), 'DELIVERED', '已签收', '测试地址');
  UPDATE commerce.shipment SET status='DELIVERED', delivered_at=now() WHERE id=v_ship_id;
  UPDATE commerce.orders SET status='COMPLETED', fulfillment_status='DELIVERED', completed_at=now() WHERE id=v_order_id;

  INSERT INTO commerce.after_sales_application (tenant_id, application_no, order_id, customer_id, channel_account_id,
      type, reason_code, description, status, need_return, approved_amount, reviewer_id, reviewed_at, completed_at, sla_due_at)
  VALUES (1, 'AS-TEST-' || v_order_id, v_order_id, 1, 1, 'RETURN_REFUND', 'QUALITY_ISSUE', '测试售后',
      'COMPLETED', false, v_payable, 4, now(), now(), now() + interval '1 day') RETURNING id INTO v_app;

  INSERT INTO commerce.refund (tenant_id, refund_no, order_id, application_id, customer_id, method, amount, status,
      approved_by, approved_at, executed_at)
  VALUES (1, 'REF-TEST-' || v_order_id, v_order_id, v_app, 1, 'ORIGINAL', v_payable, 'SUCCESS', 4, now(), now())
  RETURNING id INTO v_refund;
  INSERT INTO commerce.refund_attempt (refund_id, attempt_no, status, request_payload, response_payload)
  VALUES (v_refund, 1, 'SUCCESS', '{"amount":400.00}'::jsonb, '{"channel_refund_no":"MOCK-RF-TEST"}'::jsonb);

  UPDATE commerce.orders SET refunded_amount = v_payable, payment_status='REFUNDED', after_sales_status='COMPLETED'
   WHERE id = v_order_id;
  UPDATE commerce.order_item SET refunded_amount = v_payable, item_status='REFUNDED', after_sales_status='COMPLETED'
   WHERE id = v_item_id;

  SELECT status, payment_status, refunded_amount INTO v_order_status, v_pay_status, v_refunded
    FROM commerce.orders WHERE id = v_order_id;
  RAISE NOTICE '% | status=% payment=% refunded=%', rpad('6 退款完成', 22), v_order_status, v_pay_status, v_refunded;
  RAISE NOTICE '% | 账实一致=%', rpad('7 校验', 22),
    (v_refunded <= v_payable AND v_order_status='COMPLETED' AND v_pay_status='REFUNDED');
END $e2e$;
ROLLBACK;

\echo '===== 5. 关键索引命中检查（EXPLAIN） ====='
EXPLAIN (COSTS OFF) SELECT * FROM commerce.orders WHERE customer_id = 1 ORDER BY created_at DESC LIMIT 10;
EXPLAIN (COSTS OFF) SELECT * FROM commerce.orders WHERE tenant_id = 1 AND channel_account_id = 1 AND status = 'PAID' ORDER BY created_at DESC LIMIT 10;
EXPLAIN (COSTS OFF) SELECT * FROM commerce.product WHERE name ILIKE '%智能门锁%';

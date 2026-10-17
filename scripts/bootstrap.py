"""栖云智家一期测试数据生成：企业基础、商品（依据企业知识库产品主档）、库存、客户、订单与售后。"""
import random
from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models import (
    AppPermission, AppRole, AppRolePermission, AppUser, AppUserRole, AttributeDefinition, Brand, Carrier,
    Category, ChannelAccount, CustomerAddress, CustomerProfile, Inventory, Product, ProductMedia, Sku,
    StaffChannelScope, Tenant, Warehouse,
)
from app.services import aftersales, cart, catalog, customer, fulfillment, invoice, order, payment
from app.services.common import now

DEV_PASSWORD = "Qiyun@2026#Dev"

PERMISSIONS = [
    ("shop:product:read", "查看商品", "shop"), ("shop:product:write", "维护商品", "shop"),
    ("shop:category:read", "查看类目", "shop"), ("shop:category:write", "维护类目", "shop"),
    ("shop:inventory:read", "查看库存", "shop"), ("shop:inventory:write", "调整库存", "shop"),
    ("shop:order:read", "查看订单", "shop"), ("shop:order:write", "处理订单", "shop"),
    ("shop:fulfillment:read", "查看履约", "shop"), ("shop:fulfillment:write", "发货与物流", "shop"),
    ("shop:payment:read", "查看支付", "shop"), ("shop:refund:read", "查看退款", "shop"),
    ("shop:refund:write", "执行退款", "shop"), ("shop:aftersales:read", "查看售后", "shop"),
    ("shop:aftersales:review", "审核售后", "shop"),
    ("shop:invoice:read", "查看发票", "shop"), ("shop:invoice:write", "开具发票", "shop"),
    ("shop:customer:read", "查看客户", "shop"), ("shop:customer:write", "维护客户", "shop"),
    ("shop:report:read", "查看报表", "shop"),
    ("shared:staff:read", "查看员工", "shared"), ("shared:staff:write", "维护员工", "shared"),
    ("shared:channel:read", "查看渠道", "shared"), ("shared:channel:write", "维护渠道", "shared"),
    ("shared:audit:read", "查看审计", "shared"),
    ("knowledge:document:read", "查看知识文档与版本", "knowledge"),
    ("knowledge:document:write", "新建与编辑知识文档", "knowledge"),
    ("knowledge:document:import", "批量导入知识文档", "knowledge"),
    ("knowledge:document:archive", "归档知识文档", "knowledge"),
    ("knowledge:document:publish", "发布知识文档", "knowledge"),
    ("knowledge:document:rollback", "回滚知识文档", "knowledge"),
    ("knowledge:rule:read", "查看结构化规则", "knowledge"),
    ("knowledge:rule:write", "维护结构化规则", "knowledge"),
    ("knowledge:review:read", "查看审核队列", "knowledge"),
    ("knowledge:review:write", "审核决定与批注", "knowledge"),
    ("knowledge:retrieval:test", "执行检索测试", "knowledge"),
    ("knowledge:governance:read", "查看治理报告", "knowledge"),
    ("ai:chat:read", "查看客服会话与消息", "ai"),
    ("ai:chat:write", "以客服身份回话与结束会话", "ai"),
    ("ai:handoff:read", "查看转人工队列", "ai"),
    ("ai:handoff:write", "接单与关闭转人工", "ai"),
    ("ai:trace:read", "查看问答链路留痕", "ai"),
    ("tool:read", "触发只读工具", "tool"),
    ("tool:write:order", "触发订单写工具", "tool"),
    ("tool:write:aftersales", "触发售后写工具", "tool"),
    ("tool:admin", "维护工具开关与查看评测报告", "tool"),
    ("ontology:read", "查看本体实体与关系", "ontology"),
    ("ontology:write", "维护本体实体与关系", "ontology"),
    ("ontology:review", "审核本体导入候选", "ontology"),
]

ROLES = [
    ("SUPER_ADMIN", "企业管理员", "全部权限，仅初始化创建", "ALL"),
    ("ECOMMERCE_OPS", "电商运营", "商品、类目、订单、履约、报表",
     ["shop:product:read", "shop:product:write", "shop:category:read", "shop:category:write", "shop:inventory:read",
      "shop:order:read", "shop:order:write", "shop:fulfillment:read", "shop:fulfillment:write", "shop:payment:read",
      "shop:aftersales:read", "shop:invoice:read", "shop:customer:read", "shop:report:read", "shared:channel:read"]),
    ("INVENTORY_MANAGER", "库存管理员", "库存、仓库、商品只读",
     ["shop:product:read", "shop:category:read", "shop:inventory:read", "shop:inventory:write", "shop:order:read",
      "shop:fulfillment:read", "shop:report:read"]),
    ("AFTER_SALES", "售后专员", "售后、退款、发票、订单只读",
     ["shop:order:read", "shop:aftersales:read", "shop:aftersales:review", "shop:refund:read", "shop:refund:write",
      "shop:invoice:read", "shop:invoice:write", "shop:customer:read", "shop:fulfillment:read", "shop:report:read"]),
    ("FINANCE_VIEWER", "财务只读", "支付、退款、发票、报表只读",
     ["shop:order:read", "shop:payment:read", "shop:refund:read", "shop:invoice:read", "shop:report:read"]),
    ("CS_SUPERVISOR", "客服主管", "订单与售后只读、售后审核、知识只读与检索测试、转人工只读",
     ["shop:order:read", "shop:aftersales:read", "shop:aftersales:review", "shop:customer:read", "shop:report:read",
      "shop:fulfillment:read", "knowledge:document:read", "knowledge:retrieval:test", "knowledge:governance:read",
      "ai:handoff:read"]),
    ("AUDITOR", "只读审计", "全部模块只读（不含知识库正文）", "READ_ONLY"),
    ("KNOWLEDGE_ADMIN", "知识管理员", "全部 knowledge:* 权限",
     ["knowledge:document:read", "knowledge:document:write", "knowledge:document:import",
      "knowledge:document:archive", "knowledge:document:publish", "knowledge:document:rollback",
      "knowledge:rule:read", "knowledge:rule:write", "knowledge:review:read", "knowledge:review:write",
      "knowledge:retrieval:test", "knowledge:governance:read",
      "ontology:read", "ontology:write", "ontology:review"]),
    ("KNOWLEDGE_REVIEWER", "知识审核员", "读、审核、批注、发布",
     ["knowledge:document:read", "knowledge:document:publish", "knowledge:review:read",
      "knowledge:review:write", "knowledge:rule:read", "knowledge:governance:read",
      "ontology:read", "ontology:review"]),
    ("KNOWLEDGE_EDITOR", "内容运营", "读、编辑、提交审核、导入",
     ["knowledge:document:read", "knowledge:document:write", "knowledge:document:import",
      "ontology:read"]),
    ("CS_AGENT", "普通客服", "只读知识文档，供三期问答使用",
     ["knowledge:document:read"]),
    ("AI_AGENT", "智能客服坐席", "会话读写、转人工接单、只读工具",
     ["ai:chat:read", "ai:chat:write", "ai:handoff:read", "ai:handoff:write", "tool:read"]),
    ("AI_SUPERVISOR", "智能客服主管", "坐席全部权限 + 问答留痕 + 写工具",
     ["ai:chat:read", "ai:chat:write", "ai:handoff:read", "ai:handoff:write", "ai:trace:read",
      "knowledge:document:read", "tool:read", "tool:write:order", "tool:write:aftersales"]),
]

CHANNELS = [
    ("OFFICIAL_MALL", "栖云智家官方商城", "SELF_MALL", "OFFICIAL_MALL"),
    ("TMALL", "天猫栖云智家官方旗舰店", "TMALL", "ECOMMERCE"),
    ("JD", "京东栖云智家自营旗舰店", "JD", "ECOMMERCE"),
    ("DOUYIN", "抖音栖云智家旗舰店", "DOUYIN", "ECOMMERCE"),
    ("STORE", "授权零售门店", "OFFLINE", "RETAIL"),
]

STAFF = [
    ("admin", "企业管理员", ["SUPER_ADMIN"], []),
    ("ops01", "电商运营-王敏", ["ECOMMERCE_OPS"], [1, 2, 3, 4]),
    ("ops02", "电商运营-刘洋", ["ECOMMERCE_OPS"], [1, 2, 3, 4, 5]),
    ("stock01", "库存管理员-李强", ["INVENTORY_MANAGER"], [1, 2]),
    ("aftersales01", "售后专员-赵蕾", ["AFTER_SALES"], [1, 2, 3, 4]),
    ("aftersales02", "售后专员-周航", ["AFTER_SALES"], [1, 2, 3, 4, 5]),
    ("finance01", "财务只读-陈洁", ["FINANCE_VIEWER"], []),
    ("cs01", "客服主管-孙昊", ["CS_SUPERVISOR"], [1, 2, 3, 4]),
    ("auditor01", "只读审计-何静", ["AUDITOR"], []),
]

CUSTOMERS = [
    ("buyer_zhang", "张三", "13900000001", "浙江省", "杭州市", "余杭区", "文一西路 100 号 1 幢 1801 室"),
    ("buyer_li", "李四", "13900000002", "广东省", "深圳市", "南山区", "科技园南路 9 号 A 座 3201"),
    ("buyer_wang", "王五", "13900000003", "北京市", "北京市", "海淀区", "上地信息路 5 号 2 号楼 606"),
    ("buyer_chen", "陈晨", "13900000004", "上海市", "上海市", "浦东新区", "张江高科技园区 88 号 5 号楼"),
    ("buyer_zhao", "赵敏", "13900000005", "江苏省", "南京市", "建邺区", "江东中路 200 号 12 层"),
    ("buyer_sun", "孙悦", "13900000006", "四川省", "成都市", "高新区", "天府大道 666 号 B 座 2201"),
    ("buyer_zhou", "周涛", "13900000007", "湖北省", "武汉市", "洪山区", "珞喻路 129 号 3 栋 902"),
    ("buyer_wu", "吴迪", "13900000008", "福建省", "厦门市", "思明区", "软件园二期望海路 21 号"),
    ("buyer_xu", "徐蕾", "13900000009", "山东省", "青岛市", "市南区", "香港中路 76 号 1503"),
    ("buyer_he", "何俊", "13900000010", "湖南省", "长沙市", "岳麓区", "麓谷大道 217 号"),
    ("buyer_guo", "郭静", "13900000011", "陕西省", "西安市", "雁塔区", "高新四路 30 号"),
    ("buyer_ma", "马超", "13900000012", "重庆市", "重庆市", "渝北区", "金开大道 1001 号"),
]

CATEGORIES = [
    ("SMART_LOCK", "智能门锁", None),
    ("CAMERA", "家用摄像头", None),
    ("ROBOT_VACUUM", "清洁机器人", None),
    ("LIGHTING", "智能灯具", None),
    ("GATEWAY", "家庭网关", None),
    ("ACCESSORY", "配件与耗材", None),
    ("CLOUD_SERVICE", "云服务", None),
    ("INSTALL_SERVICE", "安装与维修服务", None),
]

# 依据 knowledge_raw/01_产品知识/*/产品主档.md 与 QA_配件与耗材/配件兼容矩阵.md
PRODUCTS = [
    {
        "spu_code": "SPU-QL-L3P", "name": "栖云智能门锁 L3 Pro", "category": "SMART_LOCK", "brand": "QIYUN",
        "product_line": "智能门锁", "model_code": "QL-L3P",
        "subtitle": "指纹/密码/NFC/钥匙/App 临时授权，8 节 AA 电池，支持 5V USB-C 应急供电",
        "warranty": "整机保修 2 年，锁体与电子件按保修矩阵执行",
        "install_required": True, "service_scope": "中国大陆上门安装，玻璃门/双开门/异形锁体需先测量",
        "spec_summary": {"开锁方式": "指纹/密码/NFC 门卡/机械钥匙/App 临时授权", "供电": "8 节 AA 碱性电池",
                          "应急供电": "外侧底部 5V USB-C（仅恢复供电，仍需合法凭证开锁）", "无线": "2.4GHz Wi-Fi + 蓝牙",
                          "安装适配": "门厚 40-120mm", "包装清单": "前后面板、锁体、锁芯、机械钥匙 2 把、门卡 2 张、安装配件"},
        "highlights": ["不支持客服远程开锁", "应急供电不等于开锁", "玻璃门/双开门/异形锁体须先测量"],
        "skus": [("SKU-QL-L3P-BK", "栖云智能门锁 L3 Pro 曜石黑", "曜石黑", 1299.00, 1599.00, 880.00, "6900000000011", 3200)],
    },
    {
        "spu_code": "SPU-QC-C2G", "name": "栖云摄像头 C2 守望版", "category": "CAMERA", "brand": "QIYUN",
        "product_line": "家用摄像头", "model_code": "QC-C2G",
        "subtitle": "2560×1440 云台摄像头，红外夜视、双向语音、实体隐私遮蔽、microSD 本地存储",
        "warranty": "整机保修 1 年",
        "install_required": False, "service_scope": None,
        "spec_summary": {"分辨率": "2560×1440", "云台": "水平 360°／垂直 110°", "夜视": "红外夜视",
                          "存储": "microSD 16-256GB（Class 10）", "供电": "5V/2A USB-C", "网络": "仅 2.4GHz Wi-Fi",
                          "包装清单": "主机、电源适配器、线缆、壁装底座"},
        "highlights": ["仅 2.4GHz Wi-Fi", "不承诺杜绝盗窃或替代专业安防系统", "实体隐私遮蔽"],
        "skus": [("SKU-QC-C2G-WH", "栖云摄像头 C2 守望版 白色", "白色", 249.00, 299.00, 150.00, "6900000000021", 420)],
    },
    {
        "spu_code": "SPU-QR-R5M", "name": "栖云扫地机器人 R5 Max", "category": "ROBOT_VACUUM", "brand": "QIYUN",
        "product_line": "清洁机器人", "model_code": "QR-R5M",
        "subtitle": "激光建图、分区清扫、扫拖、自动集尘、拖布清洗与热风烘干",
        "warranty": "整机保修 1 年，锂电池保修 6 个月",
        "install_required": False, "service_scope": None,
        "spec_summary": {"导航": "激光建图", "机器人功率": "65W", "基站": "220V~ 50Hz／1000W",
                          "水箱": "清水箱 4L／污水箱 3.5L", "电池": "5200mAh 锂电池", "网络": "2.4GHz Wi-Fi"},
        "highlights": ["不吸取液体、燃烧物、尖锐物、建筑粉尘或宠物排泄物", "需平整室内地面"],
        "skus": [("SKU-QR-R5M-STD", "栖云扫地机器人 R5 Max 标准版", "标准版", 2599.00, 2999.00, 1750.00, "6900000000031", 11800)],
    },
    {
        "spu_code": "SPU-QT-L1C", "name": "栖云智能吸顶灯 LightOne", "category": "LIGHTING", "brand": "QIYUN",
        "product_line": "智能灯具", "model_code": "QT-L1C",
        "subtitle": "48W 无极调光调色，2700K-6500K，Ra≥90，支持 2.4GHz Wi-Fi 与蓝牙配网",
        "warranty": "整机保修 2 年",
        "install_required": True, "service_scope": "中国大陆上门安装，需断电施工",
        "spec_summary": {"额定输入": "220V~ 50Hz", "额定功率": "48W", "色温": "2700K-6500K", "显色指数": "Ra≥90",
                          "适用面积": "15-25㎡", "防护等级": "IP20（仅室内干燥环境）", "包装清单": "灯体、安装底盘、遥控器、紧固件"},
        "highlights": ["IP20 不可用于潮湿环境", "需专业电工安装"],
        "skus": [("SKU-QT-L1C-48W", "栖云智能吸顶灯 LightOne 48W", "48W／直径 480mm", 599.00, 699.00, 360.00, "6900000000041", 2100)],
    },
    {
        "spu_code": "SPU-QH-G1", "name": "栖云家庭网关 Hub G1", "category": "GATEWAY", "brand": "QIYUN",
        "product_line": "家庭网关", "model_code": "QH-G1",
        "subtitle": "Zigbee 3.0 + 蓝牙 Mesh + 以太网，支持本地自动化，单网关建议不超过 128 个子设备",
        "warranty": "整机保修 2 年",
        "install_required": False, "service_scope": None,
        "spec_summary": {"协议": "Zigbee 3.0／蓝牙 Mesh", "网络": "以太网 + 2.4GHz Wi-Fi", "供电": "5V/2A USB-C",
                          "接入上限": "建议不超过 128 个子设备"},
        "highlights": ["依赖云服务的通知与远程访问在外网中断时不可用", "部分自动化可本地运行"],
        "skus": [("SKU-QH-G1-STD", "栖云家庭网关 Hub G1 标准版", "标准版", 349.00, 399.00, 210.00, "6900000000051", 260)],
    },
    {
        "spu_code": "SPU-QA-L3-BAT8", "name": "AA 碱性电池组（8 节）", "category": "ACCESSORY", "brand": "QIYUN_ECO",
        "product_line": "配件耗材", "model_code": "QA-L3-BAT8",
        "subtitle": "适配 QL-L3P 智能门锁，8 节整组更换，不混用新旧电池",
        "warranty": "耗材类保修 6 个月（质量问题换新）",
        "install_required": False, "service_scope": None,
        "spec_summary": {"适配产品": "QL-L3P", "规格": "AA 碱性电池 ×8"},
        "highlights": ["整组更换，不混用新旧电池"],
        "skus": [("SKU-QA-L3-BAT8", "AA 碱性电池组（8 节）", "8 节装", 59.00, 69.00, 26.00, "6900000000061", 220)],
    },
    {
        "spu_code": "SPU-QA-R5-BRUSH-MOP", "name": "扫地机器人主刷与拖布组件", "category": "ACCESSORY", "brand": "QIYUN_ECO",
        "product_line": "配件耗材", "model_code": "QA-R5-BRUSH",
        "subtitle": "适配 QR-R5M 的主刷组件与拖布组件，不与其他型号通用",
        "warranty": "耗材类保修 6 个月（质量问题换新）",
        "install_required": False, "service_scope": None,
        "spec_summary": {"适配产品": "QR-R5M", "包含": "主刷组件 ×1、拖布组件 ×1"},
        "highlights": ["不与其他型号通用"],
        "skus": [("SKU-QA-R5-BRUSH", "R5 Max 主刷组件", "主刷", 99.00, 129.00, 42.00, "6900000000071", 180),
                 ("SKU-QA-R5-MOP", "R5 Max 拖布组件", "拖布", 79.00, 99.00, 30.00, "6900000000072", 120)],
    },
]

WAREHOUSES = [
    ("WH-HZ-01", "华东一号仓", "华东", "浙江省杭州市余杭区仓前街道 1 号", 10),
    ("WH-GZ-02", "华南仓", "华南", "广东省广州市白云区物流大道 88 号", 20),
]

CARRIERS = [
    ("SF", "顺丰速运", "https://www.sf-express.com/chn/sc/waybill/list?billNo={tracking_no}"),
    ("JD", "京东物流", "https://www.jdl.com/orderSearch?waybillCode={tracking_no}"),
    ("ZTO", "中通快递", "https://www.zto.com/express/expressCheck.html?txtBill={tracking_no}"),
    ("DBL", "德邦快递", "https://www.deppon.com/express/waybill?waybillNo={tracking_no}"),
]


def _has(db: Session, table) -> bool:
    return (db.execute(select(func.count()).select_from(table)).scalar_one() or 0) > 0


def bootstrap_reference(db: Session) -> dict:
    if _has(db, Tenant):
        return {"skipped": True}
    db.add(Tenant(id=settings.tenant_id, code="QIYUN", name="栖云智家科技有限公司"))
    db.flush()
    channels = []
    for code, name, platform, ctype in CHANNELS:
        ch = ChannelAccount(tenant_id=settings.tenant_id, code=code, name=name, platform_code=platform, channel_type=ctype)
        db.add(ch)
        channels.append(ch)
    perms = {}
    for code, name, module in PERMISSIONS:
        p = AppPermission(code=code, name=name, module=module)
        db.add(p)
        perms[code] = p
    db.flush()
    roles = {}
    for code, name, desc, mapping in ROLES:
        role = AppRole(tenant_id=settings.tenant_id, code=code, name=name, description=desc, is_system=True)
        db.add(role)
        db.flush()
        if mapping == "ALL":
            selected = list(perms.values())
        elif mapping == "READ_ONLY":
            # 审计员只读全部业务模块，但不得读取知识库正文（含高风险话术与定价口径）
            selected = [p for p in perms.values() if p.code.endswith(":read") and not p.code.startswith("knowledge:")]
        else:
            selected = [perms[c] for c in mapping]
        for p in selected:
            db.add(AppRolePermission(role_id=role.id, permission_id=p.id))
        roles[code] = role
    db.flush()
    staff_ids = {}
    for username, display, role_codes, scope_ids in STAFF:
        user = AppUser(tenant_id=settings.tenant_id, party="STAFF", username=username, display_name=display,
                       email=f"{username}@qiyun.local", password_hash=hash_password(DEV_PASSWORD),
                       is_super_admin=("SUPER_ADMIN" in role_codes))
        db.add(user)
        db.flush()
        for code in role_codes:
            db.add(AppUserRole(user_id=user.id, role_id=roles[code].id))
        for cid in scope_ids:
            db.add(StaffChannelScope(user_id=user.id, channel_account_id=cid))
        staff_ids[username] = user.id
    for code, name, url in CARRIERS:
        db.add(Carrier(tenant_id=settings.tenant_id, code=code, name=name, tracking_url_template=url))
    for code, name, region, address, priority in WAREHOUSES:
        db.add(Warehouse(tenant_id=settings.tenant_id, code=code, name=name, region=region, address=address, priority=priority))
    db.commit()
    return {"channels": len(channels), "permissions": len(perms), "roles": len(roles), "staff": len(staff_ids)}


def bootstrap_catalog(db: Session) -> dict:
    if _has(db, Product):
        return {"skipped": True}
    brands = {}
    for code, name in (("QIYUN", "栖云智家"), ("QIYUN_ECO", "栖云智家生态配件")):
        b = Brand(tenant_id=settings.tenant_id, code=code, name=name)
        db.add(b)
        brands[code] = b
    db.flush()
    categories = {}
    for idx, (code, name, parent) in enumerate(CATEGORIES, start=1):
        c = Category(tenant_id=settings.tenant_id, code=code, name=name, depth=1, sort_order=idx * 10)
        db.add(c)
        db.flush()
        c.path = "/" + str(c.id) + "/"
        categories[code] = c
    for code, name, dtype, options in [
        ("COLOR", "颜色", "ENUM", ["曜石黑", "皓月银", "白色"]),
        ("POWER", "供电方式", "ENUM", ["8 节 AA 碱性电池", "5V/2A USB-C", "220V~ 50Hz"]),
        ("PROTOCOL", "连接协议", "ENUM", ["Zigbee 3.0", "蓝牙 Mesh", "2.4GHz Wi-Fi", "以太网"]),
        ("FIT_MODEL", "适配型号", "TEXT", []),
    ]:
        db.add(AttributeDefinition(tenant_id=settings.tenant_id, code=code, name=name, data_type=dtype, options=options))
    db.flush()
    product_count = sku_count = 0
    for spec in PRODUCTS:
        product = Product(
            tenant_id=settings.tenant_id, spu_code=spec["spu_code"], name=spec["name"],
            brand_id=brands[spec["brand"]].id, category_id=categories[spec["category"]].id,
            product_line=spec["product_line"], model_code=spec["model_code"], subtitle=spec["subtitle"],
            description_md=f"# {spec['name']}\n\n{spec['subtitle']}\n\n来源：企业知识库产品主档。",
            highlights=spec["highlights"], spec_summary=spec["spec_summary"],
            warranty_summary=spec["warranty"], install_required=spec["install_required"],
            install_notes=spec.get("service_scope"), service_scope=spec.get("service_scope"),
            min_price=min(s[3] for s in spec["skus"]), max_price=max(s[3] for s in spec["skus"]),
            status="ON_SALE", published_at=now(),
        )
        db.add(product)
        db.flush()
        product_count += 1
        db.add(ProductMedia(tenant_id=settings.tenant_id, product_id=product.id, url=f"/products/{spec['model_code']}.webp",
                            alt_text=spec["name"], sort_order=0))
        for sku_code, sku_name, sku_spec, price, market, cost, barcode, weight in spec["skus"]:
            db.add(Sku(tenant_id=settings.tenant_id, product_id=product.id, sku_code=sku_code, name=sku_name,
                       spec_summary=sku_spec, price=price, market_price=market, cost_price=cost, barcode=barcode,
                       weight_g=weight, status="ON_SALE"))
            sku_count += 1
        db.flush()
    warehouses = db.execute(select(Warehouse)).scalars().all()
    skus = db.execute(select(Sku)).scalars().all()
    for sku in skus:
        for idx, wh in enumerate(warehouses):
            base = {0: 120, 1: 30}[idx]
            qty = base + (hash(sku.sku_code) % 80)
            safety = {0: 20, 1: 10}[idx]
            if sku.sku_code in ("SKU-QA-R5-BRUSH", "SKU-QA-L3-BAT8") and idx == 1:
                qty = 5
            db.add(Inventory(tenant_id=settings.tenant_id, sku_id=sku.id, warehouse_id=wh.id,
                             qty_available=qty, qty_reserved=0, qty_in_transit=0, safety_stock=safety))
    db.commit()
    return {"products": product_count, "skus": sku_count}


def bootstrap_customers(db: Session) -> dict:
    if _has(db, CustomerProfile):
        return {"skipped": True}
    created = 0
    for username, name, phone, province, city, district, detail in CUSTOMERS:
        user = AppUser(tenant_id=settings.tenant_id, party="CUSTOMER", username=username, display_name=name,
                       phone=phone, email=f"{username}@example.com", password_hash=hash_password(DEV_PASSWORD))
        db.add(user)
        db.flush()
        profile = CustomerProfile(tenant_id=settings.tenant_id, user_id=user.id, nickname=name, real_name=name)
        db.add(profile)
        db.flush()
        db.add(CustomerAddress(tenant_id=settings.tenant_id, customer_id=profile.id, receiver_name=name,
                               receiver_phone=phone, province=province, city=city, district=district, detail=detail,
                               is_default=True))
        created += 1
    db.commit()
    return {"customers": created}

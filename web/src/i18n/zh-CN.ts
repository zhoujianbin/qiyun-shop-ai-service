/** 一期中文文案单一真源；页面可见文案统一从此处取。 */
export const zhCN: Record<string, string> = {
  'app.name': '栖云智家 · 企业电商平台',
  'app.company': '栖云智家科技有限公司',
  'common.confirm': '确认',
  'common.cancel': '取消',
  'common.save': '保存',
  'common.reset': '重置',
  'common.search': '查询',
  'common.retry': '重试',
  'common.empty': '暂无数据',
  'common.loading': '加载中…',
  'common.copy': '复制',
  'common.export': '导出',
  'common.readonly': '只读',
  'action.login': '登录',
  'action.logout': '退出登录',
  'action.register': '注册',
  'nav.home': '首页',
  'nav.products': '商品',
  'nav.cart': '购物车',
  'nav.orders': '我的订单',
  'nav.afterSales': '售后服务',
  'nav.invoices': '发票',
  'nav.account': '个人中心',
  'footer.copyright': '© 栖云智家科技有限公司 第一期企业电商基础平台',
};

export type MessageKey = keyof typeof zhCN;

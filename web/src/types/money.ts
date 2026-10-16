/**
 * 金额类型：全链路以字符串承载 numeric(14,2)，币种固定 CNY。
 * 禁止使用 number 参与金额加减；需要运算时通过 utils/money.ts 转整数分。
 */
export type MoneyString = string;
export type Currency = 'CNY';

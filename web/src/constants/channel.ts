import type { ChannelType } from '@/types/status';

export const CHANNEL_TYPE_LABELS: Record<ChannelType, string> = {
  OFFICIAL_MALL: '官方商城',
  ECOM_FLAGSHIP: '电商官方旗舰店',
  AUTHORIZED_RETAIL: '授权零售门店',
};
export const CHANNEL_TYPE_OPTIONS = (Object.keys(CHANNEL_TYPE_LABELS) as ChannelType[]).map((value) => ({
  value, label: CHANNEL_TYPE_LABELS[value],
}));

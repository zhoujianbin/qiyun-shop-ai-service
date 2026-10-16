import App from 'antd/es/app';
import { useCallback } from 'react';
import { errorMessage } from '@/api/errors';

/**
 * 写操作统一反馈：成功 message.success，失败 message.error（带可执行提示）。
 * 返回 wrapper，调用处无需重复 try/catch。
 */
export function useAsyncAction() {
  const { message } = App.useApp();

  const run = useCallback(
    async <T,>(
      action: () => Promise<T>,
      options: { success: string; failure?: string; onSuccess?: (result: T) => void; onError?: (error: unknown) => void } = { success: '操作成功' },
    ): Promise<T | undefined> => {
      try {
        const result = await action();
        message.success(options.success);
        options.onSuccess?.(result);
        return result;
      } catch (error) {
        message.error(options.failure ?? errorMessage(error) ?? '操作失败，请稍后重试');
        options.onError?.(error);
        return undefined;
      }
    },
    [message],
  );

  return { run, message };
}

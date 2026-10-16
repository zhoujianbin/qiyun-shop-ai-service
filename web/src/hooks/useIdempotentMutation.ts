import { useMutation, type UseMutationOptions, type UseMutationResult } from '@tanstack/react-query';
import { useCallback, useRef } from 'react';
import { newIdempotencyKey } from '@/api/idempotency';
import type { ApiError } from '@/api/errors';

export type IdempotentMutationResult<TData, TVars> = UseMutationResult<TData, ApiError, TVars, unknown> & {
  /** 重新生成幂等键：上一次提交已成功/已取消、或表单内容变化时调用。 */
  resetKey: () => void;
  currentKey: () => string;
};

/**
 * 幂等写 mutation：一次提交动作内复用同一个 Idempotency-Key（重试不换 key），
 * 成功后由调用方 resetKey，避免不同意图复用同一 key。
 */
export function useIdempotentMutation<TData, TVars>(
  mutationFn: (vars: TVars, idempotencyKey: string) => Promise<TData>,
  options?: Omit<UseMutationOptions<TData, ApiError, TVars, unknown>, 'mutationFn'>,
): IdempotentMutationResult<TData, TVars> {
  const keyRef = useRef<string>(newIdempotencyKey());
  const resetKey = useCallback(() => {
    keyRef.current = newIdempotencyKey();
  }, []);

  const mutation = useMutation<TData, ApiError, TVars, unknown>({
    ...options,
    retry: options?.retry ?? 1,
    mutationFn: (vars) => mutationFn(vars, keyRef.current),
  });

  return Object.assign(mutation, { resetKey, currentKey: () => keyRef.current });
}

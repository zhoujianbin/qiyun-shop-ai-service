import { useNavigate } from 'react-router-dom';
import { useCallback } from 'react';
import { queryClient } from '@/app/providers';
import { useAuthStore } from '@/stores/authStore';
import { ROUTES } from '@/constants/routes';

/** 登出：清 Cookie/令牌、清空 query 缓存，跳转登录页。 */
export function useLogout(redirect: string = ROUTES.login) {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);

  return useCallback(async () => {
    await logout();
    queryClient.clear();
    navigate(redirect, { replace: true });
  }, [logout, navigate, redirect]);
}

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { useAuthStore } from './stores/authStore';
import './styles/index.css';

// 应用启动即恢复登录态（/auth/me + 单飞刷新）
void useAuthStore.getState().bootstrap();

const container = document.getElementById('root');
if (!container) {
  throw new Error('缺少 #root 挂载点');
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

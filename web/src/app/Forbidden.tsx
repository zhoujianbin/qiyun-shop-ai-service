import Button from 'antd/es/button';
import Result from 'antd/es/result';
import { useLocation, useNavigate } from 'react-router-dom';
import { ROUTES } from '@/constants/routes';

/** 403：展示所需权限码，便于运维定位。 */
export function Forbidden() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as { required?: string[] } | null;
  const required = state?.required ?? [];

  return (
    <Result
      status="403"
      title="403 无访问权限"
      subTitle={
        required.length > 0
          ? `当前账号缺少权限：${required.join('、')}。请联系企业管理员分配角色或渠道范围。`
          : '当前账号无权访问该页面，请联系企业管理员。'
      }
      extra={
        <Button type="primary" onClick={() => navigate(ROUTES.adminDashboard)}>
          返回工作台
        </Button>
      }
    />
  );
}

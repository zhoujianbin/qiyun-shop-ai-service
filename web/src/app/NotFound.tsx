import Button from 'antd/es/button';
import Result from 'antd/es/result';
import { Link } from 'react-router-dom';
import { ROUTES } from '@/constants/routes';

export function NotFound() {
  return (
    <Result
      status="404"
      title="404 页面不存在"
      subTitle="您访问的页面不存在或已被移除。"
      extra={<Link to={ROUTES.home}><Button type="primary">返回首页</Button></Link>}
    />
  );
}

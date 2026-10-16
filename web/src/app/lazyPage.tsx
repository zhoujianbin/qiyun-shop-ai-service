import { lazy, Suspense, type ComponentType, type ReactElement } from 'react';
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton';

/** 路由级懒加载 + Suspense fallback（骨架屏）。 */
export function lazyEl(factory: () => Promise<{ default: ComponentType }>): ReactElement {
  const Component = lazy(factory);
  return (
    <Suspense fallback={<div className="qy-page"><LoadingSkeleton rows={8} /></div>}>
      <Component />
    </Suspense>
  );
}

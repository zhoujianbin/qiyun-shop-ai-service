import { Component, Suspense, lazy, type ErrorInfo, type ReactNode } from 'react';

// ErrorState 只在「出错」时才渲染，而它会引入 Alert / Typography 等一批首屏用不到的
// 组件（Typography 内部还会静态带出 Editable -> Input -> rc-input/rc-textarea）。
// 因此按需加载，避免为「可能不会发生的错误」支付首屏体积。
const LazyErrorState = lazy(() =>
  import('@/components/common/ErrorState').then((m) => ({ default: m.ErrorState })),
);

interface Props { children: ReactNode }
interface State { error: Error | null }

/** 路由级错误边界：统一渲染 ErrorState，避免白屏。 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    if (import.meta.env.DEV) {
      // eslint-disable-next-line no-console
      console.error('[ErrorBoundary]', error, info.componentStack);
    }
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div style={{ padding: 32 }}>
          <Suspense fallback={<div aria-busy="true" />}>
            <LazyErrorState title="页面出现异常" error={this.state.error} onRetry={() => this.setState({ error: null })} />
          </Suspense>
        </div>
      );
    }
    return this.props.children;
  }
}

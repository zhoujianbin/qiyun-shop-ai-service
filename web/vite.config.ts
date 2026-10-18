import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

// 栖云智家 第一期 企业电商基础平台 —— 构建配置
// dev: /api 代理到本地 FastAPI（不 rewrite）；build: 产物输出 dist/

/** 取模块所属 npm 包名（支持 @scope/name）。 */
function pkgOf(id: string): string {
  const rel = id.split('node_modules/')[1] ?? '';
  const seg = rel.split('/');
  const first = seg[0] ?? '';
  return first.startsWith('@') ? `${first}/${seg[1] ?? ''}` : first;
}

// —— 依赖分包策略（v2） ——
// 首屏 gzip 的大头从来不是「哪个包大」，而是「谁被塞进了入口静态图」。
// Rollup 默认按可达性分包：只有静态可达的模块才会进入口 chunk；动态 import
// 的页面只带走自己用到的模块。真正需要人工干预的只有「稳定且首屏必用的核心 vendor」，
// 让业务代码改动不击穿第三方缓存：
//
//   · vendor-react / vendor-router / vendor-data —— 首屏必用且版本稳定，单独成 chunk；
//   · 其余第三方（antd / rc-* / @ant-design/icons / dayjs / 工具库…）一律交给
//     Rollup 按可达性自动分包。
//
// 反例（v1，已废弃）：按「包名」把整个 antd 或 @ant-design/icons 合成一个 vendor chunk。
// 这些包内部是 barrel 互引，只要首屏用到一个组件（例如 ConfigProvider），按包名聚合就会
// 把 Table/Form/DatePicker/Upload/Carousel 等只在个别路由用到的重组件一起拖进首屏。
// 实测 v1 的 vendor-antd = 626KB raw / 192KB gzip，其中首屏真正需要的只有 8KB raw。
//
// 配套改造（缺一不可）：
//   1) 源码里 antd / @ant-design/icons 全部改为深路径导入，切断 barrel 静态边；
//   2) AdminShell、AuthLayout 改为路由级懒加载，C 端首屏不再下载 B 端外壳；
//   3) ErrorBoundary 懒加载 ErrorState、NotFound/Forbidden 懒加载，避免 Result/Alert/Typography 进首屏。
/**
 * 斩断首屏到 rc-field-form barrel 的静态边。
 *
 * antd 的 _util/ContextIsolator（被 Menu/Dropdown 引用）会静态引入 antd/es/form/context，
 * 而它从 rc-field-form 的 barrel 取 FormProvider。barrel 又静态导出 Field / useForm /
 * validateUtil / @rc-component/async-validator，于是这 ~117KB 源码（rc-field-form 81KB +
 * async-validator 36KB）即便 C 端首屏只用到一个 FormProvider 也会被算作「首屏静态可达」，
 * 随后又被懒加载的表单页共享，最终落进入口 chunk。
 *
 * 这里只把「antd form/context 对 rc-field-form 的引入」重定向到 rc-field-form 内部只导出
 * FormProvider 的 es/FormContext 模块（两者是同一个实现，行为完全一致）；懒加载表单页仍
 * 使用完整 barrel。只影响打包图，不改运行语义。
 */
function rcFieldFormBarrelSplit(): Plugin {
  const ANTD_FORM_CONTEXT = /[\\/]antd[\\/]es[\\/]form[\\/]context\.js$/;
  return {
    name: 'rc-field-form-barrel-split',
    enforce: 'pre',
    resolveId(source, importer) {
      if (source === 'rc-field-form' && importer && ANTD_FORM_CONTEXT.test(importer)) {
        return this.resolve('rc-field-form/es/FormContext', importer, { skipSelf: true });
      }
      return null;
    },
  };
}

/** react 系（含调度器与共享运行时辅助）。 */
const REACT_PKGS = new Set(['react', 'react-dom', 'scheduler', 'react-is', 'use-sync-external-store']);
/** 路由。 */
const ROUTER_PKGS = new Set(['react-router', 'react-router-dom', '@remix-run/router']);
/** 数据层：HTTP / 服务端缓存 / 状态。 */
const DATA_PKGS = new Set(['axios', 'zustand', '@tanstack/query-core', '@tanstack/react-query']);

/** 只给「首屏必用且稳定」的核心依赖命名固定 chunk，其余交给 Rollup 按可达性分包。 */
function manualChunks(id: string): string | undefined {
  if (!id.includes('node_modules')) return undefined;
  const pkg = pkgOf(id);
  if (REACT_PKGS.has(pkg)) return 'vendor-react';
  if (ROUTER_PKGS.has(pkg)) return 'vendor-router';
  if (DATA_PKGS.has(pkg)) return 'vendor-data';
  return undefined;
}

export default defineConfig({
  plugins: [rcFieldFormBarrelSplit(), react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      // rc-resize-observer 会静态引入整包 resize-observer-polyfill（首屏约 34KB 源码）。
      // es2020 目标浏览器都已原生支持 ResizeObserver，接口一致，用原生实现替换。
      // 详见 src/shims/resizeObserver.ts。
      'resize-observer-polyfill': fileURLToPath(new URL('./src/shims/resizeObserver.ts', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    // 监听所有网卡，允许同一局域网内的其他机器访问 http://<本机 IP>:5173 。
    // 只想本机访问时用 `vite --host 127.0.0.1` 覆盖。
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // 不 rewrite：后端服务地址即 http://127.0.0.1:8000/api/v1
      },
    },
  },
  // 预览构建产物时同样把 /api 代理到本地 FastAPI，便于对 dist 做工端到端冒烟。
  preview: {
    port: 4173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    target: 'es2020',
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks,
      },
    },
  },
});

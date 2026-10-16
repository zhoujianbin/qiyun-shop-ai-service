/**
 * rc-resize-observer 静态依赖 resize-observer-polyfill（ESM 约 34KB）。
 * 本工程构建目标 es2020，对应浏览器（Chrome 64+ / Safari 13.1+ / Firefox 69+）
 * 均已原生支持 ResizeObserver，且原生实现与 polyfill 的构造 / observe / unobserve /
 * disconnect 接口完全一致，因此直接用浏览器原生实现替换整包 polyfill，
 * 避免把这份 polyfill 打进 C 端首屏。行为不变。
 */
const NativeResizeObserver = globalThis.ResizeObserver;

export default NativeResizeObserver;

# 前端技术栈事实地图

**分析日期：** 2026-06-08

**范围：** 仅 `frontend/` 子项目。依据 `frontend/package.json`、`frontend/package-lock.json`、前端配置、前端源码、前端测试配置、`docs/frontend.md`、`docs/interfaces-runtime.md` 和根级 `README.md` 刷新；未读取 `frontend/.env.local`、`frontend/.env.local.example`、`frontend/.npmrc` 或任何真实凭据文件内容。

## 语言

**主要语言：**
- TypeScript 5 - 应用源码、API client、Zustand store、类型定义和测试配置，见 `frontend/app/`、`frontend/components/`、`frontend/lib/`、`frontend/stores/`、`frontend/types/`、`frontend/jest.config.ts`、`frontend/playwright.config.ts`。
- TSX / React JSX - Next.js 页面与客户端组件，见 `frontend/app/tender/page.tsx`、`frontend/components/chat/`、`frontend/components/forms/`。

**辅助语言：**
- CSS - Tailwind 4 入口和全局样式，见 `frontend/app/globals.css`。
- JavaScript - Jest setup 与运行时 polyfill，见 `frontend/jest.setup.js`、`frontend/polyfills.js`。

## 运行时

**环境：**
- Node.js `>=20.9.0` - `frontend/package.json` 的 `engines.node` 声明。
- Node 20 - `frontend/.nvmrc` 固定主版本。
- 浏览器运行时 - 前端使用 `fetch`、`EventSource`、`sessionStorage`、`URLSearchParams`、Clipboard 和 DOM APIs，主要见 `frontend/lib/api.ts`、`frontend/lib/sse.ts`、`frontend/stores/chatStore.ts`、`frontend/components/chat/MessageList.tsx`。

**包管理器：**
- npm - `frontend/package-lock.json` 存在，lockfileVersion 为 3。
- Lockfile：存在，路径为 `frontend/package-lock.json`。
- `frontend/.npmrc` 文件存在；本次不读取内容。根级 `README.md` 记录 fresh clone 使用 `npm ci`。

## 框架

**核心框架：**
- Next.js `^16.2.6` - App Router、dev/build/start、rewrites、headers、图片 remote pattern 和 TypeScript build 校验，见 `frontend/package.json`、`frontend/app/`、`frontend/next.config.ts`。
- React `19.2.3` / React DOM `19.2.3` - 客户端组件、hooks 和 UI runtime，见 `frontend/components/`、`frontend/hooks/`。
- Zustand `^5.0.11` - 会话、草稿、任务、stream、历史和 UI 状态，见 `frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/stores/useAppStore.ts`。
- Tailwind CSS `^4` + `@tailwindcss/postcss` `^4` - utility 样式和 PostCSS 集成，见 `frontend/app/globals.css`、`frontend/postcss.config.mjs`。

**测试：**
- Jest `^29.7.0` - 单元与集成测试 runner，配置位于 `frontend/jest.config.ts`。
- `jest-environment-jsdom` `^30.3.0` - DOM 测试环境，见 `frontend/jest.config.ts`。
- Testing Library - React 组件测试依赖，见 `frontend/package.json`。
- MSW `^2.12.10` - API mock，见 `frontend/mocks/handlers.ts`、`frontend/mocks/server.ts`。
- Playwright `^1.58.2` - E2E 测试，见 `frontend/playwright.config.ts`、`frontend/e2e/`。

**构建与开发：**
- ESLint 9 + `eslint-config-next` `16.1.6` + `eslint-plugin-react-hooks` `^7.0.1` - lint，见 `frontend/eslint.config.mjs`。
- Prettier `^3.8.1` + `prettier-plugin-tailwindcss` `^0.7.2` - 格式化与 Tailwind class 排序，见 `frontend/.prettierrc`。
- TypeScript compiler `^5` - `frontend/tsconfig.json` 和 `frontend/tsconfig.typecheck.json`。

## 关键依赖

**核心依赖：**
- `next` `^16.2.6` - 页面路由、构建、开发服务器、`/api/:path*` rewrite 和生产 header。
- `react` `19.2.3` / `react-dom` `19.2.3` - UI runtime。
- `zustand` `^5.0.11` - 本地会话、草稿、任务摘要、SSE 恢复和 UI 状态。
- `lucide-react` `^0.575.0` - 图标库，见 `frontend/components/forms/TemplateCandidateDialog.tsx`、`frontend/components/chat/`。
- `clsx` `^2.1.1` / `tailwind-merge` `^3.5.0` - className 组合，见 `frontend/lib/utils.ts`。

**基础设施依赖：**
- `@playwright/test` `^1.58.2` - E2E runner 与浏览器项目配置，见 `frontend/playwright.config.ts`。
- `msw` `^2.12.10` - Jest API mock 和错误场景模拟，见 `frontend/mocks/handlers.ts`。
- `jest-fetch-mock` `^3.0.3` - fetch 测试支持，见 `frontend/package.json`。
- `undici` `^7.22.0` / `und` `^2.13.0` - Node/fetch 兼容依赖，见 `frontend/package.json`。
- `ts-node` `^10.9.2` - TypeScript 配置执行支持，见 `frontend/package.json`。

## 配置

**环境变量：**
- `frontend/.env.local` 文件存在，只作为本地环境配置；不得读取或写入真实值。
- `frontend/.env.local.example` 文件存在，只记录示例文件存在；不得复制其中内容到长期文档。
- `NEXT_PUBLIC_API_URL` 是前端 API base URL 配置键；解析逻辑在 `frontend/lib/apiBaseUrl.ts`，Next rewrite 和开发来源白名单在 `frontend/next.config.ts`。
- API base URL 缺省值由 `frontend/lib/apiBaseUrl.ts` 回落到 `http://localhost:8000`，浏览器环境还会按当前 hostname 推导 `:8000` 后端地址。

**构建配置：**
- `frontend/next.config.ts`：Next 配置、`/api/:path*` rewrite、生产缓存 header、开发来源白名单、图片 remote pattern、`reactStrictMode`、`typescript.ignoreBuildErrors: false`。
- `frontend/tsconfig.json`：`strict: true`、`moduleResolution: bundler`、`jsx: react-jsx`、Next 插件和 `@/*` path alias。
- `frontend/tsconfig.typecheck.json`：稳定 type-check 专用配置，排除 `.next/dev`。
- `frontend/eslint.config.mjs`：Next core web vitals、Next TS、React hooks 插件和生成目录 ignore。
- `frontend/.prettierrc`：2 空格、单引号、分号、100 列、Tailwind 插件。
- `frontend/jest.config.ts`：Next/Jest 集成、`jsdom`、coverage、moduleNameMapper、MSW transform 兼容和 50% 全局 coverage threshold。
- `frontend/playwright.config.ts`：`baseURL: http://localhost:8502`、Chromium 项目、HTML reporter、失败截图/视频/trace、dev server。

## 平台要求

**开发：**
- 默认前端端口是 `8502`，脚本见 `frontend/package.json` 的 `dev` / `start`。
- 端口 `8000` 用于后端 API，前端通过 `NEXT_PUBLIC_API_URL`、`frontend/lib/apiBaseUrl.ts` 和 `frontend/next.config.ts` 对接。
- 常规命令：

```bash
npm run dev
npm run lint
npm run type-check
npm run test
npm run test:e2e
```

- 根级 `README.md` 记录 Windows/WSL 双模式开发；前端依赖目录包含 `frontend/node_modules/` 和 `frontend/node_modules-wsl/`，切换平台时不要盲目复用原生依赖。

**生产：**
- `frontend/` 内未检测到 Vercel、Docker、Netlify 或 GitHub Actions 前端部署配置。
- 生产构建由 Next.js `npm run build` / `npm run start` 承载，`frontend/next.config.ts` 不忽略 TypeScript build errors。
- 生产 header：`/_next/static/:path*` 使用 immutable cache，其他路径使用 `no-store`，见 `frontend/next.config.ts`。

---

*前端技术栈分析：2026-06-08*

# 前端技术栈事实地图

**分析日期：** 2026-07-15

**范围：** 仅 `frontend/` 子项目。依据 `frontend/package.json`、`frontend/package-lock.json`、`frontend/next.config.ts`、`frontend/tsconfig.json`、`frontend/tsconfig.typecheck.json`、`frontend/jest.config.ts`、`frontend/playwright.config.ts`、`frontend/eslint.config.mjs`、`frontend/postcss.config.mjs`、`frontend/.prettierrc`、`frontend/.nvmrc`、`frontend/.npmrc`、`frontend/app/`、`frontend/components/`、`frontend/hooks/`、`frontend/lib/`、`frontend/stores/`、`frontend/types/` 与相关配置。`frontend/.env.local` 与 `frontend/.env.local.example` 文件存在；只记录配置键名，不读取 `.env.local` 真实值。

## 语言

**主要语言：**
- TypeScript（`typescript ^5`，锁版本 5.9.3）- 应用源码、API client、hooks、Zustand store、类型定义、测试配置和 Playwright 配置。代表路径：`frontend/app/tender/page.tsx`、`frontend/components/chat/ChatPanel.tsx`、`frontend/hooks/useChatSSE.ts`、`frontend/lib/api.ts`、`frontend/stores/chatStore.ts`、`frontend/types/api.ts`、`frontend/jest.config.ts`、`frontend/playwright.config.ts`。
- TSX / React JSX - Next.js App Router 页面和客户端组件。代表路径：`frontend/app/page.tsx`、`frontend/app/layout.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/MessageList.tsx`。

**辅助语言：**
- CSS - Tailwind 4 入口、CSS variables 和全局组件样式，见 `frontend/app/globals.css`。
- JavaScript - Jest setup、Node/jsdom polyfill，见 `frontend/jest.setup.js`、`frontend/polyfills.js`。
- MJS - ESLint/PostCSS ESM 配置，见 `frontend/eslint.config.mjs`、`frontend/postcss.config.mjs`。

## 运行时

**环境：**
- Node.js `>=20.9.0` - `frontend/package.json` 的 `engines.node` 声明，且 `frontend/.npmrc` 设置 `engine-strict=true` 强制约束。
- Node `20` - `frontend/.nvmrc` 固定主版本。
- 浏览器运行时 - 产品代码依赖 `fetch`、`EventSource`、`FormData`、`Blob`、`AbortController`、`URLSearchParams`、`sessionStorage`/`localStorage`、Zustand persist storage 和 Clipboard/DOM API。代表路径：`frontend/lib/api.ts`、`frontend/lib/sse.ts`、`frontend/components/forms/FileUploader.tsx`、`frontend/stores/chatStore.ts`、`frontend/stores/chatTaskSessionStore.ts`。

**包管理器：**
- npm（唯一）- `frontend/package-lock.json` 存在，`lockfileVersion` 为 3。仓库不使用 yarn/pnpm，`frontend/package.json` 无 `packageManager` 字段、无 yarn/pnpm 锁文件。
- `frontend/.npmrc` 配置：`registry=https://registry.npmjs.org/`、`engine-strict=true`。
- Lockfile 路径：`frontend/package-lock.json`。
- `overrides`：`frontend/package.json` 固定 `postcss` 为 `8.5.14`，避免 Tailwind 4 / PostCSS 版本漂移。

## 框架

**核心：**
- Next.js `^16.2.6`（锁版本 16.2.6）- App Router、dev/build/start、`/api/:path*` rewrite、生产 header、图片 remote patterns、React strict mode、devIndicators 关闭和 TypeScript build 校验，见 `frontend/package.json`、`frontend/app/`、`frontend/next.config.ts`。
- React `19.2.3` / React DOM `19.2.3`（精确版本）- 组件和 hooks runtime，见 `frontend/components/`、`frontend/hooks/`。
- Zustand `^5.0.11`（锁版本 5.0.11）- 会话、草稿、任务、stream、历史和 UI 状态，见 `frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/stores/useAppStore.ts`。
- Tailwind CSS `^4`（锁版本 4.2.1）+ `@tailwindcss/postcss ^4` - utility 样式、`@theme inline` 和 PostCSS 插件，见 `frontend/app/globals.css`、`frontend/postcss.config.mjs`（仅注册 `@tailwindcss/postcss` 一个插件）。

**测试：**
- Jest `^29.7.0`（锁版本 29.7.0）- 单元测试 runner，配置位于 `frontend/jest.config.ts`。
- `jest-environment-jsdom ^30.3.0` - DOM 测试环境，见 `frontend/jest.config.ts`。
- Testing Library - React 组件、hook 和用户事件测试：`@testing-library/react ^16.2.0`、`@testing-library/jest-dom ^6.6.3`、`@testing-library/user-event ^14.6.1`；测试位于 `frontend/__tests__/`。
- Playwright `^1.58.2`（锁版本 1.58.2）- E2E 测试，配置位于 `frontend/playwright.config.ts`，测试位于 `frontend/e2e/`。

**构建/开发：**
- Next dev server - `npm run dev` 执行 `next dev --webpack -p 8502`（强制 webpack 引擎、固定端口 8502），见 `frontend/package.json`。
- TypeScript compiler - `frontend/tsconfig.json` 和 `frontend/tsconfig.typecheck.json`。
- ESLint `^9` + `eslint-config-next` 16.1.6 + `eslint-plugin-react-hooks ^7.0.1` - lint 配置位于 `frontend/eslint.config.mjs`。
- Prettier `^3.8.1` + `prettier-plugin-tailwindcss ^0.7.2` - 格式化与 Tailwind class 排序，配置位于 `frontend/.prettierrc`。
- `ts-node ^10.9.2` - TypeScript 配置执行支持（Jest/Playwright 配置文件加载），见 `frontend/package.json`。

## 命令

包管理器一律 npm，不要使用 yarn/pnpm。脚本定义见 `frontend/package.json` 的 `scripts`：

| 命令 | 脚本 | 说明 |
| --- | --- | --- |
| `npm run dev` | `next dev --webpack -p 8502` | 启动开发服务器（webpack，端口 8502） |
| `npm run build` | `next build` | 生产构建 |
| `npm run start` | `next start -p 8502` | 生产启动（端口 8502） |
| `npm run lint` | `eslint` | 静态检查 |
| `npm run type-check` | `tsc -p tsconfig.typecheck.json --noEmit` | 类型检查（排除 `.next/dev`） |
| `npm run format` | `prettier --write .` | 格式化写入 |
| `npm run format:check` | `prettier --check .` | 格式化校验 |
| `npm run test` | `jest` | 单元测试 |
| `npm run test:watch` | `jest --watch` | 单元测试 watch |
| `npm run test:coverage` | `jest --coverage` | 单元测试 + 覆盖率 |
| `npm run test:e2e` | `playwright test` | E2E 测试 |
| `npm run test:e2e:ui` | `playwright test --ui` | E2E UI 模式 |
| `npm run test:e2e:debug` | `playwright test --debug` | E2E 调试模式 |

常用串行命令：

```bash
npm ci
npm run dev
npm run lint
npm run type-check
npm run test
npm run test:e2e
```

## 关键依赖

**运行时依赖（dependencies）：**
- `next` `^16.2.6` - 路由、构建、`/api/:path*` rewrite、生产缓存 header 和图片 remote patterns。
- `react` / `react-dom` `19.2.3`（精确）- UI runtime。
- `zustand` `^5.0.11` - `chat-storage`、`chat-task-session-storage`、`tender-history-storage`、`tender-app-storage` 等状态持久化。
- `clsx` `^2.1.1` / `tailwind-merge` `^3.5.0` - className 组合工具，封装在 `frontend/lib/utils.ts`。
- `lucide-react` `^0.575.0` - 图标库，见 `frontend/components/forms/ModelSelector.tsx`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/layout/Sidebar.tsx`。
- `prettier` `^3.8.1` / `prettier-plugin-tailwindcss` `^0.7.2` - 放在 dependencies 中以便脚本统一调用。

**开发依赖（devDependencies）：**
- `@playwright/test` `^1.58.2` - E2E runner、Chromium 项目、截图/视频/trace 证据。
- `jest` `^29.7.0`、`jest-environment-jsdom` `^30.3.0`、`@testing-library/react` `^16.2.0`、`@testing-library/jest-dom` `^6.6.3`、`@testing-library/user-event` `^14.6.1` - 单元和组件测试。
- `@types/jest`、`@types/node` `^20`、`@types/react` `^19`、`@types/react-dom` `^19` - 类型定义。
- `typescript` `^5`、`ts-node` `^10.9.2` - 严格类型检查、配置加载。
- `eslint` `^9`、`eslint-config-next` `16.1.6`、`eslint-plugin-react-hooks` `^7.0.1` - Next/React 静态检查。
- `tailwindcss` `^4`、`@tailwindcss/postcss` `^4` - Tailwind 4 编译链路。

## 配置

**环境变量（配置键名）：**
- `NEXT_PUBLIC_API_URL` - 可选 API base URL 配置键（支持逗号分隔多候选地址）；解析逻辑在 `frontend/lib/apiBaseUrl.ts`，Next rewrite 和开发期 allowed origins 在 `frontend/next.config.ts`。模板见 `frontend/.env.local.example`。
- `NODE_ENV` - `frontend/next.config.ts` 用于生产 header 分支。
- `CI` - `frontend/playwright.config.ts` 用于控制 forbidOnly、retries、workers 和 dev server reuse。
- `PLAYWRIGHT_USE_SYSTEM_CHROME` - `frontend/playwright.config.ts` 非 CI 环境下控制是否使用系统 Chrome channel（默认开启，`'0'` 关闭）。
- `frontend/.env.local` 文件存在，作为本地环境配置；内容不读取。
- `frontend/.env.local.example` 文件存在，记录 `NEXT_PUBLIC_API_URL` 配置键名（示例值可多候选、逗号分隔）。

**构建：**
- `frontend/next.config.ts`：`allowedDevOrigins`（含 `localhost`、`127.0.0.1` 与 `NEXT_PUBLIC_API_URL` 解析 hostname）、`/api/:path*` rewrite 到 `resolveApiBaseUrl()` 结果、生产缓存 header、`images.remotePatterns`（仅 `localhost:8000`）、`reactStrictMode: true`、`devIndicators: false`、`typescript.ignoreBuildErrors: false`。
- `frontend/tsconfig.json`：`strict: true`、`moduleResolution: bundler`、`jsx: react-jsx`、Next 插件、`@/*` path alias；`exclude` 同时排除 `node_modules` 与 `node_modules-*`（覆盖跨平台依赖目录）。
- `frontend/tsconfig.typecheck.json`：继承 `tsconfig.json`，type-check 专用，排除 `.next/dev`。
- `frontend/eslint.config.mjs`：`eslint-config-next/core-web-vitals` + `eslint-config-next/typescript` + `eslint-plugin-react-hooks`（规则 `react-hooks/set-state-in-effect: warn`）；全局 ignore 含 `.next`、`node_modules-*/**`、`coverage`、`playwright-report`、`test-results`。
- `frontend/.prettierrc`：`semi`、`trailingComma: es5`、`singleQuote`、`printWidth: 100`、`tabWidth: 2`、Tailwind 插件。
- `frontend/postcss.config.mjs`：仅注册 `@tailwindcss/postcss` 插件。
- `frontend/jest.config.ts`：`next/jest` 集成、`testEnvironment: jsdom`、`coverageProvider: v8`、`moduleNameMapper: ^@/(.*)$`、`polyfills.js` + `jest.setup.js`、忽略 `node_modules-wsl/`、全局 coverage threshold 50%（branches/functions/lines/statements）。
- `frontend/playwright.config.ts`：`baseURL: http://localhost:8502`、Chromium 项目（非 CI 默认用系统 Chrome）、HTML reporter、失败截图/视频/trace、`webServer` 启动 `npm run dev -- --webpack`（CI 下不复用已运行 server）。

**应用入口：**
- `frontend/app/page.tsx` 直接 `redirect('/tender')`。
- `frontend/app/tender/page.tsx` 是三栏工作台入口，组合 `TenderTypeSidebar`、`FormPanel`、`ChatPanel`，并处理 URL 深链、招标数据同步和 conversation heartbeat。
- `frontend/app/layout.tsx` 设置 `zh-CN` 根布局和 metadata。
- `frontend/app/api/` 不存在；前端不实现 Next API route。

**状态：**
- `frontend/stores/chatStore.ts` 是主会话 store，persist 到 `sessionStorage` 的 `chat-storage`，保存 conversations、草稿、任务摘要和未读结果。
- `frontend/stores/chatStreamStore.ts` 保存任务 stream 运行时日志、正文、进度、agent step 和 last event id；纯内存 store，不持久化完整 stream payload。
- `frontend/stores/chatTaskSessionStore.ts` persist 到 `sessionStorage` 的 `chat-task-session-storage`，保存 task id 与 last event id。
- `frontend/stores/historyStore.ts` persist 到 `sessionStorage` 的 `tender-history-storage`，保存最近生成历史。
- `frontend/stores/useAppStore.ts` persist 到 `tender-app-storage`（未显式指定 storage adapter，Zustand 默认 `localStorage`），`partialize` 只保留 `sidebarOpen`。

**Hooks（网络/任务相关）：**
- `frontend/hooks/useSSE.ts` - 通用 EventSource 连接 hook，封装 `createSSEConnection()`。
- `frontend/hooks/useChatSSE.ts` - 任务 SSE 事件到 chat/stream store 的映射与终态清理。
- `frontend/hooks/useTaskHeartbeat.ts` - 周期调用 `sendTaskHeartbeat()`（默认间隔 5s）。
- `frontend/hooks/useCurrentConversationTaskStatus.ts` - 拉取当前会话任务状态。
- `frontend/hooks/useLatestActiveTaskSummary.ts` - 任务列表/活跃摘要。
- `frontend/hooks/useUrlParams.ts` - URL 深链与招标类型 canonical。
- `frontend/hooks/useHydrated.ts` - persist 水合完成标记。

## 平台要求

**开发：**
- 前端开发端口固定 `8502`，脚本见 `frontend/package.json` 的 `dev` / `start`。
- 后端 API 默认端口 `8000`，前端通过 `NEXT_PUBLIC_API_URL`、`frontend/lib/apiBaseUrl.ts` 和 `frontend/next.config.ts` 对接。
- 前端依赖目录可能出现 `frontend/node_modules/`、`frontend/node_modules-wsl/` 或 `frontend/node_modules-win/`，跨平台切换时不要复用原生依赖目录（`tsconfig.json` / `jest.config.ts` 已对 `node_modules-*` 做忽略）。
- 完整 Word 生成闭环依赖后端 Windows Python、pywin32 和 Word/WPS COM 环境；前端自身只负责浏览器工作台和 API/SSE 接入。

**生产：**
- `frontend/` 顶层未检测到 `vercel.json`、`Dockerfile`、`docker-compose*.yml` 或 `netlify.toml`。
- 仓库级 `.github/workflows/` 未检测到。
- 生产构建由 `npm run build` / `npm run start` 承载，`frontend/next.config.ts` 不忽略 TypeScript build errors。
- 生产 header：`/_next/static/:path*` 使用 immutable cache，其他路径使用 `no-store`，见 `frontend/next.config.ts`。

---

*前端技术栈分析：2026-07-15*

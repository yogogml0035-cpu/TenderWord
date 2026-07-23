# 前端技术栈事实地图

**分析日期：** 2026-07-21

**范围：** 仅 `frontend/` 子项目。依据 `frontend/package.json`、`frontend/package-lock.json`、`frontend/next.config.ts`、`frontend/tsconfig.json`、`frontend/tsconfig.typecheck.json`、`frontend/jest.config.ts`、`frontend/playwright.config.ts`、`frontend/eslint.config.mjs`、`frontend/postcss.config.mjs`、`frontend/.prettierrc`、`frontend/.nvmrc`、`frontend/.npmrc`、`frontend/app/`、`frontend/components/`、`frontend/hooks/`、`frontend/lib/`、`frontend/stores/`、`frontend/types/`、`frontend/utils/` 与相关配置。只记录 `frontend/.env.local.example` 中的配置键名；不读取 `.env.local` 真实值。

**对照提交：** `e748f16d1a2b253c766008f1a060e3ebba9b2f85`（映射时仓库 HEAD 与该提交一致）。

## 语言

**主要语言：**
- TypeScript（`typescript ^5`，锁版本 `5.9.3`）— 应用源码、API client、hooks、Zustand store、类型定义、Jest/Playwright 配置。代表路径：`frontend/app/tender/page.tsx`、`frontend/components/chat/ChatPanel.tsx`、`frontend/hooks/useChatSSE.ts`、`frontend/lib/api.ts`、`frontend/stores/chatStore.ts`、`frontend/types/api.ts`、`frontend/jest.config.ts`、`frontend/playwright.config.ts`。
- TSX / React JSX — Next.js App Router 页面与客户端组件。代表路径：`frontend/app/page.tsx`、`frontend/app/layout.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/MessageList.tsx`。

**辅助语言：**
- CSS — Tailwind 4 入口、CSS variables 与全局组件样式，见 `frontend/app/globals.css`（`@import 'tailwindcss'` + `@theme inline`）。
- JavaScript — Jest setup、Node/jsdom polyfill，见 `frontend/jest.setup.js`、`frontend/polyfills.js`。
- MJS — ESLint / PostCSS ESM 配置，见 `frontend/eslint.config.mjs`、`frontend/postcss.config.mjs`。

## 运行时

**环境：**
- Node.js `>=20.9.0` — `frontend/package.json` 的 `engines.node` 声明；`frontend/.npmrc` 设置 `engine-strict=true` 强制约束。
- Node 主版本 `20` — `frontend/.nvmrc` 固定。
- 浏览器运行时 — 产品代码依赖 `fetch`、`EventSource`、`FormData`、`Blob`、`AbortController`、`URLSearchParams`、`sessionStorage` / `localStorage`、Zustand persist storage 与 DOM API。代表路径：`frontend/lib/api.ts`、`frontend/lib/sse.ts`、`frontend/components/forms/FileUploader.tsx`、`frontend/stores/chatStore.ts`、`frontend/stores/chatTaskSessionStore.ts`。

**包管理器：**
- npm（唯一）— 存在 `frontend/package-lock.json`，`lockfileVersion` 为 `3`。无 yarn/pnpm 锁文件，`package.json` 无 `packageManager` 字段。
- `frontend/.npmrc`：`registry=https://registry.npmjs.org/`、`engine-strict=true`。
- `overrides`：`frontend/package.json` 固定 `postcss` 为 `8.5.14`，避免 Tailwind 4 / PostCSS 版本漂移。

## 框架

**核心：**
- Next.js `^16.2.6`（锁版本 `16.2.6`）— App Router、dev/build/start、`/api/:path*` rewrite、生产 header、图片 remote patterns、React strict mode、关闭 devIndicators、TypeScript build 校验。见 `frontend/package.json`、`frontend/app/`、`frontend/next.config.ts`。
- React `19.2.3` / React DOM `19.2.3`（精确版本）— 组件与 hooks runtime。见 `frontend/components/`、`frontend/hooks/`。
- Zustand `^5.0.11`（锁版本 `5.0.11`）— 会话、草稿、任务、stream、历史与 UI 状态。见 `frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/stores/useAppStore.ts`。
- Tailwind CSS `^4`（锁版本 `4.2.1`）+ `@tailwindcss/postcss ^4`（锁版本 `4.2.1`）— utility 样式与 PostCSS 插件。见 `frontend/app/globals.css`、`frontend/postcss.config.mjs`（仅注册 `@tailwindcss/postcss`）。

**测试：**
- Jest `^29.7.0`（锁版本 `29.7.0`）— 单元测试 runner，配置 `frontend/jest.config.ts`。
- `jest-environment-jsdom ^30.3.0`（锁版本 `30.3.0`）— DOM 测试环境。
- Testing Library — `@testing-library/react ^16.2.0`（锁 `16.3.2`）、`@testing-library/jest-dom ^6.6.3`（锁 `6.9.1`）、`@testing-library/user-event ^14.6.1`（锁 `14.6.1`）；测试位于 `frontend/__tests__/`。
- Playwright `^1.58.2`（锁版本 `1.58.2`）— E2E，配置 `frontend/playwright.config.ts`，用例 `frontend/e2e/`。
- 测试辅助：`frontend/__tests__/mocks/`（`data-factories.ts`、`sse-mock.ts`）、`frontend/test-shims/until-async.ts`、`frontend/polyfills.js`（TextEncoder/Decoder、MessageChannel、Streams）。

**构建 / 开发：**
- Next dev server — `npm run dev` 执行 `next dev --webpack -p 8502`（强制 webpack、端口 8502）。
- TypeScript — `frontend/tsconfig.json` 与 `frontend/tsconfig.typecheck.json`。
- ESLint `^9`（锁 `9.39.3`）+ `eslint-config-next` `16.1.6` + `eslint-plugin-react-hooks ^7.0.1` — `frontend/eslint.config.mjs`。
- Prettier `^3.8.1`（锁 `3.8.1`）+ `prettier-plugin-tailwindcss ^0.7.2` — `frontend/.prettierrc`。
- `ts-node ^10.9.2` — TypeScript 配置加载支持。

## 命令

包管理器一律 npm，不要使用 yarn/pnpm。脚本定义见 `frontend/package.json` 的 `scripts`：

| 命令 | 脚本 | 说明 |
| --- | --- | --- |
| `npm run dev` | `next dev --webpack -p 8502` | 开发服务器（webpack，端口 8502） |
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
- `next` `^16.2.6` — 路由、构建、`/api/:path*` rewrite、生产缓存 header、图片 remote patterns。
- `react` / `react-dom` `19.2.3`（精确）— UI runtime。
- `zustand` `^5.0.11` — `chat-storage`、`chat-task-session-storage`、`tender-history-storage`、`tender-app-storage` 等状态持久化。
- `clsx` `^2.1.1` / `tailwind-merge` `^3.5.0` — className 组合，封装在 `frontend/lib/utils.ts` 的 `cn()`。
- `lucide-react` `^0.575.0` — 图标库（如 `ModelSelector`、`ChatPanel`、`Sidebar`）。
- `prettier` / `prettier-plugin-tailwindcss` — 放在 dependencies，便于脚本统一调用。

**开发依赖（devDependencies）：**
- `@playwright/test` — E2E runner、Chromium 项目、截图/视频/trace。
- `jest`、`jest-environment-jsdom`、`@testing-library/*`、`@types/jest` — 单元与组件测试。
- `@types/node` `^20`、`@types/react` `^19`、`@types/react-dom` `^19` — 类型定义。
- `typescript`、`ts-node` — 严格类型检查与配置加载。
- `eslint`、`eslint-config-next`、`eslint-plugin-react-hooks` — Next/React 静态检查。
- `tailwindcss`、`@tailwindcss/postcss` — Tailwind 4 编译链路。

**刻意未引入的类别：**
- 无 axios / react-query / SWR；HTTP 统一用原生 `fetch`（`frontend/lib/api.ts`）。
- 无 UI 组件库（无 shadcn/MUI/Antd）；表单与布局为自研组件。
- 无 auth SDK、监控 SDK、图表库、国际化框架。

## 配置

**环境变量（配置键名）：**
- `NEXT_PUBLIC_API_URL` — 可选 API base URL（支持逗号分隔多候选）；解析逻辑在 `frontend/lib/apiBaseUrl.ts`；Next rewrite 与 `allowedDevOrigins` 在 `frontend/next.config.ts`。模板键见 `frontend/.env.local.example`。
- `NODE_ENV` — `frontend/next.config.ts` 用于生产 header 分支。
- `CI` — `frontend/playwright.config.ts` 控制 forbidOnly、retries、workers、dev server reuse。
- `PLAYWRIGHT_USE_SYSTEM_CHROME` — 非 CI 下控制是否使用系统 Chrome channel（默认开启，`'0'` 关闭）。
- 本地可存在 `frontend/.env.local`；内容不写入本知识包。

**构建：**
- `frontend/next.config.ts`：`allowedDevOrigins`（`localhost`、`127.0.0.1` 与 `NEXT_PUBLIC_API_URL` 解析 hostname）、`/api/:path*` rewrite 到 `resolveApiBaseUrl()`、生产缓存 header、`images.remotePatterns`（仅 `http://localhost:8000`）、`reactStrictMode: true`、`devIndicators: false`、`typescript.ignoreBuildErrors: false`。
- `frontend/tsconfig.json`：`strict: true`、`target: ES2017`、`moduleResolution: bundler`、`jsx: react-jsx`、Next 插件、`@/*` path alias；`exclude` 含 `node_modules` 与 `node_modules-*`。
- `frontend/tsconfig.typecheck.json`：继承主配置，排除 `.next/dev`。
- `frontend/eslint.config.mjs`：`eslint-config-next/core-web-vitals` + `typescript` + `react-hooks`（`react-hooks/set-state-in-effect: warn`）；ignore 含 `.next`、`node_modules-*/**`、`coverage`、`playwright-report`、`test-results`。
- `frontend/.prettierrc`：`semi: true`、`trailingComma: es5`、`singleQuote: true`、`printWidth: 100`、`tabWidth: 2`、Tailwind 插件。
- `frontend/postcss.config.mjs`：仅 `@tailwindcss/postcss`。
- `frontend/jest.config.ts`：`next/jest`、`testEnvironment: jsdom`、`coverageProvider: v8`、`moduleNameMapper: ^@/(.*)$`、`polyfills.js` + `jest.setup.js`、忽略 `e2e/` 与 `node_modules-wsl/`、全局 coverage threshold 50%。
- `frontend/playwright.config.ts`：`baseURL: http://localhost:8502`、Chromium（非 CI 默认系统 Chrome）、HTML reporter、失败截图/视频/trace、`webServer` 启动 `npm run dev -- --webpack`。

**应用入口：**
- `frontend/app/page.tsx` 直接 `redirect('/tender')`。
- `frontend/app/tender/page.tsx` 是三栏工作台入口（`TenderTypeSidebar`、`FormPanel`、`ChatPanel`），处理 URL 深链、招标数据同步与 conversation heartbeat。
- `frontend/app/layout.tsx`：`lang="zh-CN"` 根布局与 metadata。
- `frontend/app/api/` 不存在；前端不实现 Next API route。

**状态：**
- `frontend/stores/chatStore.ts` — 主会话 store；persist 到 `sessionStorage` 的 `chat-storage`（conversations、草稿、任务摘要、未读结果）。
- `frontend/stores/chatStreamStore.ts` — 任务 stream 运行时（日志、正文、进度、agent step、last event id）；纯内存，不持久化完整 stream payload。
- `frontend/stores/chatTaskSessionStore.ts` — persist 到 `sessionStorage` 的 `chat-task-session-storage`（task id 与 last event id）。
- `frontend/stores/historyStore.ts` — persist 到 `sessionStorage` 的 `tender-history-storage`。
- `frontend/stores/useAppStore.ts` — persist 到 `tender-app-storage`；未显式指定 storage adapter（Zustand 默认 `localStorage`）；`partialize` 仅保留 `sidebarOpen`。

**Hooks（网络 / 任务相关）：**
- `frontend/hooks/useSSE.ts` — 通用 EventSource 连接（`createSSEConnection()`）。
- `frontend/hooks/useChatSSE.ts` — 任务 SSE 事件到 chat/stream store 映射与终态清理；SSE `heartbeatTimeout: 45000`。
- `frontend/hooks/useTaskHeartbeat.ts` — 周期调用 `sendTaskHeartbeat()`（`HEARTBEAT_INTERVAL_MS = 5000`）。
- `frontend/hooks/useCurrentConversationTaskStatus.ts` — 当前会话任务状态轮询（默认 5s；starting 任务可降至 400ms）。
- `frontend/hooks/useLatestActiveTaskSummary.ts` — 任务列表 / 活跃摘要（默认 5s）。
- `frontend/hooks/useUrlParams.ts` — URL 深链与招标类型 canonical。
- `frontend/hooks/useHydrated.ts` — persist 水合完成标记。

**库模块（非网络 UI 辅助）：**
- `frontend/lib/apiBaseUrl.ts` — `NEXT_PUBLIC_API_URL` 多候选解析、host 别名、默认 `http://localhost:8000`。
- `frontend/lib/api.ts` — 唯一产品 `fetch` 出口（JSON / FormData / Blob / NDJSON）。
- `frontend/lib/sse.ts` — EventSource 封装。
- `frontend/lib/formDataConverter.ts` — 表单 draft → `GenerateRequest`。
- `frontend/lib/gngkFormType.ts` — `gngk` UI 类型 → 后端 `form_type`。
- `frontend/lib/tenderFetch.ts` — 招标查询封装。
- `frontend/lib/agentThinking.ts` — agent run 思考阶段折叠。
- `frontend/lib/chat-utils.ts`、`frontend/lib/utils.ts` — 聊天与 className 工具。
- `frontend/utils/tenderTypeMapper.ts` — tender type URL/UI canonical。

## 平台要求

**开发：**
- 前端端口固定 `8502`（`dev` / `start`）。
- 后端 API 默认端口 `8000`，经 `NEXT_PUBLIC_API_URL`、`apiBaseUrl.ts`、`next.config.ts` 对接。
- 配置与 Jest 已预留 `node_modules-*` / `node_modules-wsl` 忽略，跨平台切换时不要复用原生依赖目录。
- 完整 Word 生成闭环依赖后端 Windows Python、pywin32 与 Word/WPS COM；前端只负责浏览器工作台与 API/SSE。

**生产：**
- `frontend/` 顶层未检测到 `vercel.json`、`Dockerfile`、`docker-compose*.yml` 或 `netlify.toml`。
- 仓库级 `.github/workflows/` 未检测到。
- 生产由 `npm run build` / `npm run start` 承载；`typescript.ignoreBuildErrors: false`。
- 生产 header：`/_next/static/:path*` 为 immutable cache；其他路径 `no-store`。

---

*前端技术栈分析：2026-07-21*

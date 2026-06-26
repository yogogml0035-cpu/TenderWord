# 前端技术栈事实地图

**分析日期：** 2026-06-25

**范围：** 仅 `frontend/` 子项目。依据 `frontend/package.json`、`frontend/package-lock.json`、`frontend/next.config.ts`、`frontend/tsconfig.json`、`frontend/tsconfig.typecheck.json`、`frontend/jest.config.ts`、`frontend/playwright.config.ts`、`frontend/eslint.config.mjs`、`frontend/postcss.config.mjs`、`frontend/app/`、`frontend/components/`、`frontend/hooks/`、`frontend/lib/`、`frontend/stores/`、`frontend/types/`、`docs/frontend.md`、`docs/interfaces-runtime.md` 和 `README.md`。`frontend/.env.local`、`frontend/.env.local.example` 和 `frontend/.npmrc` 文件存在；只记录存在性，不读取内容。

## 语言

**主要语言：**
- TypeScript 5.9.3 - 应用源码、API client、hooks、Zustand store、类型定义、测试配置和 Playwright 配置。代表路径：`frontend/app/tender/page.tsx`、`frontend/components/chat/ChatPanel.tsx`、`frontend/hooks/useChatSSE.ts`、`frontend/lib/api.ts`、`frontend/stores/chatStore.ts`、`frontend/types/api.ts`、`frontend/jest.config.ts`、`frontend/playwright.config.ts`。
- TSX / React JSX - Next.js App Router 页面和客户端组件。代表路径：`frontend/app/page.tsx`、`frontend/app/layout.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/MessageList.tsx`。

**辅助语言：**
- CSS - Tailwind 4 入口、CSS variables 和全局组件样式，见 `frontend/app/globals.css`。
- JavaScript - Jest setup、Node/jsdom polyfill，见 `frontend/jest.setup.js`、`frontend/polyfills.js`。
- MJS - ESLint/PostCSS ESM 配置，见 `frontend/eslint.config.mjs`、`frontend/postcss.config.mjs`。

## 运行时

**环境：**
- Node.js `>=20.9.0` - `frontend/package.json` 的 `engines.node` 声明。
- Node 20 - `frontend/.nvmrc` 固定主版本。
- 浏览器运行时 - 产品代码依赖 `fetch`、`EventSource`、`FormData`、`Blob`、`AbortController`、`URLSearchParams`、`sessionStorage`、Zustand persist storage 和 Clipboard/DOM API。代表路径：`frontend/lib/api.ts`、`frontend/lib/sse.ts`、`frontend/components/forms/FileUploader.tsx`、`frontend/stores/chatStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/components/chat/TaskLogMessage.tsx`。

**包管理器：**
- npm - `frontend/package-lock.json` 存在，`lockfileVersion` 为 3。
- Lockfile：存在，路径为 `frontend/package-lock.json`。
- `frontend/.npmrc` 文件存在；内容不读取。

## 框架

**核心：**
- Next.js 16.2.6 - App Router、dev/build/start、`/api/:path*` rewrite、生产 header、图片 remote pattern、React strict mode 和 TypeScript build 校验，见 `frontend/package.json`、`frontend/app/`、`frontend/next.config.ts`。
- React 19.2.3 / React DOM 19.2.3 - 组件和 hooks runtime，见 `frontend/components/`、`frontend/hooks/`。
- Zustand 5.0.11 - 会话、草稿、任务、stream、历史和 UI 状态，见 `frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/stores/useAppStore.ts`。
- Tailwind CSS 4.2.1 + `@tailwindcss/postcss` 4.2.1 - utility 样式、`@theme inline` 和 PostCSS 插件，见 `frontend/app/globals.css`、`frontend/postcss.config.mjs`。

**测试：**
- Jest 29.7.0 - 单元测试 runner，配置位于 `frontend/jest.config.ts`。
- `jest-environment-jsdom` 30.3.0 - DOM 测试环境，见 `frontend/jest.config.ts`。
- Testing Library - React 组件、hook 和用户事件测试，依赖见 `frontend/package.json`，测试位于 `frontend/__tests__/unit/`。
- Playwright 1.58.2 - E2E 测试，配置位于 `frontend/playwright.config.ts`，测试位于 `frontend/e2e/`。

**构建/开发：**
- Next dev server - `npm run dev` 执行 `next dev --webpack -p 8502`，见 `frontend/package.json`。
- TypeScript compiler 5.9.3 - `frontend/tsconfig.json` 和 `frontend/tsconfig.typecheck.json`。
- ESLint 9.39.3 + `eslint-config-next` 16.1.6 + `eslint-plugin-react-hooks` 7.0.1 - lint 配置位于 `frontend/eslint.config.mjs`。
- Prettier 3.8.1 + `prettier-plugin-tailwindcss` 0.7.2 - 格式化与 Tailwind class 排序，配置位于 `frontend/.prettierrc`。
- `ts-node` 10.9.2 - TypeScript 配置执行支持，见 `frontend/package.json`。

## 关键依赖

**关键：**
- `next` 16.2.6 - 路由、构建、`/api/:path*` rewrite、生产缓存 header 和图片 remote pattern。
- `react` 19.2.3 / `react-dom` 19.2.3 - UI runtime。
- `zustand` 5.0.11 - `chat-storage`、`chat-task-session-storage`、`tender-history-storage` 和 `tender-app-storage` 等状态持久化。
- `lucide-react` 0.575.0 - 图标库，见 `frontend/components/forms/TemplateCandidateDialog.tsx`、`frontend/components/chat/ChatInput.tsx`、`frontend/components/layout/Sidebar.tsx`。
- `clsx` 2.1.1 / `tailwind-merge` 3.5.0 - className 组合工具，封装在 `frontend/lib/utils.ts`。

**基础设施：**
- `@playwright/test` 1.58.2 - E2E runner、Chromium 项目、截图/视频/trace 证据。
- `jest` 29.7.0、`@testing-library/react` 16.3.2、`@testing-library/jest-dom` 6.9.1、`@testing-library/user-event` 14.6.1 - 单元和组件测试。
- `typescript` 5.9.3 - 严格类型检查和 Next 类型生成。
- `eslint` 9.39.3、`eslint-config-next` 16.1.6、`eslint-plugin-react-hooks` 7.0.1 - Next/React 静态检查。
- `tailwindcss` 4.2.1、`@tailwindcss/postcss` 4.2.1 - Tailwind 4 编译链路。

## 配置

**环境：**
- `NEXT_PUBLIC_API_URL` - 可选 API base URL 配置键；解析逻辑在 `frontend/lib/apiBaseUrl.ts`，Next rewrite 和开发期 allowed origins 在 `frontend/next.config.ts`。
- `NODE_ENV` - `frontend/next.config.ts` 用于生产 header 分支。
- `CI` - `frontend/playwright.config.ts` 用于控制 forbidOnly、retries、workers 和 dev server reuse。
- `PLAYWRIGHT_USE_SYSTEM_CHROME` - `frontend/playwright.config.ts` 用于控制非 CI 环境是否使用系统 Chrome channel。
- `frontend/.env.local` 文件存在，作为本地环境配置；内容不读取。
- `frontend/.env.local.example` 文件存在，作为示例环境文件；内容不读取。

**构建：**
- `frontend/next.config.ts`：`allowedDevOrigins`、`/api/:path*` rewrite、生产缓存 header、`images.remotePatterns`、`reactStrictMode: true`、`typescript.ignoreBuildErrors: false`。
- `frontend/tsconfig.json`：`strict: true`、`moduleResolution: bundler`、`jsx: react-jsx`、Next 插件、`@/*` path alias。
- `frontend/tsconfig.typecheck.json`：type-check 专用配置，排除 `.next/dev`。
- `frontend/eslint.config.mjs`：Next core web vitals、Next TypeScript、React hooks 插件和生成目录 ignore。
- `frontend/.prettierrc`：2 空格、单引号、分号、100 列、Tailwind 插件。
- `frontend/postcss.config.mjs`：`@tailwindcss/postcss` 插件。
- `frontend/jest.config.ts`：Next/Jest 集成、`jsdom`、coverage、moduleNameMapper、`polyfills.js`、`jest.setup.js` 和 50% 全局 coverage threshold。
- `frontend/playwright.config.ts`：`baseURL: http://localhost:8502`、Chromium 项目、HTML reporter、失败截图/视频/trace、dev server。

**应用入口：**
- `frontend/app/page.tsx` 直接 redirect 到 `/tender`。
- `frontend/app/tender/page.tsx` 是三栏工作台入口，组合 `TenderTypeSidebar`、`FormPanel`、`ChatPanel`，并处理 URL 深链、招标数据同步和 conversation heartbeat。
- `frontend/app/layout.tsx` 设置 `zh-CN` 根布局和 metadata。
- `frontend/app/api/` 未检测到；前端不实现 Next API route。

**状态：**
- `frontend/stores/chatStore.ts` 是主会话 store，持久化 conversations、草稿、任务摘要和未读结果到 `sessionStorage` 的 `chat-storage`。
- `frontend/stores/chatStreamStore.ts` 保存任务 stream 运行时日志、正文、进度、agent step 和 last event id；该 store 不持久化完整 stream payload。
- `frontend/stores/chatTaskSessionStore.ts` 持久化 task id 与 last event id 到 `sessionStorage` 的 `chat-task-session-storage`。
- `frontend/stores/historyStore.ts` 持久化最近生成历史到 `sessionStorage` 的 `tender-history-storage`。
- `frontend/stores/useAppStore.ts` 仅持久化 `sidebarOpen` 到 `tender-app-storage`。

## 平台要求

**开发：**
- 前端开发端口是 `8502`，脚本见 `frontend/package.json` 的 `dev` / `start`。
- 后端 API 默认端口是 `8000`，前端通过 `NEXT_PUBLIC_API_URL`、`frontend/lib/apiBaseUrl.ts` 和 `frontend/next.config.ts` 对接。
- 推荐命令：

```bash
npm ci
npm run dev
npm run lint
npm run type-check
npm run test
npm run test:e2e
```

- `README.md` 记录 Windows/WSL 双模式开发；前端依赖目录可能出现 `frontend/node_modules/`、`frontend/node_modules-wsl/` 或 `frontend/node_modules-win/`，跨平台切换时不要复用原生依赖目录。
- 完整 Word 生成闭环依赖后端 Windows Python、pywin32 和 Word/WPS COM 环境；前端自身只负责浏览器工作台和 API/SSE 接入。

**生产：**
- `frontend/` 顶层未检测到 `vercel.json`、`Dockerfile`、`docker-compose*.yml` 或 `netlify.toml`。
- 仓库级 `.github/workflows/` 未检测到。
- 生产构建由 `npm run build` / `npm run start` 承载，`frontend/next.config.ts` 不忽略 TypeScript build errors。
- 生产 header：`/_next/static/:path*` 使用 immutable cache，其他路径使用 `no-store`，见 `frontend/next.config.ts`。

---

*前端技术栈分析：2026-06-25*

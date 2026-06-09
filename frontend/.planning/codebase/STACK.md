# 前端技术栈事实地图

**分析日期：** 2026-06-09

**范围：** 仅 `frontend/` 子项目。依据 `frontend/package.json`、`frontend/package-lock.json`、`frontend/next.config.ts`、TypeScript/Jest/Playwright/ESLint/Prettier/PostCSS 配置、`frontend/app/`、`frontend/components/`、`frontend/hooks/`、`frontend/lib/`、`frontend/stores/`、`frontend/types/`、`README.md`、`docs/frontend.md`、`docs/interfaces-runtime.md` 和既有 `frontend/.planning/codebase/` 事实文档刷新。`frontend/README*` 未检测到。`frontend/.env.local`、`frontend/.env.local.example` 和 `frontend/.npmrc` 文件存在；内容不读取，不写入事实文档。

## 语言

**主要语言：**
- TypeScript 5 - 应用源码、类型、API client、Zustand store、测试配置和 Playwright 配置，见 `frontend/app/`、`frontend/components/`、`frontend/hooks/`、`frontend/lib/`、`frontend/stores/`、`frontend/types/`、`frontend/jest.config.ts`、`frontend/playwright.config.ts`。
- TSX / React JSX - Next.js App Router 页面和客户端组件，见 `frontend/app/page.tsx`、`frontend/app/tender/page.tsx`、`frontend/components/chat/`、`frontend/components/forms/`。

**辅助语言：**
- CSS - Tailwind 4 入口、CSS variables 和全局样式，见 `frontend/app/globals.css`。
- JavaScript - Jest setup 与 Node/jsdom polyfill，见 `frontend/jest.setup.js`、`frontend/polyfills.js`。

## 运行时

**环境：**
- Node.js `>=20.9.0` - `frontend/package.json` 的 `engines.node` 声明。
- Node 20 - `frontend/.nvmrc` 固定主版本。
- 浏览器运行时 - 前端依赖 `fetch`、`EventSource`、`FormData`、`Blob`、`sessionStorage`、`URLSearchParams`、`AbortController`、Clipboard 和 DOM APIs，代表文件为 `frontend/lib/api.ts`、`frontend/lib/sse.ts`、`frontend/components/forms/FileUploader.tsx`、`frontend/stores/chatStore.ts`。

**包管理器：**
- npm - `frontend/package-lock.json` 存在。
- Lockfile：存在，`frontend/package-lock.json` 的 `lockfileVersion` 为 3。
- `frontend/.npmrc` 文件存在；内容不读取。`README.md` 记录 fresh clone 使用 `npm ci`。

## 框架

**核心：**
- Next.js `^16.2.6` - App Router、dev/build/start、rewrites、headers、图片 remote pattern、React strict mode 和 TypeScript build 校验，见 `frontend/package.json`、`frontend/app/`、`frontend/next.config.ts`。
- React `19.2.3` / React DOM `19.2.3` - 页面、客户端组件和 hooks runtime，见 `frontend/components/`、`frontend/hooks/`。
- Zustand `^5.0.11` - 会话、草稿、任务、stream、历史和 UI 状态，见 `frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/stores/useAppStore.ts`。
- Tailwind CSS `^4` + `@tailwindcss/postcss` `^4` - utility 样式与 PostCSS 插件，见 `frontend/app/globals.css`、`frontend/postcss.config.mjs`。

**测试：**
- Jest `^29.7.0` - 单元与集成测试 runner，配置位于 `frontend/jest.config.ts`。
- `jest-environment-jsdom` `^30.3.0` - DOM 测试环境，见 `frontend/jest.config.ts`。
- Testing Library - React 组件测试依赖，见 `frontend/package.json`、`frontend/__tests__/unit/components/`。
- MSW `^2.12.10` - API mock，见 `frontend/mocks/handlers.ts`、`frontend/mocks/server.ts`。
- Playwright `^1.58.2` - E2E 测试，见 `frontend/playwright.config.ts`、`frontend/e2e/`。

**构建/开发：**
- Next dev server - `npm run dev` 执行 `next dev --webpack -p 8502`，见 `frontend/package.json`。
- TypeScript compiler `^5` - `frontend/tsconfig.json` 和 `frontend/tsconfig.typecheck.json`。
- ESLint 9 + `eslint-config-next` `16.1.6` + `eslint-plugin-react-hooks` `^7.0.1` - lint，见 `frontend/eslint.config.mjs`。
- Prettier `^3.8.1` + `prettier-plugin-tailwindcss` `^0.7.2` - 格式化与 Tailwind class 排序，见 `frontend/.prettierrc`。

## 关键依赖

**关键：**
- `next` `^16.2.6` - 路由、构建、`/api/:path*` rewrite、生产缓存 header 和图片 remote pattern。
- `react` `19.2.3` / `react-dom` `19.2.3` - UI runtime。
- `zustand` `^5.0.11` - `chat-storage`、`chat-task-session-storage`、`tender-history-storage` 和 `tender-app-storage` 等前端状态。
- `lucide-react` `^0.575.0` - 图标库，见 `frontend/components/forms/TemplateCandidateDialog.tsx`、`frontend/components/chat/ChatInput.tsx`、`frontend/components/layout/Sidebar.tsx`。
- `clsx` `^2.1.1` / `tailwind-merge` `^3.5.0` - className 组合，见 `frontend/lib/utils.ts`。

**基础设施：**
- `@playwright/test` `^1.58.2` - E2E runner 与 Chromium 项目配置，见 `frontend/playwright.config.ts`。
- `msw` `^2.12.10` - Jest API mock 和错误场景模拟，见 `frontend/mocks/handlers.ts`。
- `jest-fetch-mock` `^3.0.3` - fetch mock 支持，见 `frontend/package.json`。
- `undici` `^7.22.0` / `und` `^2.13.0` - Node/fetch 兼容依赖，见 `frontend/package.json`。
- `ts-node` `^10.9.2` - TypeScript 配置执行支持，见 `frontend/package.json`。

## 配置

**环境：**
- `NEXT_PUBLIC_API_URL` - 可选 API base URL 配置键；解析逻辑在 `frontend/lib/apiBaseUrl.ts`，Next rewrite 和开发期 allowed origins 在 `frontend/next.config.ts`。
- `NODE_ENV` - `frontend/next.config.ts` 用于区分生产 header。
- `CI` - `frontend/playwright.config.ts` 用于控制 forbidOnly、retries、workers 和 dev server reuse。
- `PLAYWRIGHT_USE_SYSTEM_CHROME` - `frontend/playwright.config.ts` 用于控制非 CI 环境是否使用系统 Chrome channel。
- `frontend/.env.local` 文件存在，作为本地环境配置；内容不读取。
- `frontend/.env.local.example` 文件存在，作为示例环境文件；内容不读取。

**构建：**
- `frontend/next.config.ts`：`allowedDevOrigins`、`/api/:path*` rewrite、生产缓存 header、`images.remotePatterns`、`reactStrictMode: true`、`typescript.ignoreBuildErrors: false`。
- `frontend/tsconfig.json`：`strict: true`、`moduleResolution: bundler`、`jsx: react-jsx`、Next 插件、`@/*` path alias。
- `frontend/tsconfig.typecheck.json`：type-check 专用配置，排除 `.next/dev`。
- `frontend/eslint.config.mjs`：Next core web vitals、Next TS、React hooks 插件和生成目录 ignore。
- `frontend/.prettierrc`：2 空格、单引号、分号、100 列、Tailwind 插件。
- `frontend/postcss.config.mjs`：`@tailwindcss/postcss` 插件。
- `frontend/jest.config.ts`：Next/Jest 集成、`jsdom`、coverage、moduleNameMapper、MSW transform 兼容和 50% 全局 coverage threshold。
- `frontend/playwright.config.ts`：`baseURL: http://localhost:8502`、Chromium 项目、HTML reporter、失败截图/视频/trace、dev server。

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

- `README.md` 记录 Windows/WSL 双模式开发；前端依赖目录可能包含 `frontend/node_modules/` 和 `frontend/node_modules-wsl/`，跨平台切换时不要复用原生依赖目录。
- 完整 Word 生成闭环依赖后端 Windows Python、pywin32 和 Word/WPS COM 环境；前端自身只负责浏览器工作台和 API/SSE 接入。

**生产：**
- `frontend/` 顶层未检测到 `vercel.json`、`Dockerfile`、`docker-compose*.yml` 或 `netlify.toml`。
- 仓库级 `.github/workflows/` 未检测到。
- 生产构建由 Next.js `npm run build` / `npm run start` 承载，`frontend/next.config.ts` 不忽略 TypeScript build errors。
- 生产 header：`/_next/static/:path*` 使用 immutable cache，其他路径使用 `no-store`，见 `frontend/next.config.ts`。

---

*前端技术栈分析：2026-06-09*

# 前端技术栈事实地图

**分析日期：** 2026-06-08

**范围：** 仅 `frontend/` 子项目。依据当前 `frontend/package.json`、前端配置文件、源码目录、测试配置和项目级 `.agents/skills/` 轻量索引刷新；未读取 `.env.local`、`.env.local.example` 或 `.npmrc` 内容。

## 语言

**主要语言：**
- TypeScript 5 - 应用源码、API client、Zustand store、类型定义、Jest/Playwright 测试，见 `frontend/app/`、`frontend/components/`、`frontend/lib/`、`frontend/stores/`、`frontend/types/`。
- TSX / React JSX - Next.js 页面与客户端组件，见 `frontend/app/tender/page.tsx`、`frontend/components/chat/`、`frontend/components/forms/`。

**辅助语言：**
- CSS - Tailwind 4 入口、主题变量和少量全局组件 class，见 `frontend/app/globals.css`。
- JavaScript - Jest setup 和运行时 polyfill，见 `frontend/jest.setup.js`、`frontend/polyfills.js`。

## 运行时

**环境：**
- Node.js `>=20.9.0` - 由 `frontend/package.json` 的 `engines.node` 声明。
- Node 20 - 由 `frontend/.nvmrc` 固定主版本。
- 浏览器运行时 - 前端依赖 `fetch`、`EventSource`、`sessionStorage`、`URLSearchParams` 和 DOM APIs。

**包管理器：**
- npm - `frontend/package-lock.json` 存在。
- 依赖安装使用 npm 语义；不要在 Windows 与 WSL 之间盲目复用 `frontend/node_modules/`。

## 框架

**核心：**
- Next.js `^16.2.6` - App Router、dev/build/start、rewrites、headers，见 `frontend/package.json`、`frontend/app/`、`frontend/next.config.ts`。
- React `19.2.3` / React DOM `19.2.3` - 客户端组件和 hooks。
- Zustand `^5.0.11` - 会话、任务、stream、历史和 UI 状态，见 `frontend/stores/`。
- Tailwind CSS `^4` + `@tailwindcss/postcss` - utility 样式和 PostCSS 集成，见 `frontend/app/globals.css`、`frontend/postcss.config.mjs`。

**测试：**
- Jest `^29.7.0` - 单元/集成测试 runner，见 `frontend/jest.config.ts`。
- `jest-environment-jsdom` `^30.3.0` - DOM 测试环境。
- Testing Library - React 组件测试，见 `frontend/__tests__/unit/components/`。
- MSW `^2.12.10` - 测试 API mock，见 `frontend/mocks/`。
- Playwright `^1.58.2` - E2E 测试，见 `frontend/playwright.config.ts`、`frontend/e2e/`。

**构建/开发：**
- ESLint 9 + `eslint-config-next` - lint，见 `frontend/eslint.config.mjs`。
- Prettier 3 + `prettier-plugin-tailwindcss` - 格式化与 Tailwind class 排序，见 `frontend/.prettierrc`。
- TypeScript compiler - `frontend/tsconfig.json` 和 `frontend/tsconfig.typecheck.json`。

## 关键依赖

**关键：**
- `next` - 页面、构建、开发服务器和 `/api` rewrite。
- `react` / `react-dom` - UI runtime。
- `zustand` - 本地会话、草稿、任务摘要和恢复状态。
- `lucide-react` - 图标库，组件按钮和状态图标优先使用它。
- `tailwind-merge` / `clsx` - className 组合，见 `frontend/lib/utils.ts`。

**基础设施：**
- `undici` / `und` - 测试或 Node fetch 兼容依赖，见 `frontend/package.json`。
- `msw` - Jest API mocking，见 `frontend/mocks/handlers.ts`。
- `ts-node` - TypeScript 配置执行支持，见 `frontend/jest.config.ts` 等工具链。

## 配置

**环境：**
- `frontend/.env.local` 存在，只作为本地环境配置文件；不得读取或写入真实值。
- `frontend/.env.local.example` 存在，只记录示例文件存在；不得复制其中内容到长期文档。
- `NEXT_PUBLIC_API_URL` 是前端可识别的 API base URL 配置键；解析逻辑在 `frontend/lib/apiBaseUrl.ts`，开发期 rewrite 在 `frontend/next.config.ts`。
- 缺省 API base URL 由 `frontend/lib/apiBaseUrl.ts` 回落到本机后端端口或按浏览器 hostname 推导。

**构建：**
- `frontend/next.config.ts`：Next 配置、`/api/:path*` rewrite、生产缓存 header、开发来源白名单和图片远程模式。
- `frontend/tsconfig.json`：严格 TypeScript、`@/*` path alias、Next 插件。
- `frontend/tsconfig.typecheck.json`：稳定 type-check 专用配置，排除 `.next/dev`。
- `frontend/eslint.config.mjs`：Next core web vitals、Next TS 和 React hooks 规则。
- `frontend/.prettierrc`：2 空格、单引号、分号、100 列、Tailwind 插件。
- `frontend/jest.config.ts`：Next/Jest 集成、jsdom、coverage、moduleNameMapper 和 MSW transform 兼容。
- `frontend/playwright.config.ts`：E2E baseURL、Chromium 项目、dev server。

## 平台要求

**开发：**
- 默认前端端口是 `8502`，脚本见 `frontend/package.json` 的 `dev` / `start`。
- 常规命令：

```bash
npm run dev
npm run lint
npm run type-check
npm run test
npm run test:e2e
```

- WSL 环境运行测试时优先显式设置 `TMPDIR=/tmp TMP=/tmp TEMP=/tmp`，避免继承 Windows 临时目录导致缓存或浏览器工具异常。

**生产：**
- 当前前端产物由 Next.js build/start 承载；仓库内未在 `frontend/` 检测到独立前端部署平台配置。
- 前端生产构建不忽略 TypeScript build errors，见 `frontend/next.config.ts` 的 `typescript.ignoreBuildErrors: false`。

---

*前端技术栈分析：2026-06-08*

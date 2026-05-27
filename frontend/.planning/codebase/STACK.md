# 前端技术栈事实地图

**分析日期：** 2026-05-27

**范围：** `frontend/` 及前端启动/测试相关根脚本。

## 语言与运行时

- **TypeScript / TSX**：应用、组件、hook、store、API client、测试。
- **React JSX**：Next App Router 页面与客户端组件。
- **CSS + Tailwind 4**：全局样式与 utility。
- **JavaScript**：Jest setup、polyfill。
- **PowerShell / Bash**：本地启动脚本。

Node 要求来自 `frontend/package.json`：`>=20.9.0`；`frontend/.nvmrc` 固定 Node 20。

## 包管理与脚本

- 包管理器：npm。
- lockfile：`frontend/package-lock.json`。
- 依赖安装推荐：`npm ci`。

常用脚本：

```bash
npm run dev            # Next dev server，端口 8502
npm run build          # Next production build
npm run start          # Next production server，端口 8502
npm run lint           # ESLint
npm run type-check     # tsc --noEmit
npm run test           # Jest
npm run test:coverage  # Jest coverage
npm run test:e2e       # Playwright
```

## 核心框架与库

| 技术 | 用途 | 证据 |
| --- | --- | --- |
| Next.js 16 | App Router、dev/build、rewrites、headers | `frontend/package.json`, `frontend/next.config.ts` |
| React 19 | 客户端组件与 hooks | `frontend/components/`, `frontend/app/tender/page.tsx` |
| Tailwind CSS 4 | 样式系统 | `frontend/app/globals.css`, `frontend/postcss.config.mjs` |
| Zustand 5 | 会话、stream、历史与 UI 状态 | `frontend/stores/` |
| lucide-react | 图标库 | `frontend/package.json` |
| Jest + Testing Library | 单元/集成测试 | `frontend/jest.config.ts`, `frontend/__tests__/` |
| MSW | API mock | `frontend/mocks/` |
| Playwright | E2E | `frontend/playwright.config.ts`, `frontend/e2e/` |
| ESLint / Prettier | lint 与格式化 | `frontend/eslint.config.mjs`, `frontend/.prettierrc` |

## 配置

- Next 配置：`frontend/next.config.ts`。
- TypeScript 配置：`frontend/tsconfig.json`，包含 `@/*` alias。
- Jest 配置：`frontend/jest.config.ts`。
- Playwright 配置：`frontend/playwright.config.ts`，baseURL 为 `http://localhost:8502`。
- 环境示例：`frontend/.env.local.example`。
- `.npmrc` 固定 npm registry。

## 前端入口

- 页面入口：`frontend/app/page.tsx`、`frontend/app/tender/page.tsx`。
- API 入口：`frontend/lib/api.ts`。
- SSE 入口：`frontend/lib/sse.ts`、`frontend/hooks/useChatSSE.ts`。
- 表单转换：`frontend/lib/formDataConverter.ts`；`gngk` form type 分派：`frontend/lib/gngkFormType.ts`。
- URL 映射：`frontend/utils/tenderTypeMapper.ts`。
- 主 store：`frontend/stores/chatStore.ts`。

## 平台要求

- 前端 dev server 默认端口：`8502`。
- WSL 中运行前端时，必须使用 Linux `node` / `npm`。
- Windows 启动前端时，`frontend/node_modules` 应由 Windows npm 安装或由启动脚本修复。
- 测试前若在 WSL，优先设置 `TMPDIR=/tmp TMP=/tmp TEMP=/tmp`，避免继承 Windows 临时目录导致 Jest/Playwright 缓存失败。

---

*前端技术栈分析：2026-05-23*

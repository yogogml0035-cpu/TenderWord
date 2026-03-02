# AGENTS.md - frontend/

招标文档系统前端层。Next.js 16 App Router + React 19 + Tailwind CSS 4。

## STRUCTURE

```
frontend/
├── app/                    # App Router
│   ├── layout.tsx          # 根布局
│   ├── page.tsx            # 主页面
│   └── tender/[type]/      # 动态招标类型路由
├── components/
│   ├── common/             # 通用组件 (Button, Card, Input)
│   ├── forms/              # 表单组件 (按招标类型)
│   ├── generation/         # 文档生成相关组件
│   └── layout/             # 布局组件 (Header, Sidebar)
├── stores/
│   ├── useAppStore.ts      # 全局应用状态 (Zustand)
│   └── historyStore.ts     # 生成历史记录状态
├── hooks/
│   └── useSSE.ts           # Server-Sent Events Hook
├── types/
│   ├── api.ts              # API 类型定义
│   └── index.ts            # 全局类型
├── lib/
│   └── utils.ts            # 工具函数 (cn, formatDate)
└── e2e/                    # Playwright E2E 测试
```

## WHERE TO LOOK

| 任务 | 位置 | 说明 |
|------|------|------|
| 添加新表单 | `components/forms/` | 按招标类型分目录 |
| 修改全局状态 | `stores/useAppStore.ts` | 招标类型、文件、进度 |
| 添加 API 类型 | `types/api.ts` | 后端接口类型映射 |
| 修改页面布局 | `app/layout.tsx` | 根布局 |
| 新招标类型路由 | `app/tender/[type]/page.tsx` | 动态路由 |
| 新增工具函数 | `lib/utils.ts` | 公共工具函数 |
| E2E 测试 | `e2e/*.spec.ts` | Playwright 测试用例 |

## CONVENTIONS

- **路径别名**: `@/*` 映射到项目根目录
- **状态命名**: Store 文件用 camelCase (useXxxStore.ts)，使用时用 useXxxStore()
- **组件组织**: 按功能域分目录，非按类型分
- **类型导出**: `types/index.ts` 统一导出，组件就近定义 Props
- **Tailwind 4**: 不使用 `tailwind.config.ts`，配置在 CSS 变量

## ANTI-PATTERNS

| 禁止 | 原因 | 位置 |
|------|------|------|
| 中文 npm 镜像 | 供应链风险 | `package-lock.json` 存在 |
| `use client` 滥用 | 增加客户端 bundle | 检查组件必要性 |
| 直接调用 fetch | 使用统一的 API 封装 | - |

## COMMANDS

```bash
npm run dev          # 开发服务器 (port 3000)
npm run build        # 生产构建
npm run lint         # ESLint 检查
npm run format       # Prettier 格式化
npm run test:e2e     # Playwright E2E 测试
```

# frontend/

**Generated:** 2026-03-03  
**Commit:** 998002b  
**Branch:** feat-wsq-h

招标文档系统前端层。Next.js 16 App Router + React 19 + Tailwind CSS 4。

## STRUCTURE

```
frontend/
├── app/                          # App Router
│   ├── layout.tsx                # 根布局 (全局 Provider)
│   ├── page.tsx                  # 主页面 (招标类型选择)
│   ├── globals.css               # 全局样式 (Tailwind 4 + CSS 变量)
│   └── tender/
│       └── [type]/               # 动态招标类型路由
│           └── page.tsx          # 招标表单页面 (xjcg/gngk)
│
├── components/                   # React 组件
│   ├── forms/                    # 表单组件 (按招标类型)
│   │   ├── BaseForm.tsx          # 表单基础布局
│   │   ├── XjcgTenderForm.tsx    # 询价采购表单
│   │   ├── GngkTenderForm.tsx    # 公开招标表单
│   │   ├── TenderNoInput.tsx     # 招标编号输入组件
│   │   ├── FileUploader.tsx      # 文件上传组件
│   │   └── ModelSelector.tsx     # 模型选择器
│   │
│   └── layout/                   # 布局组件
│       ├── Header.tsx            # 页面头部
│       ├── Sidebar.tsx           # 侧边栏导航
│       ├── MainLayout.tsx        # 主布局容器
│       └── HistorySection.tsx    # 历史记录面板
│
├── stores/                       # Zustand 状态管理
│   ├── useAppStore.ts            # 全局应用状态
│   └── historyStore.ts           # 生成历史记录
│
├── hooks/                        # React Hooks
│   └── useSSE.ts                 # Server-Sent Events Hook
│
├── types/                        # TypeScript 类型定义
│   ├── index.ts                  # 全局类型导出
│   └── api.ts                    # API 类型定义
│
├── lib/                          # 工具库
│   ├── utils.ts                  # 工具函数 (cn, formatDate)
│   ├── api.ts                    # API 封装方法
│   └── sse.ts                    # SSE 工具函数
│
├── e2e/                          # Playwright E2E 测试
│   └── home.spec.ts              # 首页测试用例
│
├── public/                       # 静态资源
│
├── next.config.ts                # Next.js 配置
├── next-env.d.ts                 # Next.js 类型声明
└── playwright.config.ts          # Playwright 配置
```

## CODE MAP

| 模块 | 类型 | 位置 | 职责 |
|------|------|------|------|
| `useAppStore` | Zustand Store | `stores/useAppStore.ts` | 全局状态：招标类型、任务进度、侧边栏状态 |
| `historyStore` | Zustand Store | `stores/historyStore.ts` | 生成历史记录，持久化存储 |
| `useSSE` | Hook | `hooks/useSSE.ts` | SSE 连接管理，实时接收日志和进度 |
| `FileUploader` | 组件 | `components/forms/FileUploader.tsx` | 文件上传组件，支持拖拽 |
| `TenderNoInput` | 组件 | `components/forms/TenderNoInput.tsx` | 招标编号输入，自动获取项目信息 |
| `BaseForm` | 组件 | `components/forms/BaseForm.tsx` | 表单基础布局和逻辑 |
| `XjcgTenderForm` | 组件 | `components/forms/XjcgTenderForm.tsx` | 询价采购表单 |
| `GngkTenderForm` | 组件 | `components/forms/GngkTenderForm.tsx` | 公开招标表单 |

## WHERE TO LOOK

| 任务 | 位置 | 说明 |
|------|------|------|
| **添加新表单** | `components/forms/` | 按招标类型创建新表单组件 |
| **修改全局状态** | `stores/useAppStore.ts` | 招标类型、文件、进度、侧边栏 |
| **修改历史记录** | `stores/historyStore.ts` | 生成历史、持久化 |
| **添加 API 类型** | `types/api.ts` | 后端接口类型映射 |
| **修改页面布局** | `app/layout.tsx` | 根布局、全局 Provider |
| **新招标类型路由** | `app/tender/[type]/page.tsx` | 动态路由参数 `type` |
| **新增工具函数** | `lib/utils.ts` | 公共工具函数 |
| **新增 API 封装** | `lib/api.ts` | HTTP 请求封装 |
| **修改 SSE 逻辑** | `hooks/useSSE.ts` | 实时通信 |
| **E2E 测试** | `e2e/*.spec.ts` | Playwright 测试用例 |

## CONVENTIONS

### 路径别名

```typescript
// ✅ 使用 @/* 映射到项目根目录
import { useAppStore } from '@/stores/useAppStore';
import { Button } from '@/components/ui/Button';

// ❌ 避免相对路径
import { useAppStore } from '../../../stores/useAppStore';
```

### 状态管理 (Zustand)

- **Store 文件命名**: `useXxxStore.ts` (camelCase)
- **使用时**: `useXxxStore()` (保持一致)
- **持久化**: 使用 `persist` middleware
  ```typescript
  export const useAppStore = create<AppState>()(
    devtools(
      persist(
        (set) => ({ ... }),
        { name: 'tender-app-storage' }
      )
    )
  );
  ```

### 组件组织

- **按功能域分目录**，而非按类型分
  ```
  components/
  ├── forms/          # 表单相关
  ├── layout/         # 布局相关
  └── ui/             # 通用 UI (Button, Input 等)
  ```

- **组件文件命名**: PascalCase
  - `XjcgTenderForm.tsx`
  - `FileUploader.tsx`

### 类型定义

- **全局类型**: `types/index.ts` 统一导出
- **组件 Props**: 就近定义，与组件同文件或同目录
  ```typescript
  // components/forms/XjcgTenderForm.tsx
  interface XjcgTenderFormProps {
    tenderNo: string;
    onSubmit: (data: FormData) => void;
  }
  ```

### Tailwind CSS 4

- **不使用** `tailwind.config.ts`
- 配置在 `globals.css` 的 CSS 变量中
  ```css
  @theme {
    --color-primary: #3b82f6;
    --font-sans: ui-sans-serif, system-ui, sans-serif;
  }
  ```

### API 调用

- **使用封装好的 API 方法**，不直接调用 `fetch`
  ```typescript
  import { uploadFile, generateDocument } from '@/lib/api';
  
  // ✅ 正确
  const result = await generateDocument(data);
  
  // ❌ 避免
  const res = await fetch('/api/generate', { ... });
  ```

### SSE 使用

```typescript
import { useSSE } from '@/hooks/useSSE';

function MyComponent() {
  const { connect, disconnect, logs, progress } = useSSE();
  
  useEffect(() => {
    connect(taskId);
    return () => disconnect();
  }, [taskId]);
  
  return <LogViewer logs={logs} progress={progress} />;
}
```

## ANTI-PATTERNS

| 禁止 | 原因 | 正确做法 |
|------|------|----------|
| **中文 npm 镜像** | 供应链风险 | 使用官方 npm registry |
| **`use client` 滥用** | 增加客户端 bundle | 检查组件必要性，优先服务端渲染 |
| **直接调用 fetch** | 缺乏统一错误处理 | 使用 `lib/api.ts` 封装方法 |
| **相对路径导入** | 难以维护 | 使用 `@/*` 路径别名 |
| **在组件内定义大对象** | 每次渲染重新创建 | 提取到组件外或使用 useMemo |

## COMMANDS

```bash
# 开发
cd frontend && npm run dev                # 开发服务器 (port 3000)

# 构建
cd frontend && npm run build              # 生产构建
cd frontend && npm run start              # 启动生产服务器

# 代码质量
cd frontend && npm run lint               # ESLint 检查
cd frontend && npm run format             # Prettier 格式化
cd frontend && npm run format:check       # Prettier 格式检查

# 测试
cd frontend && npm run test:e2e           # Playwright E2E 测试
```

## URL 参数路由

支持通过 URL 参数自动显示对应的表单:

```
http://localhost:3000/?tender_lx=0&purchase_method=5&fund_lx=0&tenderno=ZBGG-2024-001
```

**参数说明:**
- `tender_lx`: 招标类型（0=询价, 1=公开招标, 2=邀请招标）
- `purchase_method`: 采购方式（5=询价采购, 1=公开招标, 2=邀请招标）
- `fund_lx`: 资金类型（0=国内, 1=国际）
- `tenderno`: 招标编号（可选，自动填充并获取数据）

**动态路由:**
- `/tender/xjcg` - 询价采购表单
- `/tender/gngk` - 公开招标表单

## SSE 事件类型

前端通过 SSE 实时接收后端事件:

| 事件类型 | 说明 |
|----------|------|
| `log` | 普通日志消息 |
| `llm` | LLM 生成内容流 |
| `progress` | 进度更新（节点完成状态）|
| `done` | 任务完成 |
| `error` | 错误信息 |

**断线重连:**
- 支持 `Last-Event-ID` 请求头
- 服务端从该事件ID之后继续发送
- 自动重连机制内置在 `useSSE` hook 中

## NOTES

1. **端口**: 前端 3000, 后端 8000 (CORS 已配置)
2. **上传目录**: `D:/UploadFiles` (后端配置)
3. **Tailwind 4**: 不使用 `tailwind.config.ts`，配置在 CSS 变量
4. **状态持久化**: `useAppStore` 只持久化 `sidebarOpen`，其他状态不持久化
5. **类型安全**: 所有 API 调用都有对应的 TypeScript 类型定义

## REFACTORING NOTES

### 2026-03-03 更新 (commit 998002b)

1. **组件更新**: 表单组件类名和状态类型定义更新
2. **FileUploader 重构**: 改进文件上传逻辑
3. **清理无用文件**: 删除根级过时模块

### 开发注意事项

- 新增招标类型需要：
  1. 在 `components/forms/` 创建表单组件
  2. 在 `app/tender/[type]/page.tsx` 添加路由支持
  3. 在 `stores/useAppStore.ts` 添加招标类型定义
- 所有 API 调用使用 `lib/api.ts` 中的封装方法
- 组件 Props 类型就近定义，不要放在 `types/index.ts`

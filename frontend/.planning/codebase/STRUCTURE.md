# 前端结构事实地图

**分析日期：** 2026-05-23

**范围：** `frontend/` 源码、测试和前端配置。

## 目录布局

```text
frontend/
├── app/                    # Next.js App Router 页面与全局样式
├── components/chat/         # 工作台、聊天、任务消息、类型侧栏
├── components/forms/        # 招标表单、上传、模板候选、共享控件
├── components/layout/       # 布局与历史/侧栏组件
├── hooks/                   # URL、hydration、SSE、任务状态、心跳 hook
├── lib/                     # API client、SSE wrapper、转换工具
├── stores/                  # Zustand stores
├── types/                   # API、聊天、招标类型 TS 类型
├── utils/                   # 招标类型和 URL 映射
├── mocks/                   # MSW mock
├── __tests__/               # Jest 单元/集成测试
├── e2e/                     # Playwright E2E
├── test-shims/              # 测试 shim
├── package.json             # 脚本和依赖
├── next.config.ts           # Next 配置与 /api rewrite
├── jest.config.ts           # Jest 配置
└── playwright.config.ts     # Playwright 配置
```

## 目录职责

| 目录 | 当前职责 |
| --- | --- |
| `frontend/app/` | `/` 首页、`/tender` 工作台、layout、global CSS。 |
| `frontend/components/chat/` | 类型侧栏、表单面板、聊天面板、输入框、消息列表、任务日志/正文/下载消息。 |
| `frontend/components/forms/` | XJCG/GNGK/GJGK 表单 wrapper、共享表单、上传、模板候选弹窗、锚点默认值。 |
| `frontend/components/layout/` | Header、Sidebar、HistorySection、MainLayout。 |
| `frontend/hooks/` | hydration、URL 参数、SSE、任务状态、任务心跳、当前任务摘要。 |
| `frontend/lib/` | `api.ts`、`sse.ts`、`apiBaseUrl.ts`、`formDataConverter.ts`、`tenderFetch.ts`、工具函数。 |
| `frontend/stores/` | 主会话 store、stream store、task session store、历史 store、UI store。 |
| `frontend/types/` | `TenderType`、API payload/event、聊天消息类型。 |
| `frontend/utils/` | tender type 与 canonical URL 映射。 |
| `frontend/__tests__/` | Jest 测试，按 unit/integration 和模块路径归档。 |
| `frontend/e2e/` | Playwright 规格。 |

## 关键文件位置

### 路由与工作台

- `frontend/app/page.tsx`：首页入口。
- `frontend/app/tender/page.tsx`：工作台、URL 接入、会话启动、招标详情预取、会话心跳。
- `frontend/components/chat/TenderTypeSidebar.tsx`：类型分组、会话选择/创建/重命名/删除。
- `frontend/components/chat/FormPanel.tsx`：表单挂载、生成任务创建、任务状态 overlay、SSE hook 绑定。
- `frontend/components/chat/ChatPanel.tsx`：普通聊天、rewrite、edit、上传 edit 文件、取消、下载。

### 表单

- `frontend/components/forms/TenderFormShared.tsx`：共享表单主体。
- `frontend/components/forms/XjcgTenderForm.tsx`、`GngkTenderForm.tsx`、`GjgkTenderForm.tsx`：类型 wrapper。
- `frontend/components/forms/tenderFormConfig.ts`：默认锚点和表单配置。
- `frontend/components/forms/TemplateCandidateDialog.tsx`：模板候选弹窗。
- `frontend/components/forms/FileUploader.tsx`：文件上传控件。

### API / SSE / 类型

- `frontend/lib/api.ts`：统一后端调用入口。
- `frontend/lib/apiBaseUrl.ts`：API base URL 解析。
- `frontend/lib/sse.ts`：EventSource wrapper。
- `frontend/hooks/useChatSSE.ts`：任务 SSE 到 store/UI 的映射。
- `frontend/types/api.ts`：API 和 SSE 类型。
- `frontend/lib/formDataConverter.ts`：表单到 `GenerateRequest` 转换。
- `frontend/utils/tenderTypeMapper.ts`：URL 判型、canonical URL 构造与同步。

### 状态

- `frontend/stores/chatStore.ts`：会话、草稿、任务消息、task summary、URL 同步。
- `frontend/stores/chatStreamStore.ts`：运行中 SSE 内容。
- `frontend/stores/chatTaskSessionStore.ts`：task stream resume 元数据。
- `frontend/stores/historyStore.ts`：生成历史。
- `frontend/stores/useAppStore.ts`：UI 状态。

### 测试

- `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`：表单转换器。
- `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`：URL 和类型映射。
- `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`：会话 scope。
- `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`：SSE 映射。
- `frontend/e2e/test_url_conversation.spec.ts`：URL 会话行为。

## 命名约定

- 源码组件使用 PascalCase 文件名。
- 测试文件必须以 `test_` 开头。
- 前端单测路径：`frontend/__tests__/unit/<module_scope>/test_*.test.ts(x)`。
- 前端集成测试路径：`frontend/__tests__/integration/<module_scope>/test_*.test.ts(x)`。
- Playwright 路径：`frontend/e2e/test_*.spec.ts`。
- 不在源码目录并排新增测试文件。

## 新代码放置规则

- 新页面：`frontend/app/`。
- 新工作台组件：`frontend/components/chat/`。
- 新表单控件：`frontend/components/forms/`，共享小控件放 `frontend/components/forms/shared/`。
- 新 API helper：`frontend/lib/api.ts`，类型同步放 `frontend/types/api.ts`。
- 新 URL / 类型映射：`frontend/utils/tenderTypeMapper.ts`。
- 新会话或任务状态：优先在 `frontend/stores/chatStore.ts` 或相关专门 store。
- 新 SSE 行为：`frontend/lib/sse.ts` 或 `frontend/hooks/useChatSSE.ts`，并补测试。

## 特殊目录

- `frontend/.planning/codebase/`：前端事实地图。
- `frontend/.next/`、`test-results/`、`playwright-report/`：生成产物，不作为事实来源。
- `frontend/node_modules/`：平台原生依赖敏感；WSL 与 Windows 不要盲目复用。

---

*前端结构分析：2026-05-23*

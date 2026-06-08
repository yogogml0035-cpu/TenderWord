<!-- refreshed: 2026-06-08 -->
# 前端架构事实地图

**分析日期：** 2026-06-08

**范围：** `frontend/` 前端子项目，以及必要的根级约定文件 `AGENTS.md`、`README.md`、`docs/frontend.md`、`docs/interfaces-runtime.md`、`INTERFACES.md`。`frontend/.env.local`、`frontend/.env.local.example`、`frontend/.npmrc` 仅记录存在，不读取内容。

## 系统总览

```text
┌─────────────────────────────────────────────────────────────┐
│                    Next.js App Router                        │
│      `frontend/app/page.tsx`, `frontend/app/tender/page.tsx`  │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────────┐ ┌───────────────────────────┐
│ 三栏招标工作台 UI              │ │ URL / hydration / heartbeat │
│ `frontend/components/chat/`    │ │ `frontend/hooks/`           │
│ `frontend/components/forms/`   │ │ `frontend/app/tender/page.tsx` │
└───────────────┬───────────────┘ └──────────────┬────────────┘
                │                                │
                ▼                                ▼
┌─────────────────────────────────────────────────────────────┐
│                  Zustand 会话、任务、stream 状态              │
│                  `frontend/stores/`                          │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ API client / SSE / NDJSON / 表单转换 / URL 映射               │
│ `frontend/lib/`, `frontend/hooks/`, `frontend/utils/`, `frontend/types/` │
└───────────────┬─────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│ TenderWord FastAPI `/api/*` 与浏览器 runtime                 │
│ `frontend/next.config.ts`, `frontend/lib/api.ts`             │
└─────────────────────────────────────────────────────────────┘
```

前端是 TenderWord 的浏览器工作台。它负责招标类型选择、URL 深链、会话和草稿、招标详情预取、模板候选选择、文件上传、生成任务创建、聊天式 agent run、上传文件 rewrite、补充批注任务、SSE 进度、智能体过程卡和下载入口。

## 组件职责

| 组件 | 职责 | 文件 |
| --- | --- | --- |
| App Router 根入口 | `/` 重定向到 `/tender` | `frontend/app/page.tsx` |
| 工作台页面 | 三栏布局、URL 参数建会话、招标数据预取、会话心跳、后端重启收敛 | `frontend/app/tender/page.tsx` |
| 类型侧栏 | 招标类型分组、会话选择、创建、重命名、删除和 URL 同步 | `frontend/components/chat/TenderTypeSidebar.tsx` |
| 表单面板 | 挂载当前 tender form、创建 generate task、绑定当前任务状态和取消入口 | `frontend/components/chat/FormPanel.tsx` |
| 聊天面板 | agent run、rewrite、上传 rewrite 文件、补充批注、下载、取消和重试 | `frontend/components/chat/ChatPanel.tsx` |
| 消息列表 | 普通消息、任务日志、内容卡、下载卡、过程卡和用户消息操作 | `frontend/components/chat/MessageList.tsx` |
| 共享表单 | 模板/参数上传、模板候选、锚点、生成方式、批注开关、样式回填和 draft 同步 | `frontend/components/forms/TenderFormShared.tsx` |
| 表单注册表 | `TenderType` 到显示名、表单组件、生成转换器的映射 | `frontend/components/chat/tenderFormRegistry.ts` |
| API client | JSON、上传、下载、NDJSON、agent run、任务和模板候选 API helper | `frontend/lib/api.ts` |
| SSE runtime | `EventSource` 包装、named events、重连、heartbeat、last event id 去重 | `frontend/lib/sse.ts` |
| 任务 SSE hook | 任务状态确认、SSE 事件到 stream/store/messages 的映射 | `frontend/hooks/useChatSSE.ts` |
| 主会话 store | 会话、草稿、任务摘要、任务消息组、URL 同步、后端重启收敛 | `frontend/stores/chatStore.ts` |
| Stream store | 运行中日志、AI 文本、agent step 快照和进度 | `frontend/stores/chatStreamStore.ts` |
| URL mapper | URL 参数解析、`TenderType` 判定、canonical query 构造 | `frontend/utils/tenderTypeMapper.ts` |
| API 类型 | 后端 payload、任务、agent run、SSE、错误码和模板候选类型 | `frontend/types/api.ts` |

## 模式概览

**总体：** Next.js App Router + 客户端工作台 + Zustand 状态层 + 统一 API/SSE 边界。

**关键特征：**
- 页面层只组合路由、三栏 UI 和启动副作用；业务状态放在 `frontend/stores/`，业务 I/O 放在 `frontend/lib/` 与 `frontend/hooks/`。
- 后端请求统一走 `frontend/lib/api.ts`；组件不直接拼后端 URL、不直接访问外部模板候选 URL、不直接访问本地文件系统或云存储。
- 会话、草稿和任务摘要持久化到 `sessionStorage`；stream runtime 保持内存态；task resume 元数据单独存在 `frontend/stores/chatTaskSessionStore.ts`。
- `TenderType` 是前端 UI 类型，后端 `GenerateRequest.form_type` 由 converter/helper 产生。
- 任务链路以 task id 为主键，SSE、任务消息组、下载卡、补充批注和未读结果围绕 task summary 收敛。

## 分层

**路由层：**
- 用途：定义页面入口、元数据和工作台容器。
- 位置： `frontend/app/`
- 包含：`layout.tsx`、`page.tsx`、`tender/page.tsx`、`globals.css`。
- 依赖： Next.js、React、workspace components、hooks、stores。
- 使用方： 浏览器访问 `/` 和 `/tender`。

**工作台 UI 层：**
- 用途：展示三栏招标操作界面、聊天消息、表单、上传、下载和状态。
- 位置： `frontend/components/chat/`、`frontend/components/forms/`、`frontend/components/layout/`
- 包含：`ChatPanel`、`FormPanel`、`MessageList`、`TenderFormShared`、`FileUploader`、`TemplateCandidateDialog`。
- 依赖： `frontend/stores/`、`frontend/hooks/`、`frontend/lib/api.ts`、`frontend/types/`。
- 使用方： `frontend/app/tender/page.tsx`。

**状态层：**
- 用途：保存会话、草稿、任务摘要、任务消息分组、stream runtime、历史和局部 UI 状态。
- 位置： `frontend/stores/`
- 包含：`chatStore.ts`、`chatStreamStore.ts`、`chatTaskSessionStore.ts`、`historyStore.ts`、`useAppStore.ts`。
- 依赖： Zustand、类型、纯 helper。
- 使用方： 页面、聊天组件、表单组件、任务 hooks。

**集成层：**
- 用途：后端 API、SSE、NDJSON、上传下载、表单 payload 转换、URL canonical 化。
- 位置： `frontend/lib/`、`frontend/hooks/`、`frontend/utils/`
- 包含：`api.ts`、`apiBaseUrl.ts`、`sse.ts`、`formDataConverter.ts`、`gngkFormType.ts`、`tenderFetch.ts`、`useChatSSE.ts`、`tenderTypeMapper.ts`。
- 依赖： 浏览器 `fetch` / `EventSource` / `URL` APIs、`frontend/types/`。
- 使用方： 工作台 UI 和 stores。

**类型层：**
- 用途：定义跨层契约和类型守卫。
- 位置： `frontend/types/`
- 包含：`api.ts`、`chat.ts`、`index.ts`。
- 依赖： TypeScript 类型系统。
- 使用方： 全前端。

## 数据流

### `/tender` 深链与会话启动

1. `useUrlParams()` 从 `useSearchParams()` 解析 `tender_lx`、`purchase_method`、`fund_lx`、`tenderno`（`frontend/hooks/useUrlParams.ts:66`）。
2. `parseTenderUrlParams()` 由 URL 参数判定前端 `TenderType`，判型只依赖 `purchase_method`（`frontend/utils/tenderTypeMapper.ts:205`）。
3. `TenderPageContent` hydration 后选择 tender type，并按 tenderno/类型查找或创建 conversation（`frontend/app/tender/page.tsx:34`、`frontend/app/tender/page.tsx:58`）。
4. `gngk` 使用 tenderno + `tender_lx` + `fund_lx` 精确匹配会话（`frontend/stores/chatStore.ts:870`）。
5. 深链参数先写入 conversation draft，再由 `TenderFormShared` 以 `draft > URL > default` 初始化表单（`frontend/components/forms/TenderFormShared.tsx:632`）。
6. `syncBrowserUrlToConversation()` 和 `syncUrlToCurrentConversation()` 维护 canonical URL（`frontend/utils/tenderTypeMapper.ts:72`、`frontend/stores/chatStore.ts:2375`）。

### 生成任务

1. `TenderFormShared` 收集招标数据、模板文件、技术参数文件、锚点、生成风格、生成模式、批注开关和样式回填模式（`frontend/components/forms/TenderFormShared.tsx:632`）。
2. `FormPanel` 从 `tenderFormRegistry` 获取当前类型表单组件和 converter（`frontend/components/chat/FormPanel.tsx:159`、`frontend/components/chat/tenderFormRegistry.ts:38`、`frontend/components/chat/tenderFormRegistry.ts:44`）。
3. `formDataConverter.ts` 将表单数据转成 `GenerateRequest`，文件只进入 `file_paths.template` 和 `file_paths.tender_params`（`frontend/lib/formDataConverter.ts:117`、`frontend/lib/formDataConverter.ts:193`、`frontend/lib/formDataConverter.ts:225`）。
4. `gngk` 后端 `form_type` 由 `resolveGngkFormType()` 根据 `tender_lx + fund_lx + ifzgcg` 分派；`tender_lx=1` 工程类和 `tender_lx=2` 服务类都走 `gngk_fw_*` form type（`frontend/lib/gngkFormType.ts:18`）。
5. `createGenerateTask()` 调用 `/api/generate`（`frontend/lib/api.ts:808`）。
6. `chatStore.startTask()` 建立 task summary、active task 和 task message group（`frontend/stores/chatStore.ts:1202`）。
7. `useCurrentConversationTaskStatus()` 查任务队列/运行状态，`useChatSSE()` 连接 `/api/stream/{taskId}`（`frontend/hooks/useCurrentConversationTaskStatus.ts:88`、`frontend/hooks/useChatSSE.ts:175`）。
8. SSE `log`、`llm`、`progress`、`agent_step`、`done`、`error` 更新 `chatStreamStore` 和任务消息；终态由 store 生成下载卡或错误态（`frontend/hooks/useChatSSE.ts:371`、`frontend/hooks/useChatSSE.ts:399`、`frontend/hooks/useChatSSE.ts:441`、`frontend/hooks/useChatSSE.ts:488`、`frontend/hooks/useChatSSE.ts:530`、`frontend/hooks/useChatSSE.ts:568`）。

### Agent run 与上传文件 rewrite

1. `ChatPanel` 从聊天输入、draft、rewrite 文件和选中 skill 构造 `AgentRunStreamRequest`（`frontend/components/chat/ChatPanel.tsx:188`、`frontend/components/chat/ChatPanel.tsx:393`）。
2. 上传待改 Word 文件时调用 `uploadFile(file, 'rewrite_source')`，并写入 draft 的 `rewrite_file` 和一次性 `selected_skills: ['rewrite']`（`frontend/components/chat/ChatPanel.tsx:338`、`frontend/components/chat/ChatPanel.tsx:347`）。
3. `streamAgentRun()` 解析 `/api/agent/runs/stream` NDJSON（`frontend/lib/api.ts:590`）。
4. 只有 `task_accepted` 触发 `startTask()` 并进入 SSE；`needs_input` 只追加普通 AI 提示，不创建后端任务（`frontend/components/chat/ChatPanel.tsx:559`）。
5. 上传文件 rewrite 的 `rewrite_context.form_type` 继续调用 `resolveGngkFormType()`，保持与生成链路一致（`frontend/components/chat/ChatPanel.tsx:162`、`frontend/lib/gngkFormType.ts:18`）。

### 补充批注

1. 初次生成下载卡触发补充批注动作，入口由 `TaskDownloadMessage` 到 `MessageList` 再回调 `ChatPanel`（`frontend/components/chat/TaskDownloadMessage.tsx:15`、`frontend/components/chat/MessageList.tsx:138`、`frontend/components/chat/ChatPanel.tsx:847`）。
2. `createCommentSupplementTask()` 调用 `/api/comment-supplement`，payload 只包含会话 id、当前源文件和模型（`frontend/lib/api.ts:815`）。
3. `comment_supplement` 复用任务状态、SSE、下载消息；`comment_agent` 过程卡通过 `agent_step` 展示（`frontend/hooks/useChatSSE.ts:441`）。
4. `rewrite` 和 `comment_supplement` 下载卡不继续暴露补充批注动作；补充批注只从初次 `generate` 下载卡触发（`frontend/components/chat/TaskDownloadMessage.tsx:15`）。

### 模板候选

1. `TenderFormShared` 按招标编号和项目名维护模板候选弹窗缓存（`frontend/components/forms/TenderFormShared.tsx:632`）。
2. `fetchTemplateCandidates()` 调用项目内 `/api/template-candidates`，`selectTemplateCandidate()` 调用 `/api/template-candidates/select`（`frontend/lib/api.ts:735`、`frontend/lib/api.ts:749`）。
3. `getTemplateCandidateDownloadUrl()` 生成项目内下载代理 URL，不让组件直接访问外部候选文件 URL（`frontend/lib/api.ts:758`）。
4. `TemplateCandidateDialog` 负责候选表格、不可选状态、刷新、选择和下载代理链接渲染（`frontend/components/forms/TemplateCandidateDialog.tsx:62`）。

**状态管理：**
- `chatStore` 是持久化主状态，storage name 是 `chat-storage`，持久化目标是 `sessionStorage`（`frontend/stores/chatStore.ts:994`、`frontend/stores/chatStore.ts:2408`）。
- `chatStreamStore` 是运行时内存状态，不持久化；终态后由 `useChatSSE` 清理（`frontend/stores/chatStreamStore.ts`）。
- `chatTaskSessionStore` 只持久化 task resume 元数据，storage name 是 `chat-task-session-storage`（`frontend/stores/chatTaskSessionStore.ts:43`）。
- running task 恢复前必须先查询后端状态；404 / `TASK_NOT_FOUND` 由 `discardStaleTask()` 或本地中断态收敛。

## 核心抽象

**`TenderType`：**
- 用途：前端 UI 类型，取值为 `xjcg`、`gngk`、`gjgk`。
- 示例： `frontend/types/index.ts:6`、`frontend/components/chat/tenderFormRegistry.ts:32`。
- 模式： UI type 与后端 `GenerateRequest.form_type` 分离。

**`GenerateRequest`：**
- 用途：初次生成任务 payload。
- 示例： `frontend/types/api.ts:141`、`frontend/lib/formDataConverter.ts:117`。
- 模式： converter 负责默认值、文件路径提取、generate-only 字段和 `gngk` form type 分派。

**`ConversationFormDraft`：**
- 用途：会话级表单草稿、上传文件、生成字段、rewrite 文件、一次性 skill 和 pending 恢复状态。
- 示例： `frontend/stores/chatStore.ts:84`、`frontend/components/forms/TenderFormShared.tsx:632`、`frontend/components/chat/ChatPanel.tsx:393`。
- 模式： draft 是表单恢复和 agent run 上下文的共享来源。

**`TaskMessageGroupIds`：**
- 用途：一个 task id 对应 `task-log`、`task-content`、`task-download` 三类消息。
- 示例： `frontend/stores/chatStore.ts:47`、`frontend/stores/chatStore.ts:1263`、`frontend/stores/chatStore.ts:1536`。
- 模式： 任务消息由 store 方法维护，组件不手写 message group。

**`agent-step` message：**
- 用途：智能体过程卡，展示 `content_agent` 和 `comment_agent` 的分轮信息。
- 示例： `frontend/types/chat.ts:32`、`frontend/types/api.ts:591`、`frontend/stores/chatStore.ts:1410`、`frontend/components/chat/TaskContentMessage.tsx:369`。
- 模式： 运行中快照在 `chatStreamStore.agentSteps`，完成态 upsert 到 conversation messages。

**`AgentThinkingCardState`：**
- 用途：agent run 创建任务前的“任务上下文助手”过程卡。
- 示例： `frontend/lib/agentThinking.ts`、`frontend/components/chat/AgentThinkingMessage.tsx:107`、`frontend/types/chat.ts:59`。
- 模式： 只展示前置流状态；后台任务创建后进度交给 task/SSE 卡。

## 入口点

**浏览器入口：**
- 位置： `frontend/app/page.tsx`
- 触发： 用户访问 `/`。
- 职责： 重定向到 `/tender`。

**工作台入口：**
- 位置： `frontend/app/tender/page.tsx`
- 触发： 用户访问 `/tender` 或带查询参数的深链。
- 职责： 三栏 UI、URL 参数处理、会话创建、招标数据预取、会话心跳。

**API 入口：**
- 位置： `frontend/lib/api.ts`
- 触发： 表单提交、聊天发送、上传、下载、模板候选、任务状态/心跳。
- 职责： 构造请求、解析 wrapped/unwrapped response、抛出 `ApiError`、解析 NDJSON agent run。

**SSE 入口：**
- 位置： `frontend/hooks/useChatSSE.ts`
- 触发： 任务创建或恢复后绑定 task id。
- 职责： 状态确认、连接 SSE、映射事件、终态收敛。

**URL 入口：**
- 位置： `frontend/utils/tenderTypeMapper.ts`
- 触发： 深链加载、类型切换、会话切换、draft 同步。
- 职责： `purchase_method` 到 `TenderType` 映射、canonical query 构造、浏览器 URL 替换。

## 架构约束

- **线程模型：** 浏览器单线程 React 渲染；异步 `fetch`、`EventSource`、timer 和 visibility/focus/page show 事件驱动任务状态。
- **全局状态：** Zustand stores 是模块级 singleton，见 `frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/stores/useAppStore.ts`。
- **循环导入：** `frontend/types/` 保持无运行时副作用；修改 `stores/types/lib` 边界时避免让类型层反向依赖组件或 store runtime。
- **API 边界：** 组件不得直接裸写后端 `fetch` 或外部模板候选 URL；新增后端调用放到 `frontend/lib/api.ts`。
- **Generate-only 字段：** `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于 generate 请求，不进入 rewrite request、skill state 或 prompt surface。
- **GNGK 分派：** `gngk` 后端 `form_type` 分派必须集中到 `frontend/lib/gngkFormType.ts`，generate 和上传文件 rewrite 复用同一 helper。
- **Agent run：** `POST /api/agent/runs/stream` 是右侧聊天唯一流式入口；不要为 rewrite 重新引入旧 edit 入口或第二套任务状态机。
- **SSE 契约：** 新增 SSE 事件必须同步 `frontend/types/api.ts`、`frontend/lib/sse.ts` named event 注册、`frontend/hooks/useChatSSE.ts` 解析和相关测试。
- **敏感信息：** `.env`、token、真实路径和完整客户原文不得进入文档、日志、测试夹具或最终回复。

## 反模式

### 组件直接请求后端或外部候选 URL

**问题形态：** 在组件里拼 `/api/...`、后端主机或模板候选文件 URL。
**风险原因：** 绕过 `ApiError`、base URL resolver、Next rewrite、测试 mock 和后端模板候选安全规则。
**正确做法：** 新请求放入 `frontend/lib/api.ts`，模板候选继续使用 `fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`。

### 绕过 `resolveGngkFormType()`

**问题形态：** 在 `ChatPanel`、converter 或表单组件里手写 `gngk_hw_*` / `gngk_fw_*` 分派。
**风险原因：** generate 与上传文件 rewrite 可能进入不同后端 graph。
**正确做法：** 只修改 `frontend/lib/gngkFormType.ts`，调用点保持复用 helper，并同步 `frontend/__tests__/unit/lib/test_form_data_converter.test.ts` 和 `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。

### 手工 patch URL 参数

**问题形态：** 组件直接改单个 query 参数或直接调用 history API 构造 URL。
**风险原因：** canonical URL、会话身份和 deep-link 恢复会漂移。
**正确做法：** 使用 `buildCanonicalSearchParams()`、`syncBrowserUrlToConversation()` 和 `chatStore.syncUrlToCurrentConversation()`。

### 把 agent run 当成任务状态

**问题形态：** `run_started`、`thinking_stage` 或 `needs_input` 直接创建 task summary 或下载卡。
**风险原因：** agent run 只是任务创建前置流，后台任务只有后端接受后才存在。
**正确做法：** 只有 `task_accepted` 触发 `chatStore.startTask()`；其他 agent run 事件只更新普通消息或思考卡。

### 在前端暴露后端私有运行细节

**问题形态：** 把审计日志路径、完整下载路径、traceback、完整客户原文或检索 JSON 暴露到 UI 或前端 store。
**风险原因：** 违反 agent run 和检索审计的白名单边界，增加敏感信息泄露风险。
**正确做法：** 只消费 scrub 后的摘要字段和公开任务状态，类型定义放在 `frontend/types/api.ts`。

## 错误处理

**策略：** API 层统一转换为 `ApiError`，任务层通过状态确认、SSE 终态、心跳和本地中断态收敛 UI。

**模式：**
- `frontend/lib/api.ts` 从 HTTP status、wrapped `success: false`、嵌套 `detail` 和 network failure 提取 message/code/status。
- `frontend/hooks/useChatSSE.ts` 先 `getTaskStatus()`，再连接 SSE；terminal 或 missing task 直接收敛。
- `frontend/hooks/useCurrentConversationTaskStatus.ts` 轮询当前任务，`TASK_NOT_FOUND` 或 404 调用 `discardStaleTask()`。
- `frontend/hooks/useTaskHeartbeat.ts` 对活跃 task 发心跳，终态回调给 `FormPanel` 做补拉收敛。
- `frontend/app/tender/page.tsx` 用会话 heartbeat 检测后端 instance id 变化，并调用 `handleBackendRestart()`。
- UI 组件展示用户可读错误；下载失败路径在 `ChatPanel` 使用 alert + console 错误。

## 横切关注点

**日志：** 用户可见任务日志经 `TaskLogMessage` 渲染；排障日志使用 `console`，主要在 `frontend/lib/sse.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`。

**校验：** TypeScript strict、ESLint、Jest 单测、Playwright E2E；表单提交前在 `TenderFormShared` 做基本必填/文件检查，后端仍是最终契约校验方。

**认证：** 前端未检测到认证层；`sessionStorage` 会话只表示浏览器工作台状态，不表示用户身份或权限。

**样式：** UI 使用 Tailwind utility class、CSS variables 和 `lucide-react` 图标，组件样式主要内联在 TSX 中；共享 class helper 是 `frontend/lib/utils.ts`。

**外部 API 隔离：** 招标详情、模板候选、模板下载、Word COM、LLM 和检索运行时都在后端封装；前端只消费项目内 `/api/*`。

---

*前端架构分析：2026-06-08*

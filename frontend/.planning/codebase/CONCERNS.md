# 前端风险事实地图

**分析日期：** 2026-06-25

**范围：** `frontend/` 前端风险事实地图。必要时引用后端契约源文件来说明前后端同步边界；未读取 `frontend/.env.local`、`frontend/.npmrc` 或任何凭据文件内容。

## 技术债

**核心文件职责密集：**
- 问题： 会话、任务、SSE、表单、聊天、API 和 rewrite 的关键行为集中在少数大文件中。当前实现体量较大的文件包括 `frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/ChatPanel.tsx`、`frontend/lib/api.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/components/chat/FormPanel.tsx`、`frontend/types/api.ts`。
- 相关文件： `frontend/stores/chatStore.ts`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/lib/api.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/components/chat/FormPanel.tsx`, `frontend/types/api.ts`
- 影响： 小改动容易同时影响 URL 深链、会话草稿、任务消息、agent run、上传文件 rewrite、SSE 终态、下载卡和补充批注。
- 修复方向： 新增分支优先提取纯 helper 到 `frontend/lib/` 或 `frontend/utils/`，并补窄测试；不要在功能修复中做目录洗牌或大范围拆分。

**前后端 API shape 手写镜像：**
- 问题： 前端 `frontend/types/api.ts` 与 `frontend/lib/api.ts` 手写镜像后端 Pydantic 模型，后端 `backend/models/generate.py`、`backend/models/task.py`、`backend/models/agent_run.py`、`backend/models/sse.py` 是接口字段和枚举的源头。
- 相关文件： `frontend/types/api.ts`, `frontend/lib/api.ts`, `frontend/lib/formDataConverter.ts`, `backend/models/generate.py`, `backend/models/task.py`, `backend/models/agent_run.py`, `backend/models/sse.py`
- 影响： 字段名、枚举、响应包装或 SSE/NDJSON event 只改一端会造成前端解析失败、后端 422、任务卡状态错误或下载卡缺失。
- 修复方向： 修改 `GenerateRequest`、`AgentRunStreamRequest`、`TaskKind`、`TaskStatus`、SSE `done/error/agent_step` 时同步前端类型、API client、转换器、UI 处理和测试。

**直接 fetch 边界靠约定维护：**
- 问题： 实现层检索到的 `fetch()` 调用集中在 `frontend/lib/api.ts`，组件和 hooks 通过 API helper 访问后端；但代码中没有 lint 规则阻止后续在 `frontend/components/` 或 `frontend/hooks/` 新增裸 `fetch()`。
- 相关文件： `frontend/lib/api.ts`, `frontend/lib/apiBaseUrl.ts`, `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/FormPanel.tsx`, `frontend/components/forms/TenderFormShared.tsx`
- 影响： 裸 `fetch()` 会绕过 `resolveApiBaseUrl()`、统一 `ApiError`、FormData 头处理、NDJSON parser、下载 URL 编码和测试 mock 入口。
- 修复方向： 新后端请求必须先加到 `frontend/lib/api.ts`，调用点只使用导出的 helper；必要时补 ESLint 规则或 code review checklist 约束组件层不写裸 `fetch()`。

**generate-only 字段边界容易被误用：**
- 问题： `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于初次 generate 请求；上传文件 rewrite 的 agent run 请求只应携带 `selected_skills`、`uploaded_files` 和 `rewrite_context`。
- 相关文件： `frontend/types/api.ts`, `frontend/lib/formDataConverter.ts`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/ChatPanel.tsx`, `backend/models/generate.py`, `backend/models/agent_run.py`
- 影响： 把 generate-only 字段放进 rewrite 请求会污染 rewrite 语义，且 `backend/models/agent_run.py` 使用 `extra="forbid"`，多余字段会直接触发接口失败。
- 修复方向： generate 字段只改 `GenerateRequest` 链路；rewrite 能力只改 `AgentRunStreamRequest` 与 `AgentRunContextSnapshot` 明确存在的字段。

**`gngk` form type 分派是共享业务规则：**
- 问题： `gngk` 在前端是 UI 类型，提交到后端需要由 `tender_lx + fund_lx + ifzgcg` 分派到具体 `form_type`。
- 相关文件： `frontend/lib/gngkFormType.ts`, `frontend/lib/formDataConverter.ts`, `frontend/components/chat/ChatPanel.tsx`, `frontend/utils/tenderTypeMapper.ts`, `backend/models/generate.py`
- 影响： generate 和上传文件 rewrite 如果各自实现分派，会出现同一页面生成和重写落到不同 graph 的问题。
- 修复方向： 分派规则只通过 `frontend/lib/gngkFormType.ts` 修改，并同步 `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`、`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx` 和后端对应 graph/service 测试。

**通用 SSE hook 与业务 SSE hook 并存：**
- 问题： `frontend/hooks/useSSE.ts` 提供通用 `useTaskProgress()`，实际聊天任务进度走 `frontend/hooks/useChatSSE.ts`，两者对事件 payload 和任务终态的处理粒度不同。
- 相关文件： `frontend/hooks/useSSE.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/lib/sse.ts`, `frontend/stores/chatStreamStore.ts`, `frontend/stores/chatTaskSessionStore.ts`
- 影响： 新页面误接 `useTaskProgress()` 可能只得到通用进度，不会更新聊天消息组、下载卡、agent step 卡、session replay 和后端重启中断状态。
- 修复方向： 工作台任务优先复用 `useChatSSE()`；通用 hook 只用于不需要会话消息副作用的只读监控场景。

## 已知问题

**全局主色 hover token 重复定义：**
- Symptoms: `frontend/app/globals.css` 的 `:root` 中 `--primary-hover` 被定义两次，后定义值覆盖前定义值；`--color-primary-hover` 继续引用被覆盖后的变量。
- 相关文件： `frontend/app/globals.css`
- Trigger: 使用 `var(--primary-hover)` 或 Tailwind theme token `--color-primary-hover` 的样式会拿到后定义值。
- Workaround: 修改视觉 token 前先清理 `frontend/app/globals.css` 的重复变量，并检查引用 `--color-primary-hover` 的 UI。

**FileUploader 对拖拽文件类型只靠后端兜底：**
- Symptoms: `frontend/components/forms/FileUploader.tsx` 的 `validateFile()` 只校验大小，`accept` 主要影响文件选择器提示；拖拽路径没有前端扩展名或 MIME 校验。
- 相关文件： `frontend/components/forms/FileUploader.tsx`, `frontend/__tests__/unit/components/forms/test_file_uploader.test.tsx`, `backend/util/common_util/upload_storage.py`
- Trigger: 用户拖入非预期扩展名文件时，前端会发起上传请求，由后端 `persist_file_bytes()` 返回类型错误。
- Workaround: 后端 `backend/util/common_util/upload_storage.py` 继续作为最终文件类型和大小防线；前端如需更早提示，应在 `FileUploader` 增加扩展名校验并补单测。

## 安全注意事项

**前端没有认证和授权边界：**
- 风险： `sessionStorage` 会话、conversation id、task id、task heartbeat 和草稿状态都不是身份凭据，不能用于权限判断。
- 相关文件： `frontend/stores/chatStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `frontend/stores/historyStore.ts`, `frontend/lib/api.ts`, `backend/api/tasks.py`, `backend/api/download.py`
- Current mitigation: `frontend/lib/api.ts` 未注入稳定 `Authorization` header；任务访问、文件下载、路径校验和权限判断必须由后端控制。
- Recommendations: 新增认证时同步 API client、路由守卫、错误处理、后端鉴权、E2E 和接口文档；不要在前端会话 id 上建立安全判断。

**模板候选 URL 必须继续由后端代理：**
- 风险： UI 直接请求外部候选文件 URL 会绕过后端白名单、年份规则、文件名清洗、下载代理和落盘逻辑。
- 相关文件： `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx`, `frontend/lib/api.ts`, `backend/api/template_candidates.py`
- Current mitigation: 前端通过 `fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()` 访问 `/api/template-candidates*`。
- Recommendations: 候选列表、选择和下载继续走项目内 API；不要在组件内直接请求后端返回的外部文件 URL。

**Agent run 可见信息必须保持最小化：**
- 风险： 前端发送 `message`、`uploaded_files`、`rewrite_context` 后，后端 agent run 日志和摘要若处理不当，可能暴露完整用户原文、私有路径、traceback 或下载路径。
- 相关文件： `frontend/components/chat/ChatPanel.tsx`, `frontend/types/api.ts`, `backend/models/agent_run.py`, `backend/agents/task_context_assistant/logging.py`, `backend/agents/task_context_assistant/tools.py`
- Current mitigation: `AgentRunContextSnapshot` 是受控上下文快照，`backend/models/agent_run.py` 对请求模型使用 `extra="forbid"`。
- Recommendations: 新增 agent run event、tool summary 或前端日志时只记录白名单结构字段，不记录完整客户原文、真实密钥、完整本机路径、traceback 或下载 URL。

**环境和凭据文件存在但不能进入长期文档：**
- 风险： `frontend/.env.local`、`frontend/.npmrc` 存在；这些文件可能包含本机配置或包管理认证信息。
- 相关文件： `frontend/.env.local`, `frontend/.env.local.example`, `frontend/.npmrc`
- Current mitigation: 本次审计只记录文件存在性，未读取内容。
- Recommendations: 文档、测试夹具、E2E 截图说明和最终回复不得写入 `.env`、token、私有凭据或真实客户原文。

## 性能瓶颈

**浏览器会话和任务消息存储会随对话增长：**
- 问题： 会话、草稿、任务摘要、消息组和未读结果持久化到浏览器 `sessionStorage`；运行中 stream 快照另存在内存 store。
- 相关文件： `frontend/stores/chatStore.ts`, `frontend/stores/chatStreamStore.ts`, `frontend/stores/chatTaskSessionStore.ts`
- Cause: 前端以浏览器会话为恢复边界，没有服务端分页聊天历史。
- 改进路径： 扩展多会话或长任务前，先定义消息截断、任务摘要保留和 storage 上限测试；不要把运行中 `chatStreamStore` 的完整快照持久化到 `chatStore`。

**SSE 高事件流会放大内存和重放成本：**
- 问题： `frontend/lib/sse.ts` 为每条连接保留 `seenEventIds` 去重，上限 5000；`frontend/hooks/useChatSSE.ts` 把日志、AI 文本、进度和 agent step 写入 `chatStreamStore`。
- 相关文件： `frontend/lib/sse.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/stores/chatStreamStore.ts`, `backend/core/sse_manager.ts`, `backend/api/stream.ts`
- Cause: 断线重连、Last-Event-ID 回放、过程卡实时展示都依赖运行时缓存。
- 改进路径： 新增高频 SSE event 前定义采样、压缩或摘要策略，并补长流重连测试。

**大组件渲染路径缺少虚拟化：**
- 问题： `frontend/components/chat/MessageList.tsx`、`frontend/components/chat/TaskContentMessage.tsx`、`frontend/components/forms/TenderFormShared.tsx` 直接渲染消息、agent step、表单区和候选列表，没有列表虚拟化层。
- 相关文件： `frontend/components/chat/MessageList.tsx`, `frontend/components/chat/TaskContentMessage.tsx`, `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx`
- Cause: 当前 UI 面向单工作台会话，依赖本地状态直接渲染。
- 改进路径： 引入长消息、长候选或多轮 agent step 前先加性能测试和滚动行为测试，再考虑虚拟化或分页。

**模板候选缓存只在组件状态内：**
- 问题： 模板候选以招标号和项目名为 key 缓存在 `TenderFormShared` 组件状态中，不跨会话、跨页面或刷新持久化。
- 相关文件： `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx`
- Cause: 候选列表依赖当前招标编号、项目名和后端重排策略。
- 改进路径： 如需跨会话缓存，先定义失效规则、刷新按钮行为和后端候选策略，再改缓存层。

## 脆弱区域

**Generate 提交状态机：**
- 相关文件： `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/chat/FormPanel.tsx`, `frontend/lib/formDataConverter.ts`, `frontend/lib/api.ts`, `frontend/stores/chatStore.ts`
- 脆弱点： 表单提交先构造 `GenerateRequest`，再调用 `/api/generate`，随后补拉 `getTaskStatus()` 获取排队摘要；UI busy、取消按钮、任务消息组和 SSE 连接依赖这些步骤按序发生。
- 安全修改： 修改提交字段时同步 converter、`createGenerateTask()`、`startTask()`、`useChatSSE()` 和任务卡测试；不要在表单组件中直接拼接后端 URL。
- 测试覆盖： `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`, `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`, `frontend/__tests__/unit/components/chat/test_form_panel.test.tsx`, `frontend/e2e/test_generation_mode_agent.spec.ts`

**Rewrite 上传文件链路：**
- 相关文件： `frontend/components/chat/ChatPanel.tsx`, `frontend/components/chat/ChatInput.tsx`, `frontend/stores/chatStore.ts`, `frontend/types/api.ts`, `frontend/lib/api.ts`, `backend/models/agent_run.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`
- 脆弱点： 上传文件 rewrite 通过 `uploadFile(file, 'rewrite_source')` 进入草稿，agent run 再携带 `selected_skills: ['rewrite']`、`uploaded_files` 和 `rewrite_context`；`task_accepted` 后才进入后台 task/SSE/下载卡链路。
- 安全修改： 不要恢复旧 edit 入口，不要复用 generate 文件槽位；缺 `form_type`、锚点、`tender_lx` 或 `fund_source_lx` 时让 agent run 返回 `needs_input`。
- 测试覆盖： `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`, `frontend/e2e/test_agent_run_chat_panel.spec.ts`

**SSE 终态收口和后端重启恢复：**
- 相关文件： `frontend/lib/sse.ts`, `frontend/hooks/useSSE.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/hooks/useTaskHeartbeat.ts`, `frontend/components/chat/FormPanel.tsx`, `frontend/stores/chatStore.ts`, `frontend/stores/chatStreamStore.ts`, `frontend/stores/chatTaskSessionStore.ts`, `backend/api/stream.py`
- 脆弱点： `done`、`error`、heartbeat、`getTaskStatus()` fallback、`cancelTask()` noop 和 `TASK_NOT_FOUND` 都可能触发终态收口；同一个 task id 同时存在于 `conversations`、`activeTaskIds`、`taskMessageMap`、`taskSummaries`、`chatStreamStore`、`chatTaskSessionStore`。
- 安全修改： 新增终态或重连分支时必须同时清理三类 store，并补 `useChatSSE`、heartbeat、取消和 stale task 测试。
- 测试覆盖： `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`, `frontend/__tests__/unit/hooks/test_use_task_heartbeat.test.tsx`, `frontend/__tests__/unit/stores/test_chat_store_task_messages.test.ts`, `frontend/e2e/test_url_conversation.spec.ts`

**Agent run NDJSON 前置流：**
- 相关文件： `frontend/lib/api.ts`, `frontend/components/chat/ChatPanel.tsx`, `frontend/lib/agentThinking.ts`, `frontend/types/api.ts`, `backend/api/agent.py`, `backend/models/agent_run.py`
- 脆弱点： `run_started`、`thinking_stage`、`tool_call`、`needs_input`、`task_accepted`、`done`、`error` 的含义不同；只有 `task_accepted` 创建后台任务，`needs_input` 和非任务 `done` 只是聊天消息。
- 安全修改： 新增 NDJSON event 要同步 parser、类型、UI 处理和测试；不要在 agent run 自己复制第二套任务状态机。
- 测试覆盖： `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`, `frontend/__tests__/unit/components/chat/test_agent_thinking_message.test.tsx`, `frontend/e2e/test_agent_run_chat_panel.spec.ts`

**URL、draft 和招标类型 identity：**
- 相关文件： `frontend/app/tender/page.tsx`, `frontend/hooks/useUrlParams.ts`, `frontend/utils/tenderTypeMapper.ts`, `frontend/stores/chatStore.ts`, `frontend/components/forms/TenderFormShared.tsx`
- 脆弱点： 页面启动状态由 URL 参数、会话 draft、招标详情预取和 `gngk` 子类型共同决定；`gngk` 的 `tender_lx`/`fund_lx` 是 UI 子状态，不直接决定顶层 `TenderType`。
- 安全修改： URL 构造只走 `frontend/utils/tenderTypeMapper.ts`；深链参数先写入 draft；改动同步 URL、store 和 E2E 测试。
- 测试覆盖： `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`, `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`, `frontend/e2e/test_url_conversation.spec.ts`

**补充批注下载卡规则：**
- 相关文件： `frontend/components/chat/TaskDownloadMessage.tsx`, `frontend/components/chat/MessageList.tsx`, `frontend/components/chat/ChatPanel.tsx`, `frontend/lib/api.ts`, `backend/api/comment_supplement.py`
- 脆弱点： 补充批注从 generate 下载卡触发，rewrite 和 comment_supplement 下载卡继续显示补充批注动作会产生衍生文件重复任务。
- 安全修改： 保持 `taskKind === 'generate'` 才允许补充批注；请求只携带当前会话、当前 output file 和模型。
- 测试覆盖： `frontend/__tests__/unit/components/chat/test_message_list.test.tsx`, `frontend/e2e/test_comment_supplement.spec.ts`

## 扩展边界

**浏览器 session 不是多设备会话系统：**
- 当前能力： `frontend/stores/chatStore.ts` 和 `frontend/stores/chatTaskSessionStore.ts` 使用浏览器 `sessionStorage` 保存当前浏览器会话状态。
- 限制： 刷新同一浏览器 session 可以恢复部分状态；跨设备、跨浏览器或长期历史恢复没有稳定前端能力。
- 扩展路径： 接入服务端会话列表前先定义 `backend/api/conversations.py` 的 API shape，再更新 `frontend/lib/api.ts`、store hydration 和测试。

**前端 E2E 不能验证真实 Word COM 闭环：**
- 当前能力： `frontend/e2e/` 通过 `page.route()` mock 后端，验证 URL、表单、上传、SSE、agent run、补充批注和任务卡 UI。
- 限制： 不能验证真实 Windows Python、pywin32、Word/WPS COM、LangGraph、graph 锁、取消检查、文件写回和下载文件内容。
- 扩展路径： 发布验收需要在后端 Windows + Word/WPS COM 环境执行；前端只验证请求、状态、SSE 和下载入口。

**SSE 重放窗口和客户端去重有限：**
- 当前能力： `frontend/lib/sse.ts` 的 `seenEventIds` 上限为 5000，后端 `backend/core/sse_manager.py` 保存任务事件并支持 `lastEventId` 回放。
- 限制： 超长任务、高频日志和多轮 agent step 会放大前后端事件缓存与重放成本。
- 扩展路径： 增加高频事件前先设计摘要 event 或分页查询，避免把完整过程都塞进 SSE。

**CI 自动化未检测到：**
- 当前能力： 仓库未检测到 `.github/workflows/`。
- 限制： `npm run lint`、`npm run type-check`、`npm run test`、`npm run test:e2e` 和文档校验是否执行取决于人工或外部流水线。
- 扩展路径： 建立 CI 时按前端包边界运行 `frontend/package.json` 的脚本，并保留文档变更的 `git diff --check`。

## 高风险依赖

**Windows/WSL 原生依赖不能混用：**
- 风险： Next、SWC、Tailwind、Playwright 和相关原生包依赖平台二进制，Windows 与 WSL 复用同一 `node_modules` 容易失败。
- 影响： `npm run dev`、`npm run build`、`npm run test:e2e` 可能因平台二进制不匹配失败。
- 迁移建议： Windows 使用 `frontend/node_modules/`；WSL 使用独立 Linux 安装目录；不要提交或复制 `node_modules` 作为修复。

**Next.js 16 / React 19 / Jest 29 组合对测试环境敏感：**
- 风险： `frontend/jest.config.ts` 依赖 `next/jest`、`jest-environment-jsdom`、`frontend/polyfills.js` 和 `frontend/jest.setup.js`；升级 ESM 包或浏览器 API polyfill 容易触发测试环境问题。
- 影响： 单测可能在 `fetch`、`EventSource`、`TextEncoder`、stream polyfill 或 JSX transform 上失败。
- 迁移建议： 依赖变更后运行 `npm run type-check`、`npm run test`，重点检查 `frontend/jest.config.ts`、`frontend/polyfills.js`、`frontend/jest.setup.js`。

**Playwright 依赖本机浏览器/端口假设：**
- 风险： `frontend/playwright.config.ts` 默认使用 `http://localhost:8502`，非 CI 时倾向系统 Chrome，webServer 运行 `npm run dev -- --webpack`。
- 影响： 本机已有服务、Chrome 渠道缺失或端口冲突会影响 E2E 稳定性。
- 迁移建议： E2E 调试时明确端口和浏览器渠道；CI 中使用 Playwright 自带浏览器并保持 `workers: 1`。

## 缺失的关键能力

**自动契约同步未检测到：**
- 问题： 未检测到从后端 Pydantic schema 自动生成 `frontend/types/api.ts` 的流程。
- Blocks: 前后端字段漂移只能靠人工同步、单测 mock 和 E2E mock 暴露。

**稳定认证/权限 UI 未检测到：**
- 问题： 未检测到登录页、认证 provider、JWT 注入、OAuth SDK 或路由守卫。
- Blocks: 前端不能判断用户身份、租户或授权范围；相关能力必须由后端或新增认证层定义。

**生产监控/错误上报未检测到：**
- 问题： 未检测到 Sentry、Datadog、OpenTelemetry、PostHog、Google Analytics 或 Firebase 等前端监控 SDK。
- Blocks: 生产端错误追踪依赖部署平台、浏览器 console 或后端日志；前端代码内没有统一上报边界。

**自动视觉回归未检测到：**
- 问题： `frontend/e2e/` 中存在 `page.screenshot()` 人工证据输出，但未检测到 `toHaveScreenshot()`、baseline 截图断言或视觉 diff 阈值。
- Blocks: 布局、颜色 token、按钮文案溢出和移动端重排只能靠人工截图审查或普通 DOM 断言发现。

## 测试覆盖缺口

**真实 Word COM 生成闭环：**
- 未覆盖测试： 真实后端、任务队列、LangGraph、Word/WPS COM、文件写回、下载文件内容和补充批注写回。
- 相关文件： `frontend/e2e/`, `frontend/__tests__/`, `backend/api/generate.py`, `backend/services/document_service.py`
- 风险： 前端测试通过不代表 Word 输出正确。
- Priority: High

**跨端契约缺少统一 contract 测试：**
- 未覆盖测试： `backend/models/generate.py`、`backend/models/agent_run.py`、`backend/models/sse.py` 与 `frontend/types/api.ts` 的自动一致性。
- 相关文件： `frontend/types/api.ts`, `frontend/lib/api.ts`, `backend/models/generate.py`, `backend/models/agent_run.py`, `backend/models/sse.py`
- 风险： 字段或枚举漂移可能只在运行时 422、SSE 解析失败或 mock 不匹配时暴露。
- Priority: High

**视觉回归只保存截图，不做自动 diff：**
- 未覆盖测试： 工作台三列布局、状态 overlay、agent step 卡、rewrite 文件卡、模板候选弹窗、移动端文本溢出的自动视觉比较。
- 相关文件： `frontend/e2e/test_agent_run_chat_panel.spec.ts`, `frontend/e2e/test_comment_supplement.spec.ts`, `frontend/e2e/test_generation_mode_agent.spec.ts`, `frontend/e2e/test_tender_form_upload_slots.spec.ts`, `frontend/playwright.config.ts`
- 风险： 颜色 token、排版、截图证据目录或响应式布局退化不会让 E2E 失败。
- Priority: Medium

**文件上传前端类型校验缺口：**
- 未覆盖测试： 非 `.doc`/`.docx` 文件通过拖拽进入 `FileUploader` 时的前端拦截行为。
- 相关文件： `frontend/components/forms/FileUploader.tsx`, `frontend/__tests__/unit/components/forms/test_file_uploader.test.tsx`, `backend/util/common_util/upload_storage.py`
- 风险： 用户只能在后端错误后得到反馈，前端无法提前阻止明显错误文件。
- Priority: Medium

**直接 fetch 边界缺少静态测试：**
- 未覆盖测试： `frontend/components/`、`frontend/hooks/`、`frontend/stores/` 不允许裸 `fetch()` 的静态约束。
- 相关文件： `frontend/lib/api.ts`, `frontend/components/`, `frontend/hooks/`, `frontend/stores/`, `frontend/eslint.config.mjs`
- 风险： 新功能可能绕过 API client，导致 base URL、错误包装、FormData、SSE/NDJSON 和测试 mock 行为不一致。
- Priority: Medium

**长流和大消息性能缺少压力测试：**
- 未覆盖测试： 超过数千 SSE event、多轮 content/comment agent step、大段 AI 文本、长会话消息列表和 sessionStorage 上限。
- 相关文件： `frontend/lib/sse.ts`, `frontend/hooks/useChatSSE.ts`, `frontend/stores/chatStreamStore.ts`, `frontend/stores/chatStore.ts`, `frontend/components/chat/MessageList.tsx`
- 风险： 长任务可能出现内存增长、重连变慢、渲染卡顿或 storage 写入失败。
- Priority: Medium

**模板候选真实外部策略组合：**
- 未覆盖测试： 外部候选 API、后端 allowed host、AI ranking provider、非法年份、下载代理失败和选择落盘失败的真实组合。
- 相关文件： `frontend/components/forms/TenderFormShared.tsx`, `frontend/components/forms/TemplateCandidateDialog.tsx`, `frontend/lib/api.ts`, `backend/api/template_candidates.py`
- 风险： 前端 mock 测试通过但真实候选策略变化后 UI 回填或按钮状态不一致。
- Priority: Medium

**Agent run 日志脱敏回归：**
- 未覆盖测试： 前端 `message`、`uploaded_files.file_path`、`rewrite_context` 与后端 agent run audit summary 的端到端脱敏验证。
- 相关文件： `frontend/components/chat/ChatPanel.tsx`, `frontend/lib/api.ts`, `backend/agents/task_context_assistant/logging.py`, `backend/agents/task_context_assistant/tools.py`
- 风险： 新增事件或工具摘要时可能把真实路径、token、traceback 或完整用户原文写入日志和公共摘要。
- Priority: Medium

---

*前端风险分析：2026-06-25*

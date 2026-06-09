# 前端风险事实地图

**分析日期：** 2026-06-09

**范围：** `frontend/` 当前技术债、脆弱区、安全边界、性能限制和测试缺口；必要时引用跨前后端契约代码和根级接口文档。本文只记录有当前代码证据的事实或明确未检测到的能力。`frontend/.env.local`、`backend/.env`、`.npmrc` 和密钥类文件只记录存在性，不读取内容。

## 技术债

**核心文件职责密集：**
- 问题：会话、任务、SSE、表单、聊天、API 和 rewrite 的关键行为集中在少数大文件中。当前行数约为 `frontend/stores/chatStore.ts` 2423 行、`frontend/components/forms/TenderFormShared.tsx` 2047 行、`frontend/components/chat/ChatPanel.tsx` 1186 行、`frontend/lib/api.ts` 1033 行、`frontend/hooks/useChatSSE.ts` 787 行。
- 文件：`frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/ChatPanel.tsx`、`frontend/lib/api.ts`、`frontend/hooks/useChatSSE.ts`
- 影响：小改动容易同时影响 URL 深链、会话草稿、任务消息、agent run、上传文件 rewrite、SSE 终态、下载卡和补充批注。
- 修复方式：新增分支优先提取纯 helper 到 `frontend/lib/` 或 `frontend/utils/`，并为分支补窄测试；不要在功能修复中做目录洗牌或大范围拆分。

**前后端 API shape 需要多点同步：**
- 问题：前端 `frontend/types/api.ts`、`frontend/lib/api.ts`、`frontend/lib/formDataConverter.ts` 和后端 `backend/models/generate.py`、`backend/models/task.py`、`backend/models/agent_run.py`、`backend/models/sse.py` 承载同一批接口契约。
- 文件：`frontend/types/api.ts`、`frontend/lib/api.ts`、`frontend/lib/formDataConverter.ts`、`backend/models/generate.py`、`backend/models/task.py`、`backend/models/agent_run.py`、`backend/models/sse.py`
- 影响：字段名、枚举、响应包装或事件 payload 只改一端会造成运行时解析失败、任务卡状态错误或后端 422。
- 修复方式：新增或修改 API 字段时同步前端类型、API client、后端 Pydantic model、相关组件和测试；不要只改调用点。

**`frontend/lib/api.ts` 存在本地 mock 会话 API：**
- 问题：`saveConversation()`、`getConversations()`、`deleteConversation()`、`updateConversationTitle()` 是“后端如支持则调用”的占位实现，其中 `saveConversation()` 返回本地成功，`getConversations()` 返回空数组。
- 文件：`frontend/lib/api.ts`
- 影响：新功能如果误以为这些 helper 已连接后端，会产生“保存成功但刷新丢失”的假象。
- 修复方式：接入真实会话 API 前先确认 `backend/api/conversations.py` 的公开端点；接入后补 `frontend/__tests__/unit/lib/test_api.test.ts` 和会话恢复测试。

**招标类型身份分散注册：**
- 问题：前端 UI 类型、后端 `FormType`、URL 参数、表单注册、转换器、默认锚点和测试分布在多个文件。
- 文件：`frontend/types/index.ts`、`frontend/types/api.ts`、`frontend/utils/tenderTypeMapper.ts`、`frontend/components/chat/tenderFormRegistry.ts`、`frontend/components/forms/tenderFormConfig.ts`、`frontend/lib/formDataConverter.ts`、`frontend/lib/gngkFormType.ts`、`backend/models/generate.py`、`backend/services/document_service.py`
- 影响：新增或调整招标类型时容易漏改 URL、表单、payload、graph registry 或测试。
- 修复方式：新增类型必须同步 mapper、registry、converter、后端 `FormType`、graph/service 注册和前后端测试。

**`gngk` form type 分派不能被绕过：**
- 问题：`gngk` 在前端是一种 UI 类型，但后端需要 `gngk_hw_zc_tender`、`gngk_hw_cz_tender`、`gngk_fw_zc_tender`、`gngk_fw_cz_tender` 四种 form type。当前分派依赖 `tender_lx + fund_lx + ifzgcg`。
- 文件：`frontend/lib/gngkFormType.ts`、`frontend/lib/formDataConverter.ts`、`frontend/components/chat/ChatPanel.tsx`、`backend/models/generate.py`、`backend/services/document_service.py`
- 影响：generate 和上传文件 rewrite 如果各自实现分派，会出现同一页面生成和重写落到不同 graph 的问题。
- 修复方式：只通过 `resolveGngkFormType()` 修改分派规则；同步 `frontend/__tests__/unit/lib/test_form_data_converter.test.ts`、`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx` 和后端 graph 相关测试。

**generate-only 字段边界容易被误用：**
- 问题：`generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 在前后端模型里只属于初次 generate。上传文件 rewrite 的 agent run 请求只应携带 `selected_skills`、`uploaded_files` 和 `rewrite_context`。
- 文件：`frontend/types/api.ts`、`frontend/lib/formDataConverter.ts`、`frontend/components/chat/ChatPanel.tsx`、`backend/models/generate.py`、`backend/models/agent_run.py`、`backend/services/document_service.py`
- 影响：把 generate-only 字段塞进 rewrite 请求、skill state 或 prompt surface 会污染 rewrite 语义，也会破坏后端关于 `rewrite_source="uploaded_file"` 的判断。
- 修复方式：rewrite 能力只改 `AgentRunStreamRequest` 和 `AgentRunContextSnapshot` 明确存在的字段；generate 字段改动只进入 `GenerateRequest` 链路。

**Jest setup 存在双文件入口：**
- 问题：`frontend/jest.setup.js` 和 `frontend/jest.setup.ts` 同时存在，`frontend/jest.config.ts` 实际只引用 `frontend/jest.setup.js`。
- 文件：`frontend/jest.config.ts`、`frontend/jest.setup.js`、`frontend/jest.setup.ts`
- 影响：修改 `frontend/jest.setup.ts` 不会影响当前 Jest 运行，容易产生验证误判。
- 修复方式：测试环境变更前先看 `setupFilesAfterEnv`；需要保留双文件时同步更新，或单独计划清理。

## 已知问题

**全局 CSS 变量重复定义导致主色 hover 值被覆盖：**
- 症状：`:root` 中 `--primary-hover` 先定义为 `#2563eb`，随后再次定义为 `#e04343`，后者成为实际值。
- 文件：`frontend/app/globals.css`
- 触发方式：使用 `var(--primary-hover)` 或 Tailwind theme `--color-primary-hover` 的样式会得到后定义的红色值。
- 临时处理：修改视觉 token 前先清理 `frontend/app/globals.css` 的重复变量，并检查引用 `--color-primary-hover` 的样式。

**`waitForLoadingToFinish()` 测试工具是空实现：**
- 症状：调用该 helper 不会等待 loading 状态，只返回 resolved promise。
- 文件：`frontend/__tests__/utils/test-utils.tsx`
- 触发方式：新测试误用 `waitForLoadingToFinish()` 作为真实等待条件。
- 临时处理：使用 Testing Library `waitFor()` 或显式断言目标状态；如需通用 helper，先实现行为再补测试。

## 安全注意事项

**前端没有认证边界：**
- 风险：`sessionStorage` 会话、conversation id、task id 和本地草稿只是浏览器状态，不是用户身份或权限。
- 文件：`frontend/stores/chatStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/lib/api.ts`
- 当前缓解：`frontend/lib/api.ts` 未注入稳定 `Authorization` header；敏感权限、路径校验和下载校验由后端控制。
- 建议：新增认证时同步 API client、路由守卫、错误处理、测试和系统接口文档；不要在前端会话 id 上建立安全判断。

**模板候选 URL 必须继续由后端代理：**
- 风险：组件直接请求外部候选文件 URL 会绕过后端白名单、年份不可选规则、文件名清洗和落盘逻辑。
- 文件：`frontend/components/forms/TemplateCandidateDialog.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/lib/api.ts`、`backend/api/template_candidates.py`、`backend/util/common_util/template_candidates.py`
- 当前缓解：前端通过 `fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()` 访问 `/api/template-candidates*`；后端模型包含 `selectable` 和 `blocked_reason`。
- 建议：候选列表、选择和下载继续走项目内 API；不要在 UI 层直接暴露外部 `shener` / `fsg` URL 请求。

**agent run 日志和摘要只能暴露 scrub 后白名单信息：**
- 风险：agent run 原始用户消息、真实本机路径、token、traceback、下载路径或完整任务结果进入前端消息、日志文件或公共摘要工具。
- 文件：`frontend/components/chat/ChatPanel.tsx`、`frontend/types/api.ts`、`backend/models/agent_run.py`、`backend/agents/task_context_assistant/logging.py`、`backend/agents/task_context_assistant/tools.py`
- 当前缓解：后端 `scrub_sensitive_text()` 会替换 bearer、key、token、password、Windows/Unix 路径、`.env` 和 traceback；公共 summary tool 只返回 rewrite 可用性、任务公共摘要和脱敏近期 agent run 摘要。
- 建议：新增 agent run event、tool summary 或 E2E 日志时只记录结构化字段，不记录完整客户原文、完整文件路径、traceback 或下载 URL。

**前端 E2E 证据目录可能保存浏览器 console 内容：**
- 风险：测试运行时把 console error、page error、截图或 trace 写入长期目录，若测试使用真实客户数据会形成文档/日志泄露。
- 文件：`frontend/e2e/test_agent_run_chat_panel.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_tender_form_upload_slots.spec.ts`、`frontend/tasks/`、`frontend/.playwright-cli/`、`frontend/playwright-report/`、`frontend/test-results/`
- 当前缓解：现有 E2E 大量使用 mock 后端与合成数据，并断言 console errors 为空。
- 建议：证据目录只使用合成招标号、合成文件名和 mock 内容；提交或归档前扫描 token、私有路径和真实客户原文。

## 性能瓶颈

**长会话和任务消息存储在浏览器侧：**
- 问题：会话、草稿、任务摘要、下载卡和未读结果持久化到 `sessionStorage`；没有服务端分页或持久聊天列表。
- 文件：`frontend/stores/chatStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`
- 原因：当前前端以浏览器会话为恢复边界。
- 改进路径：扩展多会话或长任务前，先定义消息截断、任务摘要保留和 storage 上限测试。

**运行中 SSE stream 和 agent step 仍是内存热点：**
- 问题：`frontend/lib/sse.ts` 为单连接保留 `seenEventIds`，上限为 5000；`frontend/hooks/useChatSSE.ts` 会持续把日志、AI 文本和 agent step 快照写入运行时 store。
- 文件：`frontend/lib/sse.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/stores/chatStreamStore.ts`
- 原因：断线重连、去重、过程卡实时展示都依赖运行时缓存。
- 改进路径：继续保持运行中快照只进 `chatStreamStore`，完成态再写会话消息；高频事件新增前补长流测试。

**模板候选缓存只在组件状态内：**
- 问题：模板候选以 `tenderNo + projectName` 为 key 缓存在 `TenderFormShared` 组件状态中，不是跨会话、跨页面或持久缓存。
- 文件：`frontend/components/forms/TenderFormShared.tsx`
- 原因：候选列表依赖当前招标编号和项目名，且后端负责外部 API、AI 重排、年份限制和下载代理。
- 改进路径：如需跨会话缓存，先定义失效规则、刷新按钮行为和后端候选策略，再改缓存层。

## 脆弱区域

**URL、draft 和会话 identity：**
- 文件：`frontend/app/tender/page.tsx`、`frontend/hooks/useUrlParams.ts`、`frontend/utils/tenderTypeMapper.ts`、`frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx`
- 脆弱原因：`draft > URL > default`、`gngk` 子类型身份、canonical URL 和后端招标详情预取共同决定页面启动状态。
- 安全修改：URL 构造只走 `frontend/utils/tenderTypeMapper.ts`；深链参数先写入 draft；改动同步 URL/store/E2E 测试。
- 测试覆盖：`frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`、`frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`、`frontend/e2e/test_url_conversation.spec.ts`。

**SSE 生命周期和事件契约：**
- 文件：`frontend/types/api.ts`、`frontend/lib/sse.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`backend/models/sse.py`、`backend/api/stream.py`、`backend/core/sse_manager.py`
- 脆弱原因：前端 `EventSource` 使用 `lastEventId` query 参数恢复；后端按 `Last-Event-ID` header 或 `lastEventId` query 重放；终态只由 `done` / `error` 收敛。
- 安全修改：新增 SSE 事件必须同步后端发送方、前端 union 类型、named event 注册、hook 映射、store 清理和测试；`agent_step` 不能替代 `done` / `error`。
- 测试覆盖：`frontend/__tests__/unit/lib/test_sse.test.ts`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/__tests__/unit/types/test_api_sse_agent_step.test.ts`、`frontend/e2e/test_generation_mode_agent.spec.ts`、`frontend/e2e/test_comment_supplement.spec.ts`。

**上传文件 rewrite 链路：**
- 文件：`frontend/types/api.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/stores/chatStore.ts`、`backend/models/agent_run.py`、`backend/services/agent_run_service.py`、`backend/services/document_service.py`、`backend/skills/rewrite/scripts/runtime.py`
- 脆弱原因：前端上传文件类型必须是 `rewrite_source`；agent run context 必须包含 `uploaded_files` 和完整 `rewrite_context`；后端 skill state 用 `rewrite_source="uploaded_file"` 选择上传文件 rewrite 路径。
- 安全修改：不要创建第二套 rewrite 入口；不要复用 generate 文件槽位；缺 `form_type`、锚点、`tender_lx` 或 `fund_source_lx` 时让 agent run 返回 `needs_input`。
- 测试覆盖：`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`、`frontend/e2e/test_agent_run_chat_panel.spec.ts`。

**Agent run 前置流：**
- 文件：`frontend/components/chat/ChatPanel.tsx`、`frontend/lib/api.ts`、`frontend/types/api.ts`、`backend/api/agent.py`、`backend/services/agent_run_service.py`、`backend/models/agent_run.py`
- 脆弱原因：`task_accepted` 才进入后台任务、SSE、取消和下载链路；`needs_input` 与非任务 `done` 只是聊天消息，不是 task 状态。
- 安全修改：不要在 agent run 自己复制第二套任务状态机；新增 NDJSON event 要同步 parser、类型、UI 处理和测试。
- 测试覆盖：`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`、`frontend/e2e/test_agent_run_chat_panel.spec.ts`。

**补充批注下载卡规则：**
- 文件：`frontend/components/chat/TaskDownloadMessage.tsx`、`frontend/components/chat/MessageList.tsx`、`frontend/components/chat/ChatPanel.tsx`、`frontend/lib/api.ts`、`backend/api/comment_supplement.py`
- 脆弱原因：补充批注只从初次 generate 下载卡触发；rewrite 和 comment_supplement 下载卡继续显示补充批注动作会产生衍生文件重复任务。
- 安全修改：保持 `taskKind === 'generate'` 才允许补充批注；请求只携带当前会话、当前 output file 和模型。
- 测试覆盖：`frontend/__tests__/unit/components/chat/test_message_list.test.tsx`、`frontend/e2e/test_comment_supplement.spec.ts`。

**模板候选 UI 与后端策略绑定紧：**
- 文件：`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/forms/TemplateCandidateDialog.tsx`、`frontend/lib/api.ts`、`frontend/types/api.ts`、`backend/models/template_candidates.py`、`backend/api/template_candidates.py`
- 脆弱原因：候选列表、`selectable`、`blocked_reason`、AI ranking、选择回填和下载代理都跨前后端。
- 安全修改：前端只根据后端返回的 `selectable` 和 `blocked_reason` 决定按钮状态；不要用项目名在前端重排或反查候选。
- 测试覆盖：`frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`。

**开发期 API 地址联动：**
- 文件：`frontend/lib/apiBaseUrl.ts`、`frontend/next.config.ts`、`frontend/playwright.config.ts`
- 脆弱原因：`NEXT_PUBLIC_API_URL` 同时影响浏览器 API base URL、Next rewrite 目标、开发期 allowed origins 和 Playwright dev server 联调。
- 安全修改：修改 API 地址解析时同时检查三处配置，并补 `frontend/__tests__/unit/lib/test_api_base_url.test.ts`。
- 测试覆盖：`frontend/__tests__/unit/lib/test_api_base_url.test.ts`。

## 扩展限制

**浏览器会话持久化：**
- 当前容量：未设置明确 storage 上限；受浏览器 `sessionStorage` 容量和单页渲染性能限制。
- 限制：多会话、多长任务、多过程卡和大段 AI 文本可能触发 storage 或渲染压力。
- 扩展路径：引入后端会话分页或前端清理策略前，避免把运行中 stream 快照和完整审计内容持久化。

**前端 E2E 的真实生成能力：**
- 当前容量：Playwright 可验证 mock 后端下的 URL、会话、SSE、agent run、模板弹窗、下载入口和任务卡行为。
- 限制：前端 E2E 不能验证真实 Word COM、pywin32、graph 锁、后端任务队列和生成文档内容。
- 扩展路径：发布验收需要回到 Windows Python + Word/WPS COM 环境；前端只验证请求、状态、SSE 和下载入口。

**SSE 事件历史和重放窗口：**
- 当前容量：前端每个 SSE 连接用 `seenEventIds` 保存最多 5000 个事件 id；后端 `SSEManager` 保存任务事件并支持 `lastEventId` 重放。
- 限制：超长任务、高频日志或 agent step 会放大内存和重放成本。
- 扩展路径：新增高频事件时先定义事件压缩、采样或分页策略。

## 依赖风险

**Windows/WSL 原生依赖：**
- 风险：Next、Tailwind、SWC、Playwright 和 `lightningcss` 等原生依赖不能在 Windows 与 WSL 间复用同一个 `node_modules`。
- 影响：`npm run dev`、lint、build 或 E2E 可能因平台二进制不匹配失败。
- 迁移计划：Windows 使用 `frontend/node_modules/`；WSL 使用 Linux npm 安装，必要时使用 `frontend/node_modules-wsl/`；启动脚本和 README 说明以 `README.md`、`scripts/start-dev-win.ps1`、`scripts/start-dev-wsl.sh` 为准。

**Next.js 16 / React 19 / Jest 29 测试环境组合：**
- 风险：框架版本较新，测试环境依赖 `next/jest`、`jest-environment-jsdom`、MSW ESM 转换和 polyfill 配置。
- 影响：升级依赖或新增 ESM 包时可能触发 jsdom、fetch、EventSource、TextEncoder 或 transform 问题。
- 迁移计划：依赖变更后运行 `npm run type-check`、`npm run test`，重点检查 `frontend/jest.config.ts`、`frontend/polyfills.js`、`frontend/jest.setup.js`。

## 缺失或未确认能力

**稳定认证/权限 UI 未检测到：**
- 问题：前端当前没有登录页、认证 provider、JWT 注入、OAuth SDK 或路由守卫事实。
- 阻塞因素：前端不能判断用户身份、租户或授权范围；相关能力必须由后端或新增认证层定义。

**生产监控/错误上报未检测到：**
- 问题：未检测到 Sentry、Datadog、OpenTelemetry、PostHog、Google Analytics 或 Firebase 等前端监控 SDK。
- 阻塞因素：生产端错误追踪依赖部署平台、浏览器 console 或后端日志；前端代码内没有统一上报边界。

**会话后端持久化未接入：**
- 问题：前端会话 API helper 当前是占位实现；会话主状态依赖 `sessionStorage`。
- 文件：`frontend/lib/api.ts`、`frontend/stores/chatStore.ts`、`backend/api/conversations.py`
- 阻塞因素：刷新浏览器 session、跨设备恢复或服务端会话列表需要明确后端 API shape 后再接入。

**CI workflow 未检测到：**
- 问题：仓库级 `.github/workflows/` 未检测到。
- 阻塞因素：lint、type-check、Jest、Playwright 和文档校验是否执行取决于人工或外部流水线。

## 测试覆盖缺口

**真实 Word COM 生成闭环：**
- 未覆盖内容：真实后端、任务队列、LangGraph、Word/WPS COM、文件写回、下载文件内容和补充批注写回。
- 文件：`frontend/e2e/`、`frontend/__tests__/`
- 风险：前端测试通过不代表 Word 输出正确。
- 优先级：高，用于发布验收；不适合作为常规前端单元测试。

**跨端契约缺少统一 contract 测试：**
- 未覆盖内容：后端 Pydantic schema 与 `frontend/types/api.ts` 的自动一致性检查。
- 文件：`frontend/types/api.ts`、`frontend/lib/api.ts`、`backend/models/generate.py`、`backend/models/agent_run.py`、`backend/models/sse.py`
- 风险：前后端字段漂移只能在运行时或 mock 不匹配时暴露。
- 优先级：高，尤其是 `GenerateRequest`、`AgentRunStreamRequest`、`TaskKind`、SSE `done/error/agent_step`。

**模板候选真实外部策略组合：**
- 未覆盖内容：外部候选 API、后端 allowed host、AI ranking provider、非法年份、`year < 2025`、下载代理失败和选择落盘失败的真实组合。
- 文件：`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/forms/TemplateCandidateDialog.tsx`、`backend/api/template_candidates.py`、`backend/util/common_util/template_candidates.py`
- 风险：前端 mock 测试通过但真实候选策略变化后 UI 回填或按钮状态不一致。
- 优先级：中。

**agent run 日志脱敏回归：**
- 未覆盖内容：前端发送的 `message`、`uploaded_files.file_path`、`rewrite_context` 和后端 agent run audit summary 的端到端脱敏验证。
- 文件：`frontend/components/chat/ChatPanel.tsx`、`frontend/lib/api.ts`、`backend/agents/task_context_assistant/logging.py`、`backend/agents/task_context_assistant/tools.py`
- 风险：新增事件或工具摘要时可能把真实路径、token、traceback 或完整用户原文写入日志和公共摘要。
- 优先级：中。

**测试证据目录不是单一真源：**
- 未覆盖内容：`frontend/tasks/*/logs`、`frontend/tasks/*/screenshots`、`frontend/.playwright-cli/`、`frontend/playwright-report/`、`frontend/test-results/` 的新旧证据一致性。
- 文件：`frontend/tasks/`、`frontend/.playwright-cli/`、`frontend/playwright-report/`、`frontend/test-results/`
- 风险：过期截图、console log 或 Playwright report 被误当作当前验证结果。
- 优先级：中；交付说明应以本轮实际命令输出为准。

**大文件行为回归：**
- 未覆盖内容：`chatStore`、`TenderFormShared`、`ChatPanel`、`useChatSSE` 的全部组合路径。
- 文件：`frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/ChatPanel.tsx`、`frontend/hooks/useChatSSE.ts`
- 风险：局部修复影响未覆盖的任务/会话分支。
- 优先级：中；新增分支应补窄单测或 mock E2E。

**测试 setup 双入口：**
- 未覆盖内容：`frontend/jest.setup.ts` 与 `frontend/jest.setup.js` 的一致性和是否被实际加载。
- 文件：`frontend/jest.setup.js`、`frontend/jest.setup.ts`、`frontend/jest.config.ts`
- 风险：测试环境修改未生效。
- 优先级：低；除非调整测试环境。

---

*前端风险审计：2026-06-09*

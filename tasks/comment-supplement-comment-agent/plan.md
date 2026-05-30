# 功能: 补充批注与 comment_agent

下面这份计划应尽可能完整，但在真正开始实现前，你仍然必须再次验证文档、代码库模式以及任务本身是否合理。

特别注意现有 utils、types、models 的命名，并确保从正确的文件中导入。

## 功能描述

把 AI 批注从阻断生成成功的硬失败项改为可降级增强项：正文成功写入且文件可下载时，任务应完成；批注失败通过 `comment_writeback` 摘要和 warning 呈现。新增 `comment_supplement` 独立任务，允许用户在初次 generate 成功文档上补充批注。`generation_mode=agent` 在正文 `content_agent` 完成并保存文档后，进入 `comment_agent` 批注校验/修复/写入链路；`workflow` 保持旧的 `generate_comments -> update_word` 确定性路径。

## 用户故事

作为一名 TenderWord 用户，我想在正文已生成时仍能下载文档，并可按需补充批注，以便批注锚点或写入失败不会阻断主文档成果。

## 问题陈述

现有 `update_word` 类节点在 `generated_comment_count > 0` 且 `comment_writeback_added == 0` 时抛出异常，导致主任务失败。这个行为把 AI 批注增强项提升成主流程硬门槛。另一方面，agent 生成模式已有正文智能体过程展示，但批注锚点修复仍缺少独立 agent、工具限制、审计和前端过程卡。

## 方案陈述

新增统一 `CommentWritebackSummary` 契约，所有生成和补充任务完成时把批注写回统计放入任务 result 和 SSE `done`。修改各 update_word 节点，让批注失败只记录 warning，不抛出硬失败。新增 `comment_agent` 运行时，使用 LangChain `create_agent`、确定性校验工具、Word 写入工具和 `ToolCallLimitMiddleware`。新增 `comment_supplement` API、task kind、graph 和前端按钮，复用现有任务队列、SSE、下载与会话 rewrite_state 机制。

## 功能元数据

**功能类型**: 增强 / 新能力
**预估复杂度**: 高
**主要受影响系统**: 后端任务模型、SSE、DocumentService、生成 graph、Word 批注写回节点、comment prompt、LangChain agent、前端 API/SSE 类型、聊天任务消息、下载卡、E2E
**依赖项**: 现有 `langchain`、`langchain-core`、`langchain-openai`、`deepagents`、Word COM；本地已验证 `langchain.agents.create_agent` 与 `ToolCallLimitMiddleware` 可导入。

---

## 上下文参考

### 相关代码文件 重要：实现前你必须先阅读这些文件！

- `backend/task/task_queue_manager.py` (lines 29-77) - `TaskKind`、`NodeName`、`NODE_DISPLAY_NAMES` 的任务类别和进度显示真源。
- `backend/models/task.py` (lines 31-36) - API 层 `TaskKind` enum，目前只有 `generate`、`rewrite`、`edit`。
- `backend/services/task_service.py` (lines 221-227) - 内部 task kind 到 API task kind 的转换表。
- `backend/models/sse.py` (lines 144-191) - `AgentStepEventData` 与 `DoneEventData` 契约，需要补 `comment_writeback`。
- `backend/core/sse_manager.py` (lines 198-220, 665-702) - `send_done_threadsafe()` / `send_done()` 需要透传 `comment_writeback`。
- `backend/services/document_service.py` (lines 412-441) - generate 任务创建入口。
- `backend/services/document_service.py` (lines 446-593) - rewrite/edit 任务创建模式和错误返回模式，新增 `comment_supplement` 应保持一致。
- `backend/services/document_service.py` (lines 865-1022) - 任务执行完成、会话快照、`complete_task()` 和 SSE `done` 发送主路径。
- `backend/services/document_service.py` (lines 1099-1165) - `_build_rewrite_state_snapshot()` 与 `_build_task_result_payload()`，需要写入内部批注依据并输出摘要。
- `backend/services/conversation_service.py` (lines 66-86, 115-194) - 最新 `rewrite_state` 获取和追加机制，`comment_supplement` 要复用。
- `backend/graphs/base_graph.py` (lines 510-634) - 标准生成 graph 中 `generation_mode_gate`、`content_agent`、`generate_comments`、`update_word` 的真实拓扑。
- `backend/nodes/common_word_nodes/update_word.py` (lines 1177-1217) - 通用 update_word 批注硬失败逻辑，必须改为 warning。
- `backend/nodes/gjgk_word_nodes/gjgk_update_word.py` (lines 1417-1457) - `gjgk` 专属 update_word 批注硬失败逻辑。
- `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py` (lines 1126-1167) - 服务自筹 update_word 批注硬失败逻辑。
- `backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py` (lines 436-470) - 货物财政 direct-replace update_word 批注硬失败逻辑。
- `backend/nodes/common_word_nodes/comment_writeback.py` (lines 305-513) - 现有确定性批注写入工具，返回 `added/failed/skipped/issues`。
- `backend/nodes/common_word_nodes/generate_comments.py` - 普通批注 JSON 生成节点，workflow 和 agent 初始候选可复用其解析/修复模式。
- `backend/prompts/comment_prompt.py` (lines 64-84) - 有送审稿计划时的 JSON 输出和锚点约束真源。
- `backend/agents/generation/content_agents.py` (lines 119-129, 172-210, 489-544) - 现有智能体 runner 创建、stream 转发和 tool-call unsupported 处理模式。
- `backend/agents/generation/model_factory.py` - 创建聊天模型的现有封装，`comment_agent` 应复用。
- `backend/main.py` (lines 47-50, 176-185) - API router 注册入口。
- `frontend/types/api.ts` (lines 12, 202-208, 485-495) - 前端 `TaskKind`、`TaskResult`、`SSEDoneEvent` 契约。
- `frontend/lib/api.ts` (lines 191-214, 607-614) - create task response 解析、generate/edit task helper 模式。
- `frontend/lib/sse.ts` (lines 209-222) - named event 注册已包含 `agent_step` 和 `done`，新增字段无需新增事件类型。
- `frontend/hooks/useChatSSE.ts` (lines 45-59, 219-234, 465-486) - task kind 判断、任务 result 提取、SSE done 完成处理。
- `frontend/stores/chatStore.ts` (lines 1360-1460) - `completeTask()` 创建/更新下载卡 metadata。
- `frontend/components/chat/TaskDownloadMessage.tsx` (lines 1-55) - 下载卡 UI，新增 warning 和 `补充批注` 按钮。
- `frontend/components/chat/ChatPanel.tsx` (lines 647-686, 773-777) - edit task 创建和下载 handler 模式；新增补充批注 handler 应放这里或同层容器。
- `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx` - SSE 到任务消息映射测试参考。
- `frontend/e2e/test_generation_mode_agent.spec.ts` - mock SSE agent 过程和下载卡 E2E 参考。
- `asset/shared_runtime_word_skill_knowledge_pack.md` 与 `asset/README.md` - 本需求完成后必须更新的知识包。

### 需要创建的新文件

- `backend/api/comment_supplement.py` - 创建独立补充批注任务的 API route。
- `backend/graphs/comment_supplement_graph.py` - 独立补充批注 graph，复用 `BaseGraph` 锁、取消和进度包装。
- `backend/nodes/common_word_nodes/comment_supplement.py` - 准备副本、构造初始批注候选、调用 `comment_agent`、更新 state。
- `backend/agents/comments/__init__.py` - comment agent package 导出。
- `backend/agents/comments/types.py` - comment candidate、validation result、writeback summary、audit payload 类型。
- `backend/agents/comments/comment_agent.py` - `create_agent` runner、工具调用限制、stream 回调和结果收敛。
- `backend/agents/comments/tools.py` - 确定性校验工具和 Word 写入工具。
- `backend/agents/comments/workspace.py` - `comment_agent` 审计日志目录与写入 helper。
- `backend/prompts/comment_no_reference_prompt.py` - 无参考批注 prompt。
- `backend/tests/agents/test_comment_agent.py` - 工具限制、只改 `reference_text`、失败反馈、统计测试。
- `backend/tests/graphs/test_comment_supplement_graph.py` - 新 graph 节点和任务 kind 测试。
- `backend/tests/api/test_comment_supplement_api.py` - API 请求与错误测试。
- `backend/tests/prompts/test_comment_no_reference_prompt.py` - 无参考 prompt 契约测试。
- `frontend/__tests__/unit/components/chat/test_task_download_message_comment_supplement.test.tsx` - 下载卡按钮和 warning 测试。
- `frontend/e2e/test_comment_supplement.spec.ts` - mock generate 后点击 `补充批注` 的 E2E。

### 需要更新的现有文件

- `backend/models/task.py`
- `backend/task/task_queue_manager.py`
- `backend/services/task_service.py`
- `backend/models/sse.py`
- `backend/core/sse_manager.py`
- `backend/models/generate.py` 或新增模型后在 `backend/models/__init__.py` 导出
- `backend/services/document_service.py`
- `backend/graphs/base_graph.py`
- `backend/graphs/__init__.py`
- `backend/states/base_state.py`
- `backend/nodes/common_word_nodes/update_word.py`
- `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`
- `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`
- `backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py`
- `backend/nodes/common_word_nodes/comment_writeback.py` 如需把 skipped 与 failed 原因归一化
- `backend/main.py`
- `frontend/types/api.ts`
- `frontend/lib/api.ts`
- `frontend/hooks/useChatSSE.ts`
- `frontend/stores/chatStore.ts`
- `frontend/components/chat/TaskDownloadMessage.tsx`
- `frontend/components/chat/ChatPanel.tsx`
- `frontend/components/chat/MessageList.tsx` 如需传递补充批注 handler
- 相关后端、前端单测和 E2E
- `asset/shared_runtime_word_skill_knowledge_pack.md`
- `asset/README.md`

### 需要遵循的模式

**任务创建模式：** API route 保持薄入口，调用 `get_document_service()`；创建失败时返回结构化 `HTTPException`，参考 `backend/api/edit.py`。

**任务执行模式：** 新任务必须通过 `DocumentService._create_document_task()`、`TaskQueueManager` 和 `BaseGraph.invoke_with_timing_async()`，不得直接在 API 或 service 中调用 Word COM。

**SSE 模式：** 不新增 SSE event type；复用现有 `agent_step`、`progress`、`done`、`error`。`comment_agent` 内容通过 `AgentStepEventData.node='comment_agent'` 暴露。

**前端 API 模式：** 所有 JSON 请求经 `frontend/lib/api.ts`，不要在组件中裸写 `fetch`。

**前端任务消息模式：** 任务消息组仍由 `chatStore.startTask()`、`completeTask()`、`useChatSSE()` 管理；不要直接向组件局部状态 append 下载卡。

**日志模式：** 用户可见 warning 走 `progress_log.warning()`；排障细节和 agent 审计写入 execution/audit 日志，不放到用户态 SSE 文案里。

**Word 写回模式：** Word COM 写入只能在 graph 节点或工具内部经统一任务执行锁运行；确定性校验和写入工具必须再次做门禁。

---

## 实现计划

### 阶段 1：任务与结果契约

先建立 `comment_writeback` 摘要类型和 `comment_supplement` task kind，让后续 backend/frontend 都围绕同一契约实现。

**任务：**

- 增加后端和前端 `TaskKind.comment_supplement`。
- 增加后端 `CommentWritebackSummaryData` 与前端 `CommentWritebackSummary`。
- 扩展 `TaskResult`、SSE `done`、`SSEManager.send_done()`、`DocumentService._build_task_result_payload()`。
- 增加统一 builder，例如 `backend/nodes/common_word_nodes/comment_writeback.py` 或新 helper 中的 `build_comment_writeback_summary_payload()`。

### 阶段 2：批注降级和 workflow 保持旧路径

修改所有现有 update_word 批注硬失败点。`workflow` 仍通过 `generate_comments` 生成 JSON，再由 update_word 确定性写入，但写入失败只产出 warning。

**任务：**

- 删除或改写 `generated_count > 0 and added == 0` 的 raise。
- 将 summary 文案统一为用户可读 warning，例如 `AI 批注写入：生成 3 条，成功 0 条，失败 3 条`。
- `warning` 只由 `generated > 0 && failed > 0` 决定。
- `overlapping_comment_exists` 等已有批注位置归入 skipped，不计 failed。

### 阶段 3：comment_agent 运行时

新增 comment agent package，使用 `create_agent` 和两个确定性工具。工具限制由 `ToolCallLimitMiddleware` 保证，工具内部也做强校验。

**任务：**

- 实现候选 JSON 归一化，保留初始 `comment_text` 快照。
- 实现校验工具：只查 `polished_text`，返回 passed/failed、相近候选片段和失败原因。
- 实现写入工具：重新校验，通过后只在锚点区间内写入，无已有批注才写入。
- 实现 runner：`create_agent(name='comment_agent', tools=[...], middleware=[ToolCallLimitMiddleware(...)])`。
- 实现审计日志：初始 JSON、每轮 AIMessage、每轮校验结果、最终列表和写入统计。
- 通过 `agent_step_callback` 只发送 `AIMessage.content`，过滤工具消息。

### 阶段 4：agent generate 与 comment_supplement graph

把 agent 生成和独立补充任务接入 graph。agent generate 在正文保存后进入 `comment_agent`；独立补充任务读取最新 rewrite_state、复制文件、运行 agent 并更新 rewrite_state。

**任务：**

- 修改标准生成 graph：`workflow` 不变；`agent` 在 `update_word` 后按条件进入 `comment_agent` 节点。
- 给 update_word 增加状态开关，agent 模式只写正文和样式，不写 AI 批注。
- 新增 `CommentSupplementGraph`，节点顺序建议为 `prepare_comment_supplement -> comment_agent -> finalize_comment_supplement`。
- 新增 `DocumentService.create_comment_supplement_task()`，校验 `conversation_id`、最新 `rewrite_state`、source file 和模型。
- 完成后通过 conversation service 追加或更新最新 assistant rewrite_state，使 `prepared_doc_path` 指向新副本。

### 阶段 5：前端 API、SSE 和 UI

前端新增创建补充批注任务 helper，下载卡接收补充批注 handler 和 `comment_writeback` metadata。SSE 完成时把新摘要传入 `completeTask()`。

**任务：**

- 更新 `frontend/types/api.ts`。
- 在 `frontend/lib/api.ts` 增加 `createCommentSupplementTask()`。
- 在 `useChatSSE.extractOutputInfo()` 和 done 分支解析 `comment_writeback`。
- 扩展 `chatStore.completeTask()` metadata 保存 `commentWriteback`。
- `TaskDownloadMessage` 显示 warning 和 `补充批注` 按钮。
- `ChatPanel` 创建补充批注任务，调用 `startTask()` 并复用现有 SSE 流。
- 确保 `comment_agent` 的 `agent_step` 卡按 node 分组，workflow 不显示。

### 阶段 6：测试、E2E 与知识包

按风险面补齐后端、前端和 mock E2E，最后更新 `asset/`。

**任务：**

- 后端测试覆盖硬失败移除、warning 规则、skipped-only、result/SSE、rewrite_state、comment_supplement、comment_agent 和 prompt。
- 前端测试覆盖类型、SSE 解析、下载卡、按钮、warning、agent 卡追加。
- Playwright mock 覆盖 `补充批注` 创建轻量任务和 agent/workflow 展示差异。
- 更新 `asset/shared_runtime_word_skill_knowledge_pack.md` 和 `asset/README.md`。

---

## 分步任务

重要：严格按顺序执行所有任务，从上到下。每个任务都必须是原子性的，并且可独立测试。

### UPDATE `backend/task/task_queue_manager.py`

- **IMPLEMENT**: 在内部 `TaskKind` 中新增 `COMMENT_SUPPLEMENT = "comment_supplement"`；在 `NodeName` / `NODE_DISPLAY_NAMES` 中新增 `comment_agent`、`prepare_comment_supplement`、`finalize_comment_supplement` 等显示名。
- **PATTERN**: `TaskKind` 与 `NODE_DISPLAY_NAMES` 现有定义在 `backend/task/task_queue_manager.py:29` 和 `backend/task/task_queue_manager.py:60`。
- **GOTCHA**: `_normalize_task_kind()` 当前未知字符串会回退 generate；新增枚举后应能识别新值。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\services\test_task_service_task_kind.py -v`

### UPDATE `backend/models/task.py` 与 `backend/services/task_service.py`

- **IMPLEMENT**: API `TaskKind` enum 新增 `COMMENT_SUPPLEMENT`；`TaskService._convert_task_kind()` 映射内部新枚举。
- **PATTERN**: `backend/models/task.py:31` 与 `backend/services/task_service.py:221`。
- **GOTCHA**: 任务状态、心跳和列表都返回 API `TaskKind`，不要只改单个 response。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\services\test_task_service_task_kind.py -v`

### ADD comment writeback summary model

- **IMPLEMENT**: 在 `backend/models/sse.py` 增加 `CommentWritebackSummaryData`，字段为 `summary/generated/added/failed/skipped/warning`，并加到 `DoneEventData`。在 `frontend/types/api.ts` 增加镜像 `CommentWritebackSummary`，并加到 `TaskResult`、`SSEDoneEvent`。
- **PATTERN**: `StyleWritebackSummaryData` 和前端 `StyleWritebackSummary` 是直接参考。
- **GOTCHA**: `warning` 规则由后端统一计算，前端只展示，不重新推断业务语义。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\models\test_sse_agent_step.py -v`; `cd frontend; npm run type-check`

### UPDATE `backend/core/sse_manager.py`

- **IMPLEMENT**: `send_done_threadsafe()` 和 `send_done()` 新增可选 `comment_writeback` 参数，并写入 done data。
- **PATTERN**: `style_writeback` 的透传方式在 `backend/core/sse_manager.py:198` 和 `backend/core/sse_manager.py:665`。
- **GOTCHA**: 不新增 SSE event type；避免破坏 EventSource named event 注册。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\services\test_sse_manager_agent_step.py -v`

### UPDATE `backend/nodes/common_word_nodes/comment_writeback.py`

- **IMPLEMENT**: 新增 `build_comment_writeback_summary_payload(generated_count, writeback_result, fallback_summary="")`；统一计算 `failed/skipped/warning`。确保已有批注重叠等原因计 skipped，不计 failed。
- **PATTERN**: 现有 `write_polished_comments()` 返回 `added/failed/skipped/issues`，测试在 `backend/tests/nodes/test_comment_writeback.py`。
- **GOTCHA**: 如果调整 `overlapping_comment_exists` 语义，必须同步已有测试断言，不要让 skipped-only 触发 warning。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\nodes\test_comment_writeback.py -v`

### UPDATE all update_word comment hard-fail branches

- **IMPLEMENT**: 修改 `backend/nodes/common_word_nodes/update_word.py`、`backend/nodes/gjgk_word_nodes/gjgk_update_word.py`、`backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`、`backend/nodes/gngk_word_nodes/gngk_hw_cz_update_word.py`。移除 `generated_count > 0 and added == 0` 的 raise，改为 `progress_log.warning()` 与 state 统计。
- **PATTERN**: 硬失败位置分别在 `update_word.py:1201`、`gjgk_update_word.py:1441`、`gngk_fw_zc_update_word.py:1151`、`gngk_hw_cz_update_word.py:455`。
- **GOTCHA**: 仅改批注写回硬失败，不放松受保护字段、正文边界、样式写回等强契约。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\nodes\test_comment_writeback.py tests\nodes\test_gngk_hw_cz_direct_replace_word.py tests\nodes\test_gngk_fw_zc_update_word.py -v`

### UPDATE `backend/services/document_service.py` result and rewrite snapshot

- **IMPLEMENT**: `_build_task_result_payload()` 加入 `comment_writeback`；完成时将其传给 `sse_manager.send_done_threadsafe()`。`_build_rewrite_state_snapshot()` 写入 `comment_plan_detail`、`strikethrough_plan`、`non_black_font_plan`、`generation_mode`，但 `_build_task_result_payload()` 不输出这些长数组。
- **PATTERN**: `style_writeback` result 和 SSE 透传在 `backend/services/document_service.py:978` 到 `backend/services/document_service.py:1022`。
- **GOTCHA**: `REWRITE_STATE_KEYS` 当前只允许部分 key，新增内部 key 时不要让前端 payload 读到。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\services\test_document_service_task_result.py tests\services\test_document_service_initial_state.py -v`

### ADD `backend/prompts/comment_no_reference_prompt.py`

- **IMPLEMENT**: 新增无参考批注 prompt builder，保留三维审查、严格 JSON 数组输出、`reference_text` 必须精确来自 `polished_text` 的约束，去掉历史参考/送审稿差异逻辑。
- **PATTERN**: `backend/prompts/comment_prompt.py` 的 `render_comment_prompt()`。
- **GOTCHA**: Prompt Layer 只做纯渲染，不写日志、不调 LLM、不访问 Word。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\prompts\test_comment_no_reference_prompt.py tests\prompts\test_comment_prompt_reference_contract.py -v`

### ADD `backend/agents/comments/` comment_agent runtime

- **IMPLEMENT**: 创建 `comment_agent.py`，使用 `from langchain.agents import create_agent` 和 `from langchain.agents.middleware import ToolCallLimitMiddleware`。工具包含 `validate_comment_references` 和 `write_validated_comments_to_word`。
- **PATTERN**: 模型创建复用 `backend/agents/generation/model_factory.py`；stream bridge 参考 `backend/agents/generation/content_agents.py:489`。
- **GOTCHA**: 工具限制必须按工具名设置：校验工具最多 3 次，写入工具最多 1 次。写入工具内部必须重新校验，不能信任 AI。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\agents\test_comment_agent.py -v`

### ADD deterministic validation and write tools

- **IMPLEMENT**: 校验工具输入为原始候选列表、AI 修复后的候选列表、`polished_text`；按 index 校验 `comment_text` 不变，只允许 `reference_text` 变化。失败反馈返回 index、原 reference、失败原因、相近候选片段。写入工具只对通过校验且无已有批注的条目调用 Word 写入。
- **PATTERN**: 锚点匹配可复用 `backend/helper/word_helper/semantic_matcher.py` 或 `comment_writeback.py` 中既有 normalization，但不得做全文文档兜底。
- **GOTCHA**: “已有批注位置”是 skipped，不是 failed；最终 failed 只表示未通过校验或实际写入失败。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\agents\test_comment_agent.py tests\nodes\test_comment_writeback.py -v`

### UPDATE `backend/graphs/base_graph.py` for agent branch

- **IMPLEMENT**: agent 模式下 `update_word` 之后进入 `comment_agent` 节点；workflow 模式仍保持 `generate_comments -> comments_branch_done -> update_word -> END`。给 state 增加类似 `defer_comment_writeback_to_agent` 或 `suppress_ai_comment_writeback` 的布尔开关，让 update_word 在 agent 模式只写正文和样式。
- **PATTERN**: `generation_mode_gate` 和条件边在 `backend/graphs/base_graph.py:574` 到 `backend/graphs/base_graph.py:634`。
- **GOTCHA**: 不要让 workflow 路径显示 `comment_agent`；无送审稿且不是补充任务时可跳过自动无参考批注。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\graphs\test_generation_mode_branching.py tests\graphs\test_generation_mode_workflow.py tests\graphs\test_xjcg_generation_mode_agent.py -v`

### ADD `comment_supplement` backend API and graph

- **IMPLEMENT**: 新增 `CommentSupplementRequest` 和 route `POST /api/comment-supplement`。`DocumentService.create_comment_supplement_task()` 校验会话、最新 `rewrite_state`、source file，复制文件为新副本，创建 `CommentSupplementGraph` 任务。完成后更新最新 rewrite_state 的 `prepared_doc_path`。
- **PATTERN**: edit route 和 task 创建可参考 `backend/api/edit.py`、`DocumentService.create_edit_task()`。
- **GOTCHA**: API 不直接做 Word COM；文件路径必须限制在允许目录内。若前端传 `output_file` 有风险，优先后端生成新副本路径。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\api\test_comment_supplement_api.py tests\graphs\test_comment_supplement_graph.py -v`

### UPDATE `backend/main.py`

- **IMPLEMENT**: import 并注册 `comment_supplement_router`，prefix 仍为 `/api`。
- **PATTERN**: 现有 router 注册在 `backend/main.py:176` 到 `backend/main.py:185`。
- **GOTCHA**: 保持 API 前缀 `/api`，不要引入额外版本前缀。
- **VALIDATE**: `cd backend; .\.venv\Scripts\python.exe -m pytest tests\api\test_comment_supplement_api.py -v`

### UPDATE frontend API types and helper

- **IMPLEMENT**: `frontend/types/api.ts` 中 `TaskKind` 增加 `comment_supplement`，新增 `CommentWritebackSummary` 和 `CommentSupplementRequest`，`TaskResult`/`SSEDoneEvent` 增加 `comment_writeback`。`frontend/lib/api.ts` 新增 `createCommentSupplementTask()`。
- **PATTERN**: `createGenerateTask()` 与 `createEditTask()` 在 `frontend/lib/api.ts:607` 和 `frontend/lib/api.ts:614`。
- **GOTCHA**: JSON 请求必须走 `request` 封装并返回 `CreateTaskData`。
- **VALIDATE**: `cd frontend; npm run type-check; npm test -- __tests__/unit/lib/test_api.test.ts --runInBand`

### UPDATE `frontend/hooks/useChatSSE.ts` and `frontend/stores/chatStore.ts`

- **IMPLEMENT**: `extractOutputInfo()` 和 done 分支解析 `comment_writeback`；`completeTask()` 新增参数并写入下载卡 metadata；task kind resolver 接受 `comment_supplement`。
- **PATTERN**: `styleWriteback` 解析和透传在 `frontend/hooks/useChatSSE.ts:219` 与 `frontend/stores/chatStore.ts:1360`。
- **GOTCHA**: 不把三组后端批注依据长数组持久化到 sessionStorage。
- **VALIDATE**: `cd frontend; npm test -- __tests__/unit/hooks/test_use_chat_sse.test.tsx __tests__/unit/stores/test_chat_store_task_messages.test.ts --runInBand`

### UPDATE download card and chat panel supplement handler

- **IMPLEMENT**: `TaskDownloadMessage` 增加 `onSupplementComments` prop；当 metadata.taskKind 为 `generate` 且 status completed 且有 outputFile 时显示 `补充批注`。warning 时显示 `文档已生成，部分批注未写入`。`ChatPanel` 实现 handler，调用 `createCommentSupplementTask()` 并 `startTask()`。
- **PATTERN**: 下载 handler 在 `ChatPanel.tsx:773`，下载卡现有 UI 在 `TaskDownloadMessage.tsx`。
- **GOTCHA**: rewrite/edit/comment_supplement 卡片不显示补充按钮；下载按钮不能因 warning 禁用。
- **VALIDATE**: `cd frontend; npm test -- __tests__/unit/components/chat/test_task_download_message_comment_supplement.test.tsx __tests__/unit/components/chat/test_chat_panel.test.tsx --runInBand`

### UPDATE agent_step grouping for comment_agent

- **IMPLEMENT**: 确认 `agent_step.node='comment_agent'` 会生成同名过程卡，并按时间顺序追加完成态 `AIMessage.content`。如果现有逻辑只对 generate agent conversation 生效，扩展 `shouldUseAgentStepCards()` 允许 `comment_supplement`。
- **PATTERN**: `frontend/hooks/useChatSSE.ts:392` 处理 `agent_step`，store 的 agent step 持久化在 `frontend/stores/chatStore.ts:1281` 附近。
- **GOTCHA**: 不展示工具消息；运行中高频快照仍留在 stream，不直接持久化。
- **VALIDATE**: `cd frontend; npm test -- __tests__/unit/hooks/test_use_chat_sse.test.tsx __tests__/unit/components/chat/test_task_content_message.test.tsx --runInBand`

### ADD/UPDATE E2E

- **IMPLEMENT**: 新增 `frontend/e2e/test_comment_supplement.spec.ts`，用 `page.route` mock generate 完成、点击 `补充批注`、返回 `comment_supplement` task、推送 `comment_agent` agent_step 和 done，断言新下载卡出现。扩展 `test_generation_mode_agent.spec.ts` 覆盖 workflow 不显示 `comment_agent`。
- **PATTERN**: `frontend/e2e/test_generation_mode_agent.spec.ts` 已有 mocked SSE 工具。
- **GOTCHA**: 不依赖真实后端或 Word COM；locator 使用 role/name 或稳定 test id。
- **VALIDATE**: `cd frontend; npm run test:e2e`

### UPDATE `asset/shared_runtime_word_skill_knowledge_pack.md` and `asset/README.md`

- **IMPLEMENT**: 记录批注降级、`comment_writeback` warning 契约、`comment_agent` 工具限制、`comment_supplement` 任务链路、SSE/result 前端展示边界。
- **PATTERN**: `AGENTS.md` 指定本类改动回写 shared runtime 知识包。
- **GOTCHA**: 知识包只写稳定边界、同步面、验证入口和回归风险，不写一次性排障过程。
- **VALIDATE**: `git diff --check`

---

## 测试策略

### 单元测试

- 后端 `backend/tests/nodes/test_comment_writeback.py`：批注 0 写入不再失败、warning 规则、skipped-only、不丢 issues。
- 后端 `backend/tests/services/test_document_service_task_result.py`：`comment_writeback` result 与 SSE done payload。
- 后端 `backend/tests/services/test_document_service_initial_state.py`：`rewrite_state` 包含内部批注依据和 `generation_mode`。
- 后端 `backend/tests/agents/test_comment_agent.py`：工具调用上限、只改 `reference_text`、候选反馈、最终统计。
- 后端 `backend/tests/prompts/test_comment_no_reference_prompt.py`：无参考 prompt 严格 JSON 和锚点约束。
- 前端 `frontend/__tests__/unit/lib/test_api.test.ts`：新 API helper 和 task kind。
- 前端 `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`：SSE done/result 解析与 `comment_agent` agent_step。
- 前端 `frontend/__tests__/unit/components/chat/test_task_download_message_comment_supplement.test.tsx`：按钮和 warning。

### 集成测试

- 后端 `backend/tests/api/test_comment_supplement_api.py`：创建任务、缺上下文、文件不匹配。
- 后端 `backend/tests/graphs/test_comment_supplement_graph.py`：graph 节点顺序、task kind、结果 state。
- 前端 `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`：点击补充批注创建任务并启动 SSE。

### E2E

- `frontend/e2e/test_comment_supplement.spec.ts`：mock generate -> 点击补充批注 -> `comment_agent` 卡 -> 新下载卡。
- `frontend/e2e/test_generation_mode_agent.spec.ts`：agent generate 显示正文 agent 和 `comment_agent`；workflow 不显示 `comment_agent`。

### 边界情况

- `generated=0`、`failed>0` 不 warning。
- skipped-only 不 warning。
- `generated>0`、部分 failed warning。
- `generated>0`、added=0、failed>0 仍 completed。
- `comment_agent` 第 4 次校验工具调用被 middleware 阻止。
- 写入工具第 2 次调用被 middleware 阻止。
- AI 修改 `comment_text` 被确定性校验拒绝。
- 缺少 `rewrite_state.polished_text` 时 `comment_supplement` 返回明确错误。
- 前端刷新恢复任务时 `comment_supplement` task kind 不回退为 generate。

---

## 验证命令

### 级别 1：语法与风格

```powershell
cd frontend
npm run lint
npm run type-check
```

```powershell
git diff --check
```

### 级别 2：后端单元测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\nodes\test_comment_writeback.py tests\agents\test_comment_agent.py tests\prompts\test_comment_no_reference_prompt.py -v
```

### 级别 3：后端服务/API/graph 测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests\services\test_document_service_task_result.py tests\api\test_comment_supplement_api.py tests\graphs\test_comment_supplement_graph.py -v
```

### 级别 4：前端单元测试

```powershell
cd frontend
npm test -- __tests__/unit/lib/test_api.test.ts __tests__/unit/hooks/test_use_chat_sse.test.tsx __tests__/unit/components/chat/test_task_download_message_comment_supplement.test.tsx __tests__/unit/components/chat/test_chat_panel.test.tsx --runInBand
```

### 级别 5：E2E

```powershell
cd frontend
npm run test:e2e
```

### 级别 6：完整回归

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
```

```powershell
cd frontend
npm run lint
npm run type-check
npm run test
npm run test:e2e
```

---

## 验收标准

- [ ] generate 正文文件可下载时，批注写回失败不再导致任务 failed。
- [ ] `comment_writeback` 在 task result 和 SSE `done` 中字段完整。
- [ ] warning 规则严格等于 `generated > 0 && failed > 0`。
- [ ] `workflow` 不运行、不展示 `comment_agent`。
- [ ] `agent` generate 在正文保存后运行 `comment_agent`，失败不影响下载。
- [ ] `comment_supplement` 可创建任务、复制文件、写入批注、更新 latest rewrite_state。
- [ ] `comment_agent` 使用 `create_agent`，校验工具最多 3 次，写入工具最多 1 次。
- [ ] AI 修改 `comment_text` 会被拒绝。
- [ ] 前端初次 generate 下载卡显示 `补充批注`；rewrite/edit/comment_supplement 不显示。
- [ ] warning 卡片显示 `文档已生成，部分批注未写入`，下载按钮可用。
- [ ] `comment_agent` 卡按顺序追加 AIMessage 内容，不展示工具消息。
- [ ] 后端、前端相关单测和 mock E2E 通过。
- [ ] `asset/shared_runtime_word_skill_knowledge_pack.md` 与 `asset/README.md` 已更新。

---

## 完成检查清单

- [ ] 所有任务均已按顺序完成。
- [ ] 每个任务的验证都已立即通过。
- [ ] 所有新增测试文件以 `test_` 开头。
- [ ] 没有业务组件裸写 `fetch`。
- [ ] 没有绕过 Word COM 锁和任务队列。
- [ ] 没有把批注依据长数组写入前端持久化状态。
- [ ] 没有让 `generation_mode` 进入 rewrite/edit 请求。
- [ ] 知识包已按 AGENTS.md 路由回写。

---

## 备注

- 当前需求是跨后端 graph、Word、agent runtime、SSE、前端任务 UI 的高风险增强，应避免一次性重构无关任务消息结构。
- 如果实施时发现前端传 `output_file` 会带来路径安全问题，应把输出路径生成收回后端，前端只传 `source_file` 和 `conversation_id`。
- 对真实 Word COM 的端到端验证需要 Windows + Word 环境；常规测试应尽量用 fake document 和 mock SSE 覆盖业务契约。
- 一次实现成功预估信心分数：8/10。

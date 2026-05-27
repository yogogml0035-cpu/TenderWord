# 功能: DeepAgents 生成方式重构

下面这份计划应尽可能完整，但在真正开始实现前，你仍然必须再次验证文档、代码库模式以及任务本身是否合理。

特别注意现有 utils、types、models 的命名，并确保从正确的文件中导入。

## 功能描述

在初次 generate 中新增 `generation_mode: "workflow" | "agent"`。默认 `"workflow"` 完全沿用现有 `generate_polished_text` 节点；选择 `"agent"` 时进入 DeepAgents `host_agent`，由主 agent 调用已编译 LangGraph 子 agent：`generate_agent` 负责生成初稿，`verify_agent` 负责输出审核意见数组。最多修复 3 轮，第 3 轮修复后直接放行，最终仍把 `polished_text` 写入 graph state，复用批注、样式、Word 写回、任务结果和下载链路。

## 用户故事

作为一名生成招标文件的用户，我想在初次生成时选择“工作流”或“智能体”，以便默认保持稳定旧链路，同时在需要时使用可审核、可修复的智能体生成方式。

## 问题陈述

当前初次生成只有单一路径，`generate_polished_text` 直接调用 prompt 与 LLM 得到正文。它无法在生成过程中自动审核和修复，也无法把审核意见与修复过程保留给用户。新增智能体路径时，必须避免破坏现有默认行为、任务队列、Word COM 串行锁、SSE 完成/失败收敛和前端会话草稿语义。

## 方案陈述

采用“共享主干 + 分流节点”的方式实现：

- 请求层新增 generate-only `generation_mode`。
- 标准生成 graph 在提取参数和批注准备完成后进入一个未追踪的 mode gate，再按 `generation_mode` 选择旧 `generate_polished_text` 或新 `host_agent`。
- `host_agent` 节点最终返回与旧节点同形的 `{"polished_text": ..., "generate_polished_done": True}`。
- 新增 `agent_step` SSE 事件只服务智能体 generate，用于 audit / revision 过程展示；`done` / `error` 仍保持现有终态事件。
- 前端高级设置新增生成方式切换，写入会话草稿，并在提交 generate payload 时透传。
- 逐 graph 差异类型验证智能体分支，继承链路只做 smoke。

## 功能元数据

**功能类型**: 增强 / AI runtime 重构  
**预估复杂度**: 高  
**主要受影响系统**: 后端 GenerateRequest、DocumentService、StandardTenderWorkflowGraph、DeepAgents runtime、SSE 模型与推送、前端表单草稿、SSE 解析、任务消息 UI、E2E mock  
**依赖项**: `deepagents`、可能需要 `langchain-openai` 或 DeepAgents 官方推荐的 OpenAI-compatible chat model adapter

---

## 上下文参考

### 相关代码文件 重要：实现前你必须先阅读这些文件！

- `backend/models/generate.py` (lines 28, 62, 92) - 已有 `GenerationStyle` 与 `GenerateRequest` generate-only 字段模式，`generation_mode` 应按同类字段加入。
- `backend/services/document_service.py` (lines 93, 379, 410, 715, 730, 745, 1150, 1180) - 任务创建、初始 state 注入、LLM 节点名、SSE relay 都在这里串联。
- `backend/graphs/base_graph.py` (lines 245, 473, 483, 500, 531, 561, 588, 595) - 标准生成 graph、节点声明、进度统计与当前 `generate_polished_text` 边。
- `backend/nodes/common_word_nodes/generate_polished_text.py` (lines 35, 88, 91, 164, 179, 240) - 旧生成节点必须保留，智能体 `generate_agent` 可复用其 prompt 输入和 LLM 调用模式。
- `backend/util/common_util/llm_stream_utils.py` - 当前 LLM 配置、超时、OpenAI-compatible 调用和 DeepSeek/Qwen/Doubao extra body 真源。
- `backend/models/sse.py` (lines 17, 97, 147, 169) - 新增 `agent_step` 事件类型和数据模型的后端契约入口。
- `backend/core/sse_manager.py` (lines 136, 174, 200, 563, 644, 680) - 线程安全 SSE 推送和事件缓冲真源。
- `backend/graphs/xjcg_tender_graph.py` (lines 80, 105, 108, 110) - `xjcg` 标准 graph 差异验证入口。
- `backend/graphs/gngk_hw_zc_tender_graph.py` (lines 25, 34, 37, 39) - `gngk_hw_zc` 标准公开招标货物自筹验证入口。
- `backend/graphs/gngk_hw_cz_tender_graph.py` (lines 16, 19, 20) - `gngk_hw_cz` direct-replace 特化入口。
- `backend/graphs/gngk_fw_zc_tender_graph.py` (lines 17, 20, 22) - `gngk_fw_zc` 服务特化入口。
- `backend/graphs/gngk_fw_cz_tender_graph.py` (line 10) - 继承复用 smoke 入口。
- `backend/graphs/gjgk_tender_graph.py` (lines 25, 34, 37, 39, 47) - `gjgk` 专属流程和 post-update hook 入口。
- `frontend/types/api.ts` (lines 142, 145, 156, 426, 466, 484, 545) - 前端 GenerateRequest、SSE union 与节点显示名入口。
- `frontend/lib/formDataConverter.ts` (lines 108, 124, 185, 205, 222, 232) - 三类表单到 generate payload 的转换入口。
- `frontend/components/forms/TenderFormShared.tsx` (lines 48, 464, 489, 760, 1104, 1497, 1535, 1737) - 表单数据、草稿恢复、高级设置与提交入口。
- `frontend/stores/chatStore.ts` (lines 75, 83, 197, 224, 725, 1871) - 会话草稿、持久化和任务消息历史入口。
- `frontend/hooks/useChatSSE.ts` (lines 44, 307, 340, 372) - 任务 SSE 到 UI 的解析入口。
- `frontend/stores/chatStreamStore.ts` (lines 4, 66, 80) - 运行中任务内容、日志、进度缓存入口。
- `frontend/components/chat/MessageList.tsx` (lines 254, 263, 264, 271) - 任务消息类型到组件的分发入口。
- `frontend/components/chat/FormPanel.tsx` (lines 352, 369, 372, 373) - generate 表单提交、`conversation_id` 注入和 `startTask` 入口。

### 需要创建的新文件

- `backend/agents/generation/__init__.py` - 对外导出 DeepAgents 生成 runtime。
- `backend/agents/generation/types.py` - 定义 `GenerationMode` 运行时常量、agent 输出模型、审核意见模型、事件 payload 类型。
- `backend/agents/generation/model_factory.py` - 从现有 settings / `MODEL_CONFIGS` 构造 DeepAgents 可用 chat model，复用 API key、base_url、model、extra body 与超时配置。
- `backend/agents/generation/generate_agent_graph.py` - 创建并 compile `generate_agent` StateGraph。
- `backend/agents/generation/verify_agent_graph.py` - 创建并 compile `verify_agent` StateGraph。
- `backend/agents/generation/host_agent.py` - 创建 `host_agent`，执行审核/修复循环并返回最终 `polished_text`。
- `backend/nodes/common_word_nodes/host_agent_generate.py` - graph 节点包装，接收 state/config，调用 host agent，并返回 `polished_text` state 更新。
- `backend/tests/agents/test_generation_host_agent.py` - fake DeepAgents runner 单测。
- `backend/tests/graphs/test_generation_mode_branching.py` - workflow/agent 分支和逐类型 graph 差异测试。
- `frontend/components/chat/TaskAgentStepMessage.tsx` - 如现有 task card 无法自然承载 audit/revision，则新增智能体步骤卡片组件。
- `frontend/e2e/test_generation_mode_agent.spec.ts` - mock generate/SSE 的浏览器可见链路。

### 相关文档 实现前你应该先阅读这些文档！

- [DeepAgents subagents](https://docs.langchain.com/oss/python/deepagents/subagents.md)
  - 具体章节：subagents、`CompiledSubAgent`
  - 原因：本需求要求 `generate_agent` 和 `verify_agent` 都是已编译 `StateGraph` 包装成 `CompiledSubAgent`。
- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api.md)
  - 具体章节：`StateGraph`、`.compile()`
  - 原因：子 agent 和标准 graph gate 都依赖 LangGraph compile 语义。
- [LangGraph Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs.md)
  - 具体章节：subgraph 使用方式
  - 原因：标准 graph 已使用 word operations subgraph，新 agent graph 也要遵守 compile 后接入的约束。

### 需要遵循的模式

**Generate-only 字段模式：**

- `generation_style` 与 `style_writeback_mode` 已在 `GenerateRequest` 定义，并在 `DocumentService._build_initial_state()` 写入初始 state。
- `generation_mode` 应复用该模式，但不得进入 `EditTaskRequest` 或 rewrite/edit skill state。

**Graph 节点模式：**

- `StandardTenderWorkflowGraph` 通过类属性声明节点 callable。
- 类型 graph 只覆盖差异节点；不要为每个招标类型复制一整套 graph。
- 新增 agent 分支应在基类统一接入，让所有标准 generate graph 自动拥有分流能力。

**LLM 调用模式：**

- 工作流旧节点继续调用 `render_generate_prompt()` 与 `stream_llm_completion()`。
- DeepAgents 模型构造必须复用 `settings.get_llm_config()` 和 `MODEL_CONFIGS`，不能在新文件硬编码 DeepSeek/Qwen/Doubao 模型名、base_url、超时或 extra body。

**SSE 模式：**

- 后端 `SSEEventType`、数据模型、`SSECallback`、`sse_manager`、前端 `SSEEventType` union 与 `useChatSSE` 必须同步。
- `done` 和 `error` 仍是终态；`agent_step` 只补充中间过程。

**前端草稿模式：**

- `TenderFormShared` 负责表单局部状态和草稿更新。
- `chatStore` 的 `ConversationFormDraft` 是会话草稿持久化真源。
- `gngk` 现有 `generation_style` 是按 `tender_lx` 缓存；本需求要求 `generation_mode` 是全局切换，默认不需要按 `tender_lx` 分桶，除非实现时发现 UI 语义要求与用户描述冲突。

---

## 实现计划

### 阶段 1：契约与依赖准备

**任务：**

- 后端新增 `GenerationMode` enum 和 `GenerateRequest.generation_mode`。
- `TenderGraphStateBase` 新增 `generation_mode`。
- 前端新增 `GenerationMode` 类型和 `GenerateRequest.generation_mode`。
- 表单基础数据、会话草稿和转换器透传该字段。
- 增加 DeepAgents 依赖，并验证 Windows PowerShell 下可安装。

### 阶段 2：后端智能体 runtime

**任务：**

- 新建 `backend/agents/generation/`。
- 用现有 prompt 输入生成 `generate_agent` 的 StateGraph。
- 用严格 JSON 机器契约生成 `verify_agent` 的 StateGraph。
- 建立 DeepAgents model factory，复用现有模型配置。
- 建立 `host_agent` 循环：初稿 -> 审核 -> 修复 -> 最多 3 轮 -> 结构化输出。
- 所有协议错误 fail-fast，不自动回退 workflow。

### 阶段 3：Graph 分流与 SSE

**任务：**

- 在 `StandardTenderWorkflowGraph` 中新增 mode gate。
- `workflow` 分支走旧 `generate_polished_text`。
- `agent` 分支走 `host_agent` 节点。
- 两个分支后续都接入现有 `generate_comments` / `comments_branch_done` / `update_word`。
- 新增 `agent_step` 后端 SSE 类型、callback、sse_manager 线程安全发送方法。
- agent runtime 在初稿、审核、修复时推送 agent step 事件。

### 阶段 4：前端体验

**任务：**

- 高级设置新增“生成方式” segmented control。
- 默认值和草稿持久化接入。
- API payload 透传。
- 前端 SSE 类型、stream store、chat store、`useChatSSE` 和消息组件支持 agent step。
- 确保智能体过程卡任务完成后仍留在会话历史。

### 阶段 5：测试、E2E 与知识回写

**任务：**

- 后端 fake runner 覆盖 workflow 不变、agent 成功、审核 JSON 失败、工具调用不支持失败、第 3 轮放行。
- Graph 差异覆盖 `xjcg`、`gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_zc`、`gjgk`；`gngk_fw_cz` 做 smoke。
- 前端单测覆盖切换控件、草稿持久化、payload、SSE 解析和卡片保留。
- E2E mock 固化完整用户可见链路。
- 更新两个知识包和索引。

---

## 分步任务

### UPDATE `backend/models/generate.py`

- **IMPLEMENT**: 新增 `GenerationMode(str, Enum)`，成员 `WORKFLOW = "workflow"`、`AGENT = "agent"`；在 `GenerateRequest` 增加 `generation_mode: GenerationMode = Field(default=GenerationMode.WORKFLOW, description="生成方式（仅初次 generate 生效）")`。
- **PATTERN**: `GenerationStyle` 与 `style_writeback_mode` 已在同文件定义并作为 generate-only 字段使用。
- **GOTCHA**: 不修改 `EditTaskRequest`。
- **VALIDATE**: `cd backend; python -m pytest tests/models/test_generate_request_generation_style.py -v`

### UPDATE `backend/states/base_state.py`

- **IMPLEMENT**: 在 `TenderGraphStateBase` 增加 `generation_mode: str`。
- **PATTERN**: `generation_style`、`style_writeback_mode` 同属 generate runtime 字段。
- **VALIDATE**: `cd backend; python -m pytest tests/services/test_document_service_initial_state.py -v`

### UPDATE `backend/services/document_service.py`

- **IMPLEMENT**: `_build_initial_state()` 读取 `request.generation_mode`，写入 state；日志中可保留模式摘要但不要把完整 prompt 或敏感配置写入 progress log。
- **IMPLEMENT**: `TASK_KIND_TO_LLM_NODE` 仍保持 generate 默认 `generate_polished_text`，agent 中间展示走 `agent_step`，避免破坏旧 llm 卡触发。
- **PATTERN**: 参考 `generation_style` 在 lines 730-746 的处理。
- **GOTCHA**: 如果后续希望 `host_agent` 的最终正文也走 `llm` 事件，必须显式避免前端把它当旧初稿卡覆盖掉 agent revision 卡。
- **VALIDATE**: `cd backend; python -m pytest tests/services/test_document_service_initial_state.py tests/services/test_document_service_task_result.py -v`

### ADD `backend/agents/generation/types.py`

- **IMPLEMENT**: 定义 Pydantic 模型：
  - `AuditFinding(evidence: str, fix_hint: str)`
  - `HostAgentFinalOutput(polished_text: str, audit_findings: list[AuditFinding] = [], revision_rounds: int = 0)`
  - `AgentStepPayload(step_type: Literal["draft", "audit", "revision"], round: int, content: str | None, findings: list[AuditFinding])`
- **GOTCHA**: `verify_agent` 输出空数组表示通过；解析失败必须抛协议错误。
- **VALIDATE**: `cd backend; python -m pytest tests/agents/test_generation_host_agent.py -v`

### ADD `backend/agents/generation/model_factory.py`

- **IMPLEMENT**: 从 `backend.util.common_util.llm_stream_utils.MODEL_CONFIGS` 与 `settings.get_llm_config()` 构造 DeepAgents 可用 chat model。
- **IMPORTS**: 优先使用 DeepAgents 官方推荐模型接口；若需要 OpenAI-compatible chat model，新增并使用 `langchain-openai` 的 `ChatOpenAI`。
- **GOTCHA**: 必须透传现有 `extra_body`，例如 DeepSeek disabled thinking 和 Qwen disabled thinking；超时复用 `LLM_STREAM_TIMEOUT_SECONDS`。
- **VALIDATE**: `cd backend; python -m pytest tests/util/test_llm_stream_utils.py tests/agents/test_generation_host_agent.py -v`

### ADD `backend/agents/generation/generate_agent_graph.py`

- **IMPLEMENT**: 创建 `StateGraph`，节点复用旧 generate prompt 输入并返回初稿文本；对外暴露已 `.compile()` 的 graph factory，供 `CompiledSubAgent` 包装。
- **PATTERN**: 复用 `generate_polished_text.py` 中 `render_generate_prompt()`、`GeneratePromptInput` 和 `stream_llm_completion()` 的 prompt 输入构造。
- **GOTCHA**: 不直接写 Word，不直接操作 SSE 终态；只产出文本。
- **VALIDATE**: `cd backend; python -m pytest tests/agents/test_generation_host_agent.py -v`

### ADD `backend/agents/generation/verify_agent_graph.py`

- **IMPLEMENT**: 创建 `StateGraph`，输入当前正文、招标类型、项目资料和技术参数，输出严格 JSON 数组。
- **PATTERN**: 批注 JSON 解析可参考 `generate_comments` 的严格机器契约思路，但本需求解析失败要硬失败。
- **GOTCHA**: 不允许把普通说明文本当成审核通过；只有合法空数组是通过。
- **VALIDATE**: `cd backend; python -m pytest tests/agents/test_generation_host_agent.py -v`

### ADD `backend/agents/generation/host_agent.py`

- **IMPLEMENT**: 使用 `create_deep_agent()` 创建 host agent，并注册 `generate_agent`、`verify_agent` 两个 `CompiledSubAgent`。
- **IMPLEMENT**: 执行循环：
  1. 生成初稿。
  2. 审核当前正文。
  3. 审核意见为空则输出最终 JSON。
  4. 审核意见非空则修复。
  5. 修复最多 3 轮。
  6. 第 3 轮修复后直接输出最终 JSON。
- **IMPLEMENT**: 提供 fake runner 注入点，便于测试不触发真实 LLM。
- **GOTCHA**: 模型不支持工具调用或 DeepAgents 报 tool-call 能力错误时，转成用户可理解的任务失败；不回退 workflow。
- **VALIDATE**: `cd backend; python -m pytest tests/agents/test_generation_host_agent.py -v`

### ADD `backend/nodes/common_word_nodes/host_agent_generate.py`

- **IMPLEMENT**: 新增 graph 节点 `host_agent_generate(state, config)`，读取 state 与 model_provider，调用 `host_agent`，返回 `TenderGraphStateBase(polished_text=..., generate_polished_done=True)`。
- **PATTERN**: 旧 `generate_polished_text()` 返回 state 只更新 `polished_text` 和 `generate_polished_done`。
- **GOTCHA**: 节点内部不要直接写 Word；不要绕开 graph 锁、取消检查和任务队列。
- **VALIDATE**: `cd backend; python -m pytest tests/graphs/test_generation_mode_branching.py -v`

### UPDATE `backend/graphs/base_graph.py`

- **IMPLEMENT**: 在 `StandardTenderWorkflowGraph` 增加 `NODE_HOST_AGENT_GENERATE` 类属性，默认指向新节点。
- **IMPLEMENT**: `build_graph()` 添加 `generation_mode_gate` 节点，并从 `["extract_tender_params", "comments_ready"]` 连到 gate；gate 条件分流到 `generate_polished_text` 或 `host_agent`。
- **IMPLEMENT**: `host_agent` 和 `generate_polished_text` 后续都接入现有 `_has_origin_for_comments` 分支。
- **IMPLEMENT**: `estimate_total_nodes()` 根据 `generation_mode` 统计 `host_agent` 或 `generate_polished_text`，并把 `host_agent` 加入 `TRACKED_PROGRESS_NODES` 和前端显示名。
- **PATTERN**: 当前 `word_operations_subgraph` 已用 compiled subgraph，新增 gate 保持基类统一接入。
- **GOTCHA**: 不要在各类型 graph 中复制分流逻辑。
- **VALIDATE**: `cd backend; python -m pytest tests/graphs/test_generation_mode_branching.py tests/graphs/test_gngk_tender_graph.py tests/graphs/test_gjgk_tender_graph.py -v`

### UPDATE graph 子类

- **IMPLEMENT**: 如果基类新增 `NODE_HOST_AGENT_GENERATE` 默认值，则子类无需改；仅在导入/类型检查需要时更新 `backend/graphs/__init__.py` 或相关 imports。
- **VALIDATE**: `cd backend; python -m pytest tests/graphs -v`

### UPDATE `backend/models/sse.py`

- **IMPLEMENT**: `SSEEventType` 新增 `AGENT_STEP = "agent_step"`。
- **IMPLEMENT**: 新增 `AgentStepEventData`，字段包含 `task_id`、`task_kind`、`step_type`、`round`、`node`、`content`、`findings`、`is_complete`、`timestamp`。
- **GOTCHA**: `step_type` 至少支持 `draft`、`audit`、`revision`；用户需求特别要求区分 `audit` 与 `revision`。
- **VALIDATE**: `cd backend; python -m pytest tests/api/test_generate_api.py tests/services/test_document_service_task_result.py -v`

### UPDATE `backend/services/document_service.py` 与 `backend/core/sse_manager.py`

- **IMPLEMENT**: `SSECallback` 增加 `push_agent_step()`；`sse_manager` 增加 `send_agent_step_threadsafe()` 和实际发送方法。
- **IMPLEMENT**: `host_agent` 通过 config 中的 callback 或专用 emitter 推送 `agent_step`。
- **PATTERN**: 参考 LLM relay 的 callback + manager 双写模式。
- **GOTCHA**: 确保事件缓冲支持断线重放；终态仍由 `done` / `error` 负责。
- **VALIDATE**: `cd backend; python -m pytest tests/services/test_document_service_task_result.py -v`

### UPDATE `backend/requirements.txt`

- **IMPLEMENT**: 增加 DeepAgents 依赖和必要 LangChain chat model adapter。
- **GOTCHA**: 文件保持 ASCII-only；注释也必须 ASCII。
- **VALIDATE**: `cd backend; .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt`（Windows PowerShell）或 `cd backend && python -m pip install -r requirements.txt`（当前环境可用时）

### UPDATE `frontend/types/api.ts`

- **IMPLEMENT**: 新增 `export type GenerationMode = 'workflow' | 'agent'`；`GenerateRequest` 增加 `generation_mode?: GenerationMode`；`SSEEventType` union 增加 `'agent_step'`；新增 `SSEAgentStepEvent`。
- **IMPLEMENT**: `NodeDisplayNames` 增加 `host_agent` 或实际节点名。
- **VALIDATE**: `cd frontend; npm run type-check`

### UPDATE `frontend/stores/chatStore.ts`

- **IMPLEMENT**: `ConversationFormDraft` 增加 `generation_mode?: GenerationMode`；`mergeConversationDraft()` 保持普通浅合并即可。
- **IMPLEMENT**: 新建会话默认 draft 使用 `generation_mode: 'workflow'`。
- **IMPLEMENT**: 如 agent step 需要持久化为任务消息组，扩展 `TaskMessageKind` 或 metadata，不破坏现有 `task-log` / `task-content` / `task-download`。
- **VALIDATE**: `cd frontend; npm run test -- __tests__/unit/stores/test_chat_store_conversation_scope.test.ts __tests__/unit/stores/test_chat_store_task_messages.test.ts`

### UPDATE `frontend/components/forms/TenderFormShared.tsx`

- **IMPLEMENT**: `BaseTenderFormData` 增加 `generation_mode`。
- **IMPLEMENT**: 初始化默认 `"workflow"`；高级设置新增“生成方式” segmented control。
- **IMPLEMENT**: `handleGenerationModeChange()` 写入草稿。
- **IMPLEMENT**: `handleSubmit()` 把当前 `generationMode` 写入 formData。
- **PATTERN**: 复用 `generationStyle` / `handleGenerationStyleChange()` 的结构。
- **GOTCHA**: `generation_mode` 是全局切换，不按 `gngk tender_lx` 分桶。
- **VALIDATE**: `cd frontend; npm run test -- __tests__/unit/components/forms/test_tender_form_shared.test.tsx`

### UPDATE `frontend/lib/formDataConverter.ts`

- **IMPLEMENT**: 三个 converter 都透传 `generation_mode: formData.generation_mode || 'workflow'`。
- **VALIDATE**: `cd frontend; npm run test -- __tests__/unit/lib/test_form_data_converter.test.ts`

### UPDATE `frontend/components/chat/FormPanel.tsx`

- **IMPLEMENT**: 现有 `conversation_id` 注入保持不变；确保转换后的 request 包含 `generation_mode` 后再提交 `createGenerateTask()`。
- **GOTCHA**: 不把 `generation_mode` 加入 edit/rewrite 创建请求。
- **VALIDATE**: `cd frontend; npm run test -- __tests__/unit/components/chat/test_form_panel.test.tsx`

### UPDATE `frontend/hooks/useChatSSE.ts`

- **IMPLEMENT**: 增加 `case 'agent_step'`，解析 audit / revision / draft。
- **IMPLEMENT**: audit 事件追加审核卡内容；revision 事件追加或更新对应轮次“AI 修改内容”卡；draft 事件保留初稿卡。
- **GOTCHA**: 不要让 `agent_step` 覆盖旧 `llm` 的 `aiText`，否则下载完成时内容快照可能错乱。
- **VALIDATE**: `cd frontend; npm run test -- __tests__/unit/hooks/test_use_chat_sse.test.tsx`

### UPDATE `frontend/stores/chatStreamStore.ts` and task message types

- **IMPLEMENT**: 如采用运行时 stream 缓存，增加 agent steps 缓存结构；如直接写入 chatStore 消息，则保持 stream store 只处理旧日志/AI 文本。
- **GOTCHA**: 任务完成后必须把 agent 卡落到会话历史，不依赖 `clearStream()` 后还存在运行时缓存。
- **VALIDATE**: `cd frontend; npm run test -- __tests__/unit/stores/test_chat_store_task_messages.test.ts`

### ADD or UPDATE task message UI components

- **IMPLEMENT**: 新增或扩展任务消息组件，展示：
  - 初稿生成卡
  - 审核内容卡，按轮次列出 `evidence` / `fix_hint`
  - 每轮“AI 修改内容”卡
- **PATTERN**: `TaskLogMessage`、`TaskContentMessage`、`TaskDownloadMessage` 已由 `MessageList` 按 `messageKind` 分发。
- **GOTCHA**: 文案要简洁，不展示实现说明或技术教程。
- **VALIDATE**: `cd frontend; npm run test -- __tests__/unit/components/chat/test_message_list.test.tsx __tests__/unit/components/chat/test_chat_panel.test.tsx`

### ADD `backend/tests/agents/test_generation_host_agent.py`

- **IMPLEMENT**: 使用 fake model / fake DeepAgents runner 覆盖：
  - agent 成功输出最终 `polished_text`
  - 审核 JSON 无法解析失败
  - 模型不支持工具调用失败
  - 第 3 轮修复后放行
  - 最终纯文本输出失败
- **VALIDATE**: `cd backend; python -m pytest tests/agents/test_generation_host_agent.py -v`

### ADD `backend/tests/graphs/test_generation_mode_branching.py`

- **IMPLEMENT**: 覆盖：
  - `workflow` 调用旧节点
  - `agent` 调用 `host_agent`
  - `xjcg` agent 分支产出 `polished_text`
  - `gngk_hw_zc` agent 分支产出 `polished_text`
  - `gngk_hw_cz` agent 分支产出 `polished_text`
  - `gngk_fw_zc` agent 分支产出 `polished_text`
  - `gjgk` agent 分支产出 `polished_text`
  - `gngk_fw_cz` 继承链路 smoke
- **VALIDATE**: `cd backend; python -m pytest tests/graphs/test_generation_mode_branching.py -v`

### ADD `frontend/e2e/test_generation_mode_agent.spec.ts`

- **IMPLEMENT**: route mock `POST /api/generate`、`GET /api/tasks/{task_id}`、`GET /api/stream/{task_id}` 或项目现有 SSE mock helper，模拟 agent step 序列。
- **ASSERT**:
  - 选择“智能体”
  - 提交生成
  - 初稿卡可见
  - 审核卡包含轮次、`evidence`、`fix_hint`
  - 修复卡可见
  - 下载入口可见
  - 无 console error
- **VALIDATE**: `cd frontend; npm run test:e2e -- e2e/test_generation_mode_agent.spec.ts`

### UPDATE `asset/shared_runtime_word_skill_knowledge_pack.md`

- **IMPLEMENT**: 实现完成后新增已落地事实：`generation_mode`、`host_agent`、agent step SSE、失败策略、验证入口。
- **GOTCHA**: 未实现前不要提前把目标写成事实。
- **VALIDATE**: `git diff --check`

### UPDATE `asset/tender_type_identity_session_knowledge_pack.md`

- **IMPLEMENT**: 记录 `generation_mode` 是当前页面 generate 草稿字段、默认 `"workflow"`、不影响 tender identity、rewrite/edit 不接收。
- **VALIDATE**: `git diff --check`

### UPDATE `asset/README.md`

- **IMPLEMENT**: 更新索引适用范围和回写路由。
- **VALIDATE**: `git diff --check`

---

## 测试策略

### 单元测试

- 后端模型：`GenerateRequest` 默认值、`agent` 值和非法值。
- 后端服务：初始 state 注入 `generation_mode`。
- DeepAgents runtime：fake runner 覆盖成功和失败策略。
- Graph 分支：fake 节点或 monkeypatch 验证 workflow / agent 路径。
- 前端类型/转换器：payload 透传。
- 前端表单：切换控件、草稿恢复、提交数据。
- 前端 store/SSE：agent step 卡片保留。

### 集成测试

- 后端 graph 差异覆盖：`xjcg`、`gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_zc`、`gjgk`。
- `gngk_fw_cz` 继承链路 smoke。
- API create task 接受新字段，默认旧字段兼容。

### E2E

- 使用 mock 任务与 SSE，不依赖真实 Word COM。
- 固化用户可见链路：“选择智能体 -> 初稿卡 -> 审核卡 -> 修复卡 -> 下载入口”。

### 边界情况

- 未传 `generation_mode`。
- 非法 `generation_mode`。
- agent 最终输出纯文本。
- verify 输出非法 JSON。
- verify 输出空数组。
- 第 1/2/3 轮修复。
- 第 3 轮后仍有审核意见。
- DeepAgents/tool-call 能力错误。
- SSE 断线重连后 agent step 重放。
- 任务失败后不会出现下载入口。

---

## 验证命令

### 级别 1：语法与风格

```powershell
git diff --check
cd frontend; npm run lint
cd frontend; npm run type-check
```

### 级别 2：后端单元与集成测试

```powershell
cd backend; python -m pytest tests/models/test_generate_request_generation_style.py -v
cd backend; python -m pytest tests/services/test_document_service_initial_state.py tests/services/test_document_service_task_result.py -v
cd backend; python -m pytest tests/agents/test_generation_host_agent.py -v
cd backend; python -m pytest tests/graphs/test_generation_mode_branching.py tests/graphs/test_gngk_tender_graph.py tests/graphs/test_gjgk_tender_graph.py -v
```

### 级别 3：前端单元测试

```powershell
cd frontend; npm run test -- __tests__/unit/lib/test_form_data_converter.test.ts
cd frontend; npm run test -- __tests__/unit/components/forms/test_tender_form_shared.test.tsx
cd frontend; npm run test -- __tests__/unit/components/chat/test_form_panel.test.tsx __tests__/unit/hooks/test_use_chat_sse.test.tsx
cd frontend; npm run test -- __tests__/unit/stores/test_chat_store_conversation_scope.test.ts __tests__/unit/stores/test_chat_store_task_messages.test.ts
```

### 级别 4：E2E

```powershell
cd frontend; npm run test:e2e -- e2e/test_generation_mode_agent.spec.ts
```

### 级别 5：完整回归

```powershell
cd backend; python -m pytest tests -v
cd frontend; npm run test
cd frontend; npm run test:e2e
```

---

## 验收标准

- [ ] 默认工作流模式完全沿用旧 `generate_polished_text` 路径。
- [ ] 智能体模式最终产出 `polished_text`，后续链路复用现有批注、样式、Word 写回和下载。
- [ ] 审核 JSON、最终 JSON、工具调用能力错误均有明确失败策略。
- [ ] 第 3 轮修复后直接放行。
- [ ] 后端和前端 SSE 类型同步，agent step 可断线重放。
- [ ] 前端高级设置、草稿持久化和 payload 透传可验证。
- [ ] 每个 Graph 差异类型都有独立闭环测试。
- [ ] mock E2E 覆盖用户可见智能体链路。
- [ ] 知识包已更新。

---

## 完成检查清单

- [ ] 所有任务均已按顺序完成。
- [ ] 每个任务的验证都已立即通过。
- [ ] 后端测试通过。
- [ ] 前端 lint/type-check/unit 测试通过。
- [ ] Playwright mock E2E 通过。
- [ ] 知识包与索引已按回写路由更新。
- [ ] 未修改 rewrite / edit 生成契约。
- [ ] 未绕开任务队列、Graph 锁、取消检查或 Word COM 写回主干。

---

## 备注

信心分数：8/10。主要风险集中在 DeepAgents 官方 API 与当前 OpenAI-compatible 模型配置的适配、`agent_step` 卡片持久化设计，以及 LangGraph 多输入汇合后条件分流的测试覆盖。先用 fake runner 固化协议，再接真实 DeepAgents，可降低实现不确定性。

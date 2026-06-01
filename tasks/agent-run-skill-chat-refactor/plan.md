# 功能: 任务上下文助手 Agent Run Skill Chat 重构

下面这份计划应尽可能完整，但在真正开始实现前，仍然必须再次验证 deepagents 官方文档、当前安装版本、代码库模式以及任务本身是否合理。

特别注意：本重构不能让 agent 直接操作 Word COM。agent run 只负责理解、追问和创建 task；真正写 Word 的动作仍必须由现有 task 队列、graph 锁、取消检查和 SSE 包装执行。

## 功能描述

把 TenderWord 右侧聊天入口重构为“任务上下文助手”。新的入口 `POST /api/agent/runs/stream` 使用 `create_deep_agent` 加载 `rewrite`、`edit` skills，并通过工具创建现有 rewrite/edit task。前端保留当前 UI 风格，增加 `/` skill picker、用户消息 capability chip 和结构化思考过程展示。新路径验证后删除旧 `/api/user/stream`、旧 user routing graph/service/prompt，以及旧 workflow 式 skill loader/registry/scripts。

## 用户故事

作为一名 TenderWord 使用者，我想在右侧输入框中选择 rewrite/edit 或直接用自然语言描述修改需求，以便系统在上下文足够时直接创建 Word 任务，在上下文不足时明确追问缺少什么。

## 问题陈述

当前 `backend/skills` 更像工作流插件注册表，右侧聊天入口通过旧 `/api/user/stream` 和 `UserGraph` 做普通回复/rewrite 判路。该路径无法自然承载多个 skill、显式选择、LLM 兜底路由、结构化思考过程和可回放的 harness 逻辑。edit 目前还是独立显式 API，用户希望最终右侧输入只保留一个 agent run 入口。

## 方案陈述

新增 agent run 层：一次用户消息触发一次 `agent_run`，agent run 负责加载 skills、检查受控上下文、输出结构化阶段事件、调用 `create_rewrite_task_tool` 或 `create_edit_task_tool`。工具只创建现有 task，task 继续负责 Word COM 队列、SSE、下载和取消。先用 fake runtime 打通新协议和前端展示，再接入 real deepagents rewrite，然后实现 edit，最后删除旧入口和旧 workflow skill 代码。

## 功能元数据

**功能类型**: 重构 + 新能力  
**预估复杂度**: 高  
**主要受影响系统**: 后端 FastAPI、DeepAgents runtime、DocumentService task 创建、backend/skills、前端 ChatPanel/ChatInput/MessageList/api/types、测试与 E2E  
**依赖项**: `deepagents>=0.6.4`、LangChain/LangGraph、现有 FastAPI StreamingResponse、现有任务队列与 SSE  

---

## 上下文参考

### 相关代码文件

- `backend/api/user.py` (lines 27-62) - 当前旧 `/api/user/stream` 请求模型和路由，最终要删除并由新 agent run 路由替代。
- `backend/graphs/user_graph.py` (lines 23-47, 55-154, 176-196) - 当前普通回复/rewrite 判路和 `task_accepted` NDJSON 事件，迁移时要提取可复用事件语义但删除旧 graph。
- `backend/services/user_routing_service.py` (lines 138-315) - 当前 LLM + deterministic rewrite 路由逻辑，新 guard 可参考其 has rewrite history 判定，但不要保留旧 service。
- `backend/services/document_service.py` (lines 470-541, 548-631, 1021-1248, 1439) - rewrite/edit task 创建、任务执行、agent step callback 和 Word COM 队列边界，新 tools 必须复用这里。
- `backend/services/conversation_service.py` (lines 38-111, 115-215) - 当前会话内 rewrite history 与 latest rewrite state，rewrite guard 需要读取这里。
- `backend/skills/rewrite/SKILL.md` - 当前 frontmatter 仍包含 `executor_kind`、`workflow_entry` 等旧字段，需要改成 deepagents skill guide。
- `backend/skills/edit/SKILL.md` - 当前 edit skill 仍描述旧 workflow 执行，需要改成 deepagents skill guide。
- `backend/skills/loader.py`, `backend/skills/registry.py`, `backend/skills/types.py` - 旧自定义 skill registry，验证新路径后删除。
- `backend/skills/rewrite/scripts/workflow.py`, `backend/skills/edit/scripts/workflow.py` - 旧 workflow 入口，验证新 path 后删除。
- `frontend/lib/api.ts` (lines 187-239, 411-419, 636) - 当前 user stream 解析、`streamUserMessage` 和 `createEditTask`，要新增 `streamAgentRun` 并删除旧调用。
- `frontend/types/api.ts` (lines 358-396, 584) - 当前 user stream event union 和任务 SSE 类型，新 agent run 类型需同步。
- `frontend/components/chat/ChatPanel.tsx` (lines 182-220, 484-576, 692-720, 1162-1188) - 当前右侧输入流式调用、task accepted、edit 直接创建任务和 ChatInput 接线，重构主入口。
- `frontend/components/chat/ChatInput.tsx` (lines 45-120, 230-387) - 当前输入框、模型选择、上传文件修改按钮，新增 `/` skill picker 与 `$skill` 解析。
- `frontend/components/chat/MessageList.tsx` (lines 279-293) - 当前消息类型到组件映射，新增/复用 agent run 思考过程展示。
- `frontend/components/chat/TaskLogMessage.tsx`, `TaskContentMessage.tsx`, `TaskDownloadMessage.tsx` - 现有任务卡和任务进度展示，agent `task_accepted` 后继续使用这些组件。
- `frontend/stores/chatStore.ts` (lines 915-1963) - 当前 task message 创建、会话状态和任务卡状态，需新增 selected skill/capability 与 agent run 消息状态。

### DsAgent 参考文件

- `D:\AgentProject\DsAgent\backend\app\agent\factory.py` (lines 23-29, 59, 211-294) - `create_deep_agent`、`FilesystemBackend(virtual_mode=True)`、`CompositeBackend`、skills mount 的参考实现。
- `D:\AgentProject\DsAgent\backend\app\harness\run_controller.py` (lines 75-202, 494-666) - run lifecycle、selected skills、runtime stream、tool retry 和终态收敛的参考，不复制数据库历史。
- `D:\AgentProject\DsAgent\backend\app\runtime\deepagents.py` (lines 35-49) - runtime build graph / stream events 的薄封装参考。
- `D:\AgentProject\DsAgent\backend\app\streaming\event_converter.py` (lines 41-105, 131-156, 191-214) - 将 runtime events 转为 UI 友好 live metadata 的参考；TenderWord 不展示原始 reasoning。
- `D:\AgentProject\DsAgent\frontend\components\chat\ChatComposer.tsx` (lines 236-263, 385-456) - `/` skill picker、selected skill shelf、前缀解析和选项过滤的交互参考。
- `D:\AgentProject\DsAgent\frontend\components\chat\TaskConversation.tsx` (lines 92-100, 184-230) - 用户消息 capability copy text 与附件展示参考。
- `D:\AgentProject\DsAgent\frontend\app\thinking-process-view.ts` 和 `frontend\app\globals.css` 中 `.thinkingProcess*` / `.thinkingStage*` - 思考过程 stage tree 的数据投影与视觉参考，只借鉴逻辑，不复制 UI 风格。

### 相关文档

- [DeepAgents Customization](https://docs.langchain.com/oss/python/deepagents/customization) - `create_deep_agent` 参数、tools、instructions、subagents、backend 等定制入口。
- [DeepAgents Skills](https://docs.langchain.com/oss/python/deepagents/skills) - skill 目录、`SKILL.md` 描述、按需加载和 builtin skill loading 机制。
- [DeepAgents Backends](https://docs.langchain.com/oss/python/deepagents/backends) - `FilesystemBackend`、`StateBackend`、`CompositeBackend`、`virtual_mode=True` 的隔离语义。
- [DeepAgents Event Streaming](https://docs.langchain.com/oss/python/deepagents/event-streaming) - runtime event stream 与工具/模型事件处理参考。
- `ARCHITECTURE.md` (lines 168-180) - 当前 user stream 和 edit 边界，实施后需要更新。
- `INTERFACES.md` (lines 52-86, 98-119) - 当前任务 SSE、user stream、edit 接口契约，实施后需要更新。
- `coding_maps/SYSTEM_MAP.md` (lines 43-45, 71-80, 170-176) - 当前系统地图中的 user stream / skill runtime / SSE 同步面，实施后需要更新。

### 需要创建的新文件

- `backend/api/agent_runs.py` - 新 `/api/agent/runs/stream` 路由。
- `backend/models/agent_run.py` - agent run 请求、事件、阶段、context snapshot 类型。
- `backend/services/agent_run_service.py` - agent run 编排、fake/real runtime 选择、guard 入口、日志写入。
- `backend/agents/task_context_assistant/factory.py` - `create_deep_agent` 工厂、backend/skills mount。
- `backend/agents/task_context_assistant/runtime.py` - real deepagents runtime 与 fake runtime 协议适配。
- `backend/agents/task_context_assistant/tools.py` - `create_rewrite_task_tool`、`create_edit_task_tool` 和受控上下文读取工具。
- `backend/agents/task_context_assistant/guards.py` - rewrite/edit deterministic precondition guard。
- `backend/agents/task_context_assistant/logging.py` - JSONL audit writer 与敏感凭证/路径 scrubber。
- `frontend/components/chat/SkillPicker.tsx` - TenderWord 风格的 `/` skill picker。
- `frontend/components/chat/AgentThinkingMessage.tsx` - agent run 结构化思考过程卡。
- `frontend/lib/agent-run-utils.ts` - `$skill` 解析、capability copy text、stage merge helper。
- `backend/tests/api/test_agent_runs_api.py`, `backend/tests/agents/test_task_context_assistant_*.py` - 后端测试。
- `frontend/__tests__/unit/lib/test_agent_run_utils.test.ts`, `frontend/__tests__/unit/components/chat/test_skill_picker.test.tsx`, `frontend/__tests__/unit/components/chat/test_agent_thinking_message.test.tsx` - 前端单测。
- `frontend/e2e/test_agent_run_skill_chat.spec.ts` - fake runtime 浏览器闭环。

### 需要遵循的模式

**API client 模式：** 前端请求统一走 `frontend/lib/api.ts`，组件不写裸 `fetch`。新 `streamAgentRun` 应复用现有 streaming parser 风格并更新测试。

**任务边界：** 新 tools 只调用 `DocumentService.create_rewrite_task` / `create_edit_task`。不得在 API route、service、tool 或前端直接操作 Word COM。

**SSE/流式事件同步：** 新 agent run 是 POST streaming NDJSON；task 仍走现有 task SSE。若新增事件类型，必须同步后端模型、前端 union、解析、store、组件和测试。

**日志模式：** 用户可读进度仍属于任务 `progress_log`；agent run JSONL 是 debug/audit，不参与 UI 恢复，不写访问凭证、私有路径、客户原文或堆栈。

**前端状态：** 页面刷新后的当前 conversation 恢复继续由现有前端 store/sessionStorage 负责；后端 logs 不作为恢复来源。

---

## 实现计划

### 阶段 1：Agent run fake 闭环

- 定义 `AgentRunStreamRequest`、`AgentRunEvent`、`AgentThinkingStage`、`AgentRunContextSnapshot`。
- 新增 `/api/agent/runs/stream`，先接 fake runtime。
- fake runtime 输出成功、needs_input、error 三类路径。
- 前端新增 `streamAgentRun`，`ChatPanel` 初步接入新事件。
- Playwright 用 fake runtime 验证 `/rewrite` 到 `task_accepted` 的可视闭环。

### 阶段 2：显式 skill UI 与思考过程

- 在 `ChatInput` 或新 `SkillPicker` 中实现 `/` 选项、`$rewrite`/`$edit` 解析。
- 在 chat store/message type 中保存 `capabilities` / `selectedSkills`。
- 用户气泡显示 capability chip，复制文本恢复 `$skill 指令`。
- 新增 agent thinking message，展示阶段树并与 task accepted 事件衔接。

### 阶段 3：DeepAgents runtime 与 rewrite

- 新增 DeepAgents 工厂，采用隔离 backend 和受控 skills mount。
- 将 `rewrite/SKILL.md` 改为 skill guide。
- 实现 rewrite guard 和 `create_rewrite_task_tool`。
- 接入 `ConversationService` 的 rewrite history 检查。
- 写入 agent run JSONL，并提供只读当前 conversation 上下文工具。
- 后端测试覆盖 rewrite 成功、缺上下文、工具异常。

### 阶段 4：Edit skill 与上传入口

- 将 `edit/SKILL.md` 改为 skill guide。
- 实现 edit guard 和 `create_edit_task_tool`。
- 保留现有上传文件修改按钮，将上传文件上下文纳入 agent run snapshot。
- `/edit` 缺文件时追问，有文件和上下文时创建 edit task。
- 前端和后端测试覆盖 edit 缺条件与成功创建 fake/real tool 路径。

### 阶段 5：删除旧入口与旧 workflow

- 删除前端 `streamUserMessage`、旧 `UserStream*` 类型和旧测试分支。
- 删除后端 `/api/user/stream`、`UserGraph`、`user_routing_service`、仅服务旧 user stream 的 routing prompt。
- 删除旧自定义 skill registry/loader/types 和 `backend/skills/*/scripts/workflow.py`。
- 更新 `ARCHITECTURE.md`、`INTERFACES.md`、`coding_maps/SYSTEM_MAP.md` 和相关 `asset/` 知识包。
- 跑后端 pytest、前端 lint/typecheck/Jest 和相关 Playwright。

---

## 分步任务

### CREATE `backend/models/agent_run.py`

- **IMPLEMENT**: 定义请求/事件模型，包括 `conversation_id`、`message`、`model`、`selected_skills`、`context_snapshot`、`run_id`、`event`、`stage`、`tool_name`、`task_id`、`message_delta`、`final_message`、`error`。
- **PATTERN**: 参考 `frontend/types/api.ts` 当前 user stream event union 和 `backend/models/sse.py` 的 typed event 思路。
- **GOTCHA**: context snapshot 只允许最小字段，不接收完整客户原文、访问凭证、绝对私有路径。
- **VALIDATE**: `python -m pytest backend/tests/models -v`。

### CREATE `backend/api/agent_runs.py`

- **IMPLEMENT**: 新增 `POST /api/agent/runs/stream`，返回 `StreamingResponse`，格式沿用 NDJSON line，终态必须为 `done`、`needs_input` 或 `error`。
- **PATTERN**: 参考 `backend/api/user.py` 的 streaming route，但依赖新 `AgentRunService` 而不是 `UserGraph`。
- **GOTCHA**: 不在 route 中创建 Word COM，不在 route 中写复杂业务逻辑。
- **VALIDATE**: `python -m pytest backend/tests/api/test_agent_runs_api.py -v`。

### CREATE `backend/services/agent_run_service.py`

- **IMPLEMENT**: 统一 fake/real runtime 调用、run_id 生成、selected skills 标准化、guard 调用、JSONL 日志写入和 NDJSON event 输出。
- **PATTERN**: 参考 DsAgent `run_controller.py` 的 run lifecycle，但不复制数据库 repository/history。
- **GOTCHA**: agent run 结束不代表 Word task 完成；task accepted 后必须结束本 run。
- **VALIDATE**: `python -m pytest backend/tests/agents/test_task_context_assistant_runtime.py -v`。

### CREATE `backend/agents/task_context_assistant/factory.py`

- **IMPLEMENT**: 调用 `create_deep_agent`，传入 tools、instructions、skills、backend；backend 使用 virtual filesystem，skills 只读受控路径。
- **PATTERN**: 参考 DsAgent `factory.py` 的 `CompositeBackend`、`StateBackend`、`FilesystemBackend(root_dir=..., virtual_mode=True)`。
- **GOTCHA**: 不要 bare mount `backend/logs` 或项目根目录；不要让 agent 读取 `.env`。
- **VALIDATE**: `python -m pytest backend/tests/agents/test_task_context_assistant_factory.py -v`。

### CREATE `backend/agents/task_context_assistant/tools.py`

- **IMPLEMENT**: 提供 `create_rewrite_task_tool`、`create_edit_task_tool`、`read_current_conversation_summary_tool`、`read_current_task_public_summary_tool`。
- **PATTERN**: `DocumentService.create_rewrite_task` / `create_edit_task` 是唯一任务创建入口。
- **GOTCHA**: tool 返回值要适合 agent 和 UI：成功返回 task_id/task_kind，失败返回 guard/error，不泄露堆栈。
- **VALIDATE**: `python -m pytest backend/tests/agents/test_task_context_assistant_tools.py -v`。

### CREATE `backend/agents/task_context_assistant/guards.py`

- **IMPLEMENT**: rewrite guard 校验 rewrite history；edit guard 校验上传文件、锚点、form type、draft 字段；能力问答或模糊意图不创建任务。
- **PATTERN**: 可参考 `user_routing_service.py` 的 `has_rewrite_history` 判定，但 guard 应独立于旧 routing service。
- **GOTCHA**: 显式 `/rewrite`、`/edit` 也必须过 guard。
- **VALIDATE**: `python -m pytest backend/tests/agents/test_task_context_assistant_guards.py -v`。

### UPDATE `backend/skills/rewrite/SKILL.md`

- **IMPLEMENT**: 删除旧 frontmatter 中 `executor_kind`、`workflow_entry` 等 workflow 字段，改为 deepagents skill guide：适用场景、前置条件、缺失信息、工具调用、禁止事项。
- **PATTERN**: 官方 DeepAgents Skills 文档要求 `SKILL.md` 描述触发和执行指南。
- **GOTCHA**: skill 文档不应要求 agent 直接生成完整正文或调用旧 workflow。
- **VALIDATE**: `rg -n "workflow_entry|executor_kind|scripts.workflow" backend/skills/rewrite/SKILL.md` 应无结果。

### UPDATE `backend/skills/edit/SKILL.md`

- **IMPLEMENT**: 改为 deepagents skill guide，突出上传 Word 文件、锚点上下文、form type/draft 前置条件和 `create_edit_task_tool`。
- **PATTERN**: 与 rewrite skill guide 保持结构一致。
- **GOTCHA**: edit 是显式入口语义，但现在由 agent run tool 创建 task，不再由 `ChatPanel` 直接 `createEditTask`。
- **VALIDATE**: `rg -n "workflow_entry|executor_kind|scripts.workflow" backend/skills/edit/SKILL.md` 应无结果。

### UPDATE `frontend/lib/api.ts` and `frontend/types/api.ts`

- **IMPLEMENT**: 新增 agent run 请求/事件类型和 `streamAgentRun`；删除旧 `streamUserMessage` 及旧 user stream event parser。
- **PATTERN**: 复用当前 stream parser、错误处理和 API base URL helper。
- **GOTCHA**: 前端不写裸 fetch；所有调用统一从 API client 发出。
- **VALIDATE**: `npm run type-check`、`npm run test -- frontend/__tests__/unit/lib/test_api.test.ts`。

### UPDATE `frontend/components/chat/ChatInput.tsx`

- **IMPLEMENT**: 增加 `/` skill picker、`$skill` 前缀解析、selected skills 输出；保留模型选择、上传文件修改和发送/取消。
- **PATTERN**: 参考 DsAgent `ChatComposer.tsx` 的解析和选项过滤，UI 使用 TenderWord 当前组件风格。
- **GOTCHA**: 文本不能挤压按钮或在移动端溢出；不要复制 DsAgent 视觉风格。
- **VALIDATE**: `npm run test -- frontend/__tests__/unit/components/chat/test_chat_input.test.tsx`。

### UPDATE `frontend/components/chat/ChatPanel.tsx`

- **IMPLEMENT**: 右侧发送路径调用 `streamAgentRun`；处理 `run_started`、`thinking_stage`、`tool_call`、`task_accepted`、`needs_input`、`done`、`error`；删除旧 route/rewrite 分支和直接 edit 创建路径。
- **PATTERN**: 当前 `task_accepted` 已能转成任务卡，可复用 store 的 `ensureTaskLogMessage` / `ensureTaskContentMessage`。
- **GOTCHA**: task accepted 后不要等待 Word 任务完成；由现有 task SSE 接管。
- **VALIDATE**: `npm run test -- frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。

### CREATE `frontend/components/chat/AgentThinkingMessage.tsx`

- **IMPLEMENT**: 展示结构化阶段树，支持 running/completed/needs_input/error 状态。
- **PATTERN**: 参考 DsAgent thinking process view 的数据投影，但视觉遵循 TenderWord。
- **GOTCHA**: 不展示 `reasoning_content`；长工具参数要截断或只展示 tool label。
- **VALIDATE**: `npm run test -- frontend/__tests__/unit/components/chat/test_agent_thinking_message.test.tsx`。

### UPDATE stores and message types

- **IMPLEMENT**: 在 chat message 中加入 capabilities、agentRunId、thinkingStages；实现 copy text 恢复 `$skill 指令`。
- **PATTERN**: 参考当前 task message lifecycle 和 DsAgent `buildUserCopyText`。
- **GOTCHA**: 页面刷新恢复仍由前端本地状态承担，不能调用 backend logs 恢复。
- **VALIDATE**: `npm run test -- frontend/__tests__/unit/stores/test_chat_store_task_messages.test.ts`。

### REMOVE old backend user stream and skill workflow

- **IMPLEMENT**: 删除旧 route 注册、旧 graph/state/service/prompt、旧 skill registry/loader/types、旧 `scripts/workflow.py`。
- **PATTERN**: 每删除一个模块，立即用 `rg` 确认无引用。
- **GOTCHA**: 如果 `SkillGraph` 或 `nodes/skills_nodes/*` 仍被 DocumentService task 执行需要，先保留并在新 tool path 等价后再移除；不要提前删掉 task 执行仍依赖的节点。
- **VALIDATE**: `rg -n "/api/user/stream|streamUserMessage|UserGraph|user_routing_service|workflow_entry" backend frontend` 应无运行时引用。

### UPDATE documentation and asset knowledge

- **IMPLEMENT**: 更新 `ARCHITECTURE.md`、`INTERFACES.md`、`coding_maps/SYSTEM_MAP.md`，必要时更新相关 `asset/` 知识包。
- **PATTERN**: 只记录当前仍成立的边界、同步面、验证入口和回归风险。
- **GOTCHA**: 文档不能写入访问凭证、客户原文、私有路径。
- **VALIDATE**: `git diff --check` 和敏感凭证扫描。

---

## 测试策略

### 单元测试

- 后端：agent run request/event model、guard、tools、factory backend isolation、JSONL scrubber、API streaming fake runtime。
- 前端：API parser、skill picker、`$skill` parser、capability chip/copy text、thinking message、ChatPanel event reducer。

### 集成测试

- 后端 fake runtime：`/api/agent/runs/stream` 输出完整事件序列。
- 后端 real rewrite tool：mock `DocumentService.create_rewrite_task`，验证有 history 创建任务、无 history 追问。
- 后端 edit tool：mock upload/context，验证缺文件追问、有文件创建任务。
- 前端 + MSW/Jest：ChatPanel 接收 fake stream 后创建思考过程和任务卡。

### 浏览器测试

- Playwright 打开 `/tender`，输入 `/` 选择 rewrite，发送 fake 消息，确认 capability chip、thinking stage、task accepted 卡出现。
- Playwright 输入 `$edit 修改技术参数` 且无上传文件，确认出现上传文件追问。
- Playwright 上传或模拟 edit 文件上下文后发送 edit fake 消息，确认创建 task accepted。

### 边界情况

- 显式 skill 与自然语言路由冲突时，以显式 skill 为准但仍执行 guard。
- 无 rewrite history 时不得创建 rewrite task。
- 无 edit file 时不得创建 edit task。
- 模糊能力问题不得自动创建 task。
- agent tool 抛错时必须输出 error 终态，前端不能卡住。
- task accepted 后 agent run 已结束，任务 SSE 继续运行。
- 后端重启不尝试从 logs 恢复 UI。

---

## 验证命令

### 级别 1：语法与风格

```powershell
cd frontend
npm run lint
npm run type-check
```

### 级别 2：前端单元测试

```powershell
cd frontend
npm run test -- frontend/__tests__/unit/lib/test_api.test.ts frontend/__tests__/unit/components/chat/test_chat_input.test.tsx frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx
```

### 级别 3：后端单元与集成测试

```powershell
python -m pytest backend/tests -v
```

### 级别 4：浏览器验证

```powershell
cd frontend
npm run test:e2e -- frontend/e2e/test_agent_run_skill_chat.spec.ts
```

### 级别 5：清理验证

```powershell
rg -n "/api/user/stream|streamUserMessage|UserGraph|user_routing_service|workflow_entry|scripts.workflow" backend frontend
git diff --check
$patterns = @('api[_-]?key', 'sec' + 'ret', 'tok' + 'en', 'author' + 'ization', 'bear' + 'er', 'pass' + 'word', 'AK' + 'IA', 'sk-' + '[A-Za-z0-9]')
rg -n ($patterns -join '|') tasks/agent-run-skill-chat-refactor
```

---

## 验收标准

- [ ] 右侧输入只调用 `/api/agent/runs/stream`。
- [ ] rewrite 和 edit 都通过 deepagents skill guide + tool 创建现有 task。
- [ ] 显式 skill 优先，LLM 自动路由兜底，deterministic guard 负责最终任务门禁。
- [ ] 前端可展示 skill picker、capability chip、thinking stage 和 task accepted 后的现有任务卡。
- [ ] 旧 `/api/user/stream`、旧 user routing 和旧 workflow skill 入口删除且无引用。
- [ ] 后端 pytest、前端 lint/typecheck/Jest、相关 Playwright 通过。
- [ ] 文档和知识包同步更新。

## 完成检查清单

- [ ] 所有 story 按 rewrite 先、edit 后、清理最后的顺序完成。
- [ ] 每个 story 都有对应测试或浏览器验证。
- [ ] 新增日志经过敏感凭证/路径 scrubber。
- [ ] Word COM 仍只由 task 队列执行。
- [ ] fake runtime 可在无真实 LLM/Word COM 环境下跑通。
- [ ] 旧入口删除后没有隐式回退路径。

## 备注

推荐先做 fake 闭环，因为它把 API shape、前端 store、skill picker 和思考过程一次性固定下来，后续接 real deepagents rewrite/edit 时失败面更小。信心分数：8/10。主要风险是旧 `SkillGraph` 与 `DocumentService` 的依赖关系可能比表面更深；删除旧 workflow 前必须用测试证明新 tool path 已覆盖 rewrite/edit 任务创建和执行所需入口。

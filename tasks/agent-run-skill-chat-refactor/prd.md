# PRD: 任务上下文助手 Agent Run Skill Chat 重构

## Introduction

本需求将 TenderWord 右侧聊天入口重构为“任务上下文助手”。它使用 `create_deep_agent` 加载 `rewrite` 和 `edit` skills，负责理解用户消息、展示结构化思考过程、检查任务前置条件，并在条件满足时创建现有 Word COM 队列任务。旧 `/api/user/stream` 与工作流式 skill 调用逻辑将在新路径验证后删除。

## Goals

- 将右侧输入入口统一到 `POST /api/agent/runs/stream`。
- 让 rewrite/edit 以 deepagents skill guide + tool 的方式被 agent 调用，而不是旧 workflow graph 包装。
- 显式 skill 选择优先，LLM 自动路由兜底，确定性 guard 负责最终任务创建门禁。
- 保留现有 task 队列、Word COM 锁、任务 SSE、下载和取消机制。
- 前端在当前 TenderWord UI 风格下展示 skill picker、用户消息 capability chip 和结构化思考过程。
- 先实现 rewrite 闭环，再实现 edit 闭环，最后删除旧入口和旧代码。

## User Stories

### US-001: 新建 agent run 流式入口的 fake 闭环
**描述：** 作为开发者，我想先用 fake runtime 打通 `/api/agent/runs/stream`，以便在不依赖真实 LLM 和 Word COM 的情况下验证新协议。

**Acceptance Criteria：**
- [ ] `POST /api/agent/runs/stream` 接收 `conversation_id`、`message`、`model`、`selected_skills` 和受控上下文快照。
- [ ] fake runtime 能按顺序输出 `run_started`、`thinking_stage`、`tool_call`、`task_accepted`、`done` 或 `needs_input` 事件。
- [ ] fake `task_accepted` 返回的 `task_id` 可被前端映射到现有任务卡。
- [ ] 后端单元测试验证成功路径、缺条件追问路径和错误终态。
- [ ] Typecheck 通过。

### US-002: 前端 API client 切到 agent run stream
**描述：** 作为用户，我想右侧输入框只走新的 agent run 入口，以便聊天决策和任务创建都使用同一协议。

**Acceptance Criteria：**
- [ ] `frontend/lib/api.ts` 新增 `streamAgentRun` 并解析 agent run 事件。
- [ ] `ChatPanel` 发送右侧消息时调用 `/api/agent/runs/stream`，不再调用 `/api/user/stream`。
- [ ] 本地 fake stream 成功响应后，页面出现 assistant 回复或任务卡。
- [ ] 失败响应在聊天区显示明确错误消息。
- [ ] 使用 Playwright 打开 `/tender`，发送一条 fake rewrite 消息，确认前端请求真实到达新接口且无控制台错误。
- [ ] Typecheck 通过。

### US-003: `/` skill picker 与显式 skill 选择
**描述：** 作为用户，我想在输入框输入 `/` 后看到 rewrite/edit 选项，以便明确告诉助手要执行哪类任务。

**Acceptance Criteria：**
- [ ] `ChatInput` 输入 `/` 时展示 `rewrite`、`edit` 两个 skill 选项。
- [ ] 选择 skill 后，输入框正文不保留 `/rewrite` 或 `$rewrite` 前缀，`selected_skills` 单独保存。
- [ ] 支持 `$rewrite ...` 和 `$edit ...` 前缀自动转成显式选择。
- [ ] 现有模型选择、发送、取消、上传按钮仍可用。
- [ ] 使用 Playwright 打开 `/tender`，输入 `/` 并选择 rewrite，确认选中态可见且发送 payload 包含 `selected_skills=["rewrite"]`。
- [ ] Typecheck 通过。

### US-004: 用户消息 capability chip 与复制行为
**描述：** 作为用户，我想在自己发送的消息上看到已调用的 skill 标记，以便回放时知道这次消息触发了什么能力。

**Acceptance Criteria：**
- [ ] 用户消息气泡显示 capability chip，例如 `rewrite` 或 `edit`。
- [ ] 消息正文不显示 `$rewrite`、`[$rewrite]` 或 `/rewrite` 前缀。
- [ ] 复制用户消息时恢复为 `$rewrite 用户原始指令` 或 `$edit 用户原始指令`。
- [ ] 未选择 skill 的普通消息不显示 capability chip。
- [ ] 使用 Playwright 发送 `$rewrite 改写第三包`，确认气泡显示 chip，正文只显示“改写第三包”，复制文本包含 `$rewrite 改写第三包`。
- [ ] Typecheck 通过。

### US-005: 结构化思考过程卡
**描述：** 作为用户，我想看到 agent run 的阶段化进度，而不是只看到最终回复，以便理解系统正在检查上下文还是创建任务。

**Acceptance Criteria：**
- [ ] 前端可展示 `理解需求`、`执行任务`、`调用工具`、`异常与重试`、`汇总结论` 阶段。
- [ ] 思考过程只展示结构化摘要、工具名、guard 决策和结果，不展示原始 `reasoning_content`。
- [ ] `task_accepted` 事件后，思考过程终态显示已创建任务，并由现有任务卡继续展示 Word COM 任务进度。
- [ ] 使用 Playwright 触发 fake agent run，确认思考过程卡出现、阶段更新、最终收敛为完成状态且无控制台错误。
- [ ] Typecheck 通过。

### US-006: DeepAgents 工厂与隔离文件系统后端
**描述：** 作为开发者，我想用 `create_deep_agent` 创建任务上下文助手，并隔离 agent 可访问文件系统，以便安全加载 skills 和临时上下文。

**Acceptance Criteria：**
- [ ] 后端新增 agent 工厂，调用 `create_deep_agent` 并传入 tools、skills、backend 等参数。
- [ ] backend 使用隔离的 `FilesystemBackend(virtual_mode=True)`，并通过 `CompositeBackend` 或等价结构区分 scratch、skills 和运行工作区。
- [ ] skills 来源只暴露 `backend/skills/rewrite/SKILL.md` 与 `backend/skills/edit/SKILL.md` 所在受控路径。
- [ ] agent 不能直接读取 `.env`、私有模板路径、全局日志目录或任意本机文件。
- [ ] 单元测试验证 skill mount 路径、virtual backend 配置和拒绝越权路径。
- [ ] Typecheck 通过。

### US-007: Rewrite skill guide 与任务创建 tool
**描述：** 作为用户，我想在已有文档上下文时让助手直接创建 rewrite 任务，以便继续修改已生成内容。

**Acceptance Criteria：**
- [ ] `backend/skills/rewrite/SKILL.md` 改为 deepagents skill guide，说明适用场景、前置条件、缺失信息追问和 `create_rewrite_task_tool` 调用方式。
- [ ] `create_rewrite_task_tool` 复用 `DocumentService.create_rewrite_task`，不直接操作 Word COM。
- [ ] 有 rewrite history 时，显式 `/rewrite` 或 `$rewrite` 创建 rewrite task 并返回 `task_accepted`。
- [ ] 无 rewrite history 时，guard 返回 `needs_input`，不创建 task。
- [ ] 后端测试覆盖有上下文创建任务、无上下文追问、工具异常收敛为错误事件。
- [ ] Typecheck 通过。

### US-008: Agent run JSONL 日志与受控上下文读取
**描述：** 作为开发者，我想把 agent run 的关键事件写入 debug 日志，并给 agent 只读受控上下文工具，以便排障和任务执行时查阅当前会话信息。

**Acceptance Criteria：**
- [ ] 每次 agent run 写入 `backend/logs/agent-run-<id>.jsonl` 或等价命名的结构化日志。
- [ ] 日志包含 run_id、conversation_id、selected_skills、阶段摘要、工具名、guard 结果和 task_id，不包含访问凭证、完整客户原文、`.env`、私有绝对路径或堆栈明细。
- [ ] agent 只能通过受控工具读取当前 `conversation_id` 的 agent run 摘要和当前 task 公共摘要。
- [ ] 后端重启后不依赖这些日志恢复 UI 状态。
- [ ] 测试或脚本扫描证明日志样例不包含常见敏感凭证模式。
- [ ] Typecheck 通过。

### US-009: Edit skill guide、上传入口与任务创建 tool
**描述：** 作为用户，我想通过 `/edit` 或上传文件修改入口创建 edit 任务，以便修改指定 Word 文件的锚点区正文。

**Acceptance Criteria：**
- [ ] `backend/skills/edit/SKILL.md` 改为 deepagents skill guide，说明上传 Word 文件、锚点、form type 和 draft 字段等前置条件。
- [ ] `create_edit_task_tool` 复用 `DocumentService.create_edit_task`，不直接操作 Word COM。
- [ ] 有上传 Word 文件和必要表单上下文时，显式 `/edit` 或 `$edit` 创建 edit task 并返回 `task_accepted`。
- [ ] 缺上传文件、缺锚点或缺必要 form type/draft 字段时返回明确追问，不创建 task。
- [ ] 现有“上传文件修改”按钮保留，并把上传文件上下文传给 agent run。
- [ ] Typecheck 通过。

### US-010: 删除前端旧 user stream 调用
**描述：** 作为开发者，我想移除前端对旧 `/api/user/stream` 的依赖，以便右侧输入只有一个可维护入口。

**Acceptance Criteria：**
- [ ] `streamUserMessage`、`UserStreamRequest`、旧 `UserStreamEvent` 和相关测试替换为 agent run 类型。
- [ ] 仓库前端代码中不再出现对 `/api/user/stream` 的运行时请求。
- [ ] `ChatPanel` 中旧 reply/rewrite route 分支被 agent run 事件处理替代。
- [ ] 前端单元测试覆盖普通回复、needs_input、task_accepted 和 error。
- [ ] `npm run lint`、`npm run type-check` 和相关 Jest 测试通过。

### US-011: 删除后端旧 user routing 和旧 workflow skill 代码
**描述：** 作为开发者，我想删除新路径不再使用的旧代码，以便避免两套判路和两套 skill 定义长期并存。

**Acceptance Criteria：**
- [ ] 删除 `backend/api/user.py` 路由注册和 `/api/user/stream`。
- [ ] 删除 `backend/graphs/user_graph.py`、`backend/states/user_state.py`、`backend/services/user_routing_service.py` 及仅服务旧 user stream 的 routing prompt。
- [ ] 删除旧自定义 `backend/skills/loader.py`、`registry.py`、`types.py`，以及 `backend/skills/rewrite/scripts/workflow.py`、`backend/skills/edit/scripts/workflow.py`。
- [ ] 保留仍被新工具路径或现有 task skill graph 必须使用的代码，只有在替代路径测试通过后再删除。
- [ ] 后端 import、路由注册和测试不再引用已删除模块。
- [ ] `python -m pytest backend/tests -v` 通过。

### US-012: Rewrite 到 edit 的端到端回归验证
**描述：** 作为用户，我想确认 rewrite 和 edit 都能从右侧输入创建任务，并且旧任务执行展示不回归。

**Acceptance Criteria：**
- [ ] 使用 fake runtime 验证 `/rewrite` 创建 task accepted 后，现有任务卡进入生成态。
- [ ] 使用 fake runtime 验证 `/edit` 缺文件时显示追问，上传文件后创建 task accepted。
- [ ] 任务 SSE、下载卡、取消按钮和现有生成任务展示无回归。
- [ ] 使用 Playwright 打开 `/tender` 完成 rewrite fake 闭环和 edit 缺文件追问闭环，页面无控制台错误。
- [ ] 后端 pytest、前端 lint/typecheck/Jest 和相关 Playwright 测试通过。

## Functional Requirements

- FR-1: 系统必须提供 `POST /api/agent/runs/stream` 作为右侧输入唯一流式入口。
- FR-2: agent run 请求必须包含 `conversation_id`、`message`、`model`、`selected_skills` 和最小受控上下文快照。
- FR-3: 请求快照不得包含访问凭证、完整客户原文、私有绝对路径或无关表单大字段。
- FR-4: 显式 `rewrite`/`edit` 选择必须优先于 LLM 自动路由。
- FR-5: LLM 自动路由只作为兜底，所有任务创建前必须经过确定性 guard。
- FR-6: rewrite guard 必须确认当前会话存在可改写的 rewrite history 或等价当前文档上下文。
- FR-7: edit guard 必须确认上传 Word 文件、锚点配置、form type 和必要草稿字段满足创建任务要求。
- FR-8: agent run 只能通过 tool 创建 task，不得直接执行 Word COM。
- FR-9: `create_rewrite_task_tool` 和 `create_edit_task_tool` 必须复用现有 `DocumentService`。
- FR-10: agent run 必须输出结构化进度事件，不输出原始隐藏推理内容。
- FR-11: 前端必须展示 skill picker、capability chip、结构化思考过程和 task accepted 后的现有任务卡。
- FR-12: `backend/logs` 中可写 debug JSONL，但不得作为 UI 恢复数据库。
- FR-13: 新路径稳定后必须删除旧 `/api/user/stream` 和旧 user routing / skill workflow 代码。

## Non-Goals

- 不新增数据库化历史会话列表。
- 不实现跨账号日志检索或复杂搜索。
- 不改变现有生成、补充批注、任务 SSE、下载代理的核心协议。
- 不把 rewrite/edit 合并回旧 user stream 判路。
- 不让 DeepAgents 直接读取任意本机文件或直接操作 Word COM。
- 不复制 DsAgent 的 UI 风格或左侧历史会话。

## Design Considerations

- UI 延续 TenderWord 当前右侧聊天、任务卡、上传按钮和模型选择风格。
- skill picker 可借鉴 DsAgent 的交互逻辑，但视觉、间距、颜色和组件形态应贴合本项目。
- capability chip 出现在用户消息气泡中，正文保持干净；复制文本恢复 `$skill 指令`。
- 思考过程卡应紧凑、可折叠，阶段文案面向用户可理解。

## Technical Considerations

- DeepAgents API 参考官方 `create_deep_agent`、skills、backend 文档；执行前应再次核对当前安装的 `deepagents>=0.6.4` 行为。
- 文件系统 backend 推荐使用 `FilesystemBackend(virtual_mode=True)`，并用 `CompositeBackend`/`StateBackend` 隔离 scratch、skills 和临时工作区。
- task 仍是 Word COM 临界资源，必须走任务队列、graph 锁、取消检查和现有 SSE。
- fake runtime 是首期必需，以便在无 Word COM/真实 LLM 时验证前后端闭环。

## Success Metrics

- 新入口上线后，前端对 `/api/user/stream` 的运行时调用数为 0。
- rewrite 显式路径在已有上下文时一次消息即可创建任务。
- edit 缺文件时不误创建任务，上传文件后可创建任务。
- 新增 fake E2E 可在无 Word COM 环境稳定通过。
- 删除旧代码后后端 pytest、前端 lint/typecheck/Jest 无回归。

## Open Questions

- 首期是否需要 agent run 级取消 API，或只依赖客户端断开和终态收敛。
- 后端是否需要为 agent run 模型字段增加独立白名单；当前建议复用现有模型选择并做后端兜底。

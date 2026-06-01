# Requirements: 任务上下文助手 Agent Run Skill Chat 重构

## 来源

- 生成自当前对话中关于右侧聊天入口、DeepAgents skill 调用、DsAgent Harness 参考、rewrite/edit 任务边界和旧代码清理的需求对齐内容。
- 关联 PRD：`prd.md`

## 原始对齐需求

当前项目的 `backend/skills` 仍然更像工作流封装，而不是正规 agent 通过 skill 调用能力的逻辑。用户希望重构右侧聊天入口：它不再只是显示中间表单任务日志的入口，也不再由旧 `/api/user/stream` 做简单判路，而是定义为“任务上下文助手”。该助手负责理解用户在右侧输入框里的消息，按显式 skill 选择或自然语言路由决定是否创建 rewrite/edit 任务、是否追问缺失条件，或仅进行普通澄清回复。

新的后端入口采用 `create_deep_agent` 实现，并通过 deepagents 开箱即用的 skill 加载方式加载 `rewrite` 和 `edit` 两个 skill。skill 内容不再指挥主 agent 调用旧 graph，也不把旧 `backend/skills/*/scripts/workflow.py` 包装成 subagent。新的方向是：`SKILL.md` 负责说明适用场景、前置条件、缺失信息追问和应调用的工具；真正创建任务由工具完成，例如 `create_rewrite_task_tool` 和 `create_edit_task_tool`，并复用现有 `DocumentService.create_rewrite_task` / `DocumentService.create_edit_task`，继续让 Word COM 任务进入既有任务队列。

用户明确希望同时支持显式选择和自动路由，但以显式选择为主、自动路由为兜底。显式选择包括 `/rewrite`、`/edit` 和 `$rewrite ...`、`$edit ...` 这类前缀；自然语言由大模型路由，但必须有确定性 guard 兜底。满足条件时直接发起任务，缺少必要条件时追问。例如已有生成文档上下文时，用户输入 `/rewrite 把第三包技术参数补充得更完整` 应直接创建 rewrite 任务；如果用户选择 `/edit` 但没有上传 Word 文件，则 agent 只追问“请先上传要修改的 Word 文件”，不能创建任务。

用户已接受 `agent_run` 和 `task` 的边界：`agent_run` 是一次聊天/判断/工具调用过程，负责 skill 加载、上下文检查、思考过程展示、追问或创建任务；它在任务创建后即结束。`task` 是现有 Word COM 队列任务，负责排队、Word 写入、任务 SSE、取消、下载和最终状态。两者不应混为同一种状态机。

最终接口形态是完全删除旧 `/api/user/stream`，只保留新的 `/api/agent/runs/stream` 作为右侧输入入口。旧的 `streamUserMessage`、`UserGraph`、`user_routing_service`、旧 routing prompt，以及已不再使用的自定义 skill registry/loader/types 和 `backend/skills/*/scripts/workflow.py`，都应在新路径验证后删除，避免长期保留两套入口。

前端交互逻辑要全面参考甚至复制 `D:\AgentProject\DsAgent` 中前后端交互和 Harness 的思考逻辑，但不要复制 DsAgent 的左侧历史会话，也不要模仿其 UI 风格。TenderWord 保持当前工作台 UI 风格。`/` 出现 skill 名称并显示可调用能力；用户消息气泡显示 capability chip，消息正文不包含 `$rewrite` 或 `[$rewrite]` 前缀；复制用户消息时恢复为 `$skill 用户指令`。已有“上传文件修改”按钮保留，并映射到 edit skill 语义。

思考过程展示也参考 DsAgent：前端要展示 deep agent 的阶段化进度日志，但不展示或保存原始模型 `reasoning_content`。可展示结构化阶段摘要、工具名、guard 决策和结果，阶段建议包括：`理解需求`、`执行任务`、`调用工具`、`异常与重试`、`汇总结论`。

关于文件系统能力，用户接受使用 deepagents filesystem/backend，但不希望把 `backend/logs` 直接裸挂给 agent。推荐采用隔离的 `FilesystemBackend(virtual_mode=True)`，并用类似 DsAgent 的 `CompositeBackend + StateBackend + 只读 skills backend` 思路隔离 scratch、skill 和临时工作区。`backend/logs` 中的日志只用于 debug 排查和 agent 执行任务时通过受控工具查阅当前上下文，不作为 UI 恢复数据库。

后端重启后不需要通过 logs 恢复会话；页面刷新仍由前端当前 conversation 的本地状态/sessionStorage 机制恢复最近上下文，但不做数据库化历史列表，不做跨账号检索或复杂搜索。日志命名可采用 `task_<id>` 或 `agent_run_<id>` 风格，保留结构化 JSONL，避免写入访问凭证、客户原文、私有路径和堆栈细节。

用户希望第一阶段包含 rewrite 和 edit 两个 skill，但实施顺序先 rewrite 后 edit，并拆成多个小 user stories。每个 story 最好是三四个可闭环、可验证、失败后容易重试的增量。需要 Ralph 执行时，PRD 应拆成多个小闭环：先用 fake runtime 打通新接口和前端展示，再接 real deepagents rewrite，再接 edit，最后删除旧入口和旧 workflow 代码。

## 范围

### 包含

- 新增“任务上下文助手”右侧聊天 agent run 流式入口 `/api/agent/runs/stream`。
- 支持 `rewrite` 和 `edit` 两个 deepagents skills，显式选择优先，LLM 自动路由兜底。
- 使用确定性 guard 判断是否可创建任务，缺条件时由 agent 追问。
- 为 rewrite 先实现闭环，再实现 edit 闭环。
- 复用现有 Word COM 任务队列、任务 SSE、下载卡和 `DocumentService` 创建任务能力。
- 前端保留 TenderWord UI 风格，增加 `/` skill picker、用户气泡 capability chip、结构化思考过程展示。
- 写入 `backend/logs` 中的 agent run/task debug JSONL 日志，但不把日志作为 UI 持久化或历史会话数据库。
- 删除旧 `/api/user/stream` 与不再使用的旧 user routing / skill workflow 代码。

### 不包含

- 不新增左侧历史会话列表。
- 不引入数据库保存聊天历史、agent run 历史或跨账号检索。
- 不让 agent 直接操作 Word COM；Word COM 仍只由 task 队列执行。
- 不把旧 `workflow.py` 图包装为 subagent 或 tool。
- 不展示、保存或回放原始模型隐藏推理文本。
- 不把 TenderWord 改成通用招标问答机器人；普通聊天只是不可执行意图的兜底澄清。

## 业务场景

- 用户已有生成文档上下文，输入 `/rewrite 把第三包技术参数补充得更完整`，系统显示 rewrite capability chip，agent run 展示结构化思考阶段，调用 `create_rewrite_task_tool` 创建 rewrite task，随后由现有任务卡和任务 SSE 展示执行进度。
- 用户输入 `$rewrite 帮我把评分办法写得更专业`，前端识别并移除正文中的 `$rewrite` 前缀，仍将 `selected_skills=["rewrite"]` 发送给后端。
- 用户自然语言输入“把刚才生成的文档第三包技术参数扩写一下”，未显式选择 skill 时，LLM 可路由到 rewrite；但若没有 rewrite history，guard 必须追问缺少当前文档上下文。
- 用户点击现有“上传文件修改”并上传 Word 文件后输入修改要求，系统按 edit skill 创建 edit task；如果用户选择 `/edit` 但没有上传 Word 文件，则 agent 只追问上传文件，不创建 task。
- 用户询问“你能做什么”或输入模糊意图时，系统说明可选择 rewrite/edit 或追问必要条件，不自动创建任务。

## 验收口径

- 右侧输入只调用 `/api/agent/runs/stream`，仓库内不再存在 `/api/user/stream` 调用路径。
- `agent_run` 和 `task` 的职责、状态、事件和日志边界清晰，任务创建后仍由现有 task SSE 执行。
- rewrite 与 edit 的缺失条件都能被 guard 拦截并给出明确追问。
- 前端可见 skill picker、capability chip、结构化思考过程，并保持 TenderWord 当前 UI 风格。
- fake runtime 可在无真实 LLM/Word COM 环境下验证新接口和前端闭环。
- 删除旧 user routing 和旧 skill workflow 后，相关测试更新，前后端 lint/typecheck/pytest 可通过。

## 待确认问题

- agent run 的取消是否需要首期支持单独取消，还是仅支持客户端断开并让 run 自然结束。当前建议首期只保证断开后终态可收敛。
- real deepagents 的模型选择是否完全复用当前右侧模型下拉，还是需要后端白名单映射。当前建议复用现有 `model` 字段并由后端设置兜底。

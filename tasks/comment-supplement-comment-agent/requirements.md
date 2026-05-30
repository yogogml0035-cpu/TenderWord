# 需求：补充批注与 comment_agent

## 来源

- 生成自当前对话中的计划需求。
- 关联 PRD：`prd.md`

## 原始对齐需求

本需求围绕 TenderWord 的 AI 批注生成、写回、任务结果和前端展示链路进行增强。当前批注写回失败会让生成任务硬失败，用户即使正文已经生成、文件已经可下载，也会被阻断。本次改动要求把批注降级为增强项：正文写入成功且文件可下载时，生成任务必须完成；批注失败只通过 warning 和统计摘要暴露。

同时新增独立的 `comment_supplement` 任务，允许用户在初次 generate 成功后的下载卡片上点击 `补充批注`。该任务复制当前文档为新副本，基于会话里的最新 `rewrite_state.polished_text` 生成或补充批注，完成后更新最新 `rewrite_state.prepared_doc_path`，让后续 rewrite/edit 基于补充批注后的文件继续工作。

`generation_mode=agent` 时，需要复用新增 `comment_agent`；`workflow` 保持非 agent 路径，只做普通批注生成和确定性写入。`comment_agent` 必须使用 LangChain `create_agent` 实现，名称固定为 `comment_agent`，只向前端展示同名内容卡，并按时间顺序追加所有 `AIMessage.content`，不展示工具消息。

## 范围

### 包含

- 后端任务契约新增 `TaskKind.comment_supplement`，同步任务队列、任务服务、SSE 模型、前端 `TaskKind` union 和进度节点显示名。
- `TaskResult` 和 SSE `done` 增加 `comment_writeback` 摘要对象，至少包含 `summary`、`generated`、`added`、`failed`、`skipped`、`warning`。
- 批注 warning 规则固定为 `generated > 0 && failed > 0`；`generated=0` 不警告；已有批注位置计入 `skipped`，不计入失败。
- `workflow` 生成路径继续执行 `generate_comments -> update_word`，但移除“生成批注且 0 写入则 raise”的硬失败。
- `agent` 生成路径正文仍走现有 `content_agent`，正文写入节点只写正文、样式并保存；随后由 `comment_agent` 处理批注。
- 独立 `comment_supplement` API、任务创建、graph 和前端按钮。
- 生成成功后，把 `comment_plan_detail`、`strikethrough_plan`、`non_black_font_plan`、`generation_mode` 写入后端 `rewrite_state`，但不透传到前端或 `sessionStorage`。
- 有送审稿计划时继续复用 `backend/prompts/comment_prompt.py`；新增无参考批注 prompt 模块，例如 `backend/prompts/comment_no_reference_prompt.py`。
- `comment_agent` 的校验工具最多 3 次调用，包含初次校验；写入工具最多 1 次调用。
- `comment_agent` 审计日志保存初始 JSON、每轮 `AIMessage`、每轮校验结果、最终通过/失败/跳过列表、Word 写入统计。
- 前端下载卡 warning、补充批注按钮、`comment_agent` 流式内容卡和相关单测/E2E。
- 更新 `asset/shared_runtime_word_skill_knowledge_pack.md` 和 `asset/README.md`。

### 不包含

- 不把 `generation_mode` 透传到 rewrite/edit 请求模型、skill state 或 prompt surface。
- 不把三组批注依据长数组透传到前端 payload 或 `sessionStorage`。
- 不让 `workflow` 模式显示 `comment_agent` 内容卡。
- 不把独立 edit 入口重新并回 `/api/user/stream`。
- 不新增与本需求无关的招标类型、模板候选能力或 UI 重构。

## 业务场景

- 用户初次生成文档时，正文已经成功写入并保存，但部分或全部 AI 批注因为锚点不匹配、已有批注重叠或 Word 写入失败而未写入。此时任务仍应完成，下载按钮可用，卡片显示轻量 warning。
- 用户在初次生成成功的下载卡片上点击 `补充批注`，系统创建轻量任务，对当前文档副本补充批注，完成后展示新的下载卡片。
- 用户选择 `generation_mode=agent` 初次生成，前端应看到正文智能体过程卡和 `comment_agent` 过程卡；选择 `workflow` 时不显示 `comment_agent` 卡。
- 后续 rewrite/edit 必须基于最新补充批注后的文档路径继续工作。

## 验收口径

- 正文写入成功且文件存在时，批注失败不会把 generate 或 comment_supplement 任务置为 failed。
- `comment_writeback.warning` 只在 `generated > 0 && failed > 0` 时为 true。
- 下载按钮在 warning 状态下仍可用。
- `补充批注` 只在初次 generate 成功卡片显示，rewrite/edit/comment_supplement 卡片不显示。
- `comment_agent` 使用 `create_agent` 和 `ToolCallLimitMiddleware`，校验工具最多 3 次，写入工具最多 1 次。
- `comment_agent` 只允许 AI 修改 `reference_text`，`comment_text` 必须保持原样。
- 校验只看 `polished_text`，Word 写入只在目标锚点区间内查找，不做全文兜底。
- `comment_supplement` 缺少会话上下文或最新 `rewrite_state` 时返回明确错误。
- 后端、前端单测和 mock E2E 覆盖需求中列出的关键路径。

## 假设

- “3 轮”按校验工具最多 3 次调用解释，包含初次校验；因此最多 2 次 AI 修复机会。
- 初次 generate 无送审稿时不强制自动插入无参考批注；无参考 prompt 主要用于用户点击 `补充批注` 的独立任务。
- 当前本地后端虚拟环境已支持 `langchain.agents.create_agent` 与 `langchain.agents.middleware.ToolCallLimitMiddleware`，计划阶段不要求新增重量级依赖。

## 待确认问题

- 无阻塞问题。若实施时发现 `comment_supplement` 请求里的 `output_file` 不应由前端指定，应优先由后端生成安全副本路径，并保持前端只传当前下载卡片的 `source_file`。

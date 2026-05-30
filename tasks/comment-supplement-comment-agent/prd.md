# PRD：补充批注与 comment_agent

## 介绍/概述

当前生成链路把 AI 批注写回视为阻断成功的硬失败项。只要 AI 生成了批注但 0 条写入，任务就会失败，即使正文已经写入成功、Word 文件已经可下载。这会把增强项失败扩大成主流程失败。

本功能将 AI 批注改为可降级增强项，新增 `comment_writeback` 统计与 warning 契约，并引入独立 `comment_supplement` 任务和 `comment_agent`。用户可以在初次 generate 成功后的下载卡片上补充批注，agent 模式也可以在正文生成后用 `comment_agent` 修复锚点并写入批注。

## 目标

- 正文生成成功且文件可下载时，批注写回失败不再阻断任务完成。
- 通过 `comment_writeback` 摘要让后端、SSE 和前端对批注生成、成功、失败、跳过、warning 有一致契约。
- 提供独立 `comment_supplement` 任务，让用户在初次 generate 成功文档上补充批注。
- 在 `generation_mode=agent` 路径复用 `comment_agent`，并用工具调用上限约束 AI 修复轮数。
- 保持 rewrite/edit 不接收 `generation_mode` 和三组批注依据长数组，避免前端持久化膨胀。
- 用单测和 mock E2E 覆盖任务、SSE、UI 和 agent 工具限制。

## 用户故事

### US-001: 批注写回降级为 warning
**描述：** 作为生成文档的用户，我想在正文生成成功时仍能下载文件，以便批注失败不会阻断主流程成果。

**验收标准：**
- [ ] 当正文写入成功且输出文件存在时，`generated_comment_count > 0` 且 `comment_writeback_added == 0` 不再抛出硬失败。
- [ ] 任务结果和 SSE `done` 包含 `comment_writeback` 对象，字段至少包含 `summary`、`generated`、`added`、`failed`、`skipped`、`warning`。
- [ ] `warning` 仅在 `generated > 0 && failed > 0` 时为 true。
- [ ] `generated=0` 时不显示 warning。
- [ ] 已有批注位置计入 `skipped`，不计入 `failed`，skipped-only 不显示 warning。
- [ ] 后端相关 pytest 通过。

### US-002: workflow 生成保持确定性批注路径
**描述：** 作为维护者，我想让 `workflow` 模式沿用普通批注生成与确定性写入，以便保持旧路径稳定。

**验收标准：**
- [ ] `generation_mode=workflow` 仍走 `generate_comments -> update_word`。
- [ ] `workflow` 模式不调用 `comment_agent`。
- [ ] `workflow` 模式批注失败只产生 warning 统计，不影响下载。
- [ ] 前端 `workflow` mock E2E 不出现 `comment_agent` 内容卡。
- [ ] 后端 graph 路由测试通过。

### US-003: agent 生成在正文写入后运行 comment_agent
**描述：** 作为选择智能体生成的用户，我想在正文 agent 完成后看到独立的批注 agent 过程，以便批注锚点修复和写入过程可观察。

**验收标准：**
- [ ] `generation_mode=agent` 正文仍走现有 `content_agent`。
- [ ] agent 生成路径的正文写入节点只写正文、样式并保存，不写 AI 批注。
- [ ] 正文保存后进入 `comment_agent` 批注链路。
- [ ] `comment_agent` 失败或部分失败不影响输出文件下载。
- [ ] 前端 agent generate mock E2E 同时显示正文 agent 卡和 `comment_agent` 卡。

### US-004: 新增 comment_supplement 任务闭环
**描述：** 作为已经生成文档的用户，我想点击下载卡片上的 `补充批注`，以便在不重新生成正文的情况下补充批注。

**验收标准：**
- [ ] 后端提供独立 `comment_supplement` API，前端只传 `conversation_id`、当前文件信息和 `model`。
- [ ] 后端按 `conversation_id` 读取最新 `rewrite_state`，缺少上下文时返回明确错误。
- [ ] 后端复制当前文件为新副本，并基于 `rewrite_state.polished_text` 生成或补充批注。
- [ ] 任务完成后更新最新 `rewrite_state.prepared_doc_path` 为新副本路径。
- [ ] 后续 rewrite/edit 使用补充批注后的文件路径。
- [ ] 缺少文件、文件不匹配或会话不存在时不创建不可恢复任务。

### US-005: comment_agent 工具限制和确定性门禁
**描述：** 作为维护者，我想用确定性工具约束 AI 批注修复，以便 AI 只能修复锚点而不能改写批注意见。

**验收标准：**
- [ ] `comment_agent` 使用 LangChain `create_agent` 创建，名称固定为 `comment_agent`。
- [ ] 使用 `ToolCallLimitMiddleware` 限制校验工具最多 3 次调用，写入工具最多 1 次调用。
- [ ] AI 只允许修改 `reference_text`，`comment_text` 必须与初始 JSON 同 index 原样一致。
- [ ] 校验工具只基于 `polished_text` 查找锚点，不做全文兜底。
- [ ] Word 写入工具只在锚点区间内查找，通过确定性校验且目标位置没有已有批注的条目才写入。
- [ ] 校验失败反馈包含 index、原 `reference_text`、失败原因和相近候选片段。
- [ ] 最终统计区分 passed、failed、skipped 和 Word 写入 added/failed/skipped。

### US-006: 会话上下文保存批注依据但不前端持久化
**描述：** 作为后续 rewrite/edit 用户，我想让后端保留批注依据和生成模式，以便后续任务可以复用上下文且前端不会存储长数组。

**验收标准：**
- [ ] generate 成功后 `rewrite_state` 包含 `comment_plan_detail`、`strikethrough_plan`、`non_black_font_plan`、`generation_mode`。
- [ ] 前端任务结果、SSE `done`、下载卡 metadata 和 `sessionStorage` 不包含这三组长数组。
- [ ] rewrite/edit 请求模型仍不包含 `generation_mode`。
- [ ] 后端 conversation service 可返回最新内部 `rewrite_state` 供 `comment_supplement` 使用。

### US-007: 新增无参考批注 prompt
**描述：** 作为用户，我想在没有送审稿参考时也能通过补充任务生成通用审查批注，以便补充批注任务不依赖历史参考文件。

**验收标准：**
- [ ] 新增 `backend/prompts/comment_no_reference_prompt.py`。
- [ ] 无参考 prompt 保留三维审查、严格 JSON 数组输出和 `reference_text` 精确锚点约束。
- [ ] 无参考 prompt 去掉历史参考逻辑，不要求引用送审稿差异。
- [ ] prompt 单测断言 JSON 契约、锚点约束和不包含历史参考要求。

### US-008: 前端任务类型、SSE 和下载卡支持新契约
**描述：** 作为前端用户，我想在成功卡片上看到可用下载、轻量 warning 和补充批注入口，以便清楚知道主文档已生成但批注有部分问题。

**验收标准：**
- [ ] 前端 `TaskKind` union 支持 `comment_supplement`。
- [ ] 前端能解析任务状态和 SSE `done` 中的 `comment_writeback`。
- [ ] 初次 generate 成功卡片显示 `补充批注` 按钮。
- [ ] rewrite/edit/comment_supplement 卡片不显示 `补充批注` 按钮。
- [ ] `comment_writeback.warning=true` 时卡片显示 `文档已生成，部分批注未写入`。
- [ ] warning 状态下下载按钮始终可用。

### US-009: comment_agent 过程卡展示
**描述：** 作为用户，我想看到 `comment_agent` 的文字过程，以便知道系统正在校验和修复批注锚点。

**验收标准：**
- [ ] 初次 generate 的 agent 模式和独立 `comment_supplement` 任务都会显示 `comment_agent` 卡。
- [ ] 卡片名称为 `comment_agent`。
- [ ] 同一张卡片按时间顺序流式追加所有 `AIMessage.content`。
- [ ] 工具消息不展示在前端卡片中。
- [ ] `workflow` 模式不显示 `comment_agent` 卡。

### US-010: 集成验证与知识包回写
**描述：** 作为维护者，我想把批注降级、补充任务和 agent 契约沉淀到测试和知识包中，以便后续需求不回退到硬失败或前端泄露长数组。

**验收标准：**
- [ ] 后端单测覆盖批注 0 写入不失败、warning 规则、skipped-only、`rewrite_state` 快照、`comment_supplement` 创建与错误、`comment_agent` 工具限制和 prompt 契约。
- [ ] 前端单测覆盖 `TaskKind`、SSE/result 解析、下载卡按钮与 warning、`comment_agent` 内容追加。
- [ ] Playwright mock E2E 覆盖 generate 后点击 `补充批注` 和 agent/workflow 两种展示差异。
- [ ] 更新 `asset/shared_runtime_word_skill_knowledge_pack.md` 和 `asset/README.md`。
- [ ] 前端 `npm run lint`、`npm run type-check`、相关 `npm run test` 和后端相关 pytest 通过。

## 功能需求

- FR-1: 系统必须新增 `comment_supplement` 任务类别，并让任务队列、任务状态接口、SSE 和前端类型一致识别。
- FR-2: 系统必须在任务结果和 SSE `done` 中输出统一 `comment_writeback` 摘要对象。
- FR-3: 系统必须把批注写回失败从 generate 主链路硬失败改为 warning。
- FR-4: 系统必须保持 `workflow` 模式使用非 agent 批注路径。
- FR-5: 系统必须让 `generation_mode=agent` 在正文写入保存后运行 `comment_agent`。
- FR-6: 系统必须提供独立 `comment_supplement` API 和 graph，并复用任务队列、Word COM 锁、取消检查、SSE 和下载链路。
- FR-7: 系统必须基于后端最新 `rewrite_state.polished_text` 生成/补充批注，并在完成后更新最新 `rewrite_state.prepared_doc_path`。
- FR-8: 系统必须用 `ToolCallLimitMiddleware` 限制 `comment_agent` 工具调用次数。
- FR-9: 系统必须用确定性校验保证 AI 只能改 `reference_text`，不能改 `comment_text`。
- FR-10: 系统必须保存 `comment_agent` 审计日志。
- FR-11: 前端必须只在初次 generate 成功下载卡展示 `补充批注` 按钮。
- FR-12: 前端必须显示批注 warning，但保持下载按钮可用。
- FR-13: 前端必须用同一张 `comment_agent` 卡按顺序追加 AI 内容，不展示工具消息。
- FR-14: 系统必须更新相关测试和 `asset/` 知识包。

## 非目标

- 不修改招标类型 identity、gngk form type 分派或 URL canonical 规则。
- 不新增真实 Word COM E2E 自动化作为常规 CI 必跑项。
- 不把 comment_agent 工具消息、候选评分或排障细节直接展示给用户。
- 不让 `comment_supplement` 支持 rewrite/edit 下载卡入口。
- 不把三组批注依据长数组放入前端持久化状态。

## 设计考虑

- 下载卡应保持安静、工作台风格：成功标题、下载按钮、轻量黄色 warning、`补充批注` 次要按钮。
- `补充批注` 按钮应只在可创建任务时启用，点击后进入现有任务消息组/SSE 流程。
- `comment_agent` 卡复用现有 agent-step 过程卡模式，名称来自 SSE `node` 字段。

## 技术考虑

- Word COM 操作必须继续通过 graph、`BaseGraph`、任务队列和现有锁执行。
- `comment_writeback` 摘要应由后端统一构造，避免每个 update_word 节点重复计算 warning。
- `comment_agent` 写入工具内部仍必须再次做确定性门禁，不能信任 AI 已经调用过校验工具。
- `comment_supplement` 必须验证会话最新 `rewrite_state` 与传入文件一致，避免对旧文件补批注后覆盖当前上下文。
- LangChain `create_agent` 和 `ToolCallLimitMiddleware` 已在本地虚拟环境可导入；实施时仍需保持依赖声明可安装。

## 成功指标

- 批注写入失败不再导致已生成正文的任务失败。
- 用户能从初次 generate 成功卡片一键创建补充批注任务。
- agent 模式下正文 agent 和 `comment_agent` 过程在前端可区分展示。
- warning、skipped、failed 的语义在后端、SSE 和前端一致。
- 相关单测和 mock E2E 覆盖新增契约。

## 待确认问题

- `comment_supplement` 请求中的 `output_file` 是否必须由前端传入。如果实施时存在路径安全或旧文件覆盖风险，应改为后端生成新副本路径，前端只传当前 `source_file`。

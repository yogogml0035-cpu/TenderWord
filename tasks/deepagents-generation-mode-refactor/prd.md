# PRD: DeepAgents 生成方式重构

## 1. 介绍/概述

TenderWord 当前初次生成任务通过标准 graph 中的 `generate_polished_text` 节点生成 `polished_text`，后续继续进入批注、样式回写、Word 写回和下载链路。本需求在初次 generate 中新增“生成方式：工作流 / 智能体”。默认仍使用“工作流”，保证旧路径完全不变；用户选择“智能体”时，生成 graph 改走 DeepAgents `host_agent`，由主 agent 调用 `generate_agent` 与 `verify_agent` 完成初稿、审核和最多 3 轮修复，最终仍回写 `polished_text` 给既有后续链路。

## 2. 目标

- G-1: 为初次 generate 新增 generate-only 字段 `generation_mode`，默认 `"workflow"`。
- G-2: 保证 `"workflow"` 模式完全沿用现有 `generate_polished_text` 行为。
- G-3: 为 `"agent"` 模式接入 DeepAgents `host_agent`，生成最终 `polished_text`。
- G-4: 将智能体审核和修复过程通过新增 SSE 事件展示到前端会话历史。
- G-5: 以 Graph 差异覆盖作为首版验收矩阵，避免所有前端组合重复验证。
- G-6: 实现后同步长期知识包，避免 generate runtime、SSE、会话草稿规则漂移。

## 3. 用户故事

### US-001: 新增 generate-only 生成方式契约

**描述：** 作为开发者，我需要在前后端请求契约中表达 `generation_mode`，以便初次生成任务可以明确选择工作流或智能体。

**验收标准：**

- [ ] 后端 `GenerateRequest` 接受 `generation_mode: "workflow" | "agent"`，默认值为 `"workflow"`。
- [ ] `generation_mode` 只进入 generate 初始 state，不进入 rewrite / edit 请求模型或 skill state。
- [ ] 前端 `GenerateRequest`、表单数据、转换器和会话草稿均包含 `generation_mode`。
- [ ] 未显式选择时，API payload 中使用 `"workflow"`。
- [ ] 后端模型测试覆盖默认值和 `"agent"` 输入。
- [ ] 前端转换器与草稿持久化测试覆盖该字段。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-002: 工作流模式保持旧路径不变

**描述：** 作为使用默认配置的用户，我想继续走当前工作流生成，以便新增智能体能力不会改变现有体验。

**验收标准：**

- [ ] `generation_mode="workflow"` 时仍执行旧 `generate_polished_text` 节点。
- [ ] 旧节点继续使用 `render_generate_prompt()` 和 `stream_llm_completion()`。
- [ ] 工作流模式仍推送现有 `llm` snapshot 事件，前端初稿生成卡行为不变。
- [ ] 现有 `generation_style` 与 `style_writeback_mode` 测试继续通过。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-003: 接入 DeepAgents host_agent 与子 agent

**描述：** 作为高级用户，我想选择智能体生成方式，以便系统可以先生成、再审核、再按意见修复采购需求正文。

**验收标准：**

- [ ] `generation_mode="agent"` 时进入 `host_agent` 分支。
- [ ] `generate_agent` 和 `verify_agent` 都以已编译 `StateGraph` 包装成 `CompiledSubAgent`。
- [ ] `generate_agent` 复用当前生成 prompt 输入与模型配置，生成初稿正文。
- [ ] `verify_agent` 输出 JSON 数组，每项包含 `evidence` 与 `fix_hint`。
- [ ] `host_agent` 最终输出结构化 JSON，至少包含最终 `polished_text`。
- [ ] 纯文本最终输出会导致任务失败，并返回明确错误。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-004: 智能体审核与修复循环

**描述：** 作为用户，我想看到智能体按审核意见多轮修复，以便最终正文经过自动质检。

**验收标准：**

- [ ] 智能体流程先生成初稿，再审核初稿。
- [ ] 审核意见非空时进入修复，修复后继续审核。
- [ ] 最多修复 3 轮。
- [ ] 第 3 轮修复完成后直接放行最终 `polished_text`，不因仍有审核意见失败。
- [ ] 审核 JSON 无法解析为数组时任务失败。
- [ ] 模型或 DeepAgents runner 报告不支持工具调用时任务失败，不自动回退工作流。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-005: 新增 agent step SSE 契约

**描述：** 作为前端开发者，我需要稳定的智能体步骤事件，以便渲染审核和修复过程卡片。

**验收标准：**

- [ ] 后端新增 `agent_step` SSE 事件类型和数据模型。
- [ ] 事件数据包含 `task_id`、`task_kind`、`step_type`、`round`、`node`、`timestamp`。
- [ ] `step_type="audit"` 事件包含本轮 `evidence` 与 `fix_hint` 列表。
- [ ] `step_type="revision"` 事件包含本轮修复正文快照或完成正文。
- [ ] `agent_step` 作为用户态 SSE 精简展示规则的显式例外，只用于智能体 generate。
- [ ] 任务失败时仍收敛为现有 `error` 事件，任务成功时仍收敛为现有 `done` 事件。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-006: 前端生成方式切换与 payload

**描述：** 作为前端用户，我想在高级设置中选择“工作流”或“智能体”，以便控制本次初次生成方式。

**验收标准：**

- [ ] 高级设置中新增“生成方式”全局切换控件，选项为“工作流”和“智能体”。
- [ ] 默认选中“工作流”。
- [ ] 用户切换后，该值写入当前会话草稿。
- [ ] 刷新页面或切换会话后，当前会话恢复上次选择。
- [ ] 提交生成时 API payload 包含当前 `generation_mode`。
- [ ] rewrite / edit 请求不包含 `generation_mode`。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-007: 前端智能体卡片保留

**描述：** 作为用户，我想在会话历史中看到初稿、审核意见和修复内容，以便理解智能体生成过程。

**验收标准：**

- [ ] 智能体模式下保留初稿生成卡。
- [ ] 审核卡按轮次追加 `evidence` 和 `fix_hint`。
- [ ] 每轮修复生成一张“AI 修改内容”卡或等价的可区分消息块。
- [ ] 任务完成后，上述卡片仍保留在会话历史中。
- [ ] `done` 事件仍生成下载入口卡。
- [ ] 刷新后通过 `sessionStorage` 恢复已落在会话历史里的智能体卡片。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-008: `xjcg` graph 智能体分支闭环

**描述：** 作为验证者，我需要确认询价采购 graph 在智能体模式下仍能产出最终正文，以便覆盖独立 graph 差异。

**验收标准：**

- [ ] 使用 fake DeepAgents runner 运行 `xjcg_tender` agent 分支。
- [ ] 分支最终 state 包含非空 `polished_text`。
- [ ] 后续 update 节点可接收该 `polished_text`。
- [ ] workflow 分支的 `xjcg_tender` 行为不变。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-009: `gngk_hw_zc` graph 智能体分支闭环

**描述：** 作为验证者，我需要确认国内公开货物自筹 graph 在智能体模式下仍能产出最终正文，以便覆盖公开招标通用货物链路。

**验收标准：**

- [ ] 使用 fake DeepAgents runner 运行 `gngk_hw_zc_tender` agent 分支。
- [ ] 分支最终 state 包含非空 `polished_text`。
- [ ] `gngk_hw_zc` 仍复用既有 replacement 与 common update 路径。
- [ ] workflow 分支行为不变。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-010: `gngk_hw_cz` graph 智能体分支闭环

**描述：** 作为验证者，我需要确认国内公开货物财政 direct-replace graph 在智能体模式下仍能产出最终正文，以便覆盖专属删除/写回链路。

**验收标准：**

- [ ] 使用 fake DeepAgents runner 运行 `gngk_hw_cz_tender` agent 分支。
- [ ] 分支最终 state 包含非空 `polished_text`。
- [ ] 后续仍进入 `gngk_hw_cz_delete_tender_param` 与 `gngk_hw_cz_update_word`。
- [ ] workflow 分支行为不变。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-011: `gngk_fw_zc` graph 智能体分支闭环

**描述：** 作为验证者，我需要确认国内公开服务自筹 graph 在智能体模式下仍能产出最终正文，以便覆盖服务专属节点链路。

**验收标准：**

- [ ] 使用 fake DeepAgents runner 运行 `gngk_fw_zc_tender` agent 分支。
- [ ] 分支最终 state 包含非空 `polished_text`。
- [ ] 后续仍进入服务专属 delete / update 节点。
- [ ] workflow 分支行为不变。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-012: `gjgk` graph 智能体分支闭环

**描述：** 作为验证者，我需要确认国际公开 graph 在智能体模式下仍能产出最终正文，以便覆盖国际公开专属流程和 post-update hook。

**验收标准：**

- [ ] 使用 fake DeepAgents runner 运行 `gjgk_tender` agent 分支。
- [ ] 分支最终 state 包含非空 `polished_text`。
- [ ] 后续仍进入 `gjgk` 专属 delete / replacement / update 和 post-update hook。
- [ ] workflow 分支行为不变。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-013: 继承复用链路 smoke

**描述：** 作为验证者，我需要对继承复用链路做最小 smoke，以便确认未覆盖矩阵不会遗漏继承分支。

**验收标准：**

- [ ] `gngk_fw_cz_tender` 至少有一条 agent 分支 smoke 测试。
- [ ] smoke 验证最终 state 包含非空 `polished_text`。
- [ ] smoke 验证继承链路没有因为新增 graph gate 断开。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-014: mock E2E 用户可见链路

**描述：** 作为用户，我需要浏览器层面看到智能体生成过程，以便确认 UI 链路可用。

**验收标准：**

- [ ] 使用 Playwright 打开本地前端页面。
- [ ] 通过 mock API / mock SSE 选择“智能体”并提交生成。
- [ ] 页面出现初稿生成卡。
- [ ] 页面出现审核卡，且包含轮次、`evidence` 与 `fix_hint`。
- [ ] 页面出现至少一轮“AI 修改内容”卡。
- [ ] 页面最终出现下载入口。
- [ ] 页面无控制台错误。
- [ ] Typecheck passes。
- [ ] Tests pass。

### US-015: 知识包与回归验证

**描述：** 作为后续维护者，我需要长期知识包记录新生成方式、SSE 例外和会话草稿规则，以便后续需求不再次漂移。

**验收标准：**

- [ ] 更新 `asset/shared_runtime_word_skill_knowledge_pack.md`，记录 generate runtime、host_agent、SSE agent step 和验证入口。
- [ ] 更新 `asset/tender_type_identity_session_knowledge_pack.md`，记录 `generation_mode` 会话草稿和表单切换边界。
- [ ] 更新 `asset/README.md` 索引和使用路由。
- [ ] 文档只记录当前已落地事实，不把未实现目标写成事实。
- [ ] `git diff --check` 通过。

## 4. 功能需求

- FR-1: 系统必须在后端 `GenerateRequest` 中新增 `generation_mode` 字段，取值为 `"workflow"` 或 `"agent"`。
- FR-2: 系统必须在前端 `GenerateRequest`、表单数据、会话草稿和转换器中同步 `generation_mode`。
- FR-3: 系统必须默认使用 `"workflow"`，并保持旧 `generate_polished_text` 路径不变。
- FR-4: 系统必须在标准生成 graph 中按 `generation_mode` 分流到 workflow 或 agent。
- FR-5: `agent` 分支必须最终返回 `polished_text`，供后续批注、写回和下载复用。
- FR-6: `generate_agent` 和 `verify_agent` 必须由已编译 `StateGraph` 包装成 `CompiledSubAgent`。
- FR-7: `verify_agent` 的审核结果必须是数组，每项至少包含 `evidence` 和 `fix_hint`。
- FR-8: 审核 JSON 无法解析、最终输出不是结构化 JSON、模型不支持工具调用时，智能体任务必须失败。
- FR-9: 智能体修复最多 3 轮，第 3 轮修复后直接放行。
- FR-10: 系统必须新增 `agent_step` SSE 事件，用于智能体 audit / revision 展示。
- FR-11: 前端必须保留智能体过程卡片，并最终保留下载入口。
- FR-12: 实现完成后必须更新指定知识包。

## 5. 非目标

- 不修改 rewrite / edit 入口或模型。
- 不让智能体模式失败时自动回退 workflow。
- 不新增独立招标类型或新的前端大类。
- 不改变模板候选和下载代理。
- 不改变 Word COM 串行锁、任务队列、取消检查和后续写回主干。

## 6. 设计考虑

- “生成方式”放在高级设置中，与“生成风格”“样式修订”同级。
- 控件使用现有 segmented control 风格，默认“工作流”。
- 智能体卡片必须可扫描，审核意见按轮次追加，修复正文与初稿正文可区分。
- 不在 UI 中解释 DeepAgents 实现细节，只展示用户需要理解的过程结果。

## 7. 技术考虑

- 当前后端依赖包含 `langgraph`、`langchain-core` 和 `langchain-deepseek`，但未包含 `deepagents`；实现前需要补充并验证依赖。
- 当前 LLM 流式调用集中在 `backend/util/common_util/llm_stream_utils.py`；DeepAgents 的模型构造应复用同一配置来源，不硬编码模型名或超时。
- 当前任务 SSE 类型在 `backend/models/sse.py` 与 `frontend/types/api.ts` 双侧维护；新增事件必须同步。
- 当前初稿内容卡由 `useChatSSE` 监听 `llm` 事件和 `generate_polished_text` 节点触发；智能体过程卡需要扩展 store 和 message metadata。
- Graph 差异覆盖以真实 graph 类差异为准：`xjcg`、`gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_zc`、`gjgk`；`gngk_fw_cz` 继承复用链路做 smoke。

## 8. 成功指标

- 默认工作流模式无用户可见回归。
- 智能体模式可以在 fake runner 下稳定完成完整生成闭环。
- 所有新增智能体事件在前端会话历史中可见并可保留。
- 每个 Graph 差异类型至少有一条可重试闭环 story。
- 后端、前端、E2E 和知识包验证均有明确命令。

## 9. 待确认问题

- 无。

# 需求归档：DeepAgents 生成方式重构

## 来源

- 生成自当前对话中的需求对齐内容。
- 关联 PRD：`prd.md`

## 原始对齐需求

本需求目标是在初次生成任务中新增“生成方式：工作流 / 智能体”。默认生成方式仍为“工作流”，选择“工作流”时必须完全沿用当前 `generate_polished_text` 路径，不改变现有生成行为。

当用户选择“智能体”时，标准生成 graph 不再直接进入旧的 `generate_polished_text` 节点，而是进入 `host_agent`。`host_agent` 由 DeepAgents 主 agent 自主调用两个子 agent：

- `generate_agent`：复用当前初稿生成逻辑，生成采购需求初稿。
- `verify_agent`：审核当前初稿或修复稿，输出数组格式的审核意见：`[{ "evidence": "...", "fix_hint": "..." }]`。

智能体模式的循环规则：

- 先生成初稿。
- 再审核初稿。
- 若审核有问题，按审核意见修复。
- 修复后继续审核，最多修复 3 轮。
- 第 3 轮修复完成后直接放行，不再因为仍有审核意见而阻塞后续写回。
- `host_agent` 最终必须输出结构化 JSON，至少包含最终 `polished_text`。
- 纯文本输出视为协议错误。

## 范围

### 包含

- 后端 `GenerateRequest` 新增 generate-only 字段 `generation_mode: "workflow" | "agent"`。
- 前端 `GenerateRequest`、表单数据、会话草稿与 API payload 同步新增 `generation_mode`。
- 默认值为 `"workflow"`，且随会话草稿持久化。
- 标准生成 graph 按 `generation_mode` 分流。
- `workflow` 分支走旧 `generate_polished_text` 路径。
- `agent` 分支走 `host_agent`，最终仍产出 `polished_text`，供后续批注、样式、Word 写回和下载链路复用。
- `generate_agent` 和 `verify_agent` 都是已编译 `StateGraph` 包装成 `CompiledSubAgent`。
- 新增 agent step SSE 事件契约，区分 `audit` 与 `revision`。
- 前端高级设置新增全局切换控件。
- 智能体模式下保留初稿生成卡、审核内容卡、每轮“AI 修改内容”卡；审核卡实时追加轮次、`evidence` 和 `fix_hint`，并保留在会话历史。
- 后端和前端测试覆盖工作流不变、智能体成功、审核 JSON 无法解析失败、模型不支持工具调用失败、第 3 轮后放行、SSE 解析与 UI 保留。
- 实现完成后更新 `asset/shared_runtime_word_skill_knowledge_pack.md`、`asset/tender_type_identity_session_knowledge_pack.md` 和 `asset/README.md`。

### 不包含

- 不影响 rewrite / edit。
- 不为智能体模式失败自动回退工作流。
- 不改变现有 `generation_style` 的语义；`generation_style` 仍只影响初次 generate 的 prompt 路由。
- 不新增招标类型。
- 不重构模板候选、下载代理或 rewrite/edit skill runtime。

## 业务场景

- 用户在表单高级设置中保持默认“工作流”，提交后获得与当前版本一致的生成行为。
- 用户在表单高级设置中切换到“智能体”，提交后看到初稿、审核意见和每轮修复内容的过程卡片。
- 智能体模式执行成功后，用户仍通过原有下载入口获取生成后的 Word 文件。
- 智能体模式执行失败时，用户看到明确错误，不产生静默中断，也不会自动切回旧工作流。

## 验收口径

- `generation_mode` 在后端请求模型、前端类型、表单数据、会话草稿和 API payload 中一致。
- 默认 `generation_mode` 为 `"workflow"`。
- `workflow` 分支仍调用旧 `generate_polished_text` 路径，现有测试不因新增字段回归。
- `agent` 分支最终写入 `polished_text`，后续批注、样式回填、Word 写回和下载链路继续使用既有主干。
- `verify_agent` 审核输出无法解析为指定 JSON 数组时，任务失败。
- 模型不满足 DeepAgents 工具调用或结构化输出要求时，任务失败。
- 第 3 轮修复完成后，即使仍有审核意见，也直接放行最终 `polished_text`。
- SSE 新增 agent step 事件后，后端模型、发送逻辑、前端 union 类型、`useChatSSE` 解析和测试同步更新。
- 首版验收按 Graph 差异覆盖逐个验证：`xjcg`、`gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_zc`、`gjgk`；继承复用链路做必要 smoke。
- E2E 使用 mock 任务和 mock SSE 固化“选择智能体 -> 初稿卡 -> 审核卡 -> 修复卡 -> 下载入口”的用户可见链路。

## 技术约束与外部依据

- 智能体模式仅适用于初次 generate。
- host/generate/verify 都沿用用户当前选择的模型。
- DeepAgents 方案按官方文档约束：
  - `create_deep_agent` 要求可工具调用模型。
  - subagents 支持 `CompiledSubAgent`。
  - LangGraph 图必须先 `.compile()` 后使用。
  - 参考：https://docs.langchain.com/oss/python/deepagents/subagents.md
  - 参考：https://docs.langchain.com/oss/python/langgraph/graph-api.md
  - 参考：https://docs.langchain.com/oss/python/langgraph/use-subgraphs.md

## 待确认问题

- 无。本轮已明确首版范围、默认行为、失败策略、SSE 例外和逐类型验收口径。

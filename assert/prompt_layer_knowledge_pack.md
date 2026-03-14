# Prompt Layer 能力知识包

## 背景与适用范围
- 适用于 `backend/` 内所有直接调用 LLM 的能力，包括生成、批注、rewrite、用户路由与 rewrite 目标选择。
- 目标是将 prompt 的模板、固定字面量、上下文裁剪和渲染逻辑集中在 `backend/prompts/`，避免 node/service 长期内联大段 prompt。
- 当前前端对话文案不在本知识包范围内；仅覆盖后端 LLM prompt 基础设施。

## 业务规则与约束
- Prompt 层只负责纯渲染，不负责 `prompts_log` 落盘、SSE、日志、副作用。
- 调用侧只做三件事：收集原始业务数据、调用 builder、执行 LLM 和后续副作用。
- 所有 prompt 输入都应使用显式类型对象，禁止继续向 builder 透传万能 dict。
- 生成与批注 prompt 维持“共享主干 + 类型特化挂点”；当前 `xjcg` / `gngk` 可共享模板，但 registry 必须保留。
- 与 LLM 契约强绑定的固定字面量必须收口到 Prompt 层，包括 `rewrite` 等机器路由字面量；普通用户提示文案应留在 service/API 层。
- 文档预览截断、历史消息压缩、候选 assistant 列表拼接等规则属于 prompt 渲染逻辑，不得散落回 service/node。

## 输入输出样例
- 生成 prompt 输入：
  - `GeneratePromptInput(tender_type, project_info, origin_tender_params, tender_params)`
  - 输出 `RenderedPrompt(system_prompt, user_prompt)`
- 批注 prompt 输入：
  - `CommentPromptInput(tender_type, polished_text, comment_plan_detail, strikethrough_plan, non_black_font_plan)`
  - 输出 `RenderedPrompt(system_prompt, user_prompt)`
- rewrite prompt 输入：
  - `RewritePromptInput(base_text, user_prompt)`
  - 输出 `RenderedPrompt(system_prompt, user_prompt)`
- 路由 prompt 输入：
  - `RouteOrReplyPromptInput(messages, latest_user_message, latest_rewrite_state, has_rewrite_history)`
  - 输出 `RenderedPrompt(system_prompt, user_prompt)`
- rewrite 目标选择输入：
  - `RewriteTargetSelectionPromptInput(messages, user_prompt)`
  - 输出 `RewriteTargetSelectionBundle(rendered_prompt, assistant_candidates)`

## 边界条件与已知坑点
- Prompt 层输入必须是最小必要字段；如果某个 builder 只需要预览文本，不要把整个 state 透传进去。
- `RewriteStateSnapshot` 只表达 prompt 需要的摘要字段，不等价于完整 graph state；调用侧若需要保留完整状态，必须继续持有原始 state。
- Prompt 层可以暴露 registry 和机器契约常量，但不能承担调用 `stream_llm_completion` 的职责，也不应承载普通用户回复文案。
- 任何新增 tender type 时，若 prompt 有特化需求，应优先在 `backend/prompts/*_prompt.py` registry 中扩展，而不是复制 node/service。
- 若某个 prompt 的输出有严格机器契约，解析与校验逻辑应与该 prompt 一起演进，并至少有结构断言测试。
- rewrite relevance classifier 已下线；rewrite 显式入口不再额外做 LLM 语义校验。

## 关联代码路径
- `backend/prompts/types.py`
- `backend/prompts/generate_prompt.py`
- `backend/prompts/comment_prompt.py`
- `backend/prompts/rewrite_prompt.py`
- `backend/prompts/routing_prompt.py`
- `backend/services/user_routing_service.py`
- `backend/nodes/common_word_nodes/generate_polished_text.py`
- `backend/nodes/common_word_nodes/generate_comments.py`
- `backend/nodes/skills_nodes/rewrite_nodes.py`

## 关联测试与验证路径
- `backend/tests/test_prompt_builders.py`
- `backend/tests/test_generate_comments.py`
- `backend/tests/test_user_routing_service.py`
- 建议验证命令：
  - `python -m py_compile backend/prompts/types.py backend/prompts/generate_prompt.py backend/prompts/comment_prompt.py backend/prompts/rewrite_prompt.py backend/prompts/routing_prompt.py backend/services/user_routing_service.py backend/nodes/common_word_nodes/generate_polished_text.py backend/nodes/common_word_nodes/generate_comments.py backend/nodes/skills_nodes/rewrite_nodes.py backend/tests/test_prompt_builders.py backend/tests/test_generate_comments.py backend/tests/test_user_routing_service.py`
  - `python -m pytest backend/tests/test_prompt_builders.py backend/tests/test_user_routing_service.py backend/tests/test_user_graph.py -q`
- 当前环境已知风险：
  - 本机 `pytest` 在收集阶段可能因 Windows `asyncio/_overlapped` 初始化异常失败，需要与代码逻辑失败区分。

## 禁忌清单
- 禁止在 node/service 内重新内联大段 system prompt 或 user prompt。
- 禁止在 Prompt builder 中直接访问文件系统、SSE、Word COM 或会话存储。
- 禁止为了一个新场景复制现有 prompt 文件再做字符串替换式扩展。
- 禁止把 Prompt 层退化成“只存字符串常量”的目录而把拼装逻辑继续散落在调用方。

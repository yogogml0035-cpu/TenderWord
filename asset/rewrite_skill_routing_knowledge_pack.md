# Rewrite Skill 路由与 Skill 化知识包

## 背景与适用范围
- 适用于统一用户流中的 rewrite 识别、rewrite skill 资源化，以及 rewrite 正文生成的二阶段 prompt 装配。
- 目标是把 rewrite 从硬编码 prompt 字面量升级为真正的后端 skill，并为后续新增 task 型 skill 提供同一套 loader、registry 和 dispatch 约束。

## 问题背景与方案选择
- 旧实现的问题：
  - `rewrite` 只有固定 prompt 文件，没有独立 skill 资源，也没有通用 skill registry。
  - 第一阶段路由 prompt 只认识 `rewrite`，无法自然扩展到更多 skill。
  - rewrite instruction 和动态上下文包装耦合在 `backend/prompts/rewrite_prompt.py`，扩展时容易再次散落。
- 本次选择的方案：
  - 第一阶段保留混合式 `route-or-reply`，但输入改为已注册 skill 的 `name + description` 目录摘要。
  - 第二阶段仅在命中 skill 时读取该 skill 的完整 `SKILL.md` instruction，并用统一 renderer 包装最小必要上下文。
  - `rewrite` 目标版本选择继续独立，避免把“选哪一版”与“如何改写”混成一个 skill。

## 关键改动点
- Skill 基础设施：
  - 新增 `backend/skills/loader.py`，扫描 `backend/skills/*/SKILL.md` 并解析 frontmatter。
  - 新增 `backend/skills/registry.py`，校验 skill 名称唯一、frontmatter 完整、`SKILL.md` 与执行器绑定一一对应。
  - 新增 `backend/skills/rewrite/SKILL.md`，承载 rewrite 的完整行为 instruction。
- 第一阶段路由：
  - `backend/prompts/routing_prompt.py` 改为动态 skill 目录 prompt builder，system prompt 只拼装 `name + description`。
  - `backend/services/user_routing_service.py` 接入 `SkillRegistry`，命中 skill 时先解析 binding，再继续维持前端只看见 `reply | rewrite` 的契约。
  - 路由前缀缓冲从固定 `rewrite` 扩展为“任一已注册 skill id”前缀，避免 skill id 误流给前端。
- 第二阶段 rewrite 执行：
  - 删除 `backend/prompts/rewrite_prompt.py`，rewrite_mode 改为读取 `rewrite` skill instruction。
  - 新增 `backend/prompts/skill_prompt.py`，统一渲染 `instruction + sections`，`skill_id` 只保留在注册与分发链路中，不再出现在用户 prompt 正文。
  - `backend/nodes/common_word_nodes/generate_polished_text.py` 统一包装 `当前文档内容 / 技术参数参考资料 / 用户修改指令`。
- 审计与可观测性：
  - rewrite 审计日志新增 `skill_directory_route` 与 `skill_prompt_render` 两个阶段。
  - 保留 `rewrite_target_selection` 与 `rewrite_text` 阶段，便于继续定位“命中了哪个 skill、最终发给 LLM 的是什么请求”。

## 输入输出样例
- `backend/skills/rewrite/SKILL.md`
  - frontmatter: `name: rewrite`, `description: ...`
  - body: rewrite 行为 instruction
- 第一阶段命中 skill：
  - LLM 输出：`rewrite`
  - 后端外部 route：`rewrite`
- 第二阶段 prompt 装配：
  - system prompt：`rewrite` skill instruction
  - user prompt sections：`当前文档内容`、`技术参数参考资料`、`用户修改指令`

## 验证路径
- 代码级检查：
  - `python -m py_compile backend/skills/types.py backend/skills/loader.py backend/skills/registry.py backend/prompts/types.py backend/prompts/skill_prompt.py backend/prompts/routing_prompt.py backend/services/user_routing_service.py backend/nodes/common_word_nodes/generate_polished_text.py backend/tests/test_skill_registry.py backend/tests/test_prompt_builders.py backend/tests/test_user_routing_service.py backend/tests/test_rewrite_audit_log.py`
- 单元测试重点：
  - `backend/tests/test_skill_registry.py`
  - `backend/tests/test_prompt_builders.py`
  - `backend/tests/test_user_routing_service.py`
  - `backend/tests/test_rewrite_audit_log.py`
  - `backend/tests/test_user_graph.py`

## 回归风险与避坑点
- 新增 skill 时，如果只放了 `SKILL.md` 但忘了加 executor binding，现在会在首次加载时直接失败，不再静默跳过。
- 第一阶段 prompt 只能看到 `description`；如果把执行细节写进 description，会污染路由判断并泄露本应只给第二阶段看的 instruction。
- 未来若新增非 `rewrite` 的 task 型 skill，必须同时明确：
  - skill id 对应的 executor binding
  - 是否复用当前前端 route 字面量，还是新增前端可见 route 契约
- `generate_polished_text` 的 rewrite_mode 现在依赖 `SkillRegistry`；如果 skill instruction 被误删或 frontmatter 非法，rewrite 不会再降级为旧 prompt，而是直接失败。
- `skill_id` 仍用于路由命中和 executor binding，但不应再被拼进第二阶段 user prompt；否则会把内部实现细节暴露给模型输入，增加无效噪音。

## 后续扩展建议
- 若后续出现更多 task 型 skill，可把 `UserRouteDecision.skill_id` 往 graph state 继续透传，为后续多分支 dispatch 做准备。
- 若未来需要“回复型 skill”或非任务型 skill，不要复用当前 task binding 语义，单独新增 executor kind。
- 若 skill 数量继续增多，可以为第一阶段目录 prompt 增加排序或分组，但仍应只暴露 `name + description`，不要泄露 instruction 正文。

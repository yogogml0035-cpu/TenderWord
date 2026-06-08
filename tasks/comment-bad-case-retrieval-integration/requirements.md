# Requirements: 批注 bad case 检索增强接入

## 来源

- 生成自当前对话中的需求对齐内容
- 关联 PRD：`prd.md`

## 原始对齐需求

本需求的目标是把 `backend/scripts/test_comment_hybrid_retrieval.py` 中已经验证过的批注 bad case 混合检索思路，正式接入当前批注生成主链路，作为所有“AI 新生成批注”的统一增强规则。

接入范围只包括：

- 初次生成 `workflow` 路径中的 `generate_comments`
- 初次生成 `agent` 路径里 `comment_agent` 的自主批注生成
- `comment_supplement` 补充批注任务中的自主批注生成

明确不包括：

- rewrite 链路
- `comment_generation_mode=off` 的所有场景
- 已有 `initial_comments` 的 `comment_agent` 纯锚点修复模式

检索增强的业务意图不是做一套强约束裁决引擎，而是通过 prompt 增强，让模型在命中 bad case 时优先参考既有风险模式、批注口径和锚点策略，同时继续保留一定自由发挥能力。该优先级是 prompt-level soft priority，不要求 deterministic guarantee，也不增加独立语义审查 agent。

bad case 数据源口径如下：

- 唯一真源格式使用 `---BEGIN_BAD_CASE--- ... ---END_BAD_CASE---`
- 正式目录使用 `backend/retrieval/bad_cases/`
- 当前主文件为 `backend/retrieval/bad_cases/comment_bad_cases.md`
- 后续新增 bad case 只往该目录下的 `.md` 文件族追加
- 旧的 `comments_bad_case_knowledge_essence.md` 只保留为历史材料，不再进入主链路

运行时检索口径如下：

- 运行时允许从正式 bad case 目录读取文件并构建 BM25 内存索引
- 不在生成链路里做 collection recreate、自动 upsert 或重建索引
- hybrid 可用时走 BM25 + vector
- hybrid 不可用或运行失败时自动降级为 BM25-only
- 两种模式都沿用同一外部口径：每条款 `top3`、`score > 0.8`
- 检索失败、collection 不存在、bad case 文件缺失或无命中时，全部降级继续，不阻塞批注生成

条款切分与上下文注入口径如下：

- 运行时严格使用 `clause_only`，查询文本只取条款正文
- 第一版沿用现有实验脚本里的简单条款切分规则
- 如果一个条款都切不出来，回退为整篇 `polished_text` 单条检索
- 同一 `case_id` 只保留一次，多个条款命中时保留最高分
- 全文 bad case 注入上限为 12 条
- 最终注入 prompt 的 bad case 条目只保留：
  - `risk_type`
  - `risk_pattern`
  - `recommended_comment_policy`
  - `applicability_boundary`
  - `anchor_policy`
- `case_id`、`hybrid_score` 等字段保留在检索日志里，不注入给模型

prompt 设计口径如下：

- 仍以 `backend/prompts/comment_prompt.py` 作为批注生成 prompt 真源
- 新增 retrieval-aware 渲染入口，但底层复用现有 `comment_prompt.py`
- `system prompt` 只能以条件式描述“你可能会收到 bad_case 参考规则”
- `user prompt` 在有命中时动态拼接 `【bad_case参考规则】`
- prompt 必须明确：
  - bad case 只能指导风险判断、批注口径和锚点策略
  - `reference_text` 仍只能来自当前 `polished_text`
  - 不得把 bad case 文本当作当前正文锚点

日志与验证口径如下：

- 保留现有 `comments_prompt_file`，用于记录最终实际发送给模型的 prompt
- 新增 `comments_bad_case_retrieval_file`，使用 JSON 记录检索过程详情
- 检索日志允许记录完整 `polished_text` 和每个条款的完整正文，方便后续归档
- bad case 检索状态不进入前端 SSE、过程卡或下载卡
- Agent run 审计日志和摘要工具的现有 scrub 红线保持不变
- 第一版测试必须小而闭环，不依赖真实 Word COM 闭环

## 范围

### 包含

- 将 v2 bad case 真源目录正式化
- 把实验脚本中的 v2 解析、条款切分、混合检索和 BM25-only fallback 抽成正式模块
- 为批注 prompt 增加可选 bad case 动态上下文注入
- 接入 `generate_comments`
- 接入仅自主生成模式下的 `comment_agent`
- 新增 prompt 日志和 retrieval JSON 日志
- 让实验脚本复用正式模块
- 增加 focused pytest / prompt / node 测试
- 更新相关长期知识包与系统边界文档

### 不包含

- rewrite 请求模型、rewrite task graph、rewrite skill state
- 前端配置项、前端开关或请求模型扩展
- 自动重建索引、自动 upsert、collection recreate
- 独立 bad case 审查 agent
- 基于 bad case 的确定性冲突裁决逻辑
- 对 bad case 文本做语义合并或压缩重写

## 业务场景

- 场景 1：`workflow` 初次生成批注
  - 系统在 `generate_comments` 调用 LLM 前，根据 `polished_text` 做条款切分和 bad case 检索。
  - 有命中时将 bad case 规则作为优先参考注入 prompt。
  - 无命中或检索失败时回退原 prompt，继续生成批注。

- 场景 2：`agent` 模式自主生成批注
  - `comment_agent` 只有在 `allow_comment_generation=True` 且 `initial_comments=[]` 时才做 bad case 检索增强。
  - 检索发生在 Word 已打开并定位锚点范围之后、真正调用 `run_comment_agent()` 之前。
  - 已有 `initial_comments` 的纯修复模式不注入 bad case。

- 场景 3：`comment_supplement` 补充批注
  - `comment_supplement` 走和自主生成模式相同的检索增强规则。
  - 基于完整 `polished_text` 检索，不再额外从 Word 反抽正文。

- 场景 4：检索链路不可用
  - Qdrant 不可用、embedding 配置缺失、向量调用失败、目录中某个 bad case 文件损坏或条款没有命中时，任务不失败。
  - 系统只记录 warning 和检索日志，继续使用原始批注 prompt。

## 验收口径

- bad case 增强统一作用于 `generate_comments`、自主生成模式下的 `comment_agent` 和 `comment_supplement`。
- rewrite 和 `comment_generation_mode=off` 不会触发 bad case 检索。
- prompt 注入只保留 5 个规则字段，不把 `case_id`、`score` 注入给模型。
- 运行时 hybrid 失败后会自动降级为 BM25-only。
- 无命中或检索失败不阻塞批注生成。
- `comments_prompt_file` 能看到最终发给模型的增强 prompt。
- `comments_bad_case_retrieval_file` 能完整回放条款切分、命中、过滤、注入和降级信息。
- focused tests 覆盖检索运行时、prompt 渲染、`generate_comments` 接入、`comment_agent` 接入和降级路径。

## 待确认问题

- 无

# PRD：批注 bad case 检索增强接入

## 介绍/概述

当前仓库已经有一套用于诊断和实验的批注 bad case 混合检索原型，核心逻辑散落在 `backend/scripts/test_comment_hybrid_retrieval.py` 和 `backend/retrieval/` 中，但它还没有正式接入批注生成主链路。与此同时，现有系统文档仍把 `backend/retrieval/` 标记为实验入口，`generate_comments` 和自主生成模式下的 `comment_agent` 仍完全依赖统一批注 prompt，没有使用 bad case 检索结果。

本功能要把这套能力正式接入所有“AI 新生成批注”的链路，让模型在命中 bad case 时优先参考历史风险模式、推荐批注口径和锚点策略，但仍保留统一 prompt 和自由生成能力。该增强必须具备轻量降级能力：检索不可用时不阻塞批注生成，不增加前端配置，也不改 rewrite。

## 目标

- 把 v2 bad case 真源从实验文件迁入正式目录，并统一后续维护入口。
- 让 `generate_comments`、自主生成模式下的 `comment_agent`、`comment_supplement` 使用同一套 bad case 检索增强规则。
- 将 bad case 作为 prompt-level 优先参考，而不是新增确定性裁决逻辑。
- 在 hybrid 不可用时自动降级到 BM25-only，并保持任务继续完成。
- 生成完整 prompt 日志和 retrieval JSON 日志，支持后续归档与回看。
- 用 focused tests 覆盖检索、prompt、节点接入和降级路径。

## 用户故事

### US-001: 统一 v2 bad case loader 与正式目录
**描述：** 作为维护者，我需要让正式 loader 读取 `backend/retrieval/bad_cases` 目录中的 v2 bad case 文件，以便主链路不再依赖 `test_doc`。

**Acceptance Criteria：**
- [ ] 正式运行时默认把 `backend/retrieval/bad_cases` 作为 bad case 输入目录。
- [ ] `backend/retrieval/bad_cases/comment_bad_cases.md` 会被识别为当前主文件。
- [ ] loader 能解析 `---BEGIN_BAD_CASE--- ... ---END_BAD_CASE---` 结构中的核心字段。
- [ ] loader 生成的 `BadCaseChunk` 仍可被现有 `HybridHit` 和 `BM25Index` 消费。
- [ ] 主链路不再从 `backend/test_doc` 读取 bad case 文件。
- [ ] Typecheck passes
- [ ] Tests pass

### US-002: 实现目录扫描与坏文件跳过
**描述：** 作为维护者，我需要运行时扫描 bad case 目录并跳过损坏文件，以便单个文件错误不会阻断批注生成。

**Acceptance Criteria：**
- [ ] 运行时扫描 `backend/retrieval/bad_cases/*.md` 并按文件名稳定排序加载。
- [ ] 单个 `.md` 文件解析失败时只记录 warning 并继续加载其余正常文件。
- [ ] 目录为空或所有文件都无法解析时，返回 `bad_case_context unavailable`。
- [ ] 检索日志 payload 记录成功加载文件数、失败文件名和失败原因。
- [ ] Typecheck passes
- [ ] Tests pass

### US-003: 缓存 chunks 和 BM25Index
**描述：** 作为维护者，我需要进程内缓存 bad case chunks 和 BM25Index，以便重复生成批注时不重复构建相同内存结构。

**Acceptance Criteria：**
- [ ] 第一次加载 bad case 目录后会缓存 chunks 和 BM25Index。
- [ ] 任一 bad case 文件的 mtime 或 size 变化时，下次调用会自动重载缓存。
- [ ] 每篇 `polished_text` 的检索结果不会进入缓存。
- [ ] 运行时不会创建磁盘缓存文件，也不会写入任何持久缓存。
- [ ] Typecheck passes
- [ ] Tests pass

### US-004: 实现 clause_only 切分与整篇回退
**描述：** 作为维护者，我需要正式运行时复用实验脚本的 `clause_only` 切分逻辑，并在切分失败时回退整篇检索。

**Acceptance Criteria：**
- [ ] 运行时沿用实验脚本的包、章节和数字顿号条款切分规则。
- [ ] 每个检索查询只使用条款正文作为 `clause_only` 查询文本。
- [ ] 当 `polished_text` 无法切出任何条款时，整篇 `polished_text` 作为单个查询单元继续检索。
- [ ] 检索日志 payload 记录 `clause_split_mode` 为 `clause_only` 或 `fallback_full_text`。
- [ ] 第一版不扩展到 `1.1`、`（一）` 或表格单元格级切分。
- [ ] Typecheck passes
- [ ] Tests pass

### US-005: 实现 BM25-only 检索模式
**描述：** 作为维护者，我需要先完成不依赖外部向量服务的 BM25-only 检索，以便 hybrid 不可用时仍有增强能力。

**Acceptance Criteria：**
- [ ] BM25-only 模式使用缓存中的 `BM25Index` 对每个 `clause_only` 查询打分。
- [ ] BM25-only 模式会把 BM25 原始分归一化成 0-1 score。
- [ ] BM25-only 模式对每个条款只保留 top3 且 `score > 0.8` 的命中。
- [ ] BM25-only 命中可以进入后续去重、排序和 prompt context 构建。
- [ ] 检索日志 payload 标记 `retrieval_mode` 为 `bm25_only`。
- [ ] Typecheck passes
- [ ] Tests pass

### US-006: 实现 hybrid 检索与自动降级
**描述：** 作为维护者，我需要在向量链路可用时走 BM25 + vector hybrid，并在任一向量环节失败时自动降级到 BM25-only。

**Acceptance Criteria：**
- [ ] 向量配置和 Qdrant 可用时，运行时使用 BM25 + vector 计算 hybrid score。
- [ ] embedding 配置缺失、embedding 调用失败、Qdrant healthcheck 失败或 Qdrant search 抛错时，自动切换为 BM25-only。
- [ ] hybrid 模式对每个条款只保留 top3 且 `score > 0.8` 的命中。
- [ ] hybrid 失败原因进入 warnings，但不会让批注生成任务失败。
- [ ] 检索日志 payload 标记最终 `retrieval_mode` 为 `hybrid` 或 `bm25_only`。
- [ ] Typecheck passes
- [ ] Tests pass

### US-007: 聚合命中并构建 prompt context
**描述：** 作为维护者，我需要把多条款命中的 bad case 去重、排序并压缩成只含 5 个字段的 prompt 规则块。

**Acceptance Criteria：**
- [ ] 同一个 `case_id` 被多个条款命中时，只保留一次。
- [ ] 同一个 `case_id` 多次命中时，保留最高 score 作为排序依据。
- [ ] 最终注入条目按 score 从高到低排序，分数相同按 `case_id` 稳定排序。
- [ ] 最终注入 prompt 的 bad case 数量上限为 12 条。
- [ ] 注入 prompt 的条目只包含 `risk_type`、`risk_pattern`、`recommended_comment_policy`、`applicability_boundary`、`anchor_policy`。
- [ ] `case_id`、`score` 和命中条款正文不会进入 prompt context。
- [ ] Typecheck passes
- [ ] Tests pass

### US-008: 构建 retrieval JSON 日志 payload
**描述：** 作为维护者，我需要让运行时产出结构化 retrieval JSON payload，以便节点只负责写文件而不重复组织检索详情。

**Acceptance Criteria：**
- [ ] payload 包含 `source_files`、`clause_split_summary`、`retrieval_mode`、warnings 和 failure summary。
- [ ] payload 中每个 clause 记录完整条款正文、过滤前命中和过滤后命中。
- [ ] payload 中 `injected_bad_cases` 记录最终注入清单，并保留 `case_id` 和 score。
- [ ] 无命中、目录不可用或检索失败时也能生成可写入的 payload。
- [ ] payload 不会通过 SSE、下载卡或 `agent_step` 对前端展示。
- [ ] Typecheck passes
- [ ] Tests pass

### US-009: 新增 retrieval-aware 批注 prompt 渲染入口
**描述：** 作为维护者，我需要在不破坏 `render_comment_prompt` 的前提下，新增能接收 `bad_case_context` 的批注 prompt 渲染入口。

**Acceptance Criteria：**
- [ ] 保留现有 `render_comment_prompt` 作为兼容入口。
- [ ] 新增 retrieval-aware 渲染入口，并底层复用现有 `comment_prompt.py`。
- [ ] `bad_case_context` 为空时，新增入口输出与原始入口兼容。
- [ ] `bad_case_context` 非空时，user prompt 会追加结构化 markdown bad case 规则块。
- [ ] system prompt 用条件式文字说明 bad case 规则块可能存在。
- [ ] prompt 明确禁止把 bad case 文本作为 `reference_text`。
- [ ] Typecheck passes
- [ ] Tests pass

### US-010: 接入 generate_comments prompt 增强
**描述：** 作为 workflow 生成用户，我希望 `generate_comments` 在调用模型前自动应用 bad case 检索增强，并在无命中或失败时回退原 prompt。

**Acceptance Criteria：**
- [ ] `generate_comments` 在构造最终 system prompt 和 user prompt 前执行 bad case 检索。
- [ ] 有命中时，压缩后的 `bad_case_context` 注入最终实际发送给模型的 prompt。
- [ ] 无命中时继续使用原始 `comment_prompt`。
- [ ] 检索失败时记录 warning 后继续调用模型，而不是返回新的硬失败。
- [ ] `comments_prompt_file` 保存最终实际发送给模型的 prompt 内容。
- [ ] Typecheck passes
- [ ] Tests pass

### US-011: 为 generate_comments 写入 retrieval JSON 文件
**描述：** 作为维护者，我需要 `generate_comments` 把运行时返回的 retrieval payload 写成 JSON 文件，以便回看每次条款命中过程。

**Acceptance Criteria：**
- [ ] `generate_comments` 为每次 bad case 检索生成一个 `comments_bad_case_retrieval_file` JSON 文件。
- [ ] JSON 文件记录完整 `polished_text`、每个条款完整正文、过滤前命中、过滤后命中、最终注入清单和 warnings。
- [ ] 检索失败时也会写入 failure summary。
- [ ] 该日志不会通过 SSE、下载卡或 `agent_step` 对前端用户展示。
- [ ] Typecheck passes
- [ ] Tests pass

### US-012: 接入自主生成模式下的 comment_agent
**描述：** 作为维护者，我需要让 `comment_agent` 只在自主生成批注时应用 bad case 增强，并保持已有候选修复模式不受影响。

**Acceptance Criteria：**
- [ ] `comment_agent` 只有在 `allow_comment_generation=true` 且 `initial_comments` 为空时才执行 bad case 检索增强。
- [ ] 已有 `initial_comments` 的纯修复模式不会执行 bad case 检索。
- [ ] `comment_agent` 只有在 Word 已打开并解析出批注范围后才执行 bad case 检索。
- [ ] bad case 检索使用完整 `polished_text` 作为输入。
- [ ] 有命中时，`bad_case_context` 拼入 `comment_generation_instruction`；无命中或失败时回退原始 instruction。
- [ ] Typecheck passes
- [ ] Tests pass

### US-013: 让实验脚本复用正式运行时
**描述：** 作为维护者，我需要把 `test_comment_hybrid_retrieval.py` 改成正式运行时的诊断入口，以便主链路和实验入口不再双轨漂移。

**Acceptance Criteria：**
- [ ] 脚本不再保留独立的 v2 解析、条款切分和检索核心逻辑。
- [ ] 脚本默认从 `backend/retrieval/bad_cases` 读取正式 bad case 真源。
- [ ] 脚本仍能输出 `clause_only` 模式下的命中结果。
- [ ] 如果脚本文件当前存在用户本地改动，改造过程会保留用户改动。
- [ ] Typecheck passes
- [ ] Tests pass

### US-014: 更新知识包和系统边界文档
**描述：** 作为维护者，我需要把 retrieval 从实验入口更新为正式批注增强入口，并同步降级和范围边界。

**Acceptance Criteria：**
- [ ] `asset/shared_runtime_word_skill_knowledge_pack.md` 不再把 `backend/retrieval` 描述为纯实验入口。
- [ ] `docs/interfaces-runtime.md`、`INTERFACES.md`、`coding_maps/SYSTEM_MAP.md`、`docs/backend.md` 中关于 retrieval 的实验描述被同步修正。
- [ ] 文档保留 `comment_generation_mode` 是 generate-only 字段且 rewrite 不接入 bad case 检索的边界。
- [ ] 文档说明 hybrid 失败会降级到 BM25-only、检索失败不会阻塞批注生成、retrieval 状态不进入前端展示。
- [ ] `git diff --check` passes
- [ ] Typecheck passes
- [ ] Tests pass

### US-015: 执行 focused 回归验证
**描述：** 作为维护者，我需要用 focused tests 验证检索、prompt、节点边界和图分流，以便确认 bad case 增强没有越界进入 rewrite 或纯修复模式。

**Acceptance Criteria：**
- [ ] retrieval tests 覆盖目录扫描、坏文件跳过、缓存重载、条款切分、fallback、BM25-only、hybrid fallback 和 context 截断。
- [ ] prompt tests 覆盖无 context 兼容输出、有 context 只注入 5 个字段、禁止 bad case 作为 `reference_text`。
- [ ] node tests 覆盖 `generate_comments` 有命中、无命中、检索失败降级，以及 `comment_agent` 自主生成才注入。
- [ ] graph tests 覆盖 `comment_generation_mode=off` 时 workflow 和 agent 分支都不触发 bad case 检索。
- [ ] 所有新测试都使用 fake 或 mock，不依赖真实 Qdrant、embedding provider 或 Word COM。
- [ ] `git diff --check` passes
- [ ] Typecheck passes
- [ ] Tests pass

## Functional Requirements

- FR-1: 系统必须以 `backend/retrieval/bad_cases/` 作为 bad case 正式真源目录。
- FR-2: 系统必须支持 v2 bad case 结构解析和目录扫描。
- FR-3: 系统必须在运行时缓存 bad case chunks 和 BM25Index，并在文件变化时自动重载。
- FR-4: 系统必须对 `polished_text` 做 `clause_only` 条款切分，并支持全文回退检索。
- FR-5: 系统必须支持 BM25-only，并在向量链路可用时优先使用 hybrid。
- FR-6: 系统必须将命中的 bad case 去重、排序并压缩为最多 12 条 prompt 规则。
- FR-7: 系统必须构建 retrieval JSON payload，并由节点写入 JSON 文件。
- FR-8: 系统必须新增 retrieval-aware 的批注 prompt 渲染入口。
- FR-9: 系统必须把 bad case 检索增强接入 `generate_comments`。
- FR-10: 系统必须把 bad case 检索增强接入仅自主生成模式下的 `comment_agent`。
- FR-11: 系统必须在检索失败、无命中或坏文件场景下降级继续，不阻塞批注生成。
- FR-12: 系统必须让实验脚本复用正式运行时模块。
- FR-13: 系统必须补齐 focused tests 和知识包文档。

## Non-Goals

- 不新增前端配置或后端请求模型字段。
- 不把 bad case 检索接入 rewrite。
- 不新增独立 bad case 审查 agent。
- 不实现基于 bad case 的确定性冲突裁决逻辑。
- 不实现运行时自动重建索引、自动 upsert 或 collection recreate。
- 不对 bad case 内容做语义合并。

## Design Considerations

- prompt 必须保持“统一批注真源 + 可选增强块”的结构，不创建第二套完整批注 prompt。
- `system prompt` 必须用条件式语气描述 bad case 块可能存在，避免无命中时显得突兀。
- 注入字段要克制，优先减少对模型上下文的干扰。
- retrieval 日志以结构化 JSON 为主，便于后续集中归档。
- 每个 Ralph story 都应是可独立验证的增量，不把 runtime、节点和文档打包在同一个 story 中。

## Technical Considerations

- 当前 `backend/retrieval/bad_case_loader.py` 仍偏旧格式解析，需要和 v2 真源格式统一。
- 当前实验脚本仍保留独立的 v2 解析与检索逻辑，正式接入后应收敛到单一运行时模块。
- 当前文档把 `backend/retrieval/` 标记为实验入口，接入主链路后必须同步文档边界。
- `comment_prompt.py` 仍是现有批注生成 prompt 真源，新增增强入口应在此基础上扩展。
- `comment_agent` 只有在自主生成模式下才能注入 bad case，不能污染已有候选的锚点修复模式。

## Success Metrics

- 有命中时，`generate_comments` 与自主生成模式下的 `comment_agent` 都能使用 bad case 增强 prompt。
- 向量链路异常时能自动切到 BM25-only，并继续生成批注。
- 无命中、坏文件、collection 缺失或 retrieval 失败时任务不新增硬失败。
- retrieval JSON 能完整回放本次检索与注入过程。
- focused tests 覆盖主接入点和降级路径。

## Open Questions

- 无

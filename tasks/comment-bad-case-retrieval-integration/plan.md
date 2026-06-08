# 功能: 批注 bad case 检索增强接入

下面这份计划用于 Ralph / GPT-5.4 单窗口执行。实现代理开始前仍必须重新读取当前代码和任务目录，尤其要注意工作区可能已有用户改动，不能回滚无关修改。

## 功能描述

把当前只作为诊断/实验入口存在的批注 bad case 检索能力，正式接入所有“AI 新生成批注”的后端链路：

- `workflow` 分支的 `generate_comments`
- `agent` 分支中自主生成批注的 `comment_agent`
- `comment_supplement` 补充批注任务

接入方式是 prompt-level soft priority：命中 bad case 时，把历史风险模式、推荐批注口径和锚点策略作为优先参考注入批注 prompt；无命中或检索失败时回退原 prompt，不阻塞任务。不新增独立审查 agent，不做确定性冲突裁决，不进入 rewrite，不增加前端配置。

## 单窗口粒度审查结论

原始任务目录的方向正确，但有三个会影响 Ralph 一次迭代成功率的问题：

1. `plan.md` 把“正式运行时模块”写成一个大任务，单个 story 会同时承担 loader、缓存、检索、上下文压缩和日志，容易超出一个窗口。
2. 测试被后置为大包，不利于每个可验证增量失败后快速重试。
3. `bad_case_loader.py` 更新策略偏侵入；更稳的做法是保留现有数据结构，逐步增加 v2 loader 能力，并让上层运行时收敛调用。

本次优化后，Ralph 执行顺序改为 15 个更小的增量。每个 US 都应该能在一个 GPT-5.4 window context 内完成，并且都有本地 pytest 或文档校验作为闭环。

## 用户故事

作为 TenderWord 维护者，我想把 bad case 混合检索变成所有 AI 新生成批注的统一增强规则，以便复用历史风险知识，同时保持生成链路轻量、可降级、可追溯。

## 问题陈述

当前代码事实：

- `backend/retrieval/bad_case_loader.py` 仍偏旧格式解析，和 v2 `---BEGIN_BAD_CASE---` 真源不一致。
- `backend/scripts/test_comment_hybrid_retrieval.py` 里有可复用的 v2 解析、`clause_only` 切分、去重和阈值逻辑，但它现在仍是实验脚本。
- `backend/prompts/comment_prompt.py` 是批注 prompt 真源，`generate_comments` 和自主生成模式下的 `comment_agent` 还没有 bad case 增强。
- 项目文档仍把 `backend/retrieval/` 标成实验/诊断入口；正式接入后必须同步边界。

## 方案陈述

新增正式的 bad case retrieval runtime，职责仅限后端检索增强：

- 扫描 `backend/retrieval/bad_cases/*.md`
- 解析 v2 bad case
- 缓存 bad case chunks 和 BM25Index
- 用 `clause_only` 切分 `polished_text`
- 优先 hybrid，失败后 BM25-only
- 按 `top3 + score > 0.8` 命中
- 按 `case_id` 去重、保留最高分、最多注入 12 条
- 构建 prompt 5 字段上下文
- 构建 retrieval JSON 日志 payload

Prompt Layer 只负责渲染。节点负责调用 runtime、写 prompt/retrieval 日志和降级。Graph、SSE、前端、rewrite 请求模型不参与本功能。

## 功能元数据

**功能类型**: 增强
**预估复杂度**: 中高
**主要受影响系统**: `backend/retrieval/`、Prompt Layer、`generate_comments`、`comment_agent`、测试、知识包与根级接口文档
**依赖项**: 现有 BM25/Qdrant/embedding 工具、`backend/prompts/comment_prompt.py`、`backend/agents/comments/` 运行时、后端 prompt 日志目录

---

## 上下文参考

### 相关代码文件

- `backend/retrieval/bad_case_loader.py`
  当前 `BadCaseChunk` 数据结构和旧格式 loader。实现时优先复用 `BadCaseChunk`，不要让主链路依赖两套 chunk 类型。
- `backend/retrieval/bm25.py`
  BM25Index 真源，BM25-only fallback 必须复用它。
- `backend/retrieval/hybrid.py`
  hybrid score 与 `HybridHit` 真源；不要在节点层重新实现 hybrid。
- `backend/retrieval/config.py`
  retrieval 配置加载真源。缺 embedding key 或 Qdrant 不可用时不能让主任务硬失败。
- `backend/retrieval/qdrant_store.py`
  向量检索入口。运行时只查询，不 upsert、不 recreate collection。
- `backend/retrieval/bad_cases/comment_bad_cases.md`
  当前正式 bad case 主文件，v2 结构真源。
- `backend/scripts/test_comment_hybrid_retrieval.py`
  现有实验脚本，当前工作区中已有本地改动；重构前必须先读取并保留这些改动。
- `backend/prompts/comment_prompt.py`
  批注生成 prompt 真源。新增 retrieval-aware 入口必须底层复用它。
- `backend/nodes/common_word_nodes/generate_comments.py`
  workflow 批注生成节点，当前已写 prompt/raw/repaired/new_comments 日志。
- `backend/nodes/common_word_nodes/comment_agent.py`
  agent/comment_supplement 的批注写回节点。只有 `allow_comment_generation=True && initial_comments=[]` 时接入。
- `backend/agents/comments/comment_agent.py`
  `comment_agent` 系统 prompt、用户 prompt 和工具门禁真源，不要在本功能里改工具语义。
- `backend/graphs/base_graph.py`
  `generation_mode` / `comment_generation_mode` 分流边界。`comment_generation_mode=off` 时完全不做检索。
- `backend/graphs/comment_supplement_graph.py`
  补充批注 graph，复用 `comment_agent`。
- `backend/tests/nodes/test_comment_agent_writeback_node.py`
  已有自主生成模式 prompt 构造测试，应扩展。
- `backend/tests/prompts/test_comment_prompt_reference_contract.py`
  已有锚点契约测试，应扩展 bad case 不能作为 `reference_text`。

### 需要创建的新文件

- `backend/retrieval/comment_bad_case_runtime.py`
- `backend/tests/retrieval/test_comment_bad_case_runtime.py`
- `backend/tests/prompts/test_comment_prompt_bad_case_context.py`
- `backend/tests/nodes/test_generate_comments_bad_case.py`

### 需要更新的现有文件

- `backend/retrieval/bad_case_loader.py`
- `backend/prompts/comment_prompt.py`
- `backend/nodes/common_word_nodes/generate_comments.py`
- `backend/nodes/common_word_nodes/comment_agent.py`
- `backend/scripts/test_comment_hybrid_retrieval.py`
- `backend/tests/nodes/test_comment_agent_writeback_node.py`
- `backend/tests/prompts/test_comment_prompt_reference_contract.py`
- `asset/shared_runtime_word_skill_knowledge_pack.md`
- `docs/interfaces-runtime.md`
- `INTERFACES.md`
- `coding_maps/SYSTEM_MAP.md`
- `docs/backend.md`
- 如需要，`ARCHITECTURE.md`

### 相关文档

- `AGENTS.md`
  保持 rewrite、prompt、SSE、日志和密钥红线。
- `docs/backend.md`
  后端边界和 retrieval 状态。
- `docs/interfaces-runtime.md`、`INTERFACES.md`
  运行时契约、`comment_generation_mode`、补充批注、retrieval 边界。
- `coding_maps/SYSTEM_MAP.md`
  系统地图中的 retrieval 实验入口描述。
- `asset/shared_runtime_word_skill_knowledge_pack.md`
  Prompt Layer、comment_agent、日志和知识包事实。

### 必须遵循的模式

- Prompt builder 只做纯渲染，不做检索、日志、Word COM 或状态变更。
- 运行时只读 bad case 文件和 Qdrant，不自动 upsert、不 recreate collection、不重建向量索引。
- 检索失败只影响是否注入 bad_case_context，不改变批注生成成功/失败语义。
- `comment_agent` 有 `initial_comments` 时是锚点修复模式，不注入 bad case。
- bad case 检索状态不进入前端 SSE、agent_step、下载卡。
- 检索日志可以记录完整 `polished_text` 和条款正文；agent run 审计日志仍按 scrub 红线。

---

## Ralph 执行切片

### US-001 统一 v2 bad case loader 与正式目录

- **目标**: 让正式 loader 和运行时读取 `backend/retrieval/bad_cases/comment_bad_cases.md`。
- **主要文件**: `backend/retrieval/bad_case_loader.py`, `backend/retrieval/bad_cases/comment_bad_cases.md`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\retrieval\\test_comment_bad_case_runtime.py -k "loader or v2" -v`
- **注意**: 不要删除旧格式解析，除非测试证明没有依赖；优先兼容。

### US-002 实现目录扫描与坏文件跳过

- **目标**: 支持 `backend/retrieval/bad_cases/*.md` 多文件扫描，坏文件 warning 后跳过。
- **主要文件**: `backend/retrieval/comment_bad_case_runtime.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\retrieval\\test_comment_bad_case_runtime.py -k "directory or bad_file or unavailable" -v`
- **注意**: 目录为空或全部失败必须返回 unavailable，不抛硬错误。

### US-003 缓存 chunks 和 BM25Index

- **目标**: 基于文件 `mtime + size` 做进程内缓存重载。
- **主要文件**: `backend/retrieval/comment_bad_case_runtime.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\retrieval\\test_comment_bad_case_runtime.py -k cache -v`
- **注意**: 不缓存每篇 `polished_text` 检索结果。

### US-004 实现 clause_only 切分与整篇回退

- **目标**: 抽正式 splitter，沿用实验脚本的包/章节/数字顿号规则。
- **主要文件**: `backend/retrieval/comment_bad_case_runtime.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\retrieval\\test_comment_bad_case_runtime.py -k clause -v`
- **注意**: 第一版不扩展编号体系。

### US-005 实现 BM25-only 检索模式

- **目标**: 在不依赖向量服务的情况下完成 `top3 + score > 0.8` 检索。
- **主要文件**: `backend/retrieval/comment_bad_case_runtime.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\retrieval\\test_comment_bad_case_runtime.py -k bm25 -v`
- **注意**: BM25 原始分需要归一化成 0-1 score。

### US-006 实现 hybrid 检索与自动降级

- **目标**: 向量链路可用时走 hybrid，不可用时自动 BM25-only。
- **主要文件**: `backend/retrieval/comment_bad_case_runtime.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\retrieval\\test_comment_bad_case_runtime.py -k "hybrid or fallback" -v`
- **注意**: 缺 embedding key、Qdrant 不可达、Qdrant search 抛错都不能让主任务失败。

### US-007 聚合命中并构建 prompt context

- **目标**: `case_id` 去重、保留最高分、最多 12 条、输出 5 字段 prompt context。
- **主要文件**: `backend/retrieval/comment_bad_case_runtime.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\retrieval\\test_comment_bad_case_runtime.py -k "dedupe or context or limit" -v`
- **注意**: prompt context 不包含 `case_id`、`score`、命中条款正文。

### US-008 构建 retrieval JSON 日志 payload

- **目标**: runtime 返回结构化 payload，节点只负责写 JSON 文件。
- **主要文件**: `backend/retrieval/comment_bad_case_runtime.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\retrieval\\test_comment_bad_case_runtime.py -k "log or payload" -v`
- **注意**: 无命中和失败也要有可写 payload。

### US-009 新增 retrieval-aware prompt 渲染入口

- **目标**: 新增可选 bad case context 渲染入口，保留 `render_comment_prompt()`。
- **主要文件**: `backend/prompts/comment_prompt.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\prompts\\test_comment_prompt_bad_case_context.py tests\\prompts\\test_comment_prompt_reference_contract.py -v`
- **注意**: system prompt 必须条件式说明；user prompt 只在有 context 时追加规则块。

### US-010 接入 generate_comments prompt 增强

- **目标**: `generate_comments` 在 LLM 调用前执行检索并选择增强 prompt 或原 prompt。
- **主要文件**: `backend/nodes/common_word_nodes/generate_comments.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\nodes\\test_generate_comments.py tests\\nodes\\test_generate_comments_bad_case.py -v`
- **注意**: 检索失败只能 warning + 降级，不能改变节点返回语义。

### US-011 为 generate_comments 写入 retrieval JSON 文件

- **目标**: 生成 `comments_bad_case_retrieval_file`，记录完整检索过程。
- **主要文件**: `backend/nodes/common_word_nodes/generate_comments.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\nodes\\test_generate_comments_bad_case.py -k "retrieval_log or failure_summary" -v`
- **注意**: prompt 文件保持纯净，只保存实际发给模型的 prompt；状态元数据放 retrieval JSON。

### US-012 接入自主生成模式下的 comment_agent

- **目标**: 仅 `allow_comment_generation=True && initial_comments=[]` 时，在 Word 范围定位后接入增强。
- **主要文件**: `backend/nodes/common_word_nodes/comment_agent.py`, `backend/agents/comments/comment_agent.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe -m pytest tests\\nodes\\test_comment_agent_writeback_node.py -v`
- **注意**: 不改工具门禁；不让已有候选修复模式接收 bad case。

### US-013 让实验脚本复用正式运行时

- **目标**: `test_comment_hybrid_retrieval.py` 变成诊断入口，不再保留独立核心逻辑。
- **主要文件**: `backend/scripts/test_comment_hybrid_retrieval.py`
- **建议验证**: `cd backend; .\\.venv\\Scripts\\python.exe scripts\\test_comment_hybrid_retrieval.py --top-k 3 --clause-limit 2`
- **注意**: 该脚本在当前工作区已有本地修改；改造前必须读取并保留。

### US-014 更新知识包和系统边界文档

- **目标**: 文档不再把 retrieval 描述为纯实验入口。
- **主要文件**: `asset/shared_runtime_word_skill_knowledge_pack.md`, `docs/interfaces-runtime.md`, `INTERFACES.md`, `coding_maps/SYSTEM_MAP.md`, `docs/backend.md`
- **建议验证**: `git diff --check`
- **注意**: 同步写清降级行为、日志出口、rewrite 不接入和 `comment_generation_mode=off` 边界。

### US-015 执行 focused 回归验证

- **目标**: 一次性验证检索、prompt、节点和图分流边界。
- **建议验证**:

```powershell
cd backend
.\\.venv\\Scripts\\python.exe -m pytest tests\\retrieval\\test_comment_bad_case_runtime.py tests\\prompts\\test_comment_prompt_bad_case_context.py tests\\prompts\\test_comment_prompt_reference_contract.py -v
.\\.venv\\Scripts\\python.exe -m pytest tests\\nodes\\test_generate_comments.py tests\\nodes\\test_generate_comments_bad_case.py tests\\nodes\\test_comment_agent_writeback_node.py -v
.\\.venv\\Scripts\\python.exe -m pytest tests\\graphs\\test_generation_mode_branching.py tests\\services\\test_document_service_comment_supplement.py tests\\agents\\test_comment_agent.py -v
```

- **注意**: 所有新测试使用 fake/mock，不依赖真实 Qdrant、embedding provider 或 Word COM。

---

## 测试策略

### 单元测试

- `backend/tests/retrieval/test_comment_bad_case_runtime.py`
  - v2 loader
  - 目录扫描和坏文件跳过
  - 缓存重载
  - 条款切分和全文回退
  - BM25-only
  - hybrid fallback
  - context 去重、排序和上限
  - retrieval payload
- `backend/tests/prompts/test_comment_prompt_bad_case_context.py`
  - 无 context 兼容输出
  - 有 context 只注入 5 个字段
  - bad case 不得作为 `reference_text`

### 节点测试

- `backend/tests/nodes/test_generate_comments_bad_case.py`
  - 有命中注入
  - 无命中回退
  - 检索失败降级
  - retrieval JSON 写入
- `backend/tests/nodes/test_comment_agent_writeback_node.py`
  - 自主生成模式下注入
  - 已有 `initial_comments` 不注入
  - Word 范围定位后才检索

### 图与服务回归

- `backend/tests/graphs/test_generation_mode_branching.py`
- `backend/tests/services/test_document_service_comment_supplement.py`
- `backend/tests/agents/test_comment_agent.py`

---

## 验证命令

### 级别 1：文档和差异检查

```powershell
git diff --check
```

### 级别 2：retrieval 和 prompt

```powershell
cd backend
.\\.venv\\Scripts\\python.exe -m pytest tests\\retrieval\\test_comment_bad_case_runtime.py tests\\prompts\\test_comment_prompt_bad_case_context.py tests\\prompts\\test_comment_prompt_reference_contract.py -v
```

### 级别 3：节点接入

```powershell
cd backend
.\\.venv\\Scripts\\python.exe -m pytest tests\\nodes\\test_generate_comments.py tests\\nodes\\test_generate_comments_bad_case.py tests\\nodes\\test_comment_agent_writeback_node.py -v
```

### 级别 4：关键回归

```powershell
cd backend
.\\.venv\\Scripts\\python.exe -m pytest tests\\graphs\\test_generation_mode_branching.py tests\\services\\test_document_service_comment_supplement.py tests\\agents\\test_comment_agent.py -v
```

### 级别 5：脚本诊断

```powershell
cd backend
.\\.venv\\Scripts\\python.exe scripts\\test_comment_hybrid_retrieval.py --top-k 3 --clause-limit 2
```

---

## 验收标准

- [ ] 正式 bad case 真源目录为 `backend/retrieval/bad_cases/`，并支持多文件扫描。
- [ ] 主链路统一使用 v2 bad case 结构解析。
- [ ] `generate_comments` 在有命中时使用 bad case 增强 prompt，在失败时平滑降级。
- [ ] `comment_agent` 仅在自主生成模式下注入 bad case，纯修复模式不注入。
- [ ] `comment_generation_mode=off` 完全不做 bad case 检索。
- [ ] retrieval 支持 hybrid -> BM25-only 自动降级。
- [ ] prompt 注入只保留 5 个规则字段，不包含 `case_id`、`score`。
- [ ] `comments_prompt_file` 保存最终发送给模型的 prompt。
- [ ] `comments_bad_case_retrieval_file` 以 JSON 记录完整检索过程。
- [ ] 实验脚本复用正式运行时模块。
- [ ] focused tests 覆盖检索、prompt、节点接入和降级路径。
- [ ] 根级文档与知识包不再把 retrieval 描述为实验入口。

## 完成检查清单

- [ ] 没有把 bad case 检索接入 rewrite。
- [ ] 没有新增前端配置或请求模型字段。
- [ ] 没有把 retrieval 状态透传到前端 SSE、过程卡或下载卡。
- [ ] 没有让 `comment_agent` 的已有候选修复模式接收 bad case 注入。
- [ ] 没有在运行时执行 upsert、recreate collection 或持久缓存写入。
- [ ] 保持 `comment_prompt.py` 为统一批注生成 prompt 真源。
- [ ] 所有新增测试使用 fake/mock，而不是依赖真实 Qdrant、embedding 或 Word COM。

## 备注

- 当前工作区里 `backend/scripts/test_comment_hybrid_retrieval.py` 已有用户本地修改。执行代理在改造脚本前必须先读取并理解这些改动，避免覆盖用户改动。
- 当前系统文档仍把 `backend/retrieval/` 描述为实验入口，这既是需求输入，也是必须修复的同步面。
- 本需求不改变 `comment_writeback`、`comment_agent` 工具门禁、SSE event type 和 `comment_generation_mode` 的 generate-only 边界。
- 一次实现成功预估信心分数：9/10。

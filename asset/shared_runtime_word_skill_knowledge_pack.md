# 共享运行时、Word 与 Skill 边界知识包

## 背景与范围

本包适用于后端 generate / rewrite / comment_supplement 运行时、Prompt Layer、task skill runtime、Word COM、共享 Word helper、批注/样式回写、任务结果与 SSE 透传相关改动。

本包只记录当前仍存在的共享主干、稳定契约、验证入口和回归风险；实现细节以代码为准，不保留历史分叉、临时脚本或已删除文件名。

## 当前真源

- 任务创建与运行时装配：`backend/services/document_service.py`
- 招标详情数据契约：`backend/api/tender.py`、`backend/models/tender.py`、`backend/util/common_util/fetch_tender_data.py`
- 生成任务 REST 入口：`backend/api/generate.py`
- 补充批注任务 REST 入口：`backend/api/comment_supplement.py`
- Graph 主干、锁、取消与进度包装：`backend/graphs/base_graph.py`、`backend/task/task_queue_manager.py`
- 补充批注 Graph：`backend/graphs/comment_supplement_graph.py`
- 初次生成智能体运行时：`backend/agents/generation/`
- 批注锚点智能体运行时：`backend/agents/comments/`
- task skill runtime：`backend/graphs/skill_graph.py`、`backend/skills/`
- Prompt Layer：`backend/prompts/`
- Word 业务 helper：`backend/helper/word_helper/`
- SSE 与日志透传：`backend/core/sse_manager.py`、`backend/api/stream.py`、`backend/models/sse.py`、`backend/util/log_util/`
- Agent/chat NDJSON 行序列化：`backend/services/chat_stream_service.py`
- Agent workspace 日志命名：`backend/agents/log_naming.py`
- 批注坏案例检索：`backend/retrieval/` 是 `generate_comments`、自主生成模式 `comment_agent` 和 `comment_supplement` 的正式 prompt 增强入口；坏案例真源目录是 `backend/retrieval/bad_cases/`，rewrite 不接入该检索。

## 运行时分层

### 招标详情 API

- `GET /api/tender/{tender_no}` 会把外部招标详情接口数据装配成 `backend.models.tender.TenderData`；外部接口字段类型可能波动，例如 `investment` 可能返回数字而不是字符串。
- `TenderData` 是前端表单和后续 generate/rewrite 快照的文本契约边界；预算、项目编号、联系人、日期、平台等文本字段必须在模型边界转成字符串，不能把可显示数字误判成“招标数据格式错误”。
- 排查“输入招标编号显示格式错误”时，先看后端响应体里的 Pydantic 字段错误；若外部数据已返回且只是字段类型不匹配，应修归一化契约，而不是收紧招标编号格式。
- 未支持的外部采购方式不能阻断信息展示：`TenderType.purchase_method` 保留外部原值，当前只把 `0/2/5` 视为可路由类型；其它值通过 `/api/tender` 的 `warning` 透传给前端黄色提示，并由用户当前页面/按钮状态决定后续生成 graph。

### Generate / Rewrite

- generate 任务通过 `DocumentService.create_task()` 进入 `GRAPH_REGISTRY`，按 `GenerateRequest.form_type` 选择具体 graph。
- `GET /api/generate/{task_id}` 必须通过 `backend.services.task_service` 查询任务状态；API 路由中的函数内延迟导入也要使用 `backend.*` 包绝对路径，避免在不同启动/测试入口下退化为 `ModuleNotFoundError`。
- rewrite 走 `backend/graphs/skill_graph.py` 中的显式 `RewriteSkillGraph`；图结构（节点、边、条件分支、节点数估算）真源就在 `skill_graph.py`，`backend/skills/rewrite/SKILL.md` 只保留 DeepAgents guide 和后台正文改写指令，不再承担 task workflow 装配。
- `POST /api/agent/runs/stream` 默认由 `backend/services/agent_run_service.py` 构造 `TaskContextDeepAgentsRunner`，再调用 `backend/agents/task_context_assistant/factory.py#create_task_context_assistant()`；生产路径的语义选择属于 DeepAgents + rewrite skill，不应在 service 层用关键词 `_select_skill()` 判断。service 层只做客观不可执行条件 preflight、NDJSON 事件映射和审计落盘。
- task-context assistant 创建 rewrite 任务只能通过 `backend/agents/task_context_assistant/tools.py` 中的 `create_rewrite_task_tool` 复用 `DocumentService.create_rewrite_task()`；guard 先检查上传 Word 文件链路，其次检查 `rewrite history`，缺条件时返回 `needs_input`，不能直接操作 Word COM。
- `POST /api/agent/runs/stream` 必须先流出 `run_started` 和 `thinking_stage: understand completed`，再等待 `create_rewrite_task_tool` 创建 rewrite 任务；任务创建慢时前端过程卡应推进到上下文检查阶段，不能卡在“理解需求”。
- agent run NDJSON 事件来自 Pydantic `model_dump()` 并经 service 层共享辅助序列化为单行事件；可选字段会以 `null` 出现。前端 parser 必须把 `selected_skill: null`、`guard_result: null`、`tool_name: null` 和 `task_id: null` 当作缺省值处理，不能静默丢弃后续 `needs_input` / `done` 终态；新增 agent/chat 流事件时不要在调用方各自手写 JSON 行。
- 会话已有可改写文档时，用户直接输入带章节号、指标、条款等文档定位线索和“需要/增加/调整/★/▲”等编辑线索的要求，应由 task-context DeepAgents 根据上下文选择 rewrite；“生成内容太多换行 / 内容需要紧凑 / 排版格式调整”等已生成内容风格或排版修改也属于 rewrite 语义。不要强迫用户显式输入 `$rewrite` 或“改写/重写”。
- 上传 Word 文件后的修改统一走 rewrite。上传文件 rewrite 必须有非空用户重写指令、上传文件路径、当前页面 `form_type`、完整锚点、`tender_lx` 和 `fund_source_lx`；`tender_data_snapshot` 只是可选快照，不能因为未获取招标数据而阻断上传文件 rewrite。缺任一关键上下文时只返回 `needs_input`，不能自动猜测文档类型或锚点。
- 上传文件 rewrite 依赖 `rewrite_source="uploaded_file"` 在 `TaskSkillGraphState` 中穿过 LangGraph schema，再由 `select_resolve_branch()` 路由到 `extract_rewrite_context`；新增分支标记必须同步声明到 task skill state，避免初始 state 被过滤后误回落到 rewrite history。
- 上传文件 rewrite 的 task graph 必须保持单次 Word 删除：`extract_rewrite_context -> rewrite_text -> delete_section -> update_word`。不要同时保留 `extract_rewrite_context -> delete_section` 和 `rewrite_text -> delete_section`，否则 `delete_section` 会执行两次并可能与 `update_word` 并发抢占同一 Word COM 文档。
- `backend/agents/task_context_assistant/factory.py` 是右侧 agent run DeepAgents 工厂真源。运行时 backend 必须通过 `CompositeBackend` 把 `/skills/`、`/scratch/`、`/workspace/` 分隔到独立 `FilesystemBackend(virtual_mode=True)`；`/skills/` 只镜像 rewrite 受控 skill 目录，不能裸挂项目根、`.env`、`backend/logs` 或任意本机绝对路径。
- `backend/agents/task_context_assistant/logging.py` 是 agent run JSONL 审计真源：每个 run 写 `backend/logs/agent-run-<run_id>.jsonl`，只记录白名单结构化字段（`run_id`、`conversation_id`、`selected_skills`、阶段摘要、`guard_result`、`tool_name`、`task_id` 等），并统一 scrub 掉凭证、认证头、`.env`、私有绝对路径、完整原文和 traceback。生成/批注 agent workspace 与审计日志的文件名片段复用 `backend/agents/log_naming.py`，新增 agent workspace 不要复制独立清洗规则。
- task-context assistant 读取上下文时不能直接读 `backend/logs` 或任务结果原始 payload；必须通过 `read_current_conversation_summary_tool` / `read_current_task_public_summary_tool` 这种受控工具，只返回当前会话的最近 agent run 摘要、rewrite 可用性和任务公共进度概览，不暴露输出路径、完整结果或隐藏推理。
- `/api/edit`、edit skill、edit task kind 和 `create_edit_task_tool` 已删除；右侧聊天与任务判路统一走 `POST /api/agent/runs/stream`，不再保留 `/api/user/stream` 或 edit 兼容入口。
- `POST /api/comment-supplement` 是独立补充批注入口；请求只携带会话、当前下载卡文件路径和模型。`DocumentService.create_comment_supplement_task()` 必须校验 latest `rewrite_state`、`polished_text`、当前文件存在且等于 latest `prepared_doc_path` 后才创建任务。
- `generation_mode`、`generation_style`、`comment_generation_mode` 与 `style_writeback_mode` 都是 generate-only 字段：`DocumentService._build_initial_state()` 可写入 generate state，rewrite 请求模型和初始 state 不得注入这些字段。
- `generation_mode` 当前只允许 `workflow` 与 `agent`，默认 `workflow`。`workflow` 继续走 `generate_polished_text`，保留 `render_generate_prompt()`、`stream_llm_completion()` 和旧 `llm` snapshot 事件；`agent` 只影响初次 generate 的生成节点选择，最终仍必须产出 `polished_text` 给批注开关开启时的批注分支、样式回写、Word 写回和下载主干。
- `comment_generation_mode` 当前只允许 `on` 与 `off`，默认 `on`。`on` 时 workflow generate 继续经过 `generate_comments`，agent generate 继续在 `update_word` 后经过公共 `comment_agent`；`off` 时两种生成方式都跳过批注生成逻辑和 bad case 检索增强，并在 `comments_branch_done` 设置 `suppress_ai_comment_writeback=True`、清空临时批注计数。
- generate 成功后的后端 `rewrite_state` 可以保留 `generation_mode`、`polished_text`、`prepared_doc_path` 和后续链路所需的稳定运行态字段；初次生成时的临时批注推导结果不应进入任务 result、SSE `done`、前端下载卡 metadata 或 `sessionStorage`。
- 标准生成 graph 的分流只在 `StandardTenderWorkflowGraph` 基类实现：`generation_mode_gate` 后按 `_select_generation_node()` 进入 `generate_polished_text` 或 `content_agent`；正文生成后再按 `comment_generation_mode` 选择 workflow 的 `generate_comments` 或跳过，`update_word` 后再按 `generation_mode=agent && comment_generation_mode=on` 选择是否进入公共 `comment_agent`。类型 graph 不应复制这段分流。
- `generation_mode=agent` 的 `update_word` 只负责正文、样式和保存：`comments_branch_done` 会在 agent 分支或 `comment_generation_mode=off` 时设置 `suppress_ai_comment_writeback=True`，各类型 update 节点必须跳过确定性 AI 批注写回；`comment_generation_mode=on` 时，agent generate 的 `update_word` 完成后由标准 graph 路由到公共 `comment_agent` 节点，workflow 分支不得进入该节点。agent generate 无 `polished_comments` 时，`comment_agent` 可复用 `backend/prompts/comment_prompt.py` 自主生成批注候选。
- 公共 `comment_agent` graph 节点位于 `backend/nodes/common_word_nodes/comment_agent.py`，只作为批注增强项运行：它重新按锚点解析 Word 正文范围，调用 `backend/agents/comments/run_comment_agent()`，并把结果收敛成 `comment_writeback` 摘要；自主生成批注时会基于完整 `polished_text` 应用 bad case prompt 增强，已有 `initial_comments` 的锚点修复模式不执行检索；节点异常、保存失败、上下文缺失或检索失败只能降级为 warning，不能让已保存正文的 generate 任务失败。
- `comment_agent` 不再让模型做二轮锚点修复：模型只生成首版批注候选，代码负责确定性定位和写回。`validate_comment_references` 的 `ToolCallLimitMiddleware` 收敛为 `run_limit=1`，第二次校验调用会被拦住并以审计形式落盘，不再抛错阻断任务；`initial_comments` 非空（非自主生成）时直接跳过 runner，对现有候选做确定性校验和写回。
- 批注写回统一收敛到 `backend/nodes/common_word_nodes/comment_writeback.py::write_polished_comments()`：workflow、agent generate、comment_supplement、`comment_agent` 工具写回 (`write_validated_comment_candidates_to_word`) 都复用同一套 helper，`comment_agent` 不再保留独立的 `_find_word_anchor_ranges()`。重复锚点不再直接失败：共享写回层对所有未批注的真实重复位置分别写入同一条批注，已有批注的位置计入 `overlapping_comment_exists` 跳过，找不到目标才计入 warning/failed。`validate_comment_reference_candidates` 中“正文中出现多次”改为可写入状态（`reference_text_non_unique_will_expand_on_writeback`），不再进入 failed。
- `comment_agent` 运行异常和写回异常分支也必须写 comment agent audit JSON，至少包含 `tool_snapshots`、`validation_results`、`final_proposed_comments`、`writeback_result` 和错误文本；最终统计以实际 Word 写回结果为准。
- 独立 `comment_supplement` 任务通过 `CommentSupplementGraph` 执行，节点顺序为 `prepare_comment_supplement -> comment_agent -> finalize_comment_supplement`。准备节点复制 latest 文档为新副本；`comment_agent` 在补充批注任务里直接基于 latest `rewrite_state.polished_text` 复用 `comment_prompt.py` 和 bad case prompt 增强生成批注候选，再做锚点校验和 Word 写回；完成后会话最新 `rewrite_state.prepared_doc_path` 指向补充批注后的副本，后续 rewrite 应继续使用该路径。
- bad case 检索运行时优先尝试 hybrid；embedding 配置、向量调用、Qdrant healthcheck 或 search 不可用时自动降级到 `bm25_only`。无命中、坏文件或检索失败都只写 retrieval JSON / warning，不阻塞批注生成，也不把检索状态、日志路径或命中详情透传到 SSE、下载卡或 `agent_step`。
- bad case loader 必须同时支持 v2 `---BEGIN_BAD_CASE---` 块格式和旧格式；目录入口按文件名稳定扫描 `backend/retrieval/bad_cases/*.md`，单个坏文件只进入 warning / failure payload，不能阻断其它有效文件加载。
- `load_bad_case_runtime_index()` 是 bad case chunks 与 `BM25Index` 的进程内缓存入口；缓存只按目录内 markdown 文件的 mtime/size 签名失效，不缓存单篇 `polished_text` 的检索结果，也不写磁盘缓存文件。
- `split_polished_text_into_clauses()` 是当前 `clause_only` 切分入口，只覆盖包、中文数字章节和数字顿号条款；切不出条款时回退整篇正文检索。不要在未验证前扩展到 `1.1`、`（一）` 或表格单元格级切分。
- prompt context 注入前必须先按 `case_id` 去重并稳定排序；注入给模型的 bad case 只保留 `risk_type`、`risk_pattern`、`recommended_comment_policy`、`applicability_boundary`、`anchor_policy` 5 个字段，`case_id`、score、命中条款和审计字段只留在 retrieval JSON。

### DeepAgents 初次生成

- 智能体生成入口是公共节点 `backend/nodes/common_word_nodes/content_agent_generate.py`，节点调用 `run_content_agent_generation()` 后只向 graph state 写回标准契约：`polished_text` 与 `generate_polished_done=True`。
- `backend/agents/generation/content_agents.py` 是 DeepAgents 主 runner 真源。生产路径用 `create_deep_agent(..., backend=FilesystemBackend(root_dir=workspace_dir, virtual_mode=True))` 创建单次任务工作区，工作区位于 `backend/context_log/content_agent_workspace/{task_id}_{YYYYMMDD-HHMMSS}/`，长期保留完整输入、草稿、审核、修订和最终正文。
- 工作区虚拟路径是硬协议：`/inputs/generation_context.md`、`/drafts/round-1.md`、`/audits/round-1.json` 至 `/audits/round-3.json`、`/revisions/round-1.md` 至 `/revisions/round-3.md`、`/final/polished_text.md`。`generation_context.md` 是 Markdown，内部 JSON code block 至少包含 `task_id`、`tender_type`、`generation_style`、`project_info`、`template_reference_text`、`tender_params`、`model_provider`。
- `content_agent` 是唯一主调度者。它必须用 TodoList 展示计划，通过 task 工具自主调用 `content_generate_agent`、`content_verify_agent`、`content_revise_agent`，最多 3 轮审核 / 修订；只有 `content_agent` 可以写 `/final/polished_text.md`，子 agent 不得写 final。
- 子 agent 不通过 task prompt 传完整正文，只通过文件读写交接。`content_generate_agent` 读取 `/inputs/generation_context.md`，复用 `backend/prompts/generate_prompt.py` 的 `render_generate_prompt()` 和当前 `generation_style` 写 `/drafts/round-1.md`；`content_verify_agent` 读取上下文和当前正文文件，输出原始 JSON 数组并写 `/audits/round-N.json`；`content_revise_agent` 读取当前正文与对应 audit，只修复 `evidence` / `fix_hint` 指定位置并写 `/revisions/round-N.md`。当对应 audit 为 `[]` 时，主 `content_agent` 不应再调用 `content_revise_agent`，而是直接写 `/final/polished_text.md`；若子修订节点被单独调用且 audit 为 `[]`，它必须短路返回“无需修订”，不得调用 LLM、输出完整正文或写 `/revisions/round-N.md`。
- `content_verify_agent` 的事实真源必须与当前 `generation_style` 的生成 prompt 保持一致：`project_info` 是项目名称、数量、交付和付款等基础事实；`tender_params` 是技术参数、重要性标识（紧邻编号前后的 `★/▲/△/Δ/*/#/※/●`，例如 Symbol 字体抽取出的 `Δ`）、包件数量、业务要求、表格 schema、条款物理顺序和文本/表格容器的原材料事实真源；`template_reference_text` 只是受限基础格式真源，只能提供一级章节壳、基础信息字段壳、编号标点、冒号、占位符和通用排版线索，不能作为技术/服务/商务/售后参数正文、旧表格、旧重要性标识或旧子章节的审核依据。`template` 和 `param` 都必须审核项目概述、总体需求等基础信息结构的字段位置和容器是否被保留并用新事实替换；参数章节内部必须按当前生成风格校验技术/服务/商务/售后条款接管、旧标题粉碎、无源旧事实删除、旧表壳清洗和连续重编号。审核必须检查技术参数中重要性标识不能缺漏、额外增加或改变归属，且多包件/多标段原材料不能只生成一个包件。正文技术符号（`≥/±/×/Ω/SpO₂/℃`）按参数文本原样保留，不作为重要性标识参与审核。
- `[[TABLE:<id>]]` 占位符是结构化表的内部写回入口，不是最终正文可见内容：审核与生成都不再要求模型原样保留或补回占位符，缺失占位符不产生 finding、不报错。写回层（`backend/helper/word_helper/text_parsing.py:convert_lines_to_items`）按 `tender_param_table_models` sidecar 决定是否恢复真实结构化表：命中 sidecar 时恢复为 `structured_table`，未命中时静默丢弃该占位符行（绝不作为可见文本写入 Word）；占位符前的 Markdown/pipe 投影表若无法匹配 sidecar，连同占位符整段丢弃，避免把近似/编造数据写入 Word。`table_placeholder_utils` 只保留 `extract_table_placeholders`、`find_missing_table_placeholders`、`find_required_table_placeholders` 三个识别 helper，不再有 `raise_if_table_placeholders_missing` / `restore_missing_table_placeholders` / `build_missing_table_placeholder_findings`。
- 所有进入 `draft/revision/final/polished_text` 的文本先过统一 sanitizer `backend/agents/generation/content_sanitizer.py:sanitize_generated_content`：删除 AI 自述/包装语（“好的，已收到您的指令”“以下是重构后的招标文件”等）、最终说明/内部自检、Markdown 代码块外壳与行内 `**`/`#`/`---` 装饰、无信息占位句（“须提供详细技术参数要求/须提供详细配置清单”）；保留 `[[TABLE:id]]` 占位符、技术符号和重要性标识。content agent 的 draft/revision/final 写入点、`generate_polished_text` 返回点都接入该 sanitizer。
- Word OOXML 抽取层 `backend/util/word_util/word_extraction_utils.py` 必须把 Symbol 字体的 `<w:sym w:font="Symbol" w:char="F044"/>` 映射为可见 `Δ`（重要性标识），覆盖正文段落（regex 路径 `_process_run_text`）、表格 cell（ElementTree 路径 `_iter_paragraph_texts_from_xml`）和结构化表 prompt context。映射表 `SYMBOL_FONT_CHAR_MAP` 只命中 `font="Symbol"` 的 sym，非 Symbol 字体（如 Wingdings）不映射；这是“抽取出来是什么，AI 就生成什么”的确定性前置条件，避免 Symbol Δ 在下游被当成乱码丢失。
- `content_verify_agent` 必须返回 JSON 数组，每项包含非空 `evidence` 与 `fix_hint`，不得输出“第 N 轮审核”、Markdown、解释或中文字段名。审核输出先做严格解析；失败后按错误类型走本地 JSON 修复 / 低温 JSON repair prompt 重试 / fallback finding，最终写入工作区的 audit 必须保持合法数组形状。语义上表达“无问题 / 实质一致 / 无需修改”的 no-op finding 必须折叠为 `[]`，不得进入工作区 audit、`content_agent` highlights 或前端 SSE 过程卡。
- Prompt builder 渲染 `project_info`、`template_reference_text`、`tender_params` 时不得把 Python `None` 字面量塞进模型提示词；缺失值应渲染为空文本，真实是否缺失通过进度日志中的字符数摘要排查。
- `content_generate_agent` 使用 `stream_llm_completion()` 时要复用 graph config 中的 `llm_stream_callback`，继续产生既有 `llm` snapshot 流；同时通过 `agent_step` 发…

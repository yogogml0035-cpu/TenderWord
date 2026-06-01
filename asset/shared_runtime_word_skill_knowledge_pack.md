# 共享运行时、Word 与 Skill 边界知识包

## 背景与范围

本包适用于后端 generate / rewrite / edit / comment_supplement 运行时、Prompt Layer、task skill runtime、Word COM、共享 Word helper、批注/样式回写、任务结果与 SSE 透传相关改动。

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

## 运行时分层

### 招标详情 API

- `GET /api/tender/{tender_no}` 会把外部招标详情接口数据装配成 `backend.models.tender.TenderData`；外部接口字段类型可能波动，例如 `investment` 可能返回数字而不是字符串。
- `TenderData` 是前端表单和后续 generate/rewrite/edit 快照的文本契约边界；预算、项目编号、联系人、日期、平台等文本字段必须在模型边界转成字符串，不能把可显示数字误判成“招标数据格式错误”。
- 排查“输入招标编号显示格式错误”时，先看后端响应体里的 Pydantic 字段错误；若外部数据已返回且只是字段类型不匹配，应修归一化契约，而不是收紧招标编号格式。

### Generate / Rewrite / Edit

- generate 任务通过 `DocumentService.create_task()` 进入 `GRAPH_REGISTRY`，按 `GenerateRequest.form_type` 选择具体 graph。
- `GET /api/generate/{task_id}` 必须通过 `backend.services.task_service` 查询任务状态；API 路由中的函数内延迟导入也要使用 `backend.*` 包绝对路径，避免在不同启动/测试入口下退化为 `ModuleNotFoundError`。
- rewrite 与 edit 走 `SkillGraph.for_skill(...)` 返回的 task graph；当前 task skill 注册以 `backend/skills/rewrite/SKILL.md`、`backend/skills/edit/SKILL.md` 为准。
- `POST /api/edit` 是显式 edit 入口；`/api/user/stream` 只负责普通聊天与 rewrite 路由，不承接显式 edit。
- `POST /api/comment-supplement` 是独立补充批注入口；请求只携带会话、当前下载卡文件路径和模型。`DocumentService.create_comment_supplement_task()` 必须校验 latest `rewrite_state`、`polished_text`、当前文件存在且等于 latest `prepared_doc_path` 后才创建任务。
- `/api/user/stream` 在已有 rewrite history 且最新消息具备明确修改意图时，应优先走确定性 rewrite fast-path，再进入 rewrite task 创建；普通闲聊、能力询问和不确定语义仍走 LLM 路由/回复。前端构造 user stream `messages` 时必须过滤空内容气泡，避免历史空 AI 消息触发后端请求体验证失败。
- `generation_mode`、`generation_style`、`comment_generation_mode` 与 `style_writeback_mode` 都是 generate-only 字段：`DocumentService._build_initial_state()` 可写入 generate state，edit / rewrite 请求模型和初始 state 不得注入这些字段。
- `generation_mode` 当前只允许 `workflow` 与 `agent`，默认 `workflow`。`workflow` 继续走 `generate_polished_text`，保留 `render_generate_prompt()`、`stream_llm_completion()` 和旧 `llm` snapshot 事件；`agent` 只影响初次 generate 的生成节点选择，最终仍必须产出 `polished_text` 给批注开关开启时的批注分支、样式回写、Word 写回和下载主干。
- `comment_generation_mode` 当前只允许 `on` 与 `off`，默认 `on`。`on` 时 workflow generate 继续经过 `generate_comments`，agent generate 继续在 `update_word` 后经过公共 `comment_agent`；`off` 时两种生成方式都跳过批注生成逻辑，并在 `comments_branch_done` 设置 `suppress_ai_comment_writeback=True`、清空临时批注计数。
- generate 成功后的后端 `rewrite_state` 可以保留 `generation_mode`、`polished_text`、`prepared_doc_path` 和后续链路所需的稳定运行态字段；初次生成时的临时批注推导结果不应进入任务 result、SSE `done`、前端下载卡 metadata 或 `sessionStorage`。
- 标准生成 graph 的分流只在 `StandardTenderWorkflowGraph` 基类实现：`generation_mode_gate` 后按 `_select_generation_node()` 进入 `generate_polished_text` 或 `content_agent`；正文生成后再按 `comment_generation_mode` 选择 workflow 的 `generate_comments` 或跳过，`update_word` 后再按 `generation_mode=agent && comment_generation_mode=on` 选择是否进入公共 `comment_agent`。类型 graph 不应复制这段分流。
- `generation_mode=agent` 的 `update_word` 只负责正文、样式和保存：`comments_branch_done` 会在 agent 分支或 `comment_generation_mode=off` 时设置 `suppress_ai_comment_writeback=True`，各类型 update 节点必须跳过确定性 AI 批注写回；`comment_generation_mode=on` 时，agent generate 的 `update_word` 完成后由标准 graph 路由到公共 `comment_agent` 节点，workflow 分支不得进入该节点。agent generate 无 `polished_comments` 时，`comment_agent` 可复用 `backend/prompts/comment_prompt.py` 自主生成批注候选。
- 公共 `comment_agent` graph 节点位于 `backend/nodes/common_word_nodes/comment_agent.py`，只作为批注增强项运行：它重新按锚点解析 Word 正文范围，调用 `backend/agents/comments/run_comment_agent()`，并把结果收敛成 `comment_writeback` 摘要；节点异常、保存失败或上下文缺失只能降级为 warning，不能让已保存正文的 generate 任务失败。
- 独立 `comment_supplement` 任务通过 `CommentSupplementGraph` 执行，节点顺序为 `prepare_comment_supplement -> comment_agent -> finalize_comment_supplement`。准备节点复制 latest 文档为新副本；`comment_agent` 在补充批注任务里直接基于 latest `rewrite_state.polished_text` 复用 `comment_prompt.py` 生成批注候选，再做锚点校验和 Word 写回；完成后会话最新 `rewrite_state.prepared_doc_path` 指向补充批注后的副本，后续 rewrite / edit 应继续使用该路径。

### DeepAgents 初次生成

- 智能体生成入口是公共节点 `backend/nodes/common_word_nodes/content_agent_generate.py`，节点调用 `run_content_agent_generation()` 后只向 graph state 写回标准契约：`polished_text` 与 `generate_polished_done=True`。
- `backend/agents/generation/content_agents.py` 是 DeepAgents 主 runner 真源。生产路径用 `create_deep_agent(..., backend=FilesystemBackend(root_dir=workspace_dir, virtual_mode=True))` 创建单次任务工作区，工作区位于 `backend/prompts_log/content_agent_workspace/{task_id}_{YYYYMMDD-HHMMSS}/`，长期保留完整输入、草稿、审核、修订和最终正文。
- 工作区虚拟路径是硬协议：`/inputs/generation_context.md`、`/drafts/round-1.md`、`/audits/round-1.json` 至 `/audits/round-3.json`、`/revisions/round-1.md` 至 `/revisions/round-3.md`、`/final/polished_text.md`。`generation_context.md` 是 Markdown，内部 JSON code block 至少包含 `task_id`、`tender_type`、`generation_style`、`project_info`、`template_reference_text`、`tender_params`、`model_provider`。
- `content_agent` 是唯一主调度者。它必须用 TodoList 展示计划，通过 task 工具自主调用 `content_generate_agent`、`content_verify_agent`、`content_revise_agent`，最多 3 轮审核 / 修订；只有 `content_agent` 可以写 `/final/polished_text.md`，子 agent 不得写 final。
- 子 agent 不通过 task prompt 传完整正文，只通过文件读写交接。`content_generate_agent` 读取 `/inputs/generation_context.md`，复用 `backend/prompts/generate_prompt.py` 的 `render_generate_prompt()` 和当前 `generation_style` 写 `/drafts/round-1.md`；`content_verify_agent` 读取上下文和当前正文文件，输出原始 JSON 数组并写 `/audits/round-N.json`；`content_revise_agent` 读取当前正文与对应 audit，只修复 `evidence` / `fix_hint` 指定位置并写 `/revisions/round-N.md`。当对应 audit 为 `[]` 时，主 `content_agent` 不应再调用 `content_revise_agent`，而是直接写 `/final/polished_text.md`；若子修订节点被单独调用且 audit 为 `[]`，它必须短路返回“无需修订”，不得调用 LLM、输出完整正文或写 `/revisions/round-N.md`。
- `content_verify_agent` 的事实真源必须与 `generate_by_template_prompt.py` 保持一致：`project_info` 是项目名称、数量、交付和付款等基础事实；`tender_params` 是技术参数、★/▲指标、包件数量和业务要求的原材料事实真源；`template_reference_text` 只作章节、编号、表格和语气参考，不得被当成技术参数审计依据。审核必须检查技术参数中 ★/▲ 指标不能缺漏或额外增加，且多包件/多标段原材料不能只生成一个包件。
- `content_verify_agent` 必须返回 JSON 数组，每项包含非空 `evidence` 与 `fix_hint`，不得输出“第 N 轮审核”、Markdown、解释或中文字段名。审核输出先做严格解析；失败后按错误类型走本地 JSON 修复 / 低温 JSON repair prompt 重试 / fallback finding，最终写入工作区的 audit 必须保持合法数组形状。语义上表达“无问题 / 实质一致 / 无需修改”的 no-op finding 必须折叠为 `[]`，不得进入工作区 audit、`content_agent` highlights 或前端 SSE 过程卡。
- Prompt builder 渲染 `project_info`、`template_reference_text`、`tender_params` 时不得把 Python `None` 字面量塞进模型提示词；缺失值应渲染为空文本，真实是否缺失通过进度日志中的字符数摘要排查。
- `content_generate_agent` 使用 `stream_llm_completion()` 时要复用 graph config 中的 `llm_stream_callback`，继续产生既有 `llm` snapshot 流；同时通过 `agent_step` 发送 `node=content_generate_agent` 的流式快照。`run_content_agent_generation()` 会在 `agent_step` 上补充 `content_agent` 结构字段，由确定性规则汇总初稿、审核、修复、复核和最终完成摘要，不再为用户可见摘要额外调用 LLM。
- 智能体生成链路里面向模型的自然语言提示词必须使用中文，包括 content_agent system prompt、subagent description、generate / verify / revise prompt 的章节标题与步骤说明；但 `content_agent`、`content_generate_agent`、`content_verify_agent`、`content_revise_agent`、`polished_text`、`evidence`、`fix_hint` 等节点名、工具名、状态字段和 JSON 字段属于机器契约，不能为了中文化而改名。
- 后端 finalizer 不自动返修、不自动兜底写 final。`/final/polished_text.md` 缺失、为空、是占位符、存在 round 4 或非法 audit / revision 路径、或 Word 写回前校验失败时，任务必须失败并进入既有 `error` 终态；保留 workspace 与 agent 过程卡供用户和排障查看。模型 / DeepAgents runner 不支持工具调用时同样失败，不回退 workflow。
- `set_generation_agent_runner()` 是测试用 fake runner 注入点；fake runner 必须模拟流式事件和 workspace final 文件。生产路径默认通过 `create_content_agent_runner()` 构造 DeepAgents runner，并复用 `MODEL_CONFIGS` 与 `settings.get_llm_config()`。
- `content_agent` 与 `content_generate_agent` 的运行期日志只记录 `project_info_chars`、`template_reference_text_chars`、`tender_params_chars` 等摘要，不写完整客户正文；完整输入和正文以 `backend/prompts_log/content_agent_workspace/` 为审计真源。三者全为 0 时应优先检查前端请求文件、`extract_tender_params` 输出、DeepAgents context 透传和服务是否已重载。

### Skill 声明

- skill loader 与 registry 负责 fail-fast 校验 frontmatter、workflow 入口、返回类型和 `workflow.skill_id`。
- 修改 skill workflow、dispatch 路由或 audit log 时，必须同时检查 `backend/skills/`、`backend/graphs/skill_graph.py`、`backend/services/document_service.py` 和对应 tests。
- edit / rewrite 的 LLM 输出会作为当前文档内容或当前锚点区正文的完整替换载荷；skill instruction 必须明确“输出范围守恒”。分包名、章节名、锚点、`从……起` 等用户表述默认只定位修改范围，不能让模型把局部定位误解为只输出该局部，否则写回会丢失未修改分包或章节。

### Prompt Layer 与 LLM 流式

- `backend/` 内直接调用 LLM 的能力默认收敛到 `backend/prompts/`；Prompt Layer 只做纯渲染，不做日志、副作用、Word COM 或会话状态变更。
- generate prompt 路由当前由 `backend/prompts/generate_prompt.py` 分派到 template / param builder。
- `content_generate_agent` 会复用同一个 generate prompt builder，因此 template / param builder 中的自然语言说明会同时影响 workflow 与 agent 两条初次生成链路；改这些 prompt 时必须同时跑 prompt 路由测试和 DeepAgents content_agent 相关测试。
- generate prompt 的 builder 路由除了要返回对应文案外，还要保留可观察的模式标识；`generation_style=param` 的渲染结果必须在 prompt 文本里显式表明“参数优先模式”，避免测试、日志或排障时只能回看请求模型才能分辨当前走的是哪条 builder。
- `backend/prompts/generate_by_param_prompt.py` 必须把“参考内容里的引导句”视为可删除内容而非默认骨架：像“设备用途 / 适用范围 / 项目背景 / 服务目标 / 功能概述”这类句子，只有在 `project_info` 或 `tender_params` 明确提供等价新事实时才能保留或重写；若新材料缺失，必须删除，并把当前章节保留下来的一级条目从 `1` 重新顺排。
- param builder 里源材料常见的 `2.技术参数 / 2.1 / 2.2` 只代表原始容器层级，不是最终成稿编号真值；Prompt 必须明确要求模型保留相对层级与物理顺序，但按删减后的存活兄弟项重编号，避免删除旧引导段后正文仍从 `2` 起号。
- param builder 必须把参考内容限权为一级章节、字段标签、字段固定前后缀、编号/标点和外观线索；参考里的旧资产表、旧服务范围、旧商务条款、旧列名和旧行数都不是可继承事实。服务设备清单默认留在技术/服务章节原位置，不因参考项目概述存在“维保设备型号”表而迁移；源表没有品牌、数量、序号列时不得补列或推断。
- param builder 对技术参数表格执行源 schema 主权：列名、列数和数据行以 `tender_params` 为准，Markdown 分隔行只作为结构噪声；前置识别列为空的表格行应视为上一行续写并合并到同一设备/服务内容中。已在项目概述输出的期限、付款等元数据不得为了保留参考“商务要求”而重复输出，参考商务章无新材料支撑时整章删除。
- template generate prompt 需要把编号拆成“层级语义”和“输出样式”两层处理：原材料只提供条款内容、物理顺序、父子层级和特殊符号，输出编号的层级形态、连接符与后缀标点应从参考内容对应章节抽取并顺排生成，避免把原材料里的括号、半括号、顿号、中文数字或混合编号外形直接带入最终文本。
- template generate prompt 必须把参考内容行首符号视为不可继承的脏标记：抽取标题壳、编号范式、表格形态或商务框架前先剔除参考里的 `★/▲/*/#` 等符号；凡正文由原材料替换或灌注的输出行，行首符号只能来自对应原材料原子条款，最终输出前要按原材料做逐行符号审计。
- template generate prompt 必须先把原材料拆成原子条款：物理换行、表格行、Markdown 列表行、显式编号边界都是硬边界；“冒号引导句 + 后续编号列表”要生成父项和下钻子项，不能被枚举保护或长句压缩合并成一行。
- LLM 流式调用统一经 `backend/util/common_util/llm_stream_utils.py` 的 `stream_llm_completion()`，默认超时使用 `backend/config/settings.py` 的 `LLM_STREAM_TIMEOUT_SECONDS`。
- LangSmith 配置真源是 `backend/.env` 与 `backend/config/settings.py`。后端启动时会把 `.env` 中的 `LANGSMITH_TRACING`、`LANGSMITH_ENDPOINT`、`LANGSMITH_API_KEY`、`LANGSMITH_PROJECT` 注入 `os.environ`，供 LangChain / LangGraph / DeepAgents SDK 自动上报 tracing；`backend/.env.example` 只保留占位 key，不写真实密钥。
- DeepSeek 提供商默认使用 `deepseek-v4-flash`，并通过 OpenAI 兼容请求的 `extra_body={"thinking": {"type": "disabled"}}` 固定为非思考模式；新增调用点不得硬编码其它 DeepSeek 模型名。
- `generate_comments` 的批注 JSON 属于严格机器契约：节点必须先尝试本地提取数组、移除代码块包裹、修正常见尾逗号/非法反斜杠；仍失败时只允许再走一次 Prompt Layer 定义的 JSON 修复调用，然后再决定是否降级为空数组。原始批注输出与修复输出应继续落到 `backend/prompts_log/generate_log/` 便于排障。
- 批注生成 prompt 的 `reference_text` 必须要求连续、逐字、可精确搜索且尽量唯一；短词或高频词风险要扩展到同句、同分句或同单元格内的连续原文，不能跨行/跨段/跨单元格拼接。无法形成唯一可回填锚点时应输出空数组或删除该条。
- 批注生成 prompt 的唯一真源是 `backend/prompts/comment_prompt.py`：`workflow` 的 `generate_comments`、agent generate 无候选时的 `comment_agent`、以及 `comment_supplement` 无候选时的 `comment_agent` 都必须复用 `render_comment_prompt()` 的 system / user prompt。不要新增第二套批注生成 prompt，也不要重新引入旧版差异计划逻辑。
- `comment_agent` 运行时真源是 `backend/agents/comments/`。生产 runner 必须用 `langchain.agents.create_agent(..., name="comment_agent")` 创建，并用 `ToolCallLimitMiddleware` 按工具名限制 `validate_comment_references` 最多 2 次、`write_validated_comments_to_word` 最多 1 次；测试注入点是 `set_comment_agent_runner()`。

## Word / Queue / Helper 边界

### 队列与串行执行

- Word COM 任务统一经过 `backend/task/task_queue_manager.py` 排队，不能绕开。
- Graph 节点必须复用 `backend/graphs/base_graph.py` 的锁、取消检查、进度包装和异常汇总。
- edit 当前会复制工作副本，再把 `source_document_path` 和 `prepared_doc_path` 指向副本；源文件不直接改写。

### Helper 分层

- `backend/helper/word_helper/` 是 Word 业务逻辑层，当前包含 range、protected fields、text parsing、content ops、paragraph boundary、cleanup、semantic matcher、inline style 等共享能力。
- `backend/util/word_util/` 只承担 COM 生命周期、底层 Word API、锚点解析、文档检查与底层插入工具。
- 节点文件只保留页码/锚点定位、Word 应用生命周期、日志、保存、state 装配和类型专属编排。
- 新 helper 落地后，调用方直接从 `backend.helper.word_helper.<module>` 导入；节点里的兼容别名只能短期过渡。

### 受保护字段

- 类型更新模式与受保护字段 profile 解析真源是 `backend/config/tender_config.py`。
- 当前 `content_update_mode` 只有 `protected_fields` 与 `direct_replace`。
- `xjcg`、`gngk_hw_zc`、`gngk_fw_cz` 使用 `common_two_field`；`gngk_fw_zc` 使用 `gngk_three_field`；`gngk_hw_cz` 与 `gjgk` 是 `direct_replace`，不支持受保护字段 profile。
- 受保护字段唯一真源是带中文冒号的 canonical marker；英文冒号兼容必须先规范化，再进入扫描、重绑或 AI 文本拆块。
- 字段识别必须严格匹配“可选编号前缀 + canonical marker + 值”的字段行；表格行、单元格文本或普通叙述句里的关键字命中不算有效字段。
- 关键字段缺失、格式非法或顺序非法时必须 fail-fast，不能部分写回后再靠 cleanup 兜底。

### 正文写回与段落边界

- 正文写回统一使用真实段落边界：`<br>`、字面量 `\n` / `\r\n` / `\r` 先归一化，再落成 Word `\r`。
- 不得用 `wdLineBreak`、`\v` 或手动换行兜底正文段落，避免多段正文被压成一段。
- `gngk_hw_cz` 首次生成当前走 same-page direct replace：先清空 `第四章  招标需求` 到 `第五章  评标方法与程序` 之间的正文，再在第四章标题下方同页正文区域插入 AI 生成内容；该路径不再依赖 `交付日期：`、`付款方式：` 等受保护字段。删除阶段必须走 `backend/helper/word_helper/delete_ops.py` 的锁感知删除，遇到内容控件 / 字段 / 局部锁定时跳过锁定表格或段落，而不是对整段 `Range.Delete()` 硬删。删除后如果只剩锁定段落边界或内容控件边界，起点控制符清理也必须跳过锁定控制符，再交给同页可编辑点扫描定位插入点。连续文本行应合并为一次 Word 写入，避免每行插入后游标贴回锁定边界导致后续段落反插。
- 受保护字段后的正文写回顺序固定为：先复用现成可写段 -> 段内拆段 -> 向后扫描 -> fail-fast。
- 判断下一段是否可写时，不得把 Heading / `OutlineLevel` 当成锁；真正阻止写入的是 range 锁、字段锁、SDT 锁和文档保护。
- AI 输出中的显式空行属于正文语义；拆块阶段必须保留空字符串行，cleanup 默认不得无差别压平正文段。

## 批注、样式、日志与 SSE

### 批注与样式回写

- `backend/states/base_state.py` 是 `comment_writeback_*`、`style_writeback_*` state 字段真源。
- `common update_word`、`gjgk_update_word`、`gngk_fw_zc_update_word` 都要把批注和样式回写摘要写回 state。
- `gngk_hw_cz_update_word` 虽然改为 direct replace，但仍要复用现有样式回填安全门禁，并把 `style_writeback_result`、`style_writeback_summary`、`comment_writeback_*` 摘要完整写回 state / 任务结果 / SSE done metadata。
- AI 批注写回是可降级增强项：正文已成功写入并可下载时，`generated_comment_count > 0` 且最终成功写入数为 `0` 不再让 update 路径硬失败；统一 `comment_writeback` 摘要由共享 helper 计算，`warning` 只在 `generated > 0 && failed > 0` 时为 true，`generated=0` 和 skipped-only 不警告，用户可见统计在 warning 条件下走 `progress_log.warning()`。
- 批注写回的重试只覆盖 Word `Comments.Add` 的 COM / RPC 写入异常；`reference_text` 未匹配属于定位失败，不会靠重试恢复。
- 批注定位先走 Word 精确 `Find`；精确未命中时，共享 `comment_writeback` 可用规范化唯一匹配兜底，忽略空白、控制符、常见标点和换行。锚点范围内唯一命中才插入；若锚点范围疑似漂移，只允许全文唯一命中兜底；多处命中必须失败，避免把批注错插到其它章节。
- `comment_agent` 的确定性校验在纯修复模式下只看 `polished_text`，AI 只能在同 index 上修改 `reference_text`，`comment_text` 必须与初始 JSON 原样一致；在自主生成模式下（agent generate 无候选或 `comment_supplement` 无候选），`comment_agent` 先用 `comment_prompt.py` 生成首版候选，再通过同一套校验与写回工具完成闭环。校验失败反馈要保留 index、原始 reference、失败原因和相近候选片段。`write_validated_comments_to_word` agent 工具名保留为协议入口，但工具线程只重新校验并提交最终候选，不直接访问 Word COM，也不得记录成第 3 个用户可见工具轮次；真正 Word 写入必须在 `run_comment_agent()` 的 runner 结束后，由当前 graph 节点线程调用 `write_validated_comment_candidates_to_word()` 完成，只在传入锚点边界内查找并写入已通过且目标范围无既有批注的条目，不使用全文兜底；已有批注位置计入 skipped。
- `comment_agent` 审计日志默认写入 `backend/prompts_log/comment_agent_audit/`，至少记录初始 JSON、raw AIMessage 内容、最多两轮工具快照、最终候选、最终 passed/failed/skipped 和 Word 写入统计。对外 `agent_step` 增量扩展 `comment_agent` 结构字段，展示 `phase`、两轮 `rounds`、异常/修复/跳过 `highlights`、`final_validation` 静默复校验统计和 `writeback` 统计；`content` 只作旧前端 fallback，不展示 raw AIMessage、工具原始 JSON、token 或排障栈。普通通过项只计数，失败、修复、跳过项才进入主视图明细。
- `frontend/e2e/test_comment_supplement.spec.ts` 是补充批注与 `comment_agent` 用户可见契约的 mock E2E 入口：覆盖初次 generate 下载卡点击“补充批注”后创建 `comment_supplement`、由 `comment_agent` 直接生成补充批注并显示 `comment_agent` 卡与新下载卡，也覆盖 agent generate 显示正文 agent + `comment_agent` 卡、workflow generate 不显示 `comment_agent` 卡。
- 样式回填是 best-effort：低相似度、0 命中或片段跳过不硬失败；批注写回同样不得阻断已成功写入正文的下载主流程，只通过 `comment_writeback` 统计和 warning 暴露。
- `style_writeback_mode=bold_only` 时，样式回填必须先在共享 `inline_style_ops` 中裁剪片段：只保留 `bold=True`，并清空下划线、斜体、删除线、字体颜色、高亮和 `underline_style`；裁剪后不再含加粗的片段不得进入 extracted/attempted 计数或写回流程。
- `replace_content` 给首个正文 `project_name` 插入 `PROJECT_NAME_FIRST_HIT_COMMENT` 时，必须先按规范化后的批注文案做去重；只跳过“同文案”重复批注，其他文案批注不影响新增。Word 若把既有批注暴露成零宽或贴边锚点，也要视为同一落点参与判重。
- `DocumentService._build_task_result_payload()` 与 SSE `done` 事件必须继续透传 `style_writeback` 与 `comment_writeback`；两者都应是面向前端的摘要白名单，不得夹带批注依据长数组或逐条排障明细。

### 生成文本基础格式与样式门禁

- 生成正文的基础插入格式必须先清洗为黑色普通字体，再允许后续样式回填叠加。
- `backend/helper/word_helper/content_ops.py` 的 `reset_generated_text_font_format()` 是生成文本 font-only 清洗真源；受保护字段值和生成编号前缀只能调用 font-only 清洗，不能顺手改段落布局。
- 字体颜色属于高风险可见样式，非默认/非自动颜色默认 fail-closed；只有强锚定、唯一、语义一致的局部片段，或短整段、目标原文完全一致且跨所有目标容器全局唯一的整容器片段，才允许写入颜色；整容器片段带下划线、高亮等伴随样式时，红色也必须通过同一全局唯一门禁。
- 行首编号前缀回填是独立窄路径；不得修改 `normalize_semantic_text()` 的全局“忽略编号”语义，也不得把编号样式扩散到正文。
- 普通短片段样式必须先通过 exact / 上下文 / 容器或表格结构硬门槛，再进入综合评分；位置分只能排序，不能救回高可见风险样式。

### 日志与 SSE 分工

- `progress_log` 只写用户可理解的进度和状态；排障堆栈、候选打分、淘汰原因、阈值与诊断 marker 留在 `execution_log` 或 debug log。
- `/api/stream/{task_id}` 是任务 SSE 主入口，支持 `Last-Event-ID` 断线续传。
- 用户态实时展示依赖 `log`、`llm`、`progress`、`done`、`error`。
- `agent_step` 是智能体 generate 的用户态 SSE 显式例外，用于展示 `content_agent` 的结构化正文生成总览，以及 `comment_agent` 的结构化锚点校验、修复复核和最终写入统计，不替代 `done` / `error` 终态。
- 后端 `AgentStepEventData` 字段包括 `task_id`、`task_kind`、`step_type`、`round`、`node`、`timestamp`、`is_complete`、可选 `content`、`findings`、`content_agent` 与 `comment_agent`。`round` 是 1-based；当前智能体子 agent 流使用 `step_type=stream`，主 agent 终局事件使用 `step_type=final`。`content_agent` 结构字段是参数生成智能体主展示数据，包含 `phase`、确定性 `summary`、阶段 `rounds`、当前问题 `highlights` 和 `final_result`；`content` 只作旧前端 fallback 或复制原文来源。`comment_agent` 过程事件使用 `step_type=tool_snapshot` / `final`，`comment_agent` 是批注生成智能体主展示数据，`content` 是完整快照 fallback 而非增量追加。
- `DocumentService` 在 graph config 中注入 `agent_step_callback`，智能体生成链路统一经 `SSECallback.push_agent_step()` 进入本地缓冲与 `SSEManager.send_agent_step_threadsafe()`；子 agent 与 runner stream 不再各自直连 `sse_manager`，避免同一过程卡双通道重复推送。`SSEManager.send_agent_step()` 会进入缓冲，断线续传时可重放。
- 前端合并 `agent_step` 时必须把终态视为单调状态：迟到的 `is_complete=false` 快照不得覆盖已完成卡片；旧版无 `content_agent` 结构的 generate 子 agent 事件继续按 `node + round` 文本 fallback 展示，带 `content_agent` 结构的事件必须统一聚合到一张“参数生成智能体”卡。
- 高频 `agent_step` 运行中快照只进入 `frontend/stores/chatStreamStore.ts` 的临时 stream，不写入持久化 `chat-storage`；只有完成事件才把最终正文 / JSON 固化到 `chatStore.conversations`。否则每个 SSE 片段都会触发会话数组重写、React 消息列表重渲染和 `sessionStorage` JSON 序列化，长文本或重复任务会让浏览器主线程卡死。
- 前端实时日志展示要优先降低主线程工作量，而不是只做视觉隐藏：生成中日志明细默认不挂载，复制文本点击时才构造；外层消息列表自动滚动只跟消息数量变化，不跟每个 SSE 内容片段变化。
- `frontend/hooks/useChatSSE.ts` 负责接收 done metadata；下载卡片是否展示摘要属于 UI 决策，不能影响任务结果透传契约。

## 关联测试与验证入口

- 运行时与任务结果：`backend/tests/services/test_document_service_initial_state.py`、`backend/tests/services/test_document_service_task_result.py`
- 招标详情 API：`backend/tests/api/test_tender_api.py`、`backend/tests/util/test_fetch_tender_data.py`
- 生成任务 API：`backend/tests/api/test_generate_api.py`
- 用户流式 rewrite 路由：`backend/tests/services/test_user_routing_service.py`、`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`
- skill 与 edit/rewrite：`backend/tests/nodes/test_tender_aware_word_dispatch.py`、`backend/tests/nodes/test_edit_audit_logging.py`、`backend/tests/progress/test_edit_progress_tracking.py`
- Word helper：`backend/tests/helper/test_content_ops.py`、`backend/tests/helper/test_paragraph_boundary_ops.py`、`backend/tests/helper/test_inline_style_ops.py`
- 锁感知删除 helper：`backend/tests/helper/test_delete_ops.py`、`backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`
- 批注写回：`backend/tests/nodes/test_comment_writeback.py`
- 批注锚点智能体：`backend/tests/agents/test_comment_agent.py`
- agent generate 批注节点降级：`backend/tests/nodes/test_comment_agent_writeback_node.py`
- 补充批注任务闭环：`backend/tests/api/test_comment_supplement_api.py`、`backend/tests/graphs/test_comment_supplement_graph.py`、`backend/tests/services/test_document_service_comment_supplement.py`
- 补充批注与 `comment_agent` 前端 mock E2E：`frontend/e2e/test_comment_supplement.spec.ts`
- 受保护字段与写回：`backend/tests/nodes/test_protected_fields_strict_matching.py`、`backend/tests/nodes/test_update_word_inline_style_writeback.py`
- Prompt / LLM stream：`backend/tests/prompts/test_generate_prompt_routing.py`、`backend/tests/util/test_llm_stream_utils.py`
- 批注 prompt 契约：`backend/tests/prompts/test_comment_prompt_reference_contract.py`
- generation mode 契约与 workflow 回归：`backend/tests/models/test_generate_request_generation_style.py`、`backend/tests/services/test_document_service_initial_state.py`、`backend/tests/graphs/test_generation_mode_workflow.py`、`backend/tests/nodes/test_generate_polished_text_workflow.py`、`backend/tests/services/test_document_service_llm_snapshot.py`
- DeepAgents content_agent 与公共节点：`backend/tests/agents/test_generation_content_agent.py`、`backend/tests/nodes/test_content_agent_generate.py`
- generation mode graph 分流与逐类型闭环：`backend/tests/graphs/test_generation_mode_branching.py`、`backend/tests/graphs/test_xjcg_generation_mode_agent.py`、`backend/tests/graphs/test_gngk_hw_zc_generation_mode_agent.py`、`backend/tests/graphs/test_gngk_hw_cz_generation_mode_agent.py`、`backend/tests/graphs/test_gngk_fw_zc_generation_mode_agent.py`、`backend/tests/graphs/test_gngk_fw_cz_generation_mode_agent.py`、`backend/tests/graphs/test_gjgk_generation_mode_agent.py`
- agent_step SSE：`backend/tests/models/test_sse_agent_step.py`、`backend/tests/services/test_sse_manager_agent_step.py`、`backend/tests/services/test_document_service_agent_step.py`
- 前端 SSE / 日志性能边界：`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/__tests__/unit/components/chat/test_message_list.test.tsx`

## 回归风险

- 改 skill workflow、dispatch 或 task result 时，容易出现 generate/rewrite/edit 某一条链路漏同步。
- 改招标详情模型或外部接口解析时，容易把上游字段类型波动误报为编号不存在或数据格式错误；需要覆盖数字预算、缺失可选字段和类型路由三类回归。
- 改 `generation_mode`、content_agent 或标准 graph 分流时，必须证明默认 `workflow` 不触发 `content_agent`，同时证明 `agent` 分支的 `polished_text` 会继续进入各类型既有 delete / replacement / update / post-update 主干。
- 改智能体输出协议时，必须同步检查 `backend/agents/generation/json_utils.py`、`backend/agents/generation/types.py`、`content_agent_generate`、`AgentStepEventData` 与前端 `agent-step` 消息格式；审核阶段可以用合法 fallback finding 兜底格式异常，但不要把纯文本最终输出当作成功兜底。
- 改受保护字段规则时，必须同时检查 `tender_config.py`、`protected_fields.py`、三条 update 路径和严格匹配测试。
- 改样式回填或 SSE 结果结构时，必须同步检查后端 `DoneEventData` / `AgentStepEventData`、任务结果 payload、`frontend/hooks/useChatSSE.ts`、`frontend/lib/sse.ts` 和 chat store metadata。
- 任何新增 Word helper 都要先确认代码真实落地，再写入知识包；不要把目标设计提前写成已完成事实。

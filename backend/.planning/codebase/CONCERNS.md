# 后端风险事实地图

**分析日期：** 2026-07-21
**范围：** 仅 `backend/`
**证据来源：** 当前实现代码与目录事实（非猜测 bug）

> 本文档只记录与 `Agents.md` 红线一致的风险/关注点。每条尽量含「风险/关注点」「影响范围」「当前缓解或约束」「建议」。
> **禁止**写入真实密钥、token、`.env` 值、客户原文或本机绝对私有路径。

---

## Tech Debt（技术债）

**Word COM、公平锁与终态收尾耦合在同一条链上**
- 风险/关注点：`backend/graphs/base_graph.py` 的 `invoke_with_timing_async()` 与 `backend/task/task_queue_manager.py`、`backend/services/document_service.py` 把排队（`wait_for_turn()`）、跨进程文件锁（`CrossProcessFileLock`）、取消检查、COM 生命周期、`complete_task()` 占位收尾和业务结果落盘串在同一执行序里；`complete_task()` 可先写占位结果，再由 `DocumentService` 覆盖为完整 payload。
- 影响范围：`backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `backend/services/document_service.py`, `backend/util/word_util/word_application_util.py`
- 当前缓解：`complete_task()` 对已 `CANCELLED` 任务会跳过覆盖；运行中取消会 `call_soon_threadsafe(async_task.cancel())`，失败时由节点级 `_check_cancellation` 兜底。
- 建议：保持“队列收尾”与“业务结果落盘”分层；改顺序前先补 `wait_for_turn()`、运行中取消、双完成路径与 SSE 终态回归测试。

**进程内任务队列与线程池假并行**
- 风险/关注点：`DocumentService` 使用 `ThreadPoolExecutor(max_workers=4)` 提交后台任务，但进入 Word COM 前必须 `wait_for_turn()` + `CrossProcessFileLock`；多 worker 只提高排队/LLM 准备阶段重叠度，不能提高 Word 写回吞吐。多 uvicorn worker / 多进程部署会让进程内队列、SSE、取消状态分裂，仅靠文件锁挡 COM 撞车。
- 影响范围：`backend/services/document_service.py`, `backend/task/task_queue_manager.py`, `backend/core/sse_manager.py`, `backend/main.py`
- 当前缓解：单例 `TaskQueueManager` + 公平条件变量；`CrossProcessFileLock`（`msvcrt.locking` + 线程锁）跨进程互斥 COM。
- 建议：生产默认单 worker；扩展吞吐需专用 Windows COM worker 池或外部队列，不要只调大 `max_workers`。

**进程内状态仍是默认实现**
- 风险/关注点：`backend/core/sse_manager.py`、`backend/task/task_queue_manager.py`、`backend/services/conversation_service.py` 把任务、SSE 事件、取消状态、rewrite 历史保存在单进程内存。
- 影响范围：服务重启丢历史事件与会话状态；多进程部署会让队列、事件流、取消状态分裂。
- 当前缓解：`cleanup_old_tasks()` 按年龄回收已完成任务；SSE 受 `SSE_MAX_EVENTS_PER_TASK`（默认 1000）与 `SSE_EVENT_TTL`（默认 3600 秒）截断。
- 建议：引入持久化前先定义 task store、SSE event id、会话快照与 artifact 生命周期的统一契约。

**rewrite / graph 写回逻辑分散在大文件**
- 风险/关注点：`backend/helper/word_helper/inline_style_ops.py`、`backend/nodes/gjgk_word_nodes/gjgk_update_word.py`、`backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`、`backend/nodes/common_word_nodes/update_word.py`、`backend/services/document_service.py` 同时承担样式匹配、段落边界、表格投影、批注写回与 task 编排。
- 影响范围：`.doc/.docx` 写回、受保护字段、批注回填、`style_writeback_mode` 分支。
- 当前缓解：`backend/helper/word_helper/` 与 `backend/tests/helper/`、`backend/tests/nodes/` 有定点测试。
- 建议：改动前先缩到最小 helper/node，用定点 fixture 锁住行为，避免在大文件里连带重写。

**`TaskSkillGraphState` 结构上继承 generate-only 字段**
- 风险/关注点：`backend/states/skill_state.py` 的 `TaskSkillGraphState` 继承 `TenderGraphStateBase`，而 `backend/states/base_state.py` 中 `TenderGraphStateBase` 声明了 `generation_style` / `generation_mode` / `comment_generation_mode` / `style_writeback_mode` / `suppress_ai_comment_writeback`。即使 rewrite 路径当前不主动填这些字段，TypedDict 继承面本身仍是泄漏面；后续若从共享 base state 拷贝 initial_state，可能把 generate-only 选项带进 rewrite。
- 影响范围：`backend/states/skill_state.py`, `backend/states/base_state.py`, `backend/graphs/skill_graph.py`, `backend/services/document_service.py`
- 当前缓解：请求模型与 skill runtime 约定这些字段只属于 generate；`RewriteSkillGraph` 使用独立节点序。
- 建议：长期应拆出不含 generate-only 字段的 skill base state；短期禁止从 generate state 整包拷贝到 rewrite。

**`/health/ready` 仍是轻量探针**
- 风险/关注点：`backend/main.py` 的 `upload_dir_accessible` 仍写死为 `True`（代码中有 TODO），未检查 Word/WPS COM、LLM provider、向量检索。
- 影响范围：readiness 返回成功不代表系统具备生成 / rewrite / 补充批注能力。
- 建议：拆分上传目录、COM、LLM、Qdrant/embedding、外部 HTTP 的分项就绪检查。

**依赖声明松散**
- 风险/关注点：`backend/requirements.txt` 只写下限版本，`langgraph`、`deepagents`、`langchain-*`、`openai`、`httpx`、`pywin32` 等行为会随次版本漂移。
- 影响范围：升级可能改变 agent 协议、SSE 序列化、Word COM 行为或上传下载边界。
- 建议：把关键兼容性固化进测试而不是经验。

**运行时产物目录无统一保留策略**
- 风险/关注点：`backend/context_log/`（generate_log / content_agent_workspace / comment_agent_audit）与 `backend/logs/` 会持续累积。2026-07-21 工作区抽样：`context_log` 约 1390 个文件、约 240MB；`logs` 约 25 个文件。内容可能含任务中间正文与审计摘要。
- 影响范围：磁盘占用、备份体积、潜在敏感信息落盘面。
- 当前缓解：部分路径经 scrub 后写审计；非统一生命周期管理。
- 建议：统一保留天数/体积极限，禁止把完整客户原文长期落盘到可被 API 回读的路径。

---

## Known Bugs/Risks（已知问题与风险）

**`GET /api/generate/{task_id}` 完成态返回 shape 不稳定**
- 风险/关注点：`backend/api/generate.py` 在完成态把 `task_info.result`（dict payload 或占位字符串）直接赋给 `GenerateResponse.output_file`（期望路径字符串），二者不同源。
- 影响范围：`backend/api/generate.py`, `backend/models/generate.py`, `backend/services/document_service.py`
- 当前缓解：完整结果走 `GET /api/tasks/{task_id}` 或 SSE `done` 事件，不要把 `GET /api/generate/{task_id}` 当唯一结果源。
- 建议：补齐完成态 shape 测试（`backend/tests/api/test_generate_api.py` 目前覆盖不足）。

**心跳超时默认偏紧**
- 风险/关注点：`TASK_HEARTBEAT_TIMEOUT` 默认 15 秒；长任务期间若前端 SSE/心跳抖动，后台清理线程会把仍在运行的任务标为 `CANCELLED`（`heartbeat_timeout`），与用户主动取消共用取消路径。
- 影响范围：`backend/task/task_queue_manager.py`, `backend/config/settings.py`, `backend/core/sse_manager.py`, `backend/api/tasks.py`
- 当前缓解：仅对 `QUEUED`/`RUNNING` 更新心跳；取消后节点级 `_check_cancellation` 与 async cancel 协同退出。
- 建议：长任务场景评估超时与前端心跳间隔的匹配；改超时前补心跳/取消交互测试。

**gngk form type 分派错误会选错 graph / 锚点 / 删除节点**
- 风险/关注点：后端 `GRAPH_REGISTRY` 以具体 `form_type`（如 `gngk_hw_zc_tender` / `gngk_fw_cz_tender`）选 graph；`backend/config/tender_config.py` 对 `gngk*` 有多套锚点与 profile。`gngk` 在前端是 UI 聚合类型，若未按 `tender_lx + fund_lx + ifzgcg` 正确展开就提交到后端，会落到错误的替换/删除/update 节点（`backend/nodes/gngk_word_nodes/*`、`backend/graphs/gngk_*_tender_graph.py`）。
- 影响范围：`backend/services/document_service.py`（`GRAPH_REGISTRY`）, `backend/config/tender_config.py`, `backend/api/generate.py`, 各 `gngk_*` graph/node
- 当前缓解：后端按显式 `form_type` 注册四条 gngk 主路径 + 兼容别名锚点配置；未知 form type 直接失败。
- 建议：任何 gngk 相关改动必须同步前后端 form type 分派 helper 与 registry；禁止在后端再接受裸 `gngk` 作为可执行 form。

**LLM 非确定性导致协议/写回漂移**
- 风险/关注点：content verify/revise、annotate_corrections（生成 + 审核双 LLM）、comment agent、rewrite 文本均依赖模型输出。JSON 围栏、中文字段名、noop finding、编号壳误标、越界轮次都会触发协议错误、空结果或错误批注。
- 影响范围：`backend/agents/generation/*`, `backend/nodes/common_word_nodes/annotate_corrections.py`, `backend/agents/comments/*`, `backend/nodes/skills_nodes/rewrite_nodes.py`
- 当前缓解：`MAX_REVISION_ROUNDS=3`；verify JSON 修复；`filter_noop_audit_findings` / `sanitize_protected_field_findings`；annotate 有代码路径条款标识规范化 + 句式门禁 + 审核器；comment prompt 禁止差异批注句式。
- 建议：prompt 变更必须配结构化输出/护栏单测；CI 不以 live 模型证明契约。

**`[[TABLE:<id>]]` 占位符写回契约易被 prompt 或写回层破坏**
- 风险/关注点：占位符是内部写回入口，不是用户可见正文。template/param 两套 prompt 对“文本容器表 vs 真实数据表”规则不同；LLM 若手绘 Markdown 表、漏锚点、或“正文已展开 + 锚点仍保留”，会在写回层重复插入或丢表。
- 影响范围：`backend/agents/generation/table_placeholder_utils.py`, `backend/helper/word_helper/text_parsing.py`, `backend/agents/generation/content_sanitizer.py`, `backend/prompts/generate_by_*_prompt.py`, `backend/agents/generation/verify_agent_graph.py`
- 当前缓解：`text_parsing` 明确剥离行内占位符、sidecar 未命中时丢弃投影表；prompt 与 revise 规则要求保留/删除二选一；相关 unit tests 守契约。
- 建议：改 regex、sidecar、`table_id` 字符集或写回语义时同步测试；占位符不得出现在最终用户可见回复。

**`annotate_corrections` 与 `comment_agent` 职责交叉风险**
- 风险/关注点：`annotate_corrections` 专责技术参数差异更正批注（句式 `原技术参数为“…”，现改为“…”`）与条款标识规范化；`comment_agent` prompt 明确禁止生成同类差异批注。若边界被打破，会出现重复更正批注或合规批注被差异句式污染。编号/项目符号/展示壳变化不得当作事实更正，但重要性标识 `*/※→★`、`△/Δ→▲` 必须更正——规则复杂，误报/漏报直接影响 Word 质量。
- 影响范围：`backend/nodes/common_word_nodes/annotate_corrections.py`, `backend/helper/word_helper/clause_marker_normalize.py`, `backend/agents/comments/comment_agent.py`, `backend/nodes/common_word_nodes/comment_writeback.py`
- 当前缓解：annotate 仅接 generate 图；写回层 `apply_correction_and_ai_comments()` **先写更正批注再写普通 AI 批注**；`suppress_ai_comment_writeback` / `comment_generation_mode=off` **只跳过普通 AI 批注，不跳过更正批注**。
- 建议：不要让 comment_agent 接触“原技术参数/现改为”句式；编号隔离逻辑不要散落到 writeback 层。

**rewrite 显式 graph 与旧元数据框架并存痕迹**
- 风险/关注点：当前 rewrite 由 `backend/graphs/skill_graph.py` 的 `RewriteSkillGraph` 显式承载；`backend/graphs/task_skill_workflows.py` 等旧元数据驱动痕迹仍可能存在于仓库。回退 `SkillGraph.for_skill + TaskSkillWorkflow` 会重新引入隐式路由。
- 影响范围：`backend/graphs/skill_graph.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/skills/rewrite/scripts/runtime.py`, `backend/states/skill_state.py`
- 当前缓解：`REWRITE_NODE_NAMES` / `REWRITE_NODE_HANDLERS` 显式声明；条件分支来自 `skills/rewrite/scripts/runtime.py`。
- 建议：改 rewrite 只改显式 graph；上传文件 rewrite 继续用 `rewrite_source="uploaded_file"` 标记，不做第二套任务链路。

**受保护字段护栏与 update_word 失败耦合**
- 风险/关注点：verify LLM 可能把模板继承的付款方式/交付日期等误判为旧事实并要求删除；revise 照做后，部分 form（如 `xjcg`/`gngk_fw_zc`）的 `update_word` 会因缺字段失败。
- 影响范围：`backend/agents/generation/protected_field_guard.py`, `backend/agents/generation/verify_agent_graph.py`, `backend/agents/generation/revise_agent_graph.py`, `backend/config/tender_config.py`, `backend/nodes/*_update_word.py`
- 当前缓解：`sanitize_protected_field_findings` 在写 audit 前过滤删除类 finding，并对缺失字段追加补回 finding。
- 建议：改 protected field profile 或 content update mode 时同步 guard 与对应 form 的写回测试。

---

## Security（安全注意事项）

**Word COM 只经后端任务队列 + graph 锁 + 取消检查 + 进度包装**
- 风险/关注点：`backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_com_manager.py` 直接依赖 Windows Python、本机 Word/WPS COM（`pythoncom`、`win32com`、`DispatchEx`、`CoInitialize`）。任何绕过 `CrossProcessFileLock` + 公平队列的并发执行都会撞 COM。`CrossProcessFileLock` 使用 `msvcrt.locking`，非 Windows 不可用。COM 全局锁超时默认 1800 秒（`LOCK_TIMEOUT`）。
- 影响范围：`backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `backend/helper/word_helper/*`, `backend/nodes/*_update_word.py`
- 当前缓解：`invoke_with_timing_async()` 强制 `wait_for_turn()` → 文件锁 → `start_task()` → 节点级 `wrap_node_with_progress` 取消检查；`com_lock`、`is_rpc_error()`、重试与 gencache 清理做降级。
- 建议：不要新增直接调用 COM 的旁路（API route / service / 随意脚本）；扩展吞吐需专用 Windows worker 池。

**`.env` / token 不进文档、日志、测试夹具与最终回复**
- 风险/关注点：`backend/config/settings.py`、`backend/retrieval/config.py` 从环境与 `backend/.env` 读取配置；日志、SSE、agent 审计通道一旦写入真实路径、密钥值或 traceback 就会泄密。
- 影响范围：`backend/config/settings.py`, `backend/agents/task_context_assistant/logging.py`, `backend/util/log_util/*`
- 当前缓解：`scrub_sensitive_text()` 统一 redact bearer token、密钥赋值、Windows/Unix 路径、`.env` 字面量与 traceback（`[REDACTED_SECRET]` / `[REDACTED_PATH]` / `[REDACTED_STACK]`）；`AgentRunAuditLogger` 只写白名单字段，其余 `summary`/`message` 全部过 scrub。
- 建议：新增日志/SSE/审计字段前先经 scrub；客户原文、真实路径、密钥值、traceback 不得直接进用户可见通道。**本文档亦不得粘贴 secret 样例。**

**generate-only 字段不得进入 rewrite 请求模型 / skill state / prompt surface**
- 风险/关注点：`generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于初次 generate。若漏进 rewrite 路由会改变生成分支或污染 prompt。
- 影响范围：`backend/models/generate.py`（仅 GenerateRequest）, `backend/models/agent_run.py`, `backend/services/agent_run_service.py`, `backend/states/skill_state.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`
- 当前缓解：这些字段主要在标准 tender graph 与 `backend/agents/generation/*` 消费；rewrite 使用 `RewriteSkillGraph` 与独立 runtime。
- 建议：新增生成选项只进 `GenerateRequest` 与初始 generate state；注意 skill_state 继承面（见技术债）。

**审计 / 摘要只暴露 scrub 白名单**
- 风险/关注点：`AgentRunAuditLogger.read_conversation_summaries()` 会把历史 run 摘要回读给前端；若把 bad case 命中详情、`case_id`、`score`、`chunk_id`、匹配条款或下载路径一并写入审计字段会泄露内部细节。
- 影响范围：`backend/agents/task_context_assistant/logging.py`, `backend/retrieval/comment_bad_case_runtime.py`, `backend/api/agent.py`
- 当前缓解：审计只落白名单字段；`summary`/`message`/`task_id`/`task_kind` 经 scrub。
- 建议：新增审计/摘要字段前先确认是否在白名单，并同步 scrub。

**下载接口路径边界**
- 风险/关注点：`backend/api/download.py` 接收 URL 编码的完整路径，放松 `relative_to(settings.UPLOAD_DIR)` 会重新打开路径穿越。
- 影响范围：`backend/api/download.py`, `backend/config/settings.py`
- 当前缓解：`validate_file_path()` 解码、`resolve()` 后强制落在 `settings.UPLOAD_DIR` 内。
- 建议：保留解码、解析、containment 三步；补路径穿越、URL 编码绕过、目录路径、缺失文件测试。

**上传只做扩展名和大小校验**
- 风险/关注点：`backend/api/upload.py`、`backend/util/common_util/upload_storage.py` 只根据清洗后文件名扩展名与字节大小判断，无 magic bytes / MIME / 文档结构校验。
- 影响范围：`backend/api/upload.py`, `backend/util/common_util/upload_storage.py`
- 当前缓解：`sanitize_filename()`、`ALLOWED_EXTENSIONS`、`MAX_UPLOAD_SIZE`。
- 建议：若把上传区当生产边界，补病毒扫描、魔数检测或隔离区。

**模板候选代理放大外部 URL 风险**
- 风险/关注点：`backend/api/template_candidates.py`、`backend/util/common_util/template_candidates.py` 代理下载外部模板链接，白名单一旦放宽即变 SSRF 面。
- 当前缓解：`validate_template_download_url()` 只允许 `http/https` 且主机在 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 内，年份过旧拦截。
- 建议：新增来源/主机/文件类型时同步更新白名单、协议校验与测试；前端不直接接触上游模板 URL。

**API 面缺少统一认证与任务归属授权**
- 风险/关注点：`backend/api/` 多数端点按 `task_id` / `conversation_id` / 文件路径操作资源；`user_session_id` 仅是列表过滤可选参数，不是强制鉴权。
- 影响范围：`backend/api/tasks.py`, `backend/api/download.py`, `backend/api/stream.py`, `backend/api/conversations.py`
- 当前缓解：下载仍受 `UPLOAD_DIR` containment；生产依赖部署边界与网络隔离。
- 建议：若多租户暴露，先定义 task/conversation/file 归属与鉴权层。

---

## Performance（性能瓶颈）

**Word COM 只能串行化**
- 风险/关注点：`word_com_manager` 全局 `threading.RLock`、`CrossProcessFileLock`、公平队列把 Word COM 保护成单通道临界资源。
- 影响范围：长任务阻塞后续 Word 写入；Word/WPS 注册异常拖垮整条生成链路。
- 当前缓解：`DispatchEx`、`CoInitialize()`、`Quit()`、文件锁、公平队列、`com_lock`。
- 建议：扩展吞吐需外部队列或专用 Windows worker 池，不能只调大线程数。

**长任务 = 多轮 LLM + 串行 COM**
- 风险/关注点：generate agent 模式可走 content → verify/revise 最多 3 轮，再加 `annotate_corrections` 双 LLM（生成 + 审核）、批注生成/agent、最终 `update_word` COM；单任务墙钟时间可很长，期间占满公平锁后段。
- 影响范围：`backend/agents/generation/*`, `backend/nodes/common_word_nodes/annotate_corrections.py`, `backend/agents/comments/*`, `backend/nodes/common_word_nodes/update_word.py`
- 当前缓解：协议轮次硬上限 3；标注 LLM 失败不阻断主流程（代码路径标识更正仍可保留）。
- 建议：监控单任务耗时与队列等待；超时/取消路径必须可回归。

**SSE 与任务状态都吃内存**
- 风险/关注点：`sse_manager` 按 task 缓存事件；任务队列与 conversation 把运行态保存在内存。
- 影响范围：历史回放与断线重连依赖本进程缓存，受 `SSE_MAX_EVENTS_PER_TASK`、TTL 截断。
- 建议：需要更长历史时先定义持久化事件存储与回放协议。

**SSE 断线重连窗口有限**
- 风险/关注点：`SSEManager` 支持 `Last-Event-ID` 回放，但事件列表有上限与 TTL；长任务 + 多客户端 + `agent_step` 高频快照时，晚到客户端可能丢中间进度。跨线程发送依赖 `bind_loop()` 与 `run_coroutine_threadsafe`，主 loop 未绑定或已关闭时事件静默丢弃。
- 影响范围：`backend/core/sse_manager.py`, `backend/api/stream.py`, `backend/services/document_service.py`, `backend/agents/generation/agent_step_events.py`
- 建议：改 SSE 事件模型时同步前后端；补多客户端重连与队列溢出测试。

**样式回填匹配复杂度高**
- 风险/关注点：`inline_style_ops.py` 既做样式抽取又做回填匹配，分支多、fixture 重；`style_writeback_mode`（`full` / `bold_only`）增加分支。
- 影响范围：Word 结构、表格、编号、局部候选组合多。
- 建议：改动前先用 focused fixture 锁住具体样式分支。

**坏案例混合检索网络路径较长**
- 风险/关注点：hybrid 模式走本地 BM25 + embedding 请求 + Qdrant 查询；每个 clause 都可能触发外部向量与检索调用。
- 当前缓解：保留 `bm25_only` fallback。
- 建议：减少 clause 数量与向量查询上限，再考虑缓存。

**`context_log` / workspace 磁盘 I/O**
- 风险/关注点：content agent workspace、generate_log、comment_agent_audit 高频写文件，长任务会放大磁盘与备份压力（见技术债抽样规模）。
- 建议：生产环境评估日志级别与产物开关；定期清理。

---

## Fragile Areas（脆弱区域）

**任务完成链路对顺序敏感**
- 风险/关注点：完成、取消、进度、SSE `done`/`error` 与结果 payload 依赖同一条顺序链；任何一层顺序变掉，前端可能读到旧状态或丢终态。
- 影响范围：`backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `backend/services/document_service.py`, `backend/core/sse_manager.py`
- 当前缓解：`complete_task()` 对 `CANCELLED` 状态不覆盖；`cancel_task()` 对 RUNNING 除 cancel event 外还会 async cancel。
- 建议：改队列/锁/SSE 前先补 `wait_for_turn()`、运行中取消、双完成收尾单测。

**API shape 与内部 payload 不同源**
- 风险/关注点：`GenerateResponse`、`TaskInfo.result`、SSE `done` payload 与前端下载卡不是同一模型；改一个字段名会断查询页、结果页或 SSE 解析。
- 影响范围：`backend/api/generate.py`, `backend/models/generate.py`, `backend/services/document_service.py`, `backend/models/sse.py`
- 建议：新增字段时同步后端模型、service、API response 与 `backend/tests/api/` 断言。

**SSE 事件契约被 named event 绑定**
- 风险/关注点：`agent_step`、`done`、`error`、`progress`、`heartbeat` 都是 named event，客户端与服务端必须一起改。
- 影响范围：`backend/core/sse_manager.py`, `backend/models/sse.py`, `backend/api/stream.py`
- 建议：新事件/字段先同步 `backend/models/sse.py`、SSE 发送方、前端 EventSource 解析与测试。

**Word COM 生命周期必须收尾完整**
- 风险/关注点：`CoInitialize()`、`Open()`、`Save()`、`Quit()`、`CoUninitialize()` 依赖严格顺序；RPC 错误与缓存损坏只能降级重试，不能真正抢占。
- 影响范围：`backend/util/word_util/word_application_util.py`, `backend/util/word_util/word_com_manager.py`
- 建议：改 COM 逻辑时先锁住 close/open/save 重试路径，再验证清理顺序与异常释放。

**generation_mode 图分支与批注写回耦合**
- 风险/关注点：`backend/graphs/base_graph.py` 按 `generation_mode`（`workflow`/`agent`）与 `comment_generation_mode`（`on`/`off`）切换节点与 `suppress_ai_comment_writeback`。agent 模式会抑制普通 AI 批注写回，但更正批注仍应写入。
- 影响范围：`backend/graphs/base_graph.py`, `backend/nodes/common_word_nodes/comment_writeback.py`, 各 form tender graph
- 建议：改 generation_mode 分支时同步 annotate → writeback 顺序测试。

**批注生成与写回（含同锚点追加开关）**
- 风险/关注点：自主生成模式要求模型直接输出 JSON 数组；候选须经 `validate_comment_reference_candidates`，再由 graph 节点调用 `write_polished_comments`。`allow_existing_comments` 默认 `False`（标准写回保守跳过已有批注锚点），comment agent 显式传 `True` 允许同锚点追加。
- 影响范围：`backend/agents/comments/*`, `backend/nodes/common_word_nodes/comment_agent.py`, `backend/nodes/common_word_nodes/comment_writeback.py`
- 建议：改 JSON 契约、候选校验或写回语义时同步调用方测试；禁止在运行时外直写 COM。

**Prompt 与 bad case 上下文绑定很紧**
- 风险/关注点：`render_generate_prompt` 按 `generation_style`（`template`/`param`）路由到不同 registry；comment prompt 绑定 bad case 锚点规则。
- 影响范围：`backend/prompts/generate_prompt.py`, `backend/prompts/generate_by_*_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/retrieval/comment_bad_case_runtime.py`
- 建议：改 prompt 路由或字段时同步 `backend/tests/prompts/` 与前端 generate-only 选项。

**gngk 多图继承链脆弱**
- 风险/关注点：`GngkHwZcTenderGraph` 为基，`gngk_hw_cz` / `gngk_fw_zc` / `gngk_fw_cz` 通过覆盖 `NODE_*` 复用；改基类节点序或 state 会影响全部 gngk 变体。
- 影响范围：`backend/graphs/gngk_*_tender_graph.py`, `backend/nodes/gngk_word_nodes/*`
- 建议：改 gngk 基类时至少跑四条 form 的 graph/node 测试。

---

## Change Hotspots（变更热点）

以下路径在近期功能演进与回归中反复触及，改动成本高：

| 热点 | 路径 | 为何敏感 |
|------|------|----------|
| Graph 锁/取消/进度 | `backend/graphs/base_graph.py` | 公平锁、文件锁、wrap_node、generation_mode 门控、annotate 接入 |
| 任务队列 | `backend/task/task_queue_manager.py` | 排队、心跳超时取消、complete/cancel 终态 |
| 文档任务编排 | `backend/services/document_service.py` | generate/rewrite/comment_supplement 初始 state、GRAPH_REGISTRY、结果落盘 |
| 批注写回 | `backend/nodes/common_word_nodes/comment_writeback.py` | 更正优先、suppress AI、同锚点 opt-in |
| 更正批注 | `backend/nodes/common_word_nodes/annotate_corrections.py` | 双 LLM + 编号隔离 + 句式门禁 |
| Content agent 链路 | `backend/agents/generation/*` | verify/revise 协议、table placeholder、protected fields |
| 样式/段落写回 | `backend/helper/word_helper/inline_style_ops.py`, `*_update_word.py` | COM 写回主体，文件巨大 |
| Rewrite 显式图 | `backend/graphs/skill_graph.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/skills/rewrite/scripts/runtime.py` | 从元数据框架迁出后的唯一 rewrite 入口 |
| Prompt 路由 | `backend/prompts/generate_prompt.py`, `generate_by_*_prompt.py` | generation_style 分叉与表格锚点规则 |
| gngk 分派 | `backend/config/tender_config.py`, `backend/graphs/gngk_*`, `backend/nodes/gngk_word_nodes/*` | form type × 资金/货物服务矩阵 |
| 审计 scrub | `backend/agents/task_context_assistant/logging.py` | 用户可见摘要与密钥路径 redact |
| SSE | `backend/core/sse_manager.py`, `backend/models/sse.py` | 前后端事件契约 |
| 下载/上传边界 | `backend/api/download.py`, `backend/api/upload.py` | 路径穿越与扩展名门禁 |

---

## Recommendations for agents（给智能体的操作建议）

1. **先读红线再改代码**：Word COM 只经任务队列 + graph 锁 + 取消检查 + 进度包装；组件/API/service 不得直接操作 COM。
2. **最小必要改动**：先看同模块现有实现；不要顺手重构、目录洗牌、批量改名或清理无关旧代码；不回滚用户已有改动；不提交/推送/暂存除非用户明确要求。
3. **generate-only 字段隔离**：`generation_style` / `generation_mode` / `comment_generation_mode` / `style_writeback_mode` 只进 `GenerateRequest` 与 generate 初始 state；不要写入 rewrite 请求模型、skill prompt 或从 generate state 整包拷贝到 `TaskSkillGraphState`。
4. **rewrite 走显式图**：只用 `RewriteSkillGraph`；上传文件 rewrite 用 `rewrite_source="uploaded_file"`；不要恢复 `SkillGraph.for_skill + TaskSkillWorkflow` 元数据驱动框架。
5. **gngk 必须具体 form type**：后端 registry 需要 `gngk_hw_zc_tender` 等具体值；前端 UI 的 `gngk` 必须由共享 helper 按 `tender_lx + fund_lx + ifzgcg` 分派后再提交。
6. **表格占位符是内部入口**：`[[TABLE:<id>]]` 不得当作用户可见正文，不得写成 Markdown/手绘表格；template vs param 规则不同，改 prompt 必须同步 `table_placeholder_utils` / `text_parsing` 测试。
7. **批注职责边界**：技术参数差异更正只由 `annotate_corrections` 产出；`comment_agent` 禁止“原技术参数为…现改为…”；编号/项目符号/展示壳变化不是事实更正；写回顺序是更正批注 → 普通 AI 批注；`suppress_ai_comment_writeback` 不跳过更正批注。
8. **安全默认**：审计/摘要/SSE 新字段必须经 `scrub_sensitive_text`；下载保持 `UPLOAD_DIR` containment；模板代理保持主机白名单；不要把 secret、完整客户原文、真实路径、traceback、下载路径写进审计或文档。
9. **跨层契约同步**：改 API shape、SSE、任务类型、招标类型、Prompt/LLM、Word helper、模板候选时，同步 models、service、客户端、tests 与相关知识包。
10. **验证门槛**：后端代码改动至少跑相关 pytest；Word COM 闭环只能在 Windows + Word/WPS COM 上验收；跑不了的检查要说明原因与替代验证。
11. **产物与日志**：`backend/context_log/` 与 `backend/logs/` 是运行时产物，不是源码真相；不要把其中客户原文复制进知识文档；注意磁盘累积。
12. **测试优先锁热点**：改队列/取消、comment_writeback、annotate_corrections、generation_mode、rewrite graph、download 边界时，优先补/跑对应 `backend/tests/` 定点用例，再谈行为扩展。

---

## 测试覆盖缺口（摘要）

| 缺口 | 相关路径 | 优先级 |
|------|----------|--------|
| `wait_for_turn` / 运行中取消 / 双完成路径 | `task_queue_manager.py`, `base_graph.py`, `document_service.py` | High |
| `GET /api/generate/{task_id}` 完成态 shape | `api/generate.py`, `models/generate.py` | High |
| 下载路径穿越 / 上传伪装 / 模板代理负例 | `api/download.py`, `api/upload.py`, `template_candidates.py` | High |
| 真实 Word COM E2E | `util/word_util/`, `helper/word_helper/`, `nodes/` | High |
| annotate 编号隔离 + comment 写回 opt-in 端到端 | `annotate_corrections.py`, `comment_writeback.py` | High |
| RewriteSkillGraph 上传/会话双分支图级 | `graphs/skill_graph.py`, `rewrite_nodes.py` | Medium |
| SSE 多客户端重连与 bind_loop 静默丢事件 | `core/sse_manager.py` | Medium |
| 多 uvicorn worker 状态分裂 | `main.py`, `task_queue_manager.py`, `sse_manager.py` | Medium |
| Qdrant/embedding live 路径 | `retrieval/*` | Medium |

---

## 缺失的关键能力（摘要）

- **持久化任务/SSE/会话存储**：重启即失、跨 worker 不共享。
- **统一认证与任务归属授权**：`task_id`/路径即可操作资源。
- **真实 readiness**：`/health/ready` 未验证 COM/LLM/检索/上传目录。
- **上传内容安全检查**：仅扩展名与大小。
- **稳定的 Windows Word COM CI**：单元测试无法证明真实写回闭环。
- **context_log / logs 保留策略**：运行时产物持续累积。

---

## 高风险依赖（摘要）

| 依赖 | 风险 | 验证注意 |
|------|------|----------|
| `pywin32` / Word / WPS COM | Windows-only；RPC 脆弱；串行 | 完整写回必须本机 COM |
| `langgraph` / `deepagents` / LangChain | agent 协议与工具语义漂移 | 升级先跑 `tests/agents/` |
| 外部 LLM provider | 延迟、JSON 漂移、密钥配置 | 测试只 mock，不写 secret |
| Qdrant + embedding | hybrid 检索失败 | 保留 BM25 fallback |
| 模板/招标外部 HTTP | 字段与主机白名单变更 | 同步模型与前端 client |

---

*后端风险分析：2026-07-21*

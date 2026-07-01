# 后端风险事实地图

**分析日期：** 2026-06-29（刷新自 2026-06-25 版）

> 本文档只记录与 AGENTS.md 红线一致的风险/关注点事实，不展开 validator/progress log/agent harness 内部实现细节。每条含「风险/关注点」「影响范围」「当前缓解或约束」「建议（如适用）」。

## 技术债

**Word COM、公平锁与终态收尾耦合在同一条链上：**
- 风险/关注点： `backend/graphs/base_graph.py` 的 `invoke_with_timing_async()`、`backend/task/task_queue_manager.py` 和 `backend/services/document_service.py` 把排队（`wait_for_turn()`）、跨进程文件锁（`CrossProcessFileLock`）、取消检查、COM 生命周期、`complete_task()` 占位收尾和业务结果落盘串在同一执行序里；`complete_task()` 会先用 `"success"` 或 `prepared_doc_path` 占位，`DocumentService` 再覆盖为完整 payload。
- 影响范围： `backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `backend/services/document_service.py`, `backend/util/word_util/word_application_util.py`
- 当前缓解或约束： `complete_task()` 对已 `CANCELLED` 的任务会跳过覆盖；`_finalize_task_locked()` 统一终态收尾、清理运行态上下文并 `notify_all()`。
- 建议： 保持“队列收尾”与“业务结果落盘”分层；改顺序前先补 `wait_for_turn()`、运行中取消、双完成路径与 SSE 终态回归测试。

**rewrite/graph 写回逻辑分散在大文件：**
- 风险/关注点： `backend/helper/word_helper/inline_style_ops.py`、`backend/nodes/gjgk_word_nodes/gjgk_update_word.py`、`backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`、`backend/nodes/common_word_nodes/update_word.py`、`backend/services/document_service.py` 同时承担样式匹配、段落边界、表格投影、批注写回与 task 编排。
- 影响范围： `.doc/.docx` 写回、受保护字段、批注回填、`style_writeback_mode` 分支。
- 当前缓解或约束： `backend/helper/word_helper/` 与 `backend/tests/helper/`、`backend/tests/nodes/` 有定点测试。
- 建议： 改动前先缩到最小 helper/node，用定点 fixture 锁住行为，避免在大文件里连带重写。

**进程内状态仍是默认实现：**
- 风险/关注点： `backend/core/sse_manager.py`、`backend/task/task_queue_manager.py`、`backend/services/conversation_service.py` 把任务、SSE 事件、取消状态、rewrite 历史都保存在单进程内存。
- 影响范围： 服务重启丢历史事件与会话状态；多进程部署会让队列、事件流、取消状态分裂。
- 当前缓解或约束： `cleanup_old_tasks()` 按 `max_age_seconds` 回收已完成任务；SSE 受 `SSE_MAX_EVENTS_PER_TASK` 截断。
- 建议： 引入持久化前先定义 task store、SSE event id、会话快照与 artifact 生命周期的统一契约。

**`/health/ready` 仍是轻量探针：**
- 风险/关注点： `backend/main.py` 的 `upload_dir_accessible` 仍写死为 `True`（代码中明确 `# TODO: 实际检查目录权限`），未检查 Word/WPS COM、LLM provider、向量检索。
- 影响范围： readiness 返回成功不代表系统具备生成/rewrite/补充批注能力。
- 当前缓解或约束： `/health` 仅作为进程存活探针。
- 建议： 拆分上传目录、COM、LLM、Qdrant/embedding、外部 HTTP 的分项就绪检查。

**依赖声明松散：**
- 风险/关注点： `backend/requirements.txt` 只写下限版本，`langgraph`、`deepagents`、`langchain-*`、`openai`、`httpx`、`pywin32` 等行为会随次版本漂移。
- 影响范围： 升级可能改变 agent 协议、SSE 序列化、Word COM 行为或上传下载边界。
- 当前缓解或约束： `backend/tests/api/`、`backend/tests/agents/`、`backend/tests/services/`、`backend/tests/nodes/` 覆盖高风险路径。
- 建议： 把关键兼容性固化进测试而不是经验。

## 已知问题

**`GET /api/generate/{task_id}` 完成态返回 shape 不稳定：**
- 风险/关注点： `backend/api/generate.py` 在完成态把 `task_info.result`（dict payload）直接赋给 `GenerateResponse.output_file`（期望字符串），二者不同源。
- 影响范围： `backend/api/generate.py`, `backend/models/generate.py`, `backend/services/document_service.py`
- 当前缓解或约束： 完整结果走 `GET /api/tasks/{task_id}` 或 SSE `done` 事件，不要把 `GET /api/generate/{task_id}` 当唯一结果源。
- 建议： 补齐完成态 shape 测试（`backend/tests/api/test_generate_api.py` 目前只覆盖 404）。

## 安全注意事项

**Word COM 只经后端任务队列 + graph 锁 + 取消检查 + 进度包装（平台绑定 Windows + Word/WPS COM）：**
- 风险/关注点： `backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_com_manager.py` 直接依赖 Windows Python、本机 Word/WPS COM（`pythoncom`、`win32com`、`DispatchEx`、`CoInitialize`）；任何绕过 `CrossProcessFileLock` + 公平队列的并发执行都会撞 COM。
- 影响范围： `backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `backend/helper/word_helper/*`, `backend/nodes/*_update_word.py`
- 当前缓解或约束： `invoke_with_timing_async()` 强制 `wait_for_turn()` → 文件锁 → `start_task()` → 节点级 `wrap_node_with_progress` 取消检查（执行前/后各一次）；COM 通过 `com_lock`、`is_rpc_error()`、`calculate_retry_delay()`、gencache 缓存清理做降级重试。
- 建议： 不要新增直接调用 COM 的旁路；扩展吞吐需走专用 Windows worker 池或外部队列，不能只调大线程数。

**`.env` / token 不进文档、日志、测试夹具与最终回复：**
- 风险/关注点： `backend/config/settings.py`、`backend/retrieval/config.py` 从环境与 `backend/.env` 读取配置；日志、SSE、agent 审计通道一旦写入真实路径、密钥值或 traceback 就会泄密。
- 影响范围： `backend/config/settings.py`, `backend/retrieval/config.py`, `backend/agents/task_context_assistant/logging.py`, `backend/util/log_util/sse_log_handler.py`, `backend/util/log_util/progress_log.py`
- 当前缓解或约束： `scrub_sensitive_text()` 统一 redact bearer token、密钥赋值、Windows/Unix 路径、`.env` 字面量与 traceback（返回 `[REDACTED_SECRET]` / `[REDACTED_PATH]` / `[REDACTED_STACK]`）；`AgentRunAuditLogger` 只写白名单字段（`event`、`run_id`、`conversation_id`、`selected_skills`、`stage`、`tool_name`、`status`、`task_id`、`task_kind`、`queue_position` 等），其余 `summary`/`message` 全部过 scrub。
- 建议： 新增日志/SSE/审计字段前先经 scrub；客户原文、真实路径、密钥值、traceback 不得直接进用户可见通道。

**generate-only 字段不进 rewrite 请求模型 / skill state / prompt surface：**
- 风险/关注点： `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于初次 generate，若漏进 rewrite 路由就会改变生成分支或污染 prompt。
- 影响范围： `backend/models/agent_run.py`, `backend/services/agent_run_service.py`, `backend/agents/task_context_assistant/tools.py`, `backend/states/skill_state.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/skills/rewrite/scripts/runtime.py`
- 当前缓解或约束： 这些字段只在 `backend/graphs/base_graph.py` 的 `StandardTenderWorkflowGraph` 与 `backend/agents/generation/*`（`generate_agent_graph.py`、`content_agents.py`、`verify_agent_graph.py`）消费；`backend/states/skill_state.py` 的 `TaskSkillGraphState` 只含 rewrite 字段（`rewrite_mode`、`rewrite_source`、`rewrite_user_prompt` 等），不含 generate-only 选项。
- 建议： 新增生成选项只进 `GenerateRequest` 与初始 generate state，不要写进 rewrite 请求模型、skill state 或 prompt。

**rewrite 必须用 RewriteSkillGraph，不恢复元数据驱动框架：**
- 风险/关注点： `backend/graphs/skill_graph.py` 的 `RewriteSkillGraph(BaseGraph)` 是显式 graph（节点、边、条件分支直接写在 `build_graph()`），取代了原 `SkillGraph.for_skill + TaskSkillWorkflow` 元数据驱动框架；任何回退都会重新引入隐式路由。
- 影响范围： `backend/graphs/skill_graph.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/skills/rewrite/scripts/runtime.py`, `backend/states/skill_state.py`
- 当前缓解或约束： `REWRITE_NODE_NAMES` / `REWRITE_NODE_HANDLERS` 显式声明流程；分支函数 `select_resolve_branch`、`select_comment_branch` 来自 `backend/skills/rewrite/scripts/runtime.py`。
- 建议： 改 rewrite 流程时改这个显式 graph，不要复活元数据驱动调度。

**上传文件 rewrite 用 `rewrite_source` 标记，不做第二套任务链路：**
- 风险/关注点： 上传文件 rewrite 与会话 rewrite 共用同一条 `RewriteSkillGraph`，仅靠 `rewrite_source="uploaded_file"` 区分；若另起一套任务链路会导致取消/进度/SSE 分裂。
- 影响范围： `backend/nodes/skills_nodes/rewrite_nodes.py`（`UPLOADED_REWRITE_SOURCE = "uploaded_file"`，`resolve_rewrite_target` 分支）, `backend/services/document_service.py`（`"rewrite_source": "uploaded_file"`）, `backend/skills/rewrite/scripts/runtime.py`
- 当前缓解或约束： 上传分支在 `resolve_rewrite_target` 中把 `source_document_path` 拷贝到 `rewrite_temp_output_path` 并复用同一 graph；`backend/tests/skills/test_task_skill_runtime.py`、`backend/tests/nodes/test_uploaded_rewrite_inline_style_context.py` 守住该标记存活。
- 建议： 上传 rewrite 的新行为继续走 `rewrite_source` 标记 + 同一 graph，不要开第二套队列或第二个 graph。

**审计 / 摘要只暴露 scrub 白名单：**
- 风险/关注点： `backend/agents/task_context_assistant/logging.py` 的 `AgentRunAuditLogger.read_conversation_summaries()` 会把历史 run 摘要回读给前端；若把 bad case 命中详情、`case_id`、`score`、`chunk_id`、匹配条款一并写入审计字段会泄露内部检索细节。
- 影响范围： `backend/agents/task_context_assistant/logging.py`, `backend/retrieval/comment_bad_case_runtime.py`, `backend/prompts/comment_prompt.py`
- 当前缓解或约束： 审计只落白名单字段，所有 `summary`/`message`/`missing_requirements`/`task_id`/`task_kind` 都经 `scrub_sensitive_text()`；prompt 上下文只保留 `risk_type`、`risk_pattern`、`recommended_comment_policy`、`applicability_boundary`、`anchor_policy`，命中详情留在后端审计产物。
- 建议： 新增审计/摘要字段前先确认是否在白名单，并同步 scrub。

**`[[TABLE:<id>]]` 占位符不当用户可见正文：**
- 风险/关注点： `[[TABLE:<id>]]` 是内部写回入口（审核、sidecar 恢复、投影表），不是最终正文必须保留的可见内容；若被写成 Markdown 表格或手绘表格，或各环节丢弃语义不一致，会把表格近似文本写错、写漏或误判。
- 影响范围： `backend/agents/generation/table_placeholder_utils.py`, `backend/agents/generation/verify_agent_graph.py`, `backend/helper/word_helper/text_parsing.py`, `backend/agents/generation/content_sanitizer.py`
- 当前缓解或约束： 提取、修复、写回入口由同一组工具串接；`backend/tests/agents/test_table_placeholder_utils.py`、`backend/tests/helper/test_text_parsing_table_placeholder.py` 守契约。
- 建议： 改 regex、sidecar 匹配、`table_id` 字符集或写回语义时同步上述测试；占位符不得出现在最终回复正文。

**下载接口的路径边界必须保持：**
- 风险/关注点： `backend/api/download.py` 接收 URL 编码的完整路径，放松 `relative_to(settings.UPLOAD_DIR)` 会重新打开路径穿越。
- 影响范围： `backend/api/download.py`, `backend/config/settings.py`
- 当前缓解或约束： `validate_file_path()` 解码、`resolve()` 后强制落在 `settings.UPLOAD_DIR` 内。
- 建议： 保留解码、解析、containment 三步；补路径穿越、URL 编码绕过、目录路径、缺失文件测试。

**上传只做扩展名和大小校验：**
- 风险/关注点： `backend/api/upload.py`、`backend/util/common_util/upload_storage.py` 只根据清洗后文件名扩展名与字节大小判断，无 magic bytes / MIME / 文档结构校验。
- 影响范围： `backend/api/upload.py`, `backend/util/common_util/upload_storage.py`, `backend/config/settings.py`
- 当前缓解或约束： `sanitize_filename()`、`ALLOWED_EXTENSIONS`、`MAX_UPLOAD_SIZE` 约束文件名、类型、体积。
- 建议： 若把上传区当生产边界，补病毒扫描、魔数检测或隔离区。

**模板候选代理放大外部 URL 风险：**
- 风险/关注点： `backend/api/template_candidates.py`、`backend/util/common_util/template_candidates.py` 代理下载外部模板链接，白名单一旦放宽即变 SSRF 面。
- 影响范围： `backend/api/template_candidates.py`, `backend/util/common_util/template_candidates.py`, `backend/config/settings.py`
- 当前缓解或约束： `validate_template_download_url()` 只允许 `http/https` 且主机在 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 内，年份过旧拦截。
- 建议： 新增来源/主机/文件类型时同步更新白名单、协议校验与测试，前端不直接接触上游模板 URL。

## 性能瓶颈

**Word COM 只能串行化：**
- 风险/关注点： `backend/util/word_util/word_com_manager.py`、`backend/util/word_util/word_application_util.py`、`backend/graphs/base_graph.py`、`backend/task/task_queue_manager.py` 把 Word COM 保护成单通道临界资源。
- 影响范围： 长任务阻塞后续 Word 写入；Word/WPS 注册异常拖垮整条生成链路。
- 当前缓解或约束： `DispatchEx`、`CoInitialize()`、`Quit()`、`CrossProcessFileLock`、公平队列共同限制并发。
- 建议： 扩展吞吐需上外部队列或专用 Windows worker 池。

**SSE 与任务状态都吃内存：**
- 风险/关注点： `backend/core/sse_manager.py` 按 task 缓存事件；`backend/task/task_queue_manager.py`、`backend/services/conversation_service.py` 把运行态保存在内存。
- 影响范围： 历史回放与断线重连依赖本进程缓存，受 `SSE_MAX_EVENTS_PER_TASK`、`MAX_REWRITE_MESSAGES` 截断。
- 建议： 需要更长历史时先定义持久化事件存储与回放协议，再谈扩容。

**坏案例混合检索网络路径较长：**
- 风险/关注点： `backend/retrieval/comment_bad_case_runtime.py`、`backend/retrieval/embeddings.py`、`backend/retrieval/qdrant_store.py` 在 hybrid 模式走本地 BM25 + embedding 请求 + Qdrant 查询。
- 影响范围： 每个 clause 都可能触发外部向量与检索调用。
- 当前缓解或约束： 保留 `bm25_only` fallback。
- 建议： 减少 clause 数量与向量查询上限，再考虑缓存。

**LLM / agent 运行时受外部延迟影响：**
- 风险/关注点： `backend/util/common_util/llm_stream_utils.py`、`backend/agents/generation/content_agents.py`、`backend/agents/comments/comment_agent.py`、`backend/services/template_candidate_ranking_service.py` 依赖外部模型或重排。
- 影响范围： 网络、模型推理、重试、JSON 修复拉长单次任务时长。
- 建议： 把超时、重试、节流参数集中在 settings，别在各节点各写一套。

**样式回填匹配复杂度高：**
- 风险/关注点： `backend/helper/word_helper/inline_style_ops.py` 既做样式抽取又做回填匹配，分支多、fixture 重。
- 影响范围： Word 结构、表格、编号、局部候选组合多。
- 建议： 改动前先用 focused fixture 锁住具体样式分支。

## 脆弱区域

**任务完成链路对顺序敏感：**
- 风险/关注点： 完成、取消、进度、SSE `done`/`error` 与结果 payload 依赖同一条顺序链；任何一层顺序变掉，前端可能读到旧状态或丢终态。
- 影响范围： `backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `backend/services/document_service.py`, `backend/core/sse_manager.py`
- 当前缓解或约束： `complete_task()` 对 `CANCELLED` 状态不覆盖；`cancel_task()` 对 RUNNING 任务除设置 cancel event 外还会 `loop.call_soon_threadsafe(async_task.cancel())`，失败时由节点取消检查兜底。
- 建议： 改队列/锁/SSE 前先补 `wait_for_turn()`、运行中取消、双完成收尾单测。

**API shape 与内部 payload 不同源：**
- 风险/关注点： `GenerateResponse`、`TaskInfo.result`、SSE `done` payload 与前端下载卡不是同一模型；改一个字段名会断查询页、结果页或 SSE 解析。
- 影响范围： `backend/api/generate.py`, `backend/models/generate.py`, `backend/services/document_service.py`, `backend/models/sse.py`
- 建议： 新增字段时同步后端模型、service、API response 与 `backend/tests/api/` 断言。

**SSE 事件契约被 named event 绑定：**
- 风险/关注点： `agent_step`、`done`、`error`、`progress`、`heartbeat` 都是 named event，客户端与服务端必须一起改。
- 影响范围： `backend/core/sse_manager.py`, `backend/models/sse.py`, `backend/api/stream.py`, `backend/services/document_service.py`
- 建议： 新事件/字段先同步 `backend/models/sse.py`、SSE 发送方、NDJSON / EventSource 解析与测试。

**generate-only 字段与 rewrite 字段边界很窄：**
- 风险/关注点： `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于初次 generate；`rewrite_source="uploaded_file"` 是上传 rewrite 的路由开关。
- 影响范围： `backend/models/agent_run.py`, `backend/services/agent_run_service.py`, `backend/agents/task_context_assistant/tools.py`, `backend/states/skill_state.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/skills/rewrite/scripts/runtime.py`
- 当前缓解或约束： `backend/tests/services/test_document_service_initial_state.py`、`backend/tests/models/test_generate_request_generation_style.py`、`backend/tests/skills/test_task_skill_runtime.py` 守该边界。
- 建议： 新增生成选项只进 `GenerateRequest` 与初始 generate state。

**结构化表占位符是内部写回入口：**
- 风险/关注点： `[[TABLE:<id>]]` 不再是最终正文必须保留的可见内容；审核、写回、sidecar 恢复与投影表静默丢弃必须严格一致。
- 影响范围： `backend/agents/generation/table_placeholder_utils.py`, `backend/agents/generation/verify_agent_graph.py`, `backend/helper/word_helper/text_parsing.py`, `backend/agents/generation/content_sanitizer.py`
- 当前缓解或约束： `backend/tests/agents/test_table_placeholder_utils.py`、`backend/tests/agents/test_generation_content_agent.py`、`backend/tests/helper/test_text_parsing_table_placeholder.py` 覆盖提取/修复/写回入口。
- 建议： 改 regex/sidecar 匹配/`table_id` 字符集/写回语义时同步测试。

**Prompt 与 bad case 上下文绑定很紧：**
- 风险/关注点： prompt 里既有 generate-only 路由，又有 bad case 锚点规则；改动后若不同步解析器，会让 `reference_text` 或 JSON 结构漂移。
- 影响范围： `backend/prompts/generate_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/retrieval/comment_bad_case_runtime.py`
- 建议： 改 prompt 时同步 `backend/tests/prompts/test_generate_prompt_routing.py`、`backend/tests/prompts/test_comment_prompt_reference_contract.py`、`backend/tests/prompts/test_comment_prompt_bad_case_context.py`。

**Word COM 生命周期必须收尾完整：**
- 风险/关注点： `CoInitialize()`、`Open()`、`Save()`、`Quit()`、`CoUninitialize()` 依赖严格顺序；RPC 错误与缓存损坏只能降级重试，不能真正抢占。
- 影响范围： `backend/util/word_util/word_application_util.py`, `backend/util/word_util/word_com_manager.py`
- 建议： 改 COM 逻辑时先锁住 close/open/save 重试路径，再验证清理顺序与异常释放。

## 扩展边界

**单进程内存边界：**
- 当前能力： `backend/core/sse_manager.py`、`backend/task/task_queue_manager.py`、`backend/services/conversation_service.py` 依赖当前进程内状态。
- 限制： 重启即失、跨 worker 不共享、历史回放受 `SSE_MAX_EVENTS_PER_TASK`、`MAX_REWRITE_MESSAGES` 截断。
- 扩展路径： 需更长历史时先引入持久化队列与会话存储。

**Windows COM worker 边界：**
- 当前能力： `backend/util/word_util/word_application_util.py`、`backend/graphs/base_graph.py`、`backend/task/task_queue_manager.py` 只允许串行 Word COM。
- 限制： 长任务阻塞后续 Word 写入；Word/WPS 注册异常拖垮整条链路。
- 扩展路径： 专用 Windows worker 池、任务隔离、外部调度器。

**检索缓存与回放窗口：**
- 当前能力： `backend/retrieval/comment_bad_case_runtime.py` 依赖进程内缓存；`backend/core/sse_manager.py` 只保留有限事件窗口。
- 限制： 多进程重复建索引；晚到客户端看不到完整历史。
- 扩展路径： 显式索引刷新、共享缓存、可持久化事件流。

**本地文件与日志产物：**
- 当前能力： `backend/config/settings.py`、`backend/util/log_util/progress_log.py`、`backend/agents/task_context_assistant/logging.py`、`backend/util/common_util/upload_storage.py` 把数据落在本地磁盘。
- 限制： 上传、生成、审计、workspace 长期累积。
- 扩展路径： 统一保留策略、对象存储、清理策略。

## 高风险依赖

**`pywin32` / Word / WPS COM：**
- 风险/关注点： `backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_com_manager.py`、`backend/scripts/diagnose_word.py` 依赖 Windows Python、本机 Word/WPS COM 与 `pywin32`。
- 影响： WSL/Linux 只能验证无 COM 逻辑，不能证明真实写回。
- 迁移建议： 保持诊断脚本与 Word utility 分层；替代方案需重做 COM 访问层。

**`langgraph` / `deepagents` / LangChain：**
- 风险/关注点： `backend/agents/generation/content_agents.py`、`backend/agents/comments/comment_agent.py`、`backend/services/agent_run_service.py`、`backend/util/common_util/llm_stream_utils.py` 依赖这些运行时。
- 影响： 升级可能改掉 agent 协议、工具调用或流式回调语义。
- 迁移建议： 升级前先跑 `backend/tests/agents/`、`backend/tests/services/test_agent_run_service.py` 与 SSE 相关测试。

**外部 LLM provider：**
- 风险/关注点： `backend/config/settings.py`、`backend/agents/generation/model_factory.py`、`backend/util/common_util/llm_stream_utils.py` 依赖 `DEEPSEEK_API_KEY`、`ARK_API_KEY`、`DASHSCOPE_API_KEY` 与 provider base URL。
- 影响： 长任务失败、JSON 解析失败、流式中断、模型配置漂移。
- 迁移建议： provider 配置集中在 settings；测试只 mock provider，不把 secret 值写进日志。

**向量检索与 embedding provider：**
- 风险/关注点： `backend/retrieval/config.py`、`backend/retrieval/qdrant_store.py`、`backend/retrieval/embeddings.py` 依赖 `EMBEDDING_API_KEY`、`QDRANT_URL`、`QDRANT_API_KEY`。
- 影响： bad case hybrid 检索降级到 `bm25_only` 或直接失败。
- 迁移建议： 继续保留 BM25 fallback；live 检索单独当受控集成环境验证。

**模板与招标详情外部 HTTP 接口：**
- 风险/关注点： `backend/api/template_candidates.py`、`backend/util/common_util/template_candidates.py`、`backend/util/common_util/fetch_tender_data.py` 依赖外部接口字段与主机白名单。
- 影响： 字段变更、主机变更或超时都会让模板候选与招标详情链路失效。
- 迁移建议： 先更新后端模型与工具，再同步前端 client 与测试。

## 缺失的关键能力

**持久化任务存储：**
- 问题： `backend/task/task_queue_manager.py`、`backend/core/sse_manager.py`、`backend/services/conversation_service.py` 仍是内存态。
- Blocks: 重启恢复、跨 worker 查询、历史审计、断线重连后的完整回放。

**统一认证与授权：**
- 问题： `backend/api/`、`backend/services/task_service.py`、`backend/services/conversation_service.py`、`backend/api/download.py` 没有显式共享认证层。
- Blocks: 多用户隔离、任务归属授权、文件下载授权、会话隔离。

**真实 readiness 诊断：**
- 问题： `backend/main.py` 没有验证上传目录、COM、LLM provider、Qdrant/embedding 或外部 HTTP。
- Blocks: 线上自动化运维无法仅靠 readiness 判断能否生成。

**上传内容安全检查：**
- 问题： `backend/api/upload.py`、`backend/util/common_util/upload_storage.py` 只做扩展名与大小过滤。
- Blocks: 不能防住伪装扩展名、恶意文档结构或需隔离执行的内容。

**稳定的 Windows Word COM CI：**
- 问题： `backend/tests/` 没有真实 Word/WPS COM 端到端链路。
- Blocks: 无法自动证明 `.doc/.docx` 真写回、rewrite、补充批注与样式回填闭环。

## 测试覆盖缺口

**队列、公平锁与运行中取消：**
- What’s not tested: `backend/task/task_queue_manager.py` 的 `wait_for_turn()`、`cancel_task()`（含 `call_soon_threadsafe(async_task.cancel())` 路径）、心跳超时；`backend/graphs/base_graph.py` 的 `CrossProcessFileLock`、`invoke_with_timing_async()` 双完成路径。
- 相关文件： `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py`, `backend/services/document_service.py`
- 风险： 锁清理、排队顺序、取消态与终态收敛易在重构中被破坏。
- Priority: High

**完成态生成 API：**
- What’s not tested: `backend/api/generate.py` 在任务完成时把 dict payload 映射到 `GenerateResponse` 的行为。
- 相关文件： `backend/api/generate.py`, `backend/models/generate.py`, `backend/services/document_service.py`, `backend/tests/api/test_generate_api.py`
- 风险： 完成态查询可能返回不符合预期的 shape，影响前端结果页与下载卡。
- Priority: High

**下载、上传与模板代理边界：**
- What’s not tested: `backend/api/download.py` 路径穿越、URL 编码绕过、非文件路径；`backend/api/upload.py`、`backend/util/common_util/upload_storage.py` 扩展名伪装；`backend/util/common_util/template_candidates.py` 协议/主机白名单与年份阻断。
- 相关文件： `backend/api/download.py`, `backend/api/upload.py`, `backend/util/common_util/upload_storage.py`, `backend/api/template_candidates.py`, `backend/util/common_util/template_candidates.py`
- 风险： 安全边界在重构时最易被忽略。
- Priority: High

**真实 Word COM E2E：**
- What’s not tested: `backend/util/word_util/`、`backend/helper/word_helper/`、`backend/nodes/` 的真实 Word/WPS 自动化闭环。
- 相关文件： `backend/util/word_util/`, `backend/helper/word_helper/`, `backend/nodes/`, `backend/scripts/diagnose_word.py`
- 风险： fake object 单测通过不代表真实 COM 行为一致。
- Priority: High

**SSE 重连与多客户端：**
- What’s not tested: `backend/core/sse_manager.py` 的多客户端重连、事件回放窗口、队列溢出。
- 相关文件： `backend/core/sse_manager.py`, `backend/tests/services/test_sse_manager_agent_step.py`
- 风险： 事件 replay、心跳与终态在客户端重连后可能漂移。
- Priority: Medium

**Prompt 与 placeholder 全链路：**
- What’s not tested: `backend/prompts/comment_prompt.py`、`backend/prompts/generate_prompt.py`、`backend/agents/generation/table_placeholder_utils.py` 的端到端组合场景。
- 相关文件： `backend/prompts/comment_prompt.py`, `backend/prompts/generate_prompt.py`, `backend/agents/generation/table_placeholder_utils.py`
- 风险： 单点单测守局部 contract，守不住完整生成→审核→回填链路。
- Priority: Medium

**Retrieval live path：**
- What’s not tested: `backend/retrieval/comment_bad_case_runtime.py`、`backend/retrieval/qdrant_store.py`、`backend/retrieval/embeddings.py` 的真实外部服务行为。
- 相关文件： `backend/retrieval/comment_bad_case_runtime.py`, `backend/retrieval/qdrant_store.py`, `backend/retrieval/embeddings.py`
- 风险： mock 测试无法覆盖 provider、向量库与网络超时的组合故障。
- Priority: Medium

**rewrite 上传分支与 graph 显式流程：**
- What’s not tested: `backend/graphs/skill_graph.py` 的 `RewriteSkillGraph` 在 `rewrite_source="uploaded_file"` 与会话历史双分支下的完整流程。
- 相关文件： `backend/graphs/skill_graph.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/skills/rewrite/scripts/runtime.py`
- 风险： 显式 graph 的条件分支回归时易被破坏。
- Priority: Medium

---

*后端风险分析：2026-06-29*

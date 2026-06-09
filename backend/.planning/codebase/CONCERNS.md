# 后端代码库风险事实地图

**分析日期：** 2026-06-09

**范围：** 仅覆盖 `backend/` 当前后端代码、配置、测试、现有 `backend/.planning/codebase/` 文档和可列名的配置文件。`backend/.env` 与 `backend/.env.example` 只确认存在性，未读取内容；文档只记录环境变量名称，不记录任何值。

## 技术债

**Word COM graph 锁实现存在重复片段：**
- 问题：`backend/graphs/base_graph.py` 顶部存在重复 import，`CrossProcessFileLock` 内也出现重复初始化和 `acquire()` 定义片段；后定义覆盖前定义。
- 涉及文件：`backend/graphs/base_graph.py`
- 影响：该文件同时承载 Word COM 跨进程文件锁、公平队列入口、节点取消检查和进度包装；重复片段会增加锁超时、Windows-only `msvcrt` 行为、取消路径和维护审查的误判风险。
- 修复方式：先补 `CrossProcessFileLock` 获取/释放/超时、`TaskQueueManager.wait_for_turn()`、运行中取消和队列顺序测试，再单独清理重复片段；不要夹在业务功能改动中顺手处理。

**Word 写回与样式匹配逻辑体量集中：**
- 问题：Word helper、类型节点、service 和 agent runtime 中存在多个大型文件，复杂度集中在样式回填、段落边界、表格匹配、批注写回、rewrite 定位和任务收敛。
- 涉及文件：`backend/helper/word_helper/inline_style_ops.py`, `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `backend/services/document_service.py`, `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py`
- 影响：局部改动可能影响 `.doc/.docx` 写回、批注、受保护字段、GNGK 子类型、上传 rewrite 或 SSE 终态。
- 修复方式：修改前定位最窄 helper/节点；优先补 `backend/tests/helper/`、`backend/tests/nodes/`、`backend/tests/graphs/` 或 `backend/tests/services/` 的 focused tests；不要在类型节点中复制已有 helper 逻辑。

**任务、SSE 和会话状态均为进程内态：**
- 问题：任务队列、任务结果、取消事件、SSE 事件缓存和会话 rewrite history 都保存在单进程内存。
- 涉及文件：`backend/task/task_queue_manager.py`, `backend/core/sse_manager.py`, `backend/services/conversation_service.py`, `backend/services/task_service.py`
- 影响：服务重启会丢失任务状态、SSE 重放历史、取消状态和 rewrite 上下文；多进程部署会分裂队列、事件和会话。
- 修复方式：引入持久化前先定义 task store、SSE event id、会话快照一致性、下载文件生命周期和取消语义。

**Readiness 健康检查仍是轻量占位：**
- 问题：`/health/ready` 的 `upload_dir_accessible` 固定为 `True`，代码保留实际目录权限检查 TODO。
- 涉及文件：`backend/main.py`, `backend/config/settings.py`
- 影响：readiness 不能证明 `UPLOAD_DIR` 可写、Word/WPS COM 可用、pywin32 注册正常、LLM provider 可达、Qdrant/embedding 可达或外部 HTTP 可达。
- 修复方式：保留 `/health` 的进程探测语义；新增 readiness 时分项报告上传目录、COM、LLM、Qdrant/embedding 和外部接口，不要把轻量探测当完整生成验收。

**任务完成结果与下载字段存在分散契约：**
- 问题：`DocumentService._build_task_result_payload()` 构造 `output_file`、`file_name`、`file_size`、`model_used` 等字段，但不构造 `download_url`；`read_current_task_public_summary_tool` 用 `result_payload.get("download_url")` 判断 `download_ready`。
- 涉及文件：`backend/services/document_service.py`, `backend/agents/task_context_assistant/tools.py`, `backend/models/generate.py`, `backend/models/sse.py`
- 影响：任务已产出 `output_file` 时，agent run 公共摘要仍可能显示 `download_ready=False`；后续改下载卡或公共摘要时容易产生后端/前端理解漂移。
- 修复方式：统一 task result、SSE `done`、`GenerateResponse` 和 agent public summary 对“下载就绪”的判定；若继续不暴露下载路径，则用 `output_file` 存在性派生布尔值。

## 已知问题

**`GET /api/generate/{task_id}` 完成态返回 shape 不匹配：**
- 症状：`backend/api/generate.py` 在完成态把 `task_info.result` 直接赋给 `GenerateResponse.output_file`；`output_file` 是 `Optional[str]`，而实际任务结果由 `DocumentService._build_task_result_payload()` 构造成 dict。
- 涉及文件：`backend/api/generate.py`, `backend/models/generate.py`, `backend/services/document_service.py`, `backend/tests/api/test_generate_api.py`
- 触发方式：调用 `GET /api/generate/{task_id}` 查询已完成任务。
- 临时处理：使用 `GET /api/tasks/{task_id}` 获取完整 `TaskInfo.result`，或通过 SSE `done` 事件和前端下载卡读取结果。

**`read_current_task_public_summary_tool` 的 `download_ready` 依赖不存在的 result 字段：**
- 症状：公共摘要工具只检查 `result_payload["download_url"]`，但标准任务完成 payload 当前不写 `download_url`。
- 涉及文件：`backend/agents/task_context_assistant/tools.py`, `backend/services/document_service.py`, `backend/tests/agents/test_task_context_assistant_tools.py`
- 触发方式：agent run 读取已完成任务公共摘要。
- 临时处理：把该摘要视为“是否有后端显式下载链接”的状态，而不是“任务是否已生成文件”的状态。

**Readiness 上传目录检查未真实执行：**
- 症状：`/health/ready` 返回 `upload_dir_accessible: True`，不检查 `settings.UPLOAD_DIR` 是否存在、可写或磁盘可用。
- 涉及文件：`backend/main.py`, `backend/config/settings.py`
- 触发方式：上传目录不存在、不可写、路径配置错误或磁盘异常时请求 `/health/ready`。
- 临时处理：用真实上传、真实生成任务或 `backend/scripts/diagnose_word.py` 做可用性验证。

## 安全注意事项

**客户文本、路径、traceback、token 和 prompt 日志边界：**
- 风险：LLM key、token、客户原文、私有路径、traceback、下载路径、完整 prompt 或 retrieval payload 进入日志、SSE、agent workspace、测试夹具或用户可见事件。
- 涉及文件：`backend/main.py`, `backend/services/document_service.py`, `backend/agents/task_context_assistant/logging.py`, `backend/agents/task_context_assistant/tools.py`, `backend/util/log_util/`, `backend/nodes/common_word_nodes/generate_comments.py`, `backend/nodes/common_word_nodes/comment_agent.py`, `backend/agents/generation/workspace.py`, `backend/agents/comments/workspace.py`
- 当前缓解：agent run 审计使用 `scrub_sensitive_text()`；只读摘要工具不返回完整结果和下载路径；retrieval 命中详情不进入 SSE 或 `agent_step`；全局异常响应对客户端返回泛化 500。
- 建议：新增日志、审计、agent run 事件或工具返回字段时先定义白名单；进度/SSE 日志只写摘要；内部 `backend/prompts_log/` 和 `backend/logs/` 继续视为敏感产物。

**进度日志与执行日志没有统一 scrub 层：**
- 风险：`progress_log` 会经 `SSELogHandler` 推送 INFO 及以上日志到前端，`execution_log` 会记录项目经办人、项目编号和项目名称；多个 Word/agent 节点会记录文件路径或业务摘要。
- 涉及文件：`backend/util/log_util/progress_log.py`, `backend/util/log_util/sse_log_handler.py`, `backend/util/log_util/execution_log.py`, `backend/util/word_util/word_application_util.py`, `backend/services/document_service.py`
- 当前缓解：agent run 专用日志有 scrub；全局异常响应不向客户端返回 traceback。
- 建议：用户可见日志和长期日志都采用显式白名单；不要在 `progress_log.info()` 中写客户原文、真实路径、密钥值或完整 traceback。

**业务 API 未检测到统一认证/授权层：**
- 风险：业务 router 没有统一 `Depends()` 认证 gate；任务、上传文件、下载、agent run 和会话状态主要依赖调用方传入的 `task_id`、`conversation_id` 或文件路径。
- 涉及文件：`backend/main.py`, `backend/api/`, `backend/services/task_service.py`, `backend/services/conversation_service.py`, `backend/api/download.py`, `backend/models/agent_run.py`
- 当前缓解：下载接口做 `UPLOAD_DIR` containment；agent run 公共摘要校验 `conversation_id` 与任务会话匹配；当前更像本地/受控环境假设。
- 建议：进入多用户或生产环境前定义认证、任务归属、会话归属、文件归属和下载授权，并同步前端 API client、错误模型和测试。

**下载接口路径遍历边界：**
- 风险：下载接口接收 URL 编码完整路径，任意改动都可能破坏 containment。
- 涉及文件：`backend/api/download.py`, `backend/config/settings.py`
- 当前缓解：`validate_file_path()` 解码后 `resolve()`，再强制 `relative_to(settings.UPLOAD_DIR)`；不存在和非文件路径会拒绝。
- 建议：修改下载逻辑时保留 `relative_to(settings.UPLOAD_DIR)`；补齐 path traversal、URL 编码绕过、非文件、缺失文件和成功下载测试。

**模板候选代理 SSRF 边界：**
- 风险：外部模板下载代理如果放宽 URL 校验，会变成 SSRF 或任意内容代理。
- 涉及文件：`backend/api/template_candidates.py`, `backend/util/common_util/template_candidates.py`, `backend/config/settings.py`
- 当前缓解：`validate_template_download_url()` 限制 `http/https` 和 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS`；自动选择模板前会检查年份。
- 建议：新增模板来源或主机时同步白名单、URL parse、年份阻断和 API tests；前端不要直接访问外部模板 URL。

**上传文件只做扩展名和大小校验：**
- 风险：`persist_file_bytes()` 只按清洗后的文件名扩展名和字节大小判断，未检测实际 MIME、magic bytes 或文档结构安全；恶意内容仍可落盘。
- 涉及文件：`backend/api/upload.py`, `backend/util/common_util/upload_storage.py`, `backend/config/settings.py`
- 当前缓解：`sanitize_filename()` 清洗文件名；`ALLOWED_EXTENSIONS` 和 `MAX_UPLOAD_SIZE` 限制类型与大小；保存路径由 `UPLOAD_DIR` 生成。
- 建议：需要生产安全边界时增加 magic bytes、文档解析隔离、病毒扫描或隔离区；测试覆盖伪造扩展名和异常写入。

**Provider 与 `.env` 配置边界：**
- 风险：LLM provider、embedding、Qdrant、LangSmith 和外部接口配置来自环境变量；retrieval 配置在 `python-dotenv` 未加载成功时会手写读取 `backend/.env` 并填充 `os.environ`。
- 涉及文件：`backend/config/settings.py`, `backend/retrieval/config.py`, `backend/util/common_util/llm_stream_utils.py`, `backend/agents/generation/model_factory.py`
- 当前缓解：公开错误主要返回缺失变量名，例如 `DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY`、`ARK_API_KEY`、`EMBEDDING_API_KEY`，不应返回值。
- 建议：日志、文档、测试夹具和诊断脚本只记录变量名和缺失状态；不要打印 secret value。

## 性能瓶颈

**Word COM 串行执行：**
- 问题：`DocumentService` 用 `ThreadPoolExecutor(max_workers=4)` 接收后台任务，但 graph 内通过 `TaskQueueManager` 公平队列、`CrossProcessFileLock` 和 `com_lock()` 串行保护 Word COM。
- 涉及文件：`backend/services/document_service.py`, `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py`, `backend/util/word_util/word_com_manager.py`, `backend/util/word_util/word_application_util.py`
- 原因：Word/WPS COM 是稀缺临界资源，打开、写入、保存和关闭不适合并发。
- 改进路径：横向扩展前设计外部队列、专用 Windows worker、任务持久化和文件隔离；不要简单提高线程数。

**取消检查不是抢占式中断：**
- 问题：`wrap_node_with_progress()` 只在节点执行前后检查取消；`cancel_task()` 会尝试取消 async task，但同步 Word COM 调用仍可能等到当前调用返回。
- 涉及文件：`backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `backend/services/document_service.py`, `backend/util/word_util/word_application_util.py`
- 原因：COM 调用、文件操作和部分同步 helper 不能被可靠抢占。
- 改进路径：长耗时节点内增加安全取消检查点；UI 文案区分“已请求取消”和“资源已释放”；测试覆盖运行中取消、锁内取消和后续任务排队。

**LLM、agent 和模板候选 AI 重排延迟：**
- 问题：初次生成、rewrite、content agent、comment agent、模板候选同优先级 AI 重排和流式快照都依赖外部 LLM。
- 涉及文件：`backend/util/common_util/llm_stream_utils.py`, `backend/agents/generation/content_agents.py`, `backend/agents/comments/comment_agent.py`, `backend/services/template_candidate_ranking_service.py`, `backend/services/document_service.py`
- 原因：网络、模型推理、流式超时、JSON 修复、审核修订轮次和重排分组数量会增加长任务时延。
- 改进路径：保持 `LLM_STREAM_TIMEOUT_SECONDS` 集中配置；模板候选重排仅限同优先级候选；SSE/NDJSON 只发摘要和节流快照。

**Bad case retrieval hybrid 路径按条款调用外部向量层：**
- 问题：`retrieve_bad_case_hits()` 加载本地 bad case、拆分正文条款，并在 hybrid 模式下调用 embedding 和 Qdrant；失败后降级 `bm25_only`。
- 涉及文件：`backend/retrieval/comment_bad_case_runtime.py`, `backend/retrieval/embeddings.py`, `backend/retrieval/qdrant_store.py`, `backend/nodes/common_word_nodes/generate_comments.py`, `backend/nodes/common_word_nodes/comment_agent.py`
- 原因：正文条款数量、embedding 网络延迟、Qdrant 健康检查和 vector search 都影响批注生成前置耗时。
- 改进路径：保留本地 BM25 fallback；监控 retrieval warning；需要提速时考虑 per-task cache、top-k 限制和异步批量 embedding。

**样式回填匹配复杂度高：**
- 问题：`inline_style_ops.py` 负责编号、片段、本地候选、表格、字体和 `style_writeback_mode` 过滤，单文件体量和分支数量高。
- 涉及文件：`backend/helper/word_helper/inline_style_ops.py`, `backend/tests/helper/test_inline_style_ops.py`, `backend/tests/nodes/test_update_word_inline_style_writeback.py`
- 原因：Word 文档结构、表格、编号、局部候选和 fallback 规则复杂。
- 改进路径：修改时使用 focused fixture 和单测覆盖；真实 Word/WPS 行为仍需人工或诊断闭环。

## 脆弱区域

**Word COM 队列、锁和取消链路：**
- 涉及文件：`backend/services/document_service.py`, `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py`, `backend/util/word_util/word_com_manager.py`, `backend/util/word_util/word_application_util.py`
- 为什么脆弱：任务创建、后台线程、fair queue、跨进程文件锁、COM lock、async task cancel、节点取消检查和 SSE 终态必须协同；任意一层漏掉都会造成假完成、假取消、队列阻塞或 Word 进程残留。
- 安全修改：所有 Word 写入继续经由任务队列和 graph；不要在 API route、service、前端或临时脚本中直接操作 COM；改锁或取消时补排队、运行中取消、超时和异常释放测试。
- 测试覆盖：当前检测到 `backend/tests/services/test_task_service_task_kind.py`、`backend/tests/progress/test_uploaded_rewrite_progress_tracking.py` 等覆盖 task kind/progress，但未检测到 fair lock、`CrossProcessFileLock`、运行中取消和真实 COM 锁单测。

**SSE `agent_step`、`done`、`error` 和任务状态契约：**
- 涉及文件：`backend/models/sse.py`, `backend/core/sse_manager.py`, `backend/services/document_service.py`, `backend/api/stream.py`, `backend/models/task.py`, `backend/services/task_service.py`
- 为什么脆弱：前端依赖 named event、`agent_step` payload、`done`/`error` 终态、`style_writeback`/`comment_writeback` 摘要和任务状态查询；随意改字段会断过程卡、下载卡或重连。
- 安全修改：新增字段保持向后兼容；新增 SSE event type 同步后端模型、发送方、前端 union/parser 和测试；取消仍通过 `error` 事件且 `is_fatal=False` 表示。
- 测试覆盖：`backend/tests/models/test_sse_agent_step.py`, `backend/tests/services/test_sse_manager_agent_step.py`, `backend/tests/services/test_document_service_agent_step.py`

**上传文件 rewrite 来源与 generate-only 字段边界：**
- 涉及文件：`backend/models/agent_run.py`, `backend/services/agent_run_service.py`, `backend/agents/task_context_assistant/tools.py`, `backend/services/document_service.py`, `backend/states/skill_state.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/skills/rewrite/scripts/runtime.py`
- 为什么脆弱：上传文件 rewrite 必须用同一 rewrite skill 链路并设置 `rewrite_source="uploaded_file"`；`generation_style`、`generation_mode`、`comment_generation_mode` 和 `style_writeback_mode` 只属于初次 generate，不得进入 rewrite 请求模型、skill state 或 prompt surface。
- 安全修改：新增 generate option 时只进入 `GenerateRequest` 和初始 generate state；rewrite tool input、skill state 和 rewrite prompt types 继续禁止 generate-only 字段；上传文件 rewrite 继续要求 `form_type`、完整锚点、`tender_lx`、`fund_source_lx`。
- 测试覆盖：`backend/tests/services/test_document_service_initial_state.py`, `backend/tests/services/test_agent_run_service.py`, `backend/tests/skills/test_task_skill_runtime.py`, `backend/tests/progress/test_uploaded_rewrite_progress_tracking.py`

**GNGK 子类型继承和覆写：**
- 涉及文件：`backend/graphs/gngk_hw_zc_tender_graph.py`, `backend/graphs/gngk_hw_cz_tender_graph.py`, `backend/graphs/gngk_fw_zc_tender_graph.py`, `backend/graphs/gngk_fw_cz_tender_graph.py`, `backend/config/tender_config.py`, `backend/models/generate.py`
- 为什么脆弱：`gngk_hw_cz`、`gngk_fw_zc` 等子类型共享标准 graph 主干但覆写 delete/update/replacement；前端 `gngk` UI 类型提交到后端前必须分派为具体 `FormType`。
- 安全修改：改任一 `gngk_*` 时同步检查 graph class attributes、protected profile、content mode、form type、URL/注册表/转换器和测试。
- 测试覆盖：`backend/tests/graphs/test_gngk_tender_graph.py`, `backend/tests/graphs/test_gngk_*_generation_mode_agent.py`, `backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`, `backend/tests/nodes/test_gngk_fw_zc_update_word.py`

**补充批注依赖会话 latest state：**
- 涉及文件：`backend/api/comment_supplement.py`, `backend/services/document_service.py`, `backend/services/conversation_service.py`, `backend/graphs/comment_supplement_graph.py`, `backend/nodes/common_word_nodes/comment_supplement.py`
- 为什么脆弱：补充批注必须基于当前会话 latest `rewrite_state.prepared_doc_path` 和 `polished_text`；source file 不匹配会写回错误副本。
- 安全修改：创建任务前继续校验 `conversation_id`、`source_file`、latest path、文件存在和路径匹配；成功后更新 latest `rewrite_state.prepared_doc_path`。
- 测试覆盖：`backend/tests/api/test_comment_supplement_api.py`, `backend/tests/services/test_document_service_comment_supplement.py`, `backend/tests/graphs/test_comment_supplement_graph.py`

**Bad case retrieval 正式接入但不对前端公开：**
- 涉及文件：`backend/retrieval/`, `backend/nodes/common_word_nodes/generate_comments.py`, `backend/nodes/common_word_nodes/comment_agent.py`, `backend/prompts/comment_prompt.py`
- 为什么脆弱：retrieval JSON 是后端 prompt/retrieval 审计产物，prompt context 刻意排除 `case_id`、`score`、`chunk_id` 和匹配条款；命中详情不能进入 SSE、下载卡或 `agent_step`。
- 安全修改：保持 `comment_generation_mode=off` 不触发 retrieval；rewrite 不触发 retrieval；新增 retrieval 字段只进入审计 JSON，前端展示仍用摘要。
- 测试覆盖：`backend/tests/retrieval/test_comment_bad_case_runtime.py`, `backend/tests/nodes/test_generate_comments_bad_case.py`, `backend/tests/nodes/test_comment_agent_writeback_node.py`, `backend/tests/prompts/test_comment_prompt_bad_case_context.py`

**Prompt literal、provider 和机器契约：**
- 涉及文件：`backend/prompts/generate_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/prompts/template_candidate_ranking_prompt.py`, `backend/prompts/rewrite_target_selection_prompt.py`, `backend/util/common_util/llm_stream_utils.py`, `backend/agents/generation/json_utils.py`
- 为什么脆弱：prompt 示例、JSON 字段、provider key、机器标识符和解析规则被 tests、agent parsing 或前端过程展示依赖。
- 安全修改：改 prompt 时同步 parser/validator 测试；不要翻译 `content_agent`、`comment_agent`、`agent_step`、tool names、provider id 等机器标识符。
- 测试覆盖：`backend/tests/prompts/test_generate_prompt_routing.py`, `backend/tests/prompts/test_comment_prompt_reference_contract.py`, `backend/tests/prompts/test_comment_prompt_bad_case_context.py`, `backend/tests/agents/test_generation_content_agent.py`

## 扩展限制

**Task/SSE/conversation 内存状态：**
- 当前容量：单进程内由内存、`SSE_MAX_EVENTS_PER_TASK`、`SSE_EVENT_TTL`、`MAX_REWRITE_MESSAGES`、`TASK_HEARTBEAT_TIMEOUT` 和任务清理周期限制。
- 限制：服务重启丢任务、事件、会话 rewrite history 和取消状态；多进程无法共享当前队列。
- 扩展路径：外部队列、持久化 task store、集中事件流、会话状态存储和 artifact 生命周期管理。

**后台 Word COM worker：**
- 当前容量：后台线程可排队多个任务，但 Word 写入路径仍通过 queue + graph lock + COM lock 串行。
- 限制：长 Word/LLM 任务会阻塞后续 Word 写入；Windows COM 注册或 Word/WPS 进程异常会影响整个生成链路。
- 扩展路径：专用 Windows worker 池；每个 worker 内仍需 COM 互斥、文件隔离、取消检查和诊断。

**本地文件与日志产物：**
- 当前容量：上传文件、生成文件、agent workspace、prompt/retrieval 日志和运行日志依赖本地磁盘；启动时只清理 `backend/logs` 总量。
- 限制：多用户或长时间运行会积累 `UPLOAD_DIR`、`backend/prompts_log/`、agent/comment workspace 和 retrieval JSON。
- 扩展路径：定义上传/生成文件保留策略、对象存储、审计日志保留策略、敏感产物清理和下载授权。

**Retrieval cache 是进程内缓存：**
- 当前容量：`load_bad_case_runtime_index()` 按 bad case 目录签名缓存 BM25 index；hybrid 层依赖外部 Qdrant/embedding。
- 限制：多进程重复建索引；bad case 文件变化只在本进程缓存签名检查后生效；外部向量层不可用会降级。
- 扩展路径：保持 BM25 fallback；需要跨进程一致性时引入显式索引刷新、共享缓存或服务化 retrieval。

## 依赖风险

**`pywin32` / Word/WPS COM / `msvcrt`：**
- 风险：完整 Word 写回依赖 Windows Python、本机 Word/WPS COM 注册、`pywin32` 和 Windows `msvcrt` 文件锁。
- 影响：WSL/Linux pytest 只能验证 no-COM 逻辑，不能证明真实 `.doc/.docx` 写回。
- 迁移计划：保持 `backend/util/word_util/` 诊断分层；替代方案需要重写 Word 操作层、样式回填和锁策略。

**`deepagents` / LangChain agent runtime：**
- 风险：content agent、comment agent 和 task context assistant 依赖 `deepagents`、LangChain model factory 和工具调用协议。
- 影响：API 变化会影响 `generation_mode=agent`、补充批注、rewrite agent run 前置流和 `agent_step`。
- 迁移计划：升级时优先跑 `backend/tests/agents/`、`backend/tests/services/test_agent_run_service.py`、`backend/tests/nodes/test_content_agent_generate.py` 和 SSE `agent_step` 测试。

**外部 LLM providers：**
- 风险：DeepSeek、ARK/Doubao、DashScope/Qwen 的 key、base URL、模型名、超时或响应格式变化会影响生成、rewrite、批注和模板候选重排。
- 影响：长任务失败、流式中断、JSON 解析失败、agent 输出异常或 provider 错误暴露。
- 迁移计划：通过 `backend/config/settings.py`、`backend/util/common_util/llm_stream_utils.py` 和 `backend/agents/generation/model_factory.py` 集中配置；提交测试继续 mock 外部服务。

**向量检索 provider：**
- 风险：Hybrid retrieval 依赖 `QDRANT_URL`、`QDRANT_API_KEY`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL` 或 `DASHSCOPE_API_KEY`。
- 影响：批注 bad case hybrid retrieval 降级到 `bm25_only`；缺 key 或向量层失败会增加 warning 并降低语义检索质量。
- 迁移计划：保持 `bm25_only` fallback 和 retrieval JSON；live 诊断使用 `backend/scripts/test_comment_hybrid_retrieval.py`，不要把诊断脚本当 CI。

**外部招标详情和模板候选 HTTP 接口：**
- 风险：ERP/外部接口 URL、返回字段、模板文件主机或网络状态变化会影响招标详情和模板候选。
- 影响：`backend/api/tender.py`、`backend/api/template_candidates.py` 可能返回 502、候选格式错误或模板选择失败。
- 迁移计划：保持外部请求 timeout、格式归一化、host 白名单和 API tests；字段变化先更新后端模型/工具再同步前端。

## 缺失关键能力

**持久化任务存储：**
- 问题：任务、取消事件、任务结果和 SSE event buffer 不持久化。
- 阻塞：服务重启恢复、多进程部署、跨 worker 查询和历史任务审计。

**统一认证与授权：**
- 问题：未检测到统一 API auth layer。
- 阻塞：多用户隔离、任务归属授权、文件下载授权、会话授权和生产权限控制。

**真实 readiness 诊断：**
- 问题：`/health/ready` 不检查上传目录、Word COM、LLM provider、Qdrant/embedding 或外部接口。
- 阻塞：自动化运维判断真实生成能力。

**产物保留与敏感产物清理策略：**
- 问题：上传目录、生成文件、prompt/retrieval 审计、agent workspace 和运行日志未形成统一保留/清理策略。
- 阻塞：长期运行磁盘容量控制、客户材料生命周期管理和合规清理。

**稳定的 Windows Word COM CI：**
- 问题：未检测到自动化 Windows + Word/WPS COM 端到端 CI。
- 阻塞：自动证明真实 `.doc/.docx` 生成、rewrite、补充批注、批注写回和样式回填闭环。

**显式 cancelled SSE 终态：**
- 问题：SSE 模型只有 `done` 和 `error` 终态；取消通过 `error` 且 `is_fatal=False` 表达。
- 阻塞：前端或外部消费者如果只按 event name 判断，会把取消误归类为失败。

## 测试覆盖缺口

**`GET /api/generate/{task_id}` 完成态：**
- 未覆盖内容：已完成任务的 `GenerateResponse` shape、`output_file` 字段类型和 result payload 映射。
- 涉及文件：`backend/api/generate.py`, `backend/tests/api/test_generate_api.py`, `backend/services/document_service.py`
- 风险：完成态查询可能触发响应模型错误或返回非预期结构。
- 优先级：高

**队列、公平锁和运行中取消：**
- 未覆盖内容：`TaskQueueManager.wait_for_turn()` 顺序、排队取消、运行中取消、heartbeat 超时取消、`CrossProcessFileLock` 超时和 `TaskCancelledException` 传播。
- 涉及文件：`backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py`, `backend/services/document_service.py`
- 风险：锁清理、取消状态、SSE 终态或后续任务排队被破坏时不容易被当前测试发现。
- 优先级：高

**上传/下载安全边界用例：**
- 未覆盖内容：下载 path traversal、URL 编码绕过、非文件路径、伪造扩展名、MIME 不匹配、magic bytes 不匹配和异常落盘。
- 涉及文件：`backend/api/download.py`, `backend/api/upload.py`, `backend/util/common_util/upload_storage.py`
- 风险：安全边界在重构或扩展时被破坏。
- 优先级：高

**模板候选 URL 和年份阻断：**
- 未覆盖内容：`validate_template_download_url()` 的协议限制、host 白名单、下载代理 403/400 分支、`year < 2025` 阻断和年份缺失阻断。
- 涉及文件：`backend/api/template_candidates.py`, `backend/util/common_util/template_candidates.py`, `backend/tests/api/test_template_candidates.py`
- 风险：SSRF 防线、模板年份规则或 API 错误 shape 漂移。
- 优先级：高

**真实 Word COM E2E：**
- 未覆盖内容：真实 Word/WPS COM 下完整生成、rewrite、补充批注、样式回填、批注写回和 `.doc/.docx` 保存。
- 涉及文件：`backend/util/word_util/`, `backend/nodes/`, `backend/helper/word_helper/`, `backend/scripts/diagnose_word.py`
- 风险：fake object 单测通过但真实 COM range/table/comment/save 行为不同。
- 优先级：发布验收高

**认证与归属隔离：**
- 未覆盖内容：任务、会话、上传文件、下载文件和 agent run 是否属于同一用户/会话的统一授权。
- 涉及文件：`backend/api/`, `backend/services/task_service.py`, `backend/services/conversation_service.py`, `backend/agents/task_context_assistant/tools.py`
- 风险：引入多用户场景时出现越权查询、取消或下载。
- 优先级：高，进入非本地受控环境时尤其需要补齐。

**真实外部服务：**
- 未覆盖内容：真实 LLM、外部招标详情、模板候选接口、Qdrant 和 embedding 服务的 live 行为。
- 涉及文件：`backend/util/common_util/llm_stream_utils.py`, `backend/util/common_util/fetch_tender_data.py`, `backend/util/common_util/template_candidates.py`, `backend/retrieval/`
- 风险：配置、网络、字段或 provider API 变化导致运行时失败。
- 优先级：中；提交测试仍应继续 mock 外部服务。

**前后端完整链路：**
- 未覆盖内容：浏览器端上传、agent run、任务创建、SSE、下载、补充批注和 rewrite 的完整闭环。
- 涉及文件：后端入口在 `backend/api/`，前端 API client 和 UI 测试位于 `frontend/`。
- 风险：后端 API/SSE shape 与前端解析漂移。
- 优先级：高，跨系统改动时必须验证。

---

*风险审计：2026-06-09*

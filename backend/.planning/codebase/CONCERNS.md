# 后端风险事实地图

**分析日期：** 2026-06-08

**范围：** 仅覆盖 `backend/` 后端代码、配置、测试、README/项目文档和必要根级约定。`backend/.env` 与 `backend/.env.example` 只确认存在性，不读取内容；文档只记录环境变量名称和风险边界，不记录任何值。

## 技术债

**`BaseGraph` 锁实现存在重复片段：**
- 问题： `backend/graphs/base_graph.py` 中有重复 import，并且 `CrossProcessFileLock` 内出现重复 `acquire()` 定义/初始化片段；后定义覆盖前定义，阅读和维护锁语义时容易误判。
- 涉及文件： `backend/graphs/base_graph.py`
- 影响： Word COM 串行锁、跨进程文件锁、取消检查和进度包装是后端核心临界路径；重复片段会提高修复锁超时、Windows-only `msvcrt` 行为和取消路径的风险。
- 修复方式： 先补充锁获取、释放、超时、取消和队列顺序测试，再单独清理重复片段；不要把锁清理夹在业务功能变更里。

**Word 写回与样式匹配逻辑体量集中：**
- 问题： Word helper、类型节点、service 和 agent runtime 中存在多个大型文件，复杂度集中在样式回填、段落边界、表格匹配、批注写回和任务收敛。
- 涉及文件： `backend/helper/word_helper/inline_style_ops.py`, `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `backend/services/document_service.py`, `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py`
- 影响： 小改动可能影响 `.doc/.docx` 写回、批注、受保护字段、GNGK 子类型或 SSE 终态。
- 修复方式： 修改前定位最窄 helper/节点；优先扩展 `backend/tests/helper/`、`backend/tests/nodes/` 和相关 graph/service 测试；不要在类型节点中复制已有 helper 逻辑。

**任务、SSE 和会话状态是进程内状态：**
- 问题： 任务队列、任务结果、取消事件、SSE 事件缓存和 rewrite 会话历史都保存在单进程内存。
- 涉及文件： `backend/task/task_queue_manager.py`, `backend/core/sse_manager.py`, `backend/services/conversation_service.py`, `backend/services/task_service.py`
- 影响： 服务重启会丢失任务状态、SSE 重放历史和 rewrite 上下文；多进程部署会分裂队列、事件和会话。
- 修复方式： 引入持久化前先定义任务恢复、SSE event id、会话快照一致性、下载文件生命周期和取消语义。

**Readiness 健康检查是轻量占位：**
- 问题： `/health/ready` 的 `upload_dir_accessible` 当前固定为 `True`，代码中保留实际目录权限检查 TODO。
- 涉及文件： `backend/main.py`
- 影响： readiness 不能证明 `UPLOAD_DIR` 可写、Word/WPS COM 可用、pywin32 注册正常、LLM provider 可达或外部 HTTP 可达。
- 修复方式： 保持 `/health` 进程探测语义；新增 readiness 检查时分项报告上传目录、COM、LLM provider、Qdrant/embedding 和外部 HTTP，不要把轻量探测当完整生成验收。

**Retrieval `.env` fallback 是敏感配置边界：**
- 问题： `backend/retrieval/config.py` 在 `python-dotenv` 未加载成功时会手写读取 `backend/.env` 并填充 `os.environ`。
- 涉及文件： `backend/retrieval/config.py`, `backend/config/settings.py`
- 影响： 运行时可用，但诊断、日志和文档生成必须避免输出真实 key；agent 扫描也不能读取 `.env` 内容。
- 修复方式： 日志只记录变量名和缺失状态；文档只列 `EMBEDDING_API_KEY`、`DASHSCOPE_API_KEY`、`QDRANT_API_KEY` 等变量名；不要打印 env 值。

## 已知问题

**`GET /api/generate/{task_id}` 完成态返回 shape 不匹配：**
- 症状： `backend/api/generate.py` 在任务完成时把 `task_info.result` 直接赋给 `GenerateResponse.output_file`，而 `GenerateResponse.output_file` 是 `Optional[str]`；任务结果实际由 `DocumentService._build_task_result_payload()` 构造为 dict。
- 涉及文件： `backend/api/generate.py`, `backend/models/generate.py`, `backend/services/document_service.py`, `backend/tests/api/test_generate_api.py`
- 触发方式： 调用 `GET /api/generate/{task_id}` 查询已完成任务。
- 临时处理： 使用 `GET /api/tasks/{task_id}` 获取完整 `TaskInfo.result`，或通过 SSE `done` 事件/下载卡获取文件信息。

**Readiness 上传目录检查未真实执行：**
- 症状： `/health/ready` 返回 `upload_dir_accessible: True`，但不检查 `settings.UPLOAD_DIR` 是否存在或可写。
- 涉及文件： `backend/main.py`, `backend/config/settings.py`
- 触发方式： 上传目录不存在、不可写或磁盘异常时请求 `/health/ready`。
- 临时处理： 使用真实上传、实际生成任务或 `backend/scripts/diagnose_word.py`/人工 Word COM 闭环验证。

## 安全注意事项

**客户文本、路径、traceback 和 token 泄漏边界：**
- 风险： `.env`、LLM key、token、客户原文、私有路径、traceback、下载路径或完整任务结果进入日志、prompt/retrieval 审计文件、agent workspace、测试夹具或用户可见事件。
- 涉及文件： `backend/config/settings.py`, `backend/main.py`, `backend/services/document_service.py`, `backend/agents/task_context_assistant/logging.py`, `backend/agents/task_context_assistant/tools.py`, `backend/nodes/common_word_nodes/generate_comments.py`, `backend/nodes/common_word_nodes/comment_agent.py`, `backend/util/log_util/`
- 当前缓解： Agent run 审计使用 `scrub_sensitive_text()`；只读摘要工具不返回完整结果和下载路径；retrieval 命中详情不进入 SSE、下载卡或 `agent_step`；全局异常响应对客户端返回泛化 500。
- 建议： 新增日志、审计、agent run 事件或工具返回字段时先定义白名单；用户可见进度只写摘要；内部 prompt/retrieval 日志继续视为敏感产物。

**业务 API 未检测到统一认证/授权层：**
- 风险： 业务 router 没有统一 `Depends()` 认证 gate；任务、上传文件、下载、agent run 和会话状态主要依赖调用方传入的会话/任务标识。
- 涉及文件： `backend/main.py`, `backend/api/`, `backend/models/agent_run.py`, `backend/services/task_service.py`, `backend/api/download.py`
- 当前缓解： 本地/受控环境假设；下载接口做 `UPLOAD_DIR` containment；agent run 公共摘要校验 `conversation_id` 与任务会话匹配。
- 建议： 进入多用户或生产环境前定义认证、任务归属、文件归属、会话归属和下载授权；同步前端 API client、错误模型和测试。

**下载接口路径遍历边界：**
- 风险： 下载接口接收 URL 编码完整路径，任意改动可能破坏 containment。
- 涉及文件： `backend/api/download.py`, `backend/config/settings.py`, `backend/tests/api/`
- 当前缓解： `validate_file_path()` 对解码路径 `resolve()` 后强制 `relative_to(settings.UPLOAD_DIR)`；非文件和不存在路径返回错误。
- 建议： 修改下载逻辑时保留 `relative_to(settings.UPLOAD_DIR)`；补充路径穿越、URL 编码、非文件、缺失文件和成功下载测试。

**模板候选代理 SSRF 边界：**
- 风险： 外部模板下载代理如果放宽 URL 校验，可能变成 SSRF 或任意内容代理。
- 涉及文件： `backend/api/template_candidates.py`, `backend/util/common_util/template_candidates.py`, `backend/config/settings.py`, `backend/tests/api/test_template_candidates.py`
- 当前缓解： `validate_template_download_url()` 限制 `http/https` 和 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS`；模板选择会先检查年份规则，再保存到上传区。
- 建议： 新增下载来源或主机时同步白名单、URL parse、年份阻断和 API tests；不要让前端组件直接访问外部模板 URL。

**上传文件只做扩展名和大小校验：**
- 风险： `persist_file_bytes()` 按文件名扩展名与字节大小判断，未检测实际 MIME/文件签名；恶意内容仍可落盘。
- 涉及文件： `backend/api/upload.py`, `backend/util/common_util/upload_storage.py`, `backend/config/settings.py`
- 当前缓解： `sanitize_filename()` 清洗文件名；`ALLOWED_EXTENSIONS` 和 `MAX_UPLOAD_SIZE` 限制类型与大小；保存路径由 `UPLOAD_DIR` 生成。
- 建议： 需要生产安全边界时增加 magic bytes/文档解析安全检查、病毒扫描或隔离区；测试覆盖伪造扩展名和异常写入。

## 性能瓶颈

**Word COM 串行执行：**
- 问题： `DocumentService` 使用 `ThreadPoolExecutor(max_workers=4)` 接收后台任务，但 graph 内仍通过 `TaskQueueManager` 公平队列和 `CrossProcessFileLock` 串行保护 Word COM 写入。
- 涉及文件： `backend/services/document_service.py`, `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py`, `backend/util/word_util/word_com_manager.py`
- 原因： Word/WPS COM 是稀缺临界资源，文档打开、写入、保存和关闭不适合并发。
- 改进路径： 横向扩展前设计外部队列、专用 Windows worker、持久化任务状态和文件隔离；不要简单提高线程数。

**LLM 和 agent 循环延迟：**
- 问题： 初次生成、rewrite、content agent、comment agent、模板候选 AI 重排和流式快照都依赖外部 LLM。
- 涉及文件： `backend/util/common_util/llm_stream_utils.py`, `backend/agents/generation/content_agents.py`, `backend/agents/comments/comment_agent.py`, `backend/services/template_candidate_ranking_service.py`, `backend/services/document_service.py`
- 原因： 网络、模型推理、审核修订轮次、流式超时和 JSON 修复都会增加长任务时延。
- 改进路径： 保持 `LLM_STREAM_TIMEOUT_SECONDS` 集中配置；对可选 AI 重排保持范围限制；SSE/NDJSON 只发摘要和节流快照。

**Bad case retrieval hybrid 路径按条款调用外部向量层：**
- 问题： `retrieve_bad_case_hits()` 会加载本地 bad case、拆分正文条款，并在 hybrid 模式下为每条 query 调用 embedding 和 Qdrant 搜索；失败时降级 `bm25_only`。
- 涉及文件： `backend/retrieval/comment_bad_case_runtime.py`, `backend/retrieval/embeddings.py`, `backend/retrieval/qdrant_store.py`, `backend/nodes/common_word_nodes/generate_comments.py`, `backend/nodes/common_word_nodes/comment_agent.py`
- 原因： 正文条款数量、embedding 网络延迟、Qdrant 健康检查和 vector search 都影响批注生成前置耗时。
- 改进路径： 保持本地 BM25 降级；监控 retrieval warning；需要提速时考虑 per-task 缓存、top-k 限制和异步批量 embedding。

**样式回填匹配复杂度高：**
- 问题： `inline_style_ops.py` 负责编号、片段、本地候选、表格、字体等复杂匹配，单文件体量和分支数量都高。
- 涉及文件： `backend/helper/word_helper/inline_style_ops.py`, `backend/tests/helper/test_inline_style_ops.py`, `backend/tests/nodes/test_update_word_inline_style_writeback.py`
- 原因： Word 文档结构、表格、编号、局部候选和 fallback 规则复杂。
- 改进路径： 修改时用 focused fixture 和单测覆盖；对真实 Word/WPS 行为再做人工或诊断闭环。

## 脆弱区域

**GNGK 子类型继承和覆写：**
- 涉及文件： `backend/graphs/gngk_hw_zc_tender_graph.py`, `backend/graphs/gngk_hw_cz_tender_graph.py`, `backend/graphs/gngk_fw_zc_tender_graph.py`, `backend/graphs/gngk_fw_cz_tender_graph.py`, `backend/config/tender_config.py`
- 脆弱原因： `gngk_hw_cz`、`gngk_fw_zc` 等子类型共享主干但覆写 delete/update/replacement；前端 `gngk` UI 类型还需由共享 helper 分派到具体后端 form type。
- 安全修改： 改任一 `gngk_*` 时同步检查 graph class attributes、protected profile、content mode、form type、URL/注册表/转换器和测试。
- 测试覆盖： `backend/tests/graphs/test_gngk_tender_graph.py`, `backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`, `backend/tests/graphs/test_gngk_*_generation_mode_agent.py`

**Generate-only 字段边界：**
- 涉及文件： `backend/models/generate.py`, `backend/services/document_service.py`, `backend/states/base_state.py`, `backend/skills/rewrite/SKILL.md`, `backend/prompts/types.py`, `backend/tests/services/test_document_service_initial_state.py`
- 脆弱原因： `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于初次 generate；rewrite 请求、skill state 和 prompt surface 不接收这些字段。`DocumentService._build_rewrite_state_snapshot()` 仍把 `generation_mode` 保存到会话快照，后续改动容易误复制到 rewrite skill state。
- 安全修改： 新增 generate option 时只进入 generate request 和初始 state；rewrite tool input、skill state、rewrite prompt types 继续禁止 generate-only 字段。
- 测试覆盖： `backend/tests/models/test_generate_request_generation_style.py`, `backend/tests/services/test_document_service_initial_state.py`, `backend/tests/graphs/test_generation_mode_branching.py`, `backend/tests/services/test_document_service_task_result.py`

**Agent run 只是任务创建前置流：**
- 涉及文件： `backend/api/agent.py`, `backend/services/agent_run_service.py`, `backend/agents/task_context_assistant/tools.py`, `backend/models/agent_run.py`
- 脆弱原因： agent run 只输出 `needs_input`、`task_accepted`、`done` 等 NDJSON 事件，不复制后台任务状态机；成功后必须交给 `TaskQueueManager`、SSE 和下载链路。
- 安全修改： 新能力先定义受控 `context_snapshot` 和白名单工具；不要让 agent run 直接写 Word、暴露完整任务结果或返回下载路径。
- 测试覆盖： `backend/tests/api/test_agent_run_api.py`, `backend/tests/services/test_agent_run_service.py`, `backend/tests/agents/test_task_context_assistant_tools.py`, `backend/tests/agents/test_task_context_assistant_logging.py`

**补充批注依赖会话 latest state：**
- 涉及文件： `backend/api/comment_supplement.py`, `backend/services/document_service.py`, `backend/graphs/comment_supplement_graph.py`, `backend/nodes/common_word_nodes/comment_supplement.py`
- 脆弱原因： 补充批注必须基于当前会话 latest `rewrite_state.prepared_doc_path` 和 `polished_text`；source file 不匹配会写回错误副本。
- 安全修改： 创建任务前继续校验 `conversation_id`、`source_file`、latest path、文件存在和路径匹配；成功后更新 latest `rewrite_state.prepared_doc_path`。
- 测试覆盖： `backend/tests/api/test_comment_supplement_api.py`, `backend/tests/graphs/test_comment_supplement_graph.py`, `backend/tests/services/test_document_service_comment_supplement.py`

**SSE `agent_step` 和终态契约：**
- 涉及文件： `backend/models/sse.py`, `backend/core/sse_manager.py`, `backend/services/document_service.py`, `backend/agents/generation/agent_step_events.py`, `backend/nodes/common_word_nodes/comment_agent.py`
- 脆弱原因： 前端依赖 named event、`agent_step` payload、`done`/`error` 终态和 `style_writeback`/`comment_writeback` 摘要；随意改字段会断过程卡或下载卡。
- 安全修改： 新增字段保持向后兼容；新增 SSE event type 同步后端模型、发送方、前端 union/parser 和测试。
- 测试覆盖： `backend/tests/models/test_sse_agent_step.py`, `backend/tests/services/test_sse_manager_agent_step.py`, `backend/tests/services/test_document_service_agent_step.py`

**Bad case retrieval 正式接入但不对前端公开：**
- 涉及文件： `backend/retrieval/`, `backend/nodes/common_word_nodes/generate_comments.py`, `backend/nodes/common_word_nodes/comment_agent.py`, `backend/prompts/comment_prompt.py`
- 脆弱原因： retrieval JSON 是后端 prompt/retrieval 审计产物，prompt context 刻意排除 case id、score、chunk id 和匹配条款；命中详情不能进入 SSE、下载卡或 `agent_step`。
- 安全修改： 保持 `comment_generation_mode=off` 不触发 retrieval；rewrite 不触发 retrieval；新增 retrieval 字段时只进入审计 JSON，前端展示仍用摘要。
- 测试覆盖： `backend/tests/retrieval/test_comment_bad_case_runtime.py`, `backend/tests/nodes/test_generate_comments_bad_case.py`, `backend/tests/nodes/test_comment_agent_writeback_node.py`, `backend/tests/prompts/test_comment_prompt_bad_case_context.py`

**Prompt literal 和机器契约：**
- 涉及文件： `backend/prompts/generate_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/prompts/template_candidate_ranking_prompt.py`, `backend/prompts/rewrite_target_selection_prompt.py`, `backend/agents/generation/json_utils.py`
- 脆弱原因： prompt 示例、JSON 字段、机器标识符和解析规则被 tests、agent parsing 或前端过程展示依赖。
- 安全修改： 改 prompt 时同步 parser/validator 测试；不要翻译 `content_agent`、`comment_agent`、`agent_step`、tool names 等机器标识符。
- 测试覆盖： `backend/tests/prompts/test_generate_prompt_routing.py`, `backend/tests/prompts/test_comment_prompt_reference_contract.py`, `backend/tests/agents/test_generation_content_agent.py`

## 扩展限制

**Task/SSE/conversation 内存状态：**
- 当前容量： 单进程内由内存、`SSE_MAX_EVENTS_PER_TASK`、`SSE_EVENT_TTL`、`MAX_REWRITE_MESSAGES` 和任务清理周期限制。
- 限制： 服务重启丢任务、SSE 事件、会话 rewrite history 和取消状态；多进程无法共享当前队列。
- 扩展路径： 外部队列、持久化 task store、集中事件流、会话状态存储和 artifact 生命周期管理。

**后台 Word COM worker：**
- 当前容量： 后台线程可排队多个任务，但 Word 写入路径仍通过 queue + graph lock + COM lock 串行。
- 限制： 长 Word/LLM 任务会阻塞后续 Word 写入；Windows COM 注册或 Word/WPS 进程异常会影响整个生成链路。
- 扩展路径： 专用 Windows worker 池；每个 worker 内仍需 COM 互斥、文件隔离、取消检查和诊断。

**本地文件与日志产物：**
- 当前容量： 上传文件、生成文件、agent workspace、prompt/retrieval 日志和运行日志依赖本地磁盘；启动时只清理 `backend/logs` 总量。
- 限制： 多用户或长时间运行会积累 `UPLOAD_DIR`、`backend/prompts_log/`、agent/comment workspace 和 retrieval JSON。
- 扩展路径： 定义上传/生成文件保留策略、对象存储、审计日志保留策略和下载授权。

**Retrieval cache 是进程内缓存：**
- 当前容量： `load_bad_case_runtime_index()` 按 bad case 目录签名缓存 BM25 index；hybrid 层依赖外部 Qdrant/embedding。
- 限制： 多进程重复建索引；bad case 文件变化只在本进程缓存签名检查后生效；外部向量层不可用会降级。
- 扩展路径： 保持 BM25 fallback；需要跨进程一致性时引入显式索引刷新、共享缓存或服务化 retrieval。

## 依赖风险

**`pywin32` / Word/WPS COM / `msvcrt`：**
- 风险： 完整 Word 写回依赖 Windows Python、本机 Word/WPS COM 注册、`pywin32` 和 Windows `msvcrt` 文件锁。
- 影响： WSL/Linux pytest 只能验证 no-COM 逻辑，不能证明真实 `.doc/.docx` 写回。
- 迁移计划： 保持 `backend/util/word_util/` 诊断分层；替代方案需重写 Word 操作层和锁策略。

**`deepagents` / LangChain agent runtime：**
- 风险： content agent、comment agent 和 task context assistant 依赖 `deepagents`、LangChain model factory 和工具调用协议。
- 影响： API 变化会影响 `generation_mode=agent`、补充批注和 agent run 前置流。
- 迁移计划： 升级时优先跑 `backend/tests/agents/`、`backend/tests/services/test_agent_run_service.py`、`backend/tests/nodes/test_content_agent_generate.py` 和 `agent_step` 测试。

**外部 LLM providers：**
- 风险： DeepSeek、ARK/Doubao、DashScope/Qwen 的 key、base URL、模型名、超时或响应格式变化会影响生成、rewrite、批注和模板候选重排。
- 影响： 长任务失败、流式中断、JSON 解析失败或 agent 输出异常。
- 迁移计划： 通过 `backend/config/settings.py` 和 `backend/util/common_util/llm_stream_utils.py` 集中配置；mock 外部服务的单测继续覆盖错误分支。

**向量检索 provider：**
- 风险： Hybrid retrieval 依赖 `QDRANT_URL`、`QDRANT_API_KEY`、`EMBEDDING_*` 或 `DASHSCOPE_API_KEY`。
- 影响： 批注 bad case hybrid retrieval 降级到 `bm25_only`；缺 key 或向量层失败会增加 warning 和降低语义检索质量。
- 迁移计划： 保持 `bm25_only` fallback 和 retrieval JSON； live 诊断使用 `backend/scripts/test_comment_hybrid_retrieval.py`，不要把诊断脚本当 CI。

**外部招标详情/模板候选 HTTP 接口：**
- 风险： ERP/外部接口 URL、返回字段、模板文件主机或网络状态变化会影响招标详情和模板候选。
- 影响： `backend/api/tender.py`、`backend/api/template_candidates.py` 可能返回 502、候选格式错误或模板选择失败。
- 迁移计划： 保持外部请求 timeout、格式归一化、host 白名单和 API tests；字段变化先更新后端模型/工具再同步前端。

## 缺失关键能力

**持久化任务存储：**
- 问题： 任务、取消事件、任务结果和 SSE event buffer 不持久化。
- 阻塞： 服务重启恢复、多进程部署、跨 worker 查询和历史任务审计。

**统一认证与授权：**
- 问题： 未检测到统一 API auth layer。
- 阻塞： 多用户隔离、任务归属授权、文件下载授权和生产权限控制。

**真实 readiness 诊断：**
- 问题： `/health/ready` 不检查上传目录、Word COM、LLM provider、Qdrant/embedding 或外部接口。
- 阻塞： 自动化运维判断真实生成能力。

**产物保留策略：**
- 问题： 上传目录、生成文件、prompt/retrieval 审计和 agent workspace 未形成统一保留/清理策略。
- 阻塞： 长期运行磁盘容量控制、敏感产物生命周期管理和合规清理。

**稳定的 Windows Word COM CI：**
- 问题： 未检测到自动化 Windows + Word/WPS COM 端到端 CI。
- 阻塞： 自动证明真实 `.doc/.docx` 生成、rewrite、批注和样式写回闭环。

## 测试覆盖缺口

**`GET /api/generate/{task_id}` 完成态：**
- 未覆盖内容： 已完成任务的 `GenerateResponse` shape、`output_file` 字段类型和 result payload 映射。
- 涉及文件： `backend/api/generate.py`, `backend/tests/api/test_generate_api.py`, `backend/services/document_service.py`
- 风险： 完成态查询可能触发响应模型错误或返回非预期结构。
- 优先级：高

**真实 Word COM E2E：**
- 未覆盖内容： 真实 Word/WPS COM 下完整生成、rewrite、补充批注、样式回填、批注写回和 `.doc/.docx` 保存。
- 涉及文件： `backend/util/word_util/`, `backend/nodes/`, `backend/helper/word_helper/`, `backend/scripts/diagnose_word.py`
- 风险： fake object 单测通过但真实 COM range/table/comment/save 行为不同。
- 优先级：发布验收高

**上传/下载安全边界用例：**
- 未覆盖内容： 下载 path traversal、URL 编码绕过、非文件路径、伪造扩展名、MIME 不匹配和异常落盘。
- 涉及文件： `backend/api/download.py`, `backend/api/upload.py`, `backend/util/common_util/upload_storage.py`
- 风险： 安全边界在重构或扩展时被破坏。
- 优先级：高

**认证与归属隔离：**
- 未覆盖内容： 任务、会话、上传文件、下载文件和 agent run 是否属于同一用户/会话的统一授权。
- 涉及文件： `backend/api/`, `backend/services/task_service.py`, `backend/services/conversation_service.py`, `backend/agents/task_context_assistant/tools.py`
- 风险： 引入多用户场景时出现越权查询、取消或下载。
- 优先级：高，进入非本地受控环境时尤其需要补齐。

**真实外部服务：**
- 未覆盖内容： 真实 LLM、外部招标详情、模板候选接口、Qdrant 和 embedding 服务的 live 行为。
- 涉及文件： `backend/util/common_util/llm_stream_utils.py`, `backend/util/common_util/fetch_tender_data.py`, `backend/util/common_util/template_candidates.py`, `backend/retrieval/`
- 风险： 配置、网络、字段或 provider API 变化导致运行时失败。
- 优先级：中；提交测试仍应继续 mock 外部服务。

**前后端完整链路：**
- 未覆盖内容： 浏览器端上传、agent run、任务创建、SSE、下载、补充批注和 rewrite 的完整闭环。
- 涉及文件：后端入口在 `backend/api/`；前端 API client 和 UI 测试位于 `frontend/`。
- 风险： 后端 API/SSE shape 与前端解析漂移。
- 优先级：高，跨系统改动时必须验证。

---

*风险审计： 2026-06-08*

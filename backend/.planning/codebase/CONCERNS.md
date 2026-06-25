# 后端风险事实地图

**分析日期：** 2026-06-25

## 技术债

**Word COM、任务队列和结果收尾耦合过深：**
- 问题： `backend/graphs/base_graph.py`、`backend/task/task_queue_manager.py`、`backend/services/document_service.py`、`backend/util/word_util/word_application_util.py` 把排队、公平锁、取消检查、COM 生命周期、SSE 通知和结果收尾分散在多层；`invoke_with_timing_async()` 会先写入一个占位完成结果，随后 `DocumentService._run_graph()` 再覆盖为完整 payload，终态语义依赖调用顺序。
- 相关文件： `backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `backend/services/document_service.py`, `backend/util/word_util/word_application_util.py`
- 影响： 任务完成态、取消态和下载信息很容易在后续改动中漂移，排障时也很难判断到底是哪一层先把任务标成完成。
- 修复方向： 保持“队列收尾”和“业务结果落盘”分层，补齐 `wait_for_turn()`、运行中取消、双完成路径和 SSE 终态的回归测试后再改收尾顺序。

**Word 写回逻辑集中在大文件里：**
- 问题： `backend/helper/word_helper/inline_style_ops.py`、`backend/nodes/gjgk_word_nodes/gjgk_update_word.py`、`backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`、`backend/nodes/common_word_nodes/update_word.py`、`backend/services/document_service.py` 承担了样式匹配、段落边界、表格投影、批注写回和 task 编排。
- 相关文件： `backend/helper/word_helper/inline_style_ops.py`, `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`, `backend/nodes/common_word_nodes/update_word.py`, `backend/services/document_service.py`
- 影响： 任何局部替换都可能打坏 `.doc/.docx` 写回、受保护字段、批注回填或 `style_writeback_mode` 分支。
- 修复方向： 修改前先缩到最小 helper 或 node，再用 `backend/tests/helper/`、`backend/tests/nodes/` 和 `backend/tests/services/` 的定点测试锁住行为。

**进程内状态是默认实现：**
- 问题： `backend/core/sse_manager.py`、`backend/task/task_queue_manager.py`、`backend/services/conversation_service.py` 把任务、SSE 事件、取消状态和 rewrite 历史都保存在单进程内存里。
- 相关文件： `backend/core/sse_manager.py`, `backend/task/task_queue_manager.py`, `backend/services/conversation_service.py`
- 影响： 服务重启会丢失历史事件和会话状态，多进程部署会把队列、事件流和取消状态分裂成多个孤岛。
- 修复方向： 在引入持久化前，先定义 task store、SSE event id、会话快照和 artifact 生命周期的统一契约。

**健康检查只是轻量探针：**
- 问题： `backend/main.py` 的 `/health/ready` 仍把 `upload_dir_accessible` 写死为 `True`，没有真正检查目录权限、Word/WPS COM、LLM provider 或向量检索依赖。
- 相关文件： `backend/main.py`, `backend/config/settings.py`
- 影响： readiness 返回成功不代表系统真的具备生成、rewrite 或补充批注能力。
- 修复方向： 保留 `/health` 作为进程探针，把真正的就绪检查拆成上传目录、COM、LLM、Qdrant/embedding 和外部 HTTP 的分项检查。

**依赖声明松散：**
- 问题： `backend/requirements.txt` 只写了下限版本，`langgraph`、`deepagents`、`langchain-*`、`openai`、`httpx`、`requests`、`pydantic` 和 `pywin32` 的行为都可能随次版本漂移。
- 相关文件： `backend/requirements.txt`
- 影响： 依赖升级可能直接改变 agent 协议、SSE 序列化、Word COM 行为或上传下载边界。
- 修复方向： 把关键兼容性放进测试而不是经验里，至少锁住 `backend/tests/api/`、`backend/tests/agents/`、`backend/tests/services/` 和 `backend/tests/nodes/` 的高风险路径。

## 已知问题

**`GET /api/generate/{task_id}` 完成态返回 shape 不稳定：**
- Symptoms: `backend/api/generate.py` 在完成态把 `task_info.result` 直接赋给 `GenerateResponse.output_file`，但 `task_info.result` 实际上是 `backend/services/document_service.py` 构造的 dict payload，而不是纯字符串。
- 相关文件： `backend/api/generate.py`, `backend/models/generate.py`, `backend/services/document_service.py`, `backend/tests/api/test_generate_api.py`
- Trigger: 查询已完成任务的生成状态。
- Workaround: 先用 `GET /api/tasks/{task_id}` 或 SSE `done` 事件拿完整结果，不要依赖 `GET /api/generate/{task_id}` 作为唯一结果源。

## 安全注意事项

**下载接口的路径边界必须保持：**
- 风险： `backend/api/download.py` 接收 URL 编码的完整路径，任何放松 `relative_to(settings.UPLOAD_DIR)` 的改动都会重新打开路径穿越。
- 相关文件： `backend/api/download.py`, `backend/config/settings.py`
- Current mitigation: `validate_file_path()` 会解码、`resolve()`，再强制落在 `settings.UPLOAD_DIR` 内。
- Recommendations: 保留解码、解析和 containment 三步；补齐路径穿越、URL 编码绕过、目录路径和缺失文件测试。

**上传只做扩展名和大小校验：**
- 风险： `backend/api/upload.py` 和 `backend/util/common_util/upload_storage.py` 只根据清洗后的文件名扩展名与字节大小判断，未做 magic bytes、MIME 或文档结构校验。
- 相关文件： `backend/api/upload.py`, `backend/util/common_util/upload_storage.py`, `backend/config/settings.py`
- Current mitigation: `sanitize_filename()`、`ALLOWED_EXTENSIONS` 和 `MAX_UPLOAD_SIZE` 约束了文件名、类型和体积。
- Recommendations: 如果要把上传区当成生产边界，补病毒扫描、魔数检测或隔离区，不要只靠扩展名。

**模板候选代理会放大外部 URL 风险：**
- 风险： `backend/api/template_candidates.py` 和 `backend/util/common_util/template_candidates.py` 会代理下载外部模板链接，白名单一旦放宽就会变成 SSRF 面。
- 相关文件： `backend/api/template_candidates.py`, `backend/util/common_util/template_candidates.py`, `backend/config/settings.py`
- Current mitigation: `validate_template_download_url()` 只允许 `http/https`，并要求主机在 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 内；年份过旧还会被拦截。
- Recommendations: 新增来源、主机或文件类型时同步更新白名单、协议校验和测试，不要让前端直接接触上游模板 URL。

**环境变量和日志边界容易泄密：**
- 风险： `backend/config/settings.py`、`backend/retrieval/config.py` 会从环境和 `backend/.env` 读取配置，`backend/agents/task_context_assistant/logging.py`、`backend/util/log_util/sse_log_handler.py` 会把日志推给前端或落盘。
- 相关文件： `backend/config/settings.py`, `backend/retrieval/config.py`, `backend/agents/task_context_assistant/logging.py`, `backend/util/log_util/sse_log_handler.py`, `backend/util/log_util/progress_log.py`
- Current mitigation: `scrub_sensitive_text()` 会红acted bearer token、密码、路径和 traceback；agent run 审计只记录白名单字段。
- Recommendations: 新增日志、SSE 字段或审计字段前先过 scrub；不要把客户原文、真实路径、密钥值或 traceback 直接写进用户可见通道。

**Bad case 检索只把白名单字段送进 prompt：**
- 风险： `backend/retrieval/comment_bad_case_runtime.py` 会把 bad case 元数据注入 `backend/prompts/comment_prompt.py`，如果把 `case_id`、`score`、`chunk_id` 或匹配条款一起送进前端，就会泄露审计细节。
- 相关文件： `backend/retrieval/comment_bad_case_runtime.py`, `backend/prompts/comment_prompt.py`, `backend/nodes/common_word_nodes/generate_comments.py`, `backend/nodes/common_word_nodes/comment_agent.py`
- Current mitigation: prompt 上下文只保留 `risk_type`、`risk_pattern`、`recommended_comment_policy`、`applicability_boundary` 和 `anchor_policy`。
- Recommendations: 保持 prompt context 与 audit payload 分离，命中详情只留在后端审计产物里。

## 性能瓶颈

**Word COM 只能串行化：**
- 问题： `backend/util/word_util/word_com_manager.py`、`backend/util/word_util/word_application_util.py`、`backend/graphs/base_graph.py` 和 `backend/task/task_queue_manager.py` 把 Word COM 保护成单通道临界资源。
- 相关文件： `backend/util/word_util/word_com_manager.py`, `backend/util/word_util/word_application_util.py`, `backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`
- Cause: `DispatchEx`、`CoInitialize()`、`Quit()`、`CrossProcessFileLock` 和公平队列都在限制并发。
- 改进路径： 真要扩展吞吐，得上外部队列或专用 Windows worker 池，不能只调大线程数。

**SSE 和任务状态都吃内存：**
- 问题： `backend/core/sse_manager.py` 会按 task 缓存事件，`backend/task/task_queue_manager.py` 和 `backend/services/conversation_service.py` 也把运行态保存在内存里。
- 相关文件： `backend/core/sse_manager.py`, `backend/task/task_queue_manager.py`, `backend/services/conversation_service.py`
- Cause: 历史回放和断线重连依赖本进程缓存。
- 改进路径： 需要更长历史时先定义持久化事件存储和回放协议，再谈扩容。

**坏案例混合检索的网络路径较长：**
- 问题： `backend/retrieval/comment_bad_case_runtime.py`、`backend/retrieval/embeddings.py`、`backend/retrieval/qdrant_store.py` 在 hybrid 模式下会走本地 BM25、embedding 请求和 Qdrant 查询。
- 相关文件： `backend/retrieval/comment_bad_case_runtime.py`, `backend/retrieval/embeddings.py`, `backend/retrieval/qdrant_store.py`
- Cause: 每个 clause 都可能触发外部向量与检索调用。
- 改进路径： 保留 `bm25_only` fallback，减少 clause 数量和向量查询上限，再考虑缓存。

**LLM 和 agent 运行时受外部延迟影响：**
- 问题： `backend/util/common_util/llm_stream_utils.py`、`backend/agents/generation/content_agents.py`、`backend/agents/comments/comment_agent.py`、`backend/services/template_candidate_ranking_service.py` 都依赖外部模型或重排。
- 相关文件： `backend/util/common_util/llm_stream_utils.py`, `backend/agents/generation/content_agents.py`, `backend/agents/comments/comment_agent.py`, `backend/services/template_candidate_ranking_service.py`
- Cause: 网络、模型推理、重试和 JSON 修复都会拉长单次任务时长。
- 改进路径： 把超时、重试和节流参数集中在 settings，别在各节点各写一套。

**样式回填匹配复杂度高：**
- 问题： `backend/helper/word_helper/inline_style_ops.py` 既做样式抽取又做回填匹配，分支很多，fixture 也重。
- 相关文件： `backend/helper/word_helper/inline_style_ops.py`, `backend/tests/helper/test_inline_style_ops.py`, `backend/tests/nodes/test_update_word_inline_style_writeback.py`
- Cause: Word 结构、表格、编号和局部候选的组合太多。
- 改进路径： 改动前先用 focused fixture 锁住具体样式分支，不要直接在大文件里连带重写。

## 脆弱区域

**任务完成链路对顺序敏感：**
- 相关文件： `backend/graphs/base_graph.py`, `backend/task/task_queue_manager.py`, `backend/services/document_service.py`, `backend/core/sse_manager.py`
- 脆弱点： 完成、取消、进度、SSE `done` / `error` 和结果 payload 依赖同一条顺序链；任何一层先后顺序变掉，前端就可能读到旧状态或丢终态。
- 安全修改： 改队列、锁或 SSE 前先补 `backend/tests/services/test_document_service_agent_step.py`、`backend/tests/services/test_sse_manager_agent_step.py` 和相关 task 测试。
- 测试覆盖： 没有直接覆盖 `wait_for_turn()`、运行中取消和双完成收尾的单测。

**API shape 和内部 payload 不同源：**
- 相关文件： `backend/api/generate.py`, `backend/models/generate.py`, `backend/services/document_service.py`, `backend/models/sse.py`
- 脆弱点： `GenerateResponse`、`TaskInfo.result`、SSE `done` payload 和前端下载卡不是同一个模型；改一个字段名就会断查询页、结果页或 SSE 解析。
- 安全修改： 新增字段时同步后端模型、service、API response 和 `backend/tests/api/` 的断言。
- 测试覆盖： `backend/tests/api/test_generate_api.py` 只覆盖 404，没覆盖完成态 shape。

**SSE 事件契约被 named event 绑定：**
- 相关文件： `backend/core/sse_manager.py`, `backend/models/sse.py`, `backend/api/stream.py`, `backend/services/document_service.py`
- 脆弱点： `agent_step`、`done`、`error`、`progress` 和 `heartbeat` 都是 named event；客户端和服务端必须一起改。
- 安全修改： 新事件或新字段先同步 `backend/models/sse.py`、SSE 发送方、NDJSON / EventSource 解析和测试。
- 测试覆盖： 有 `backend/tests/services/test_sse_manager_agent_step.py` 和 `backend/tests/services/test_document_service_agent_step.py`，但没有跨重连或多客户端的端到端覆盖。

**生成-only 字段和 rewrite 字段边界很窄：**
- 相关文件： `backend/models/agent_run.py`, `backend/services/agent_run_service.py`, `backend/agents/task_context_assistant/tools.py`, `backend/states/skill_state.py`, `backend/nodes/skills_nodes/rewrite_nodes.py`, `backend/skills/rewrite/scripts/runtime.py`
- 脆弱点： `generation_style`、`generation_mode`、`comment_generation_mode` 和 `style_writeback_mode` 只属于初次 generate；`rewrite_source="uploaded_file"` 是上传 rewrite 的路由开关。
- 安全修改： 新增生成选项只进 `GenerateRequest` 和初始 generate state，不要写进 rewrite 请求模型、skill state 或 prompt surface。
- 测试覆盖： `backend/tests/services/test_document_service_initial_state.py`、`backend/tests/models/test_generate_request_generation_style.py` 和 `backend/tests/skills/test_task_skill_runtime.py` 在守这个边界。

**结构化表占位符是内部写回入口：**
- 相关文件： `backend/agents/generation/table_placeholder_utils.py`, `backend/agents/generation/verify_agent_graph.py`, `backend/helper/word_helper/text_parsing.py`, `backend/agents/generation/content_sanitizer.py`
- 脆弱点： `[[TABLE:<id>]]` 不再是最终正文必须保留的可见内容；审核、写回、sidecar 恢复和投影表静默丢弃必须严格一致，否则会把表格近似文本写错、写漏或误判。
- 安全修改： 改 regex、sidecar 匹配、`table_id` 字符集或写回语义时，同步 `backend/tests/agents/test_table_placeholder_utils.py`、`backend/tests/agents/test_generation_content_agent.py` 和 `backend/tests/helper/test_text_parsing_table_placeholder.py`。
- 测试覆盖： 现有测试覆盖提取、修复和写回入口，但缺真实 Word 写回端到端验证。

**Prompt 和 bad case 上下文绑定得很紧：**
- 相关文件： `backend/prompts/generate_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/retrieval/comment_bad_case_runtime.py`
- 脆弱点： prompt 里既有生成-only 路由，又有 bad case 锚点规则；改动后如果没有同步解析器，容易让 `reference_text` 或 JSON 结构漂掉。
- 安全修改： 改 prompt 时同步 `backend/tests/prompts/test_generate_prompt_routing.py`、`backend/tests/prompts/test_comment_prompt_reference_contract.py` 和 `backend/tests/prompts/test_comment_prompt_bad_case_context.py`。
- 测试覆盖： 目前覆盖了核心 contract，但没有真实端到端 prompt+SSE+task 组合测试。

**Word COM 生命周期必须收尾完整：**
- 相关文件： `backend/util/word_util/word_application_util.py`, `backend/util/word_util/word_com_manager.py`
- 脆弱点： `CoInitialize()`、`Open()`、`Save()`、`Quit()` 和 `CoUninitialize()` 都依赖严格顺序；RPC 错误和缓存损坏只能降级重试，不能真正抢占。
- 安全修改： 改 COM 逻辑时先锁住 close/open/save 的重试路径，再验证清理顺序和异常释放。
- 测试覆盖： 现有测试基本停留在 fake object 和 helper 层，没有真实 Word/WPS CI。

## 扩展边界

**单进程内存边界：**
- 当前能力： `backend/core/sse_manager.py`、`backend/task/task_queue_manager.py` 和 `backend/services/conversation_service.py` 都依赖当前进程内状态。
- 限制： 重启即失、跨 worker 不共享、历史回放受 `SSE_MAX_EVENTS_PER_TASK` 和 `MAX_REWRITE_MESSAGES` 截断。
- 扩展路径： 需要更长历史时先引入持久化队列和会话存储，再考虑多进程。

**Windows COM worker 边界：**
- 当前能力： `backend/util/word_util/word_application_util.py`、`backend/graphs/base_graph.py` 和 `backend/task/task_queue_manager.py` 只允许串行执行 Word COM。
- 限制： 长任务会阻塞后续 Word 写入，Word/WPS 注册异常会拖垮整条生成链路。
- 扩展路径： 专用 Windows worker 池、任务隔离和外部调度器。

**检索缓存和回放窗口：**
- 当前能力： `backend/retrieval/comment_bad_case_runtime.py` 依赖进程内缓存，`backend/core/sse_manager.py` 只保留有限事件窗口。
- 限制： 多进程重复建索引，晚到的 SSE 客户端看不到完整历史。
- 扩展路径： 显式索引刷新、共享缓存和可持久化事件流。

**本地文件和日志产物：**
- 当前能力： `backend/config/settings.py`、`backend/util/log_util/progress_log.py`、`backend/agents/task_context_assistant/logging.py` 和 `backend/util/common_util/upload_storage.py` 都把数据落在本地磁盘。
- 限制： 上传、生成、审计和 workspace 会长期累积。
- 扩展路径： 统一保留策略、对象存储和清理策略。

## 高风险依赖

**`pywin32` / Word / WPS COM：**
- 风险： `backend/util/word_util/word_application_util.py`、`backend/util/word_util/word_com_manager.py` 和 `backend/scripts/diagnose_word.py` 依赖 Windows Python、本机 Word/WPS COM 注册和 `pywin32`。
- 影响： WSL/Linux 只能验证无 COM 逻辑，不能证明真实写回。
- 迁移建议： 保持诊断脚本和 Word utility 分层；替代方案需要重做 COM 访问层。

**`langgraph` / `deepagents` / LangChain：**
- 风险： `backend/agents/generation/content_agents.py`、`backend/agents/comments/comment_agent.py`、`backend/services/agent_run_service.py` 和 `backend/util/common_util/llm_stream_utils.py` 依赖这些运行时。
- 影响： 升级可能改掉 agent 协议、工具调用或流式回调语义。
- 迁移建议： 升级前先跑 `backend/tests/agents/`、`backend/tests/services/test_agent_run_service.py` 和 SSE 相关测试。

**外部 LLM provider：**
- 风险： `backend/config/settings.py`、`backend/agents/generation/model_factory.py` 和 `backend/util/common_util/llm_stream_utils.py` 依赖 `DEEPSEEK_API_KEY`、`ARK_API_KEY`、`DASHSCOPE_API_KEY` 和 provider base URL。
- 影响： 长任务失败、JSON 解析失败、流式中断或模型配置漂移。
- 迁移建议： 保持 provider 配置集中在 settings，测试只 mock provider，不把 secret 值写进日志。

**向量检索和 embedding provider：**
- 风险： `backend/retrieval/config.py`、`backend/retrieval/qdrant_store.py` 和 `backend/retrieval/embeddings.py` 依赖 `EMBEDDING_API_KEY`、`QDRANT_URL` 和 `QDRANT_API_KEY`。
- 影响： bad case hybrid 检索会降级到 `bm25_only` 或直接失败。
- 迁移建议： 继续保留 BM25 fallback，把 live 检索单独当成受控集成环境验证。

**模板与招标详情外部 HTTP 接口：**
- 风险： `backend/api/template_candidates.py`、`backend/util/common_util/template_candidates.py` 和 `backend/util/common_util/fetch_tender_data.py` 依赖外部接口字段和主机白名单。
- 影响： 字段变更、主机变更或超时都会让模板候选和招标详情链路失效。
- 迁移建议： 先更新后端模型和工具，再同步前端 client 和测试。

## 缺失的关键能力

**持久化任务存储：**
- 问题： `backend/task/task_queue_manager.py`、`backend/core/sse_manager.py` 和 `backend/services/conversation_service.py` 仍是内存态。
- Blocks: 重启恢复、跨 worker 查询、历史审计和断线重连后的完整回放。

**统一认证与授权：**
- 问题： `backend/api/`、`backend/services/task_service.py`、`backend/services/conversation_service.py` 和 `backend/api/download.py` 没有显式共享认证层。
- Blocks: 多用户隔离、任务归属授权、文件下载授权和会话隔离。

**真实 readiness 诊断：**
- 问题： `backend/main.py` 没有验证上传目录、COM、LLM provider、Qdrant/embedding 或外部 HTTP。
- Blocks: 线上自动化运维无法仅靠 readiness 判断能否生成。

**上传内容安全检查：**
- 问题： `backend/api/upload.py` 和 `backend/util/common_util/upload_storage.py` 只做扩展名和大小过滤。
- Blocks: 不能防住伪装扩展名、恶意文档结构或需要隔离执行的内容。

**稳定的 Windows Word COM CI：**
- 问题： `backend/tests/` 没有真实 Word/WPS COM 端到端链路。
- Blocks: 无法自动证明 `.doc/.docx` 真写回、rewrite、补充批注和样式回填闭环。

## 测试覆盖缺口

**队列、公平锁和运行中取消：**
- What’s not tested: `backend/task/task_queue_manager.py` 的 `wait_for_turn()`、`cancel_task()`、心跳超时和 `backend/graphs/base_graph.py` 的 `CrossProcessFileLock`、`invoke_with_timing_async()`。
- 相关文件： `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py`, `backend/services/document_service.py`
- 风险： 锁清理、排队顺序、取消态和终态收敛很容易在重构时被破坏。
- Priority: High

**完成态生成 API：**
- What’s not tested: `backend/api/generate.py` 在任务完成时把 dict payload 映射到 `GenerateResponse` 的行为。
- 相关文件： `backend/api/generate.py`, `backend/models/generate.py`, `backend/services/document_service.py`, `backend/tests/api/test_generate_api.py`
- 风险： 完成态查询可能返回不符合预期的 shape，影响前端结果页和下载卡。
- Priority: High

**下载、上传和模板代理边界：**
- What’s not tested: `backend/api/download.py` 的路径穿越、URL 编码绕过、非文件路径，`backend/api/upload.py` 和 `backend/util/common_util/upload_storage.py` 的扩展名伪装，以及 `backend/util/common_util/template_candidates.py` 的协议/主机白名单和年份阻断。
- 相关文件： `backend/api/download.py`, `backend/api/upload.py`, `backend/util/common_util/upload_storage.py`, `backend/api/template_candidates.py`, `backend/util/common_util/template_candidates.py`
- 风险： 安全边界在重构时最容易被忽略。
- Priority: High

**真实 Word COM E2E：**
- What’s not tested: `backend/util/word_util/`、`backend/helper/word_helper/` 和 `backend/nodes/` 的真实 Word/WPS 自动化闭环。
- 相关文件： `backend/util/word_util/`, `backend/helper/word_helper/`, `backend/nodes/`, `backend/scripts/diagnose_word.py`
- 风险： fake object 单测通过不代表真实 COM 行为一致。
- Priority: High

**SSE 重连和多客户端：**
- What’s not tested: `backend/core/sse_manager.py` 的多客户端重连、事件回放窗口和队列溢出。
- 相关文件： `backend/core/sse_manager.py`, `backend/tests/services/test_sse_manager_agent_step.py`
- 风险： 事件 replay、心跳和终态在客户端重连后可能漂移。
- Priority: Medium

**Prompt 和 placeholder 全链路：**
- What’s not tested: `backend/prompts/comment_prompt.py`、`backend/prompts/generate_prompt.py` 和 `backend/agents/generation/table_placeholder_utils.py` 的端到端组合场景。
- 相关文件： `backend/prompts/comment_prompt.py`, `backend/prompts/generate_prompt.py`, `backend/agents/generation/table_placeholder_utils.py`
- 风险： 单点单测能守住局部 contract，但守不住完整生成→审核→回填链路。
- Priority: Medium

**Retrieval live path：**
- What’s not tested: `backend/retrieval/comment_bad_case_runtime.py`、`backend/retrieval/qdrant_store.py` 和 `backend/retrieval/embeddings.py` 的真实外部服务行为。
- 相关文件： `backend/retrieval/comment_bad_case_runtime.py`, `backend/retrieval/qdrant_store.py`, `backend/retrieval/embeddings.py`
- 风险： mock 测试无法覆盖 provider、向量库和网络超时的组合故障。
- Priority: Medium

---

*后端风险分析：2026-06-25*

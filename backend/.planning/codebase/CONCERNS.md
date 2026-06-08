# 后端风险事实地图

**分析日期：** 2026-06-08

**范围：** `backend/` 当前技术债、脆弱区域、安全边界、性能限制和测试缺口。`backend/.env` 只记录存在性，不读取内容。

## Tech Debt

**`BaseGraph` / file lock 重复片段：**
- Issue: `backend/graphs/base_graph.py` 中存在重复导入和重复 `CrossProcessFileLock.__init__` / `acquire` 定义片段。
- Files: `backend/graphs/base_graph.py`
- Impact: 排查锁超时、取消、跨进程互斥和 Windows-only `msvcrt` 行为时容易读错实现分支；重构风险高。
- Fix approach: 先补锁获取、释放、超时、取消和进度包装测试，再做单独重构；不要夹在功能需求中顺手整理。

**大型 Word helper 和节点复杂度高：**
- Issue: 多个文件体量很大，核心复杂度集中在 Word 样式、COM 写回、service 编排和 agent runtime。
- Files: `backend/helper/word_helper/inline_style_ops.py`, `backend/nodes/gjgk_word_nodes/gjgk_update_word.py`, `backend/services/document_service.py`, `backend/nodes/common_word_nodes/update_word.py`, `backend/nodes/gngk_word_nodes/gngk_fw_zc_update_word.py`
- Impact: 小改动可能影响样式回填、表格匹配、批注写回或多类型 graph。
- Fix approach: 修改前定位最窄 helper/节点；添加 focused tests；避免在同一变更中移动大量逻辑。

**进程内状态限制：**
- Issue: 任务、队列、SSE buffer 和会话快照都在进程内存。
- Files: `backend/task/task_queue_manager.py`, `backend/core/sse_manager.py`, `backend/services/conversation_service.py`
- Impact: 服务重启会丢失任务状态、SSE 重放历史和会话 rewrite 上下文；多进程/横向扩展会分裂状态。
- Fix approach: 引入持久化前先定义任务恢复、SSE 事件序列、会话快照一致性和下载文件生命周期契约。

**Readiness 健康检查是轻量占位：**
- Issue: `/health/ready` 中 `upload_dir_accessible` 写死为 `True` 并带 TODO。
- Files: `backend/main.py`
- Impact: readiness 不能证明上传目录可写、Word COM 可用、pywin32 注册正常或外部 LLM 可达。
- Fix approach: 保持健康检查语义清晰；如果扩展 readiness，分别报告目录、COM、provider 和外部 HTTP 状态，不要把轻量探测当完整验收。

**Retrieval config fallback 会读取 `.env`：**
- Issue: `backend/retrieval/config.py` 在 `python-dotenv` 不可用时有手写 `.env` fallback loader。
- Files: `backend/retrieval/config.py`
- Impact: 运行时可用，但文档/诊断脚本执行时要避免打印真实 env 值；agent 扫描也不能读取 `.env` 内容。
- Fix approach: 日志只记录变量名和缺失状态，不输出值；脚本文档写清敏感信息边界。

## Known Bugs

**Readiness 上传目录检查未真实执行：**
- Symptoms: `/health/ready` 返回 `upload_dir_accessible: True`，但代码注释标记需要实际检查目录权限。
- Files: `backend/main.py`
- Trigger: 上传目录不存在、不可写或权限异常时请求 `/health/ready`。
- Workaround: 使用真实上传、生成任务或专门诊断检查，不把 `/health/ready` 作为上传目录验收。

## Security Considerations

**Secret and customer data leakage:**
- Risk: `.env`、LLM key、token、客户原文、私有路径、traceback 或下载路径进入文档、日志、agent workspace 或测试夹具。
- Files: `backend/config/settings.py`, `backend/agents/task_context_assistant/logging.py`, `backend/util/log_util/`, `backend/prompts_log/`
- Current mitigation: Agent run 审计有 scrub/白名单工具；项目规则禁止读取真实 `.env`。
- Recommendations: 新日志和审计字段必须先定义白名单；用户可见进度只写摘要；文档只写 env var 名，不写值。

**Template candidate SSRF / unsafe download:**
- Risk: 外部模板代理下载可能被滥用为 SSRF 或任意内容代理。
- Files: `backend/api/template_candidates.py`, `backend/util/common_util/template_candidates.py`
- Current mitigation: `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 主机白名单、URL 校验、年份阻断和上传区落盘。
- Recommendations: 保留白名单和 URL parse；新增下载来源时补 API tests。

**File path traversal:**
- Risk: 下载接口接收 URL 编码完整路径。
- Files: `backend/api/download.py`
- Current mitigation: `validate_file_path()` 将目标路径解析后强制 `relative_to(settings.UPLOAD_DIR)`。
- Recommendations: 修改下载逻辑时保留 path containment tests；不要把 download path 暴露给 agent run 原始上下文。

**Unauthenticated API surface:**
- Risk: 业务 routers 未检测到统一认证/权限依赖。
- Files: `backend/main.py`, `backend/api/`
- Current mitigation: 本地/受控环境假设；依赖中有 auth 包但未作为统一 API gate。
- Recommendations: 引入认证时同步后端 dependencies、API errors、前端 client 和 tests；同时定义任务/文件多用户隔离。

## Performance Bottlenecks

**Word COM 串行执行：**
- Problem: Word COM 是全局临界资源，任务吞吐受串行锁限制。
- Files: `backend/task/task_queue_manager.py`, `backend/graphs/base_graph.py`, `backend/util/word_util/word_com_manager.py`
- Cause: Word COM 文档打开/写入不适合并发；需要任务队列、公平锁、文件锁和 COM lock。
- Improvement path: 横向扩展前设计外部队列、单 worker Word 执行器和持久化任务状态；不要简单增加线程数。

**LLM streaming and agent loops:**
- Problem: 初次生成、rewrite、content agent、comment agent 和模板候选 AI 重排都有外部 LLM 延迟。
- Files: `backend/util/common_util/llm_stream_utils.py`, `backend/agents/generation/content_agents.py`, `backend/agents/comments/comment_agent.py`, `backend/services/template_candidate_ranking_service.py`
- Cause: 网络、模型推理、审核修订轮次和流式超时。
- Improvement path: 保持 timeout 集中配置；对可选 AI 重排保持范围限制；过程事件只推摘要，避免 SSE payload 膨胀。

**Large style writeback matching:**
- Problem: 样式回填逻辑复杂且可能对文档片段进行大量匹配。
- Files: `backend/helper/word_helper/inline_style_ops.py`
- Cause: Word 文档结构、表格、编号、局部候选和 fallback 规则复杂。
- Improvement path: 修改时使用 focused benchmark/fixture；保持 helper 层单测覆盖，不在节点中复制匹配逻辑。

## Fragile Areas

**GNGK subtype inheritance and overrides:**
- Files: `backend/graphs/gngk_hw_zc_tender_graph.py`, `backend/graphs/gngk_hw_cz_tender_graph.py`, `backend/graphs/gngk_fw_zc_tender_graph.py`, `backend/graphs/gngk_fw_cz_tender_graph.py`
- Why fragile: `gngk_hw_cz` 继承货物自筹主干但覆写 direct-replace delete/update；`gngk_fw_zc` 覆写服务专属 delete/replacement/update；`gngk_fw_cz` 继承共享主干。
- Safe modification: 改任一 `gngk_*` 时同步检查 graph class attribute、`backend/config/tender_config.py`、protected profile、content mode、前端 form type 分派和 tests。
- Test coverage: `backend/tests/graphs/test_gngk_tender_graph.py`, `backend/tests/nodes/test_gngk_hw_cz_direct_replace_word.py`, 各 `backend/tests/graphs/test_gngk_*_generation_mode_agent.py`

**Generate-only fields leaking into rewrite:**
- Files: `backend/models/generate.py`, `backend/services/document_service.py`, `backend/states/base_state.py`, `backend/skills/rewrite/SKILL.md`
- Why fragile: `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只适用于初次 generate；rewrite 混入这些字段会误触初次生成分支或污染 prompt。
- Safe modification: rewrite 请求、skill state、prompt surface 均不接收这些字段；新增 generate option 时补模型和 service 初始 state 测试。
- Test coverage: `backend/tests/models/test_generate_request_generation_style.py`, `backend/tests/services/test_document_service_initial_state.py`, `backend/tests/graphs/test_generation_mode_branching.py`

**Agent run as pre-task stream:**
- Files: `backend/api/agent.py`, `backend/services/agent_run_service.py`, `backend/agents/task_context_assistant/tools.py`
- Why fragile: agent run 只负责判断前置条件和创建任务；如果复制后台任务状态机会和 `TaskQueueManager` 分叉。
- Safe modification: 成功只返回 `task_accepted`，后续进度交给 task/SSE；缺条件返回 `needs_input`。
- Test coverage: `backend/tests/api/test_agent_run_api.py`, `backend/tests/services/test_agent_run_service.py`, `backend/tests/agents/test_task_context_assistant_tools.py`

**Comment supplement latest-state dependency:**
- Files: `backend/api/comment_supplement.py`, `backend/services/document_service.py`, `backend/graphs/comment_supplement_graph.py`, `backend/nodes/common_word_nodes/comment_supplement.py`
- Why fragile: 任务必须基于会话 latest `rewrite_state.prepared_doc_path` 和 `polished_text`；过期 `source_file` 会写回错误副本。
- Safe modification: 创建前校验 latest state、文件存在和路径匹配；成功后更新 latest `rewrite_state.prepared_doc_path`。
- Test coverage: `backend/tests/api/test_comment_supplement_api.py`, `backend/tests/graphs/test_comment_supplement_graph.py`, `backend/tests/services/test_document_service_comment_supplement.py`

**SSE `agent_step` contract:**
- Files: `backend/models/sse.py`, `backend/core/sse_manager.py`, `backend/services/document_service.py`, `backend/agents/generation/agent_step_events.py`
- Why fragile: 前端依赖 named event、结构化 `content_agent` / `comment_agent` payload 和终态事件；随意改字段会断过程卡。
- Safe modification: 新增字段保持向后兼容；同步前端类型和 tests。
- Test coverage: `backend/tests/models/test_sse_agent_step.py`, `backend/tests/services/test_sse_manager_agent_step.py`, `backend/tests/services/test_document_service_agent_step.py`

**Prompt literals as contracts:**
- Files: `backend/prompts/generate_prompt.py`, `backend/prompts/comment_prompt.py`, `backend/prompts/template_candidate_ranking_prompt.py`
- Why fragile: prompt 示例、JSON 字段和机器标识符被 tests、agent parsing 或前端过程展示依赖。
- Safe modification: 改 prompt 时跑 `backend/tests/prompts/` 和相关 agent tests。
- Test coverage: `backend/tests/prompts/test_generate_prompt_routing.py`, `backend/tests/prompts/test_comment_prompt_reference_contract.py`

## Scaling Limits

**Task/SSE/conversation memory state:**
- Current capacity: 单进程内由内存和 `settings.SSE_MAX_EVENTS_PER_TASK` 限制。
- Limit: 服务重启丢状态，多进程无法共享任务队列和 SSE buffer。
- Scaling path: 外部任务队列、持久化任务状态、集中事件流和文件生命周期管理。

**Word COM worker:**
- Current capacity: 串行 Word 执行路径。
- Limit: 并发生成会排队，长 Word/LLM 任务阻塞后续任务。
- Scaling path: 专用 Windows worker 池，但每个 worker 内仍需明确 COM 互斥和文件隔离。

**Local file storage:**
- Current capacity: 受 `UPLOAD_DIR` 所在磁盘、日志清理和文件生命周期影响。
- Limit: 多用户/长时间运行会积累上传和生成文件。
- Scaling path: 引入文件保留策略、对象存储或 job artifact 管理，并同步下载安全契约。

## Dependencies at Risk

**`pywin32` / Word COM:**
- Risk: Windows-only，依赖本机 Office COM 注册。
- Impact: WSL/Linux 或无 Office 环境无法完成真实 Word 写回。
- Migration plan: 保持 no-COM 单测和 Windows COM 诊断分层；替代方案需重写 Word 操作层。

**`deepagents`:**
- Risk: content agent 和 task context assistant 核心依赖，API 变化会影响 agent runtime。
- Impact: 初次 `generation_mode=agent` 和 agent run 前置流可能失败。
- Migration plan: 封装点在 `backend/agents/generation/content_agents.py` 和 `backend/agents/task_context_assistant/factory.py`；升级时优先补/跑 agent tests。

**Qdrant / Embedding service:**
- Risk: 检索脚本依赖外部 Qdrant 和 embedding key。
- Impact: 批注坏案例 hybrid retrieval 无法运行。
- Migration plan: 保持 retrieval config 独立；当前只按诊断/实验入口维护，接入正式批注业务路径前先补可降级行为和 tests。

## Missing Critical Features

**Persistent task store:**
- Problem: 任务、会话和 SSE 不持久化。
- Blocks: 服务重启恢复、多进程部署、跨 worker 任务查询。

**Unified authentication and authorization:**
- Problem: 未检测到统一 API auth layer。
- Blocks: 多用户隔离、生产权限控制、下载文件访问控制。

**Stable CI for Word COM:**
- Problem: 未检测到可执行 Windows + Word COM CI。
- Blocks: 自动证明真实 `.doc/.docx` 端到端写回。

## Test Coverage Gaps

**Real Word COM E2E:**
- What's not tested: 真实 Word/WPS COM 下的完整生成、rewrite、补充批注闭环。
- Files: `backend/util/word_util/`, `backend/nodes/`, `backend/helper/word_helper/`
- Risk: Fake object 单测通过但真实 COM range/table/comment 行为不同。
- Priority: High for release validation.

**External services live behavior:**
- What's not tested: 真实 LLM、外部招标详情、模板候选、Qdrant、embedding 服务状态；其中 Qdrant/embedding 当前只服务检索诊断/实验脚本。
- Files: `backend/util/common_util/llm_stream_utils.py`, `backend/util/common_util/fetch_tender_data.py`, `backend/util/common_util/template_candidates.py`, `backend/retrieval/`
- Risk: 配置、网络、接口字段变化导致运行时失败。
- Priority: Medium; committed tests 应继续 mock 外部服务。

**Frontend-backend full flow:**
- What's not tested: 从前端上传、创建任务、SSE、下载、补充批注、rewrite 的完整浏览器路径。
- Files: Backend endpoints in `backend/api/`; frontend tests live outside backend.
- Risk: 后端 API shape 和前端解析漂移。
- Priority: High for cross-system changes.

---

*后端风险审计：2026-06-08*

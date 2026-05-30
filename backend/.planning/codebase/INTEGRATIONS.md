# 后端集成事实地图

**分析日期：** 2026-05-31

**范围：** `backend/` 对外部服务、浏览器客户端、文件系统、Word COM 和运行环境的集成边界。

## API 与外部服务

### 前端调用边界

- 后端 API 前缀是 `/api`，router 注册在 `backend/main.py`。
- 前端应只通过 `frontend/lib/api.ts` 调用后端。
- 生成、edit、补充批注、任务、SSE、用户流式、上传、下载、招标详情、模板候选都在 `backend/api/` 下暴露。

### LLM Provider

- LLM 流式调用集中在 `backend/util/common_util/llm_stream_utils.py`。
- 当前模型枚举在 `backend/models/generate.py`：`deepseek`、`qwen`、`doubao`。
- Provider 配置在 `backend/config/settings.py`，包括 key、base URL、模型名和 `LLM_STREAM_TIMEOUT_SECONDS`。
- 生成、rewrite、edit、普通聊天和模板候选 AI 重排都应复用统一流式超时配置。
- 初次生成的 `generation_mode=agent` 通过 `backend/agents/generation/` 调用 DeepAgents；模型配置仍复用 `settings.get_llm_config()` 和 OpenAI-compatible client 参数。
- `content_agent` 工作区默认位于 `backend/prompts_log/content_agent_workspace/`，作为智能体输入、草稿、审核、修订和最终正文的本地审计边界。

### Agent Step SSE

- 智能体生成步骤通过 `SSEEventType.AGENT_STEP` 推送。
- `DocumentService` 在 graph config 中注入 `agent_step_callback`，公共 `content_agent` 节点和子 agent 通过该 callback 进入 `SSEManager`。
- `SSEManager.send_agent_step()` 会进入事件缓冲，断线重连时可随 `Last-Event-ID` 重放。
- 前端必须在 `frontend/lib/sse.ts` 显式监听 `agent_step` named event，再由 `frontend/hooks/useChatSSE.ts` 映射为过程卡。

### 补充批注任务

- 后端入口：`POST /api/comment-supplement`。
- 任务类型：`comment_supplement`，复用任务状态、心跳、SSE、下载和 `agent_step` 事件通道。
- Service 边界：`DocumentService.create_comment_supplement_task()` 校验会话 latest `rewrite_state`、`polished_text` 和当前下载文件路径，拒绝缺失或过期来源。
- Graph 边界：`CommentSupplementGraph` 只处理当前文档副本的补充批注，不重新生成正文；成功后更新会话 latest `rewrite_state.prepared_doc_path`。
- 前端触发来自初次生成下载卡，rewrite/edit/comment_supplement 下载卡不应再次显示补充批注动作。

### 招标详情接口

- 后端入口：`GET /api/tender/{tender_no}`。
- 工具层：`backend/util/common_util/fetch_tender_data.py`。
- 配置：`TENDER_DATA_API_URL`。
- 前端不应直接知道外部接口细节。

### 模板候选接口

- 后端入口：`backend/api/template_candidates.py`。
- 工具层：`backend/util/common_util/template_candidates.py`。
- AI 重排：`backend/services/template_candidate_ranking_service.py`。
- Prompt：`backend/prompts/template_candidate_ranking_prompt.py`。
- 外部下载链接必须经过 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 校验。
- `year < 2025` 或缺失/非法年份的候选只允许下载参考，不允许选择写入表单。

### Word COM

- Word COM 只在后端运行。
- COM 生命周期位于 `backend/util/word_util/word_application_util.py`。
- COM 锁与重试位于 `backend/util/word_util/word_com_manager.py`。
- Graph 级锁位于 `backend/graphs/base_graph.py`。
- 任务队列串行化位于 `backend/task/task_queue_manager.py`。

## 数据存储

- 任务、进度、队列状态、SSE 事件缓存和会话快照当前是进程内存态。
- 上传文件、模板候选选择结果和生成文件存储在 `settings.UPLOAD_DIR` 下。
- 上传落盘、文件名清洗、扩展名/大小校验位于 `backend/util/common_util/upload_storage.py`。
- 下载接口必须确认目标路径解析在上传目录内。
- 当前源码未确认外部数据库、Redis、对象存储或消息队列。

## 认证与身份

- 当前后端 API 路由未检测到登录、权限或认证依赖。
- 依赖文件中有 auth 相关包，但当前 `backend/main.py` 注册的业务 router 未使用稳定认证层。
- 如果后续新增认证，应同步后端依赖、API 契约、前端 `ApiError` 处理和测试。

## 监控与日志

- `backend/main.py` 配置 JSON stdout logging，并启动 progress/execution log listener。
- `progress_log` 面向用户进度，并可通过 SSE 转发。
- `execution_log` 面向排障堆栈、关键参数摘要和 graph 执行细节。
- `prompt_log` 和 `skill_audit_log` 分别记录 prompt 与 skill task 审计。
- 当前未确认外部 APM、日志平台或 tracing 系统。
- 当前未确认外部 LangSmith / tracing 为强依赖；相关配置存在时应保持可选、fail-soft。

## CI/CD 与部署

- 当前源文档未确认稳定 CI workflow。
- 代码真源中的本地运行入口是 `backend/main.py`、`scripts/start-dev.ps1` 和 `scripts/start-dev-wsl.sh`。
- 后端完整验收需要 Windows + Word COM；CI/WSL 更适合跑无 COM 单元测试。

## 环境配置

- 后端配置由 `backend/config/settings.py` 读取。
- `backend/.env.example` 是示例文件；`backend/.env` 是本地私有文件。
- 重要运行配置包括上传目录、LLM provider、外部招标详情 URL、模板候选 URL、模板下载白名单、任务心跳、SSE 保留和锁超时。
- 文档和日志不得记录真实 key、token、客户原文或私有文件内容。

## Webhook 与回调

- 当前后端未确认第三方入站 webhook。
- SSE 是服务端到浏览器的任务事件通道，不是外部 webhook。

## 集成风险

- LLM provider 调整时必须同步 `LLMModel`、settings、stream helper、prompt 调用侧和测试。
- 模板候选下载改动必须保留白名单与路径安全，避免 SSRF 和任意文件写入。
- Word COM 改动必须保留任务队列、graph 锁、COM 锁、取消检查和进度包装。
- API shape 变化必须同步 `backend/models/`、`frontend/types/api.ts`、`frontend/lib/api.ts` 和测试。

---

*后端集成分析：2026-05-31*

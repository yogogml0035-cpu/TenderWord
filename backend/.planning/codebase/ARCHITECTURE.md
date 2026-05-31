<!-- refreshed: 2026-05-31 -->
# 后端架构事实地图

**分析日期：** 2026-05-31

**范围：** 仅覆盖 `backend/`，并在启动、验证和 Windows/WSL 运行边界上参考根级 `AGENTS.md`、`README.md` 与 `scripts/`。

## 系统总览

```text
FastAPI /api
  -> API 路由
  -> service 编排
  -> 任务队列 + SSE
  -> LangGraph 生成 / rewrite / edit / 补充批注 / 用户路由
  -> Prompt Layer + LLM provider / DeepAgents content_agent
  -> Word helper + Word COM utility
  -> 上传目录中的产物与下载接口
```

后端是 TenderWord 的任务执行端。它负责 API 契约、任务生命周期、SSE 事件、LangGraph 流程、LLM 调用、模板候选代理、文件上传下载，以及所有 Word COM 文档操作。完整生成能力依赖 Windows Python、pywin32 与本机 Word/WPS COM 能力。

## 主要层次

| 层 | 职责 | 关键路径 |
| --- | --- | --- |
| API 层 | 暴露 `/api` 下的生成、编辑、补充批注、任务、SSE、上传下载、招标详情和模板候选接口 | `backend/api/` |
| 模型层 | 定义 Pydantic 请求、响应、任务、SSE 和模板候选模型 | `backend/models/` |
| Service 层 | 任务创建、graph 选择、会话快照、用户路由、模板候选 AI 重排 | `backend/services/` |
| 任务层 | 队列、串行化、取消、心跳、进度、任务状态快照 | `backend/task/task_queue_manager.py` |
| SSE 层 | 事件缓存、客户端连接、重放、日志桥接 | `backend/core/sse_manager.py`, `backend/api/stream.py`, `backend/util/log_util/sse_log_handler.py` |
| Graph 层 | 标准生成图、补充批注图、rewrite/edit skill 图、用户路由图 | `backend/graphs/` |
| State 层 | 公共 graph state 与类型专属 state | `backend/states/` |
| Node 层 | Word 准备、抽参、删除、替换、生成、批注、写回等 graph 节点 | `backend/nodes/` |
| Word 业务 helper | 受保护字段、正文边界、插入、cleanup、样式回填、范围工具 | `backend/helper/word_helper/` |
| 技术 utility | Word COM 生命周期、上传存储、HTTP、LLM 流式、日志 | `backend/util/` |
| 内容智能体 | 初次生成 `generation_mode=agent` 的 DeepAgents 主/子智能体、工作区和步骤事件 | `backend/agents/generation/` |
| Prompt / Skill | prompt 渲染、prompt-bound 解析、rewrite/edit task skill 声明 | `backend/prompts/`, `backend/skills/` |
| 配置 | 环境配置、招标类型锚点、字号、content mode、profile、family | `backend/config/settings.py`, `backend/config/tender_config.py` |

## 关键运行链路

### 初次生成

1. `POST /api/generate` 在 `backend/api/generate.py` 校验 `GenerateRequest`。
2. `DocumentService.create_task()` 根据 `form_type` 从 `GRAPH_REGISTRY` 选择 graph，并构造初始 state。
3. 初始 state 写入 `tender_type`、`template_path`、`tender_param_paths`、招标数据、默认锚点、`generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 和会话信息。
4. `TaskQueueManager` 创建任务并进入队列。
5. 后台线程执行 graph；`BaseGraph.invoke_with_timing_async()` 等待公平队列、获取跨进程锁、注册运行上下文并执行 LangGraph。
6. `StandardTenderWorkflowGraph` 按共享拓扑执行模板准备、抽参、Word 子图、生成、批注、写回等节点；`generation_mode=workflow` 进入 `generate_polished_text`，`generation_mode=agent` 进入公共 `content_agent` 节点，`comment_generation_mode=off` 跳过 AI 批注分支。
7. 类型 graph 只绑定差异节点：`xjcg`、`gngk_hw_zc`、`gngk_hw_cz`、`gngk_fw_zc`、`gngk_fw_cz`、`gjgk` 分别由 `backend/graphs/*_tender_graph.py` 注册。
8. 成功后 `DocumentService` 构造任务结果、更新会话快照并发送 SSE `done`；失败时发送 SSE `error` 并标记任务失败。

`gngk_hw_cz` 当前是财政货物 direct-replace 首次生成类型：`GngkHwCzTenderGraph` 继承货物自筹主干，但显式覆写 delete/update 节点，继续复用货物 replacement wrapper。

### 任务状态与 SSE

- 任务状态、取消和心跳由 `backend/api/tasks.py` 与 `backend/services/task_service.py` 暴露。
- SSE 主入口是 `GET /api/stream/{task_id}`，事件缓存与 `Last-Event-ID` 重放在 `backend/core/sse_manager.py`。
- `progress_log` 通过 `sse_log_handler` 转成用户可见进度日志；排障细节应留在 `execution_log`。
- 智能体生成过程通过 `agent_step` SSE 展示 `content_agent`、`content_generate_agent`、`content_verify_agent`、`content_revise_agent` 的流式过程；终态仍必须走 `done` / `error`。

### 智能体生成分支

- `backend/nodes/common_word_nodes/content_agent_generate.py` 是标准 graph 中的公共智能体节点，只把 DeepAgents 结果收敛为 `polished_text` 与 `generate_polished_done=True`。
- `backend/agents/generation/content_agents.py` 是 DeepAgents 主运行时真源，主 `content_agent` 通过 task 工具调度 generate / verify / revise 子 agent，最多 3 轮审核修订。
- `backend/agents/generation/workspace.py` 管理单次生成工作区，默认写入 `backend/prompts_log/content_agent_workspace/`，用于审计输入、草稿、审核、修订和最终正文。
- `agent_step` 事件由 graph config 注入的 callback 进入 `SSEManager`，不由子 agent 直接连接 SSE manager。

### 普通聊天、rewrite、edit 与补充批注

- 普通聊天和 rewrite 判路走 `POST /api/user/stream`，返回 NDJSON。
- 用户路由由 `backend/services/user_routing_service.py`、`backend/graphs/user_graph.py` 与 `backend/prompts/routing_prompt.py` 负责。
- rewrite/edit 是 task skill runtime，声明在 `backend/skills/rewrite/` 与 `backend/skills/edit/`，执行图由 `backend/graphs/skill_graph.py` 构造。
- edit 是显式入口，只走 `POST /api/edit`，不并回 user stream 的模型判路链路。
- 补充批注是独立任务入口，只走 `POST /api/comment-supplement`；`DocumentService.create_comment_supplement_task()` 校验 latest `rewrite_state` 和当前下载文件后，提交 `CommentSupplementGraph`。
- `CommentSupplementGraph` 的节点顺序是 `prepare_comment_supplement -> comment_agent -> finalize_comment_supplement`，成功后会把新的 `prepared_doc_path` 写回会话 latest `rewrite_state`，后续 rewrite/edit 应继续基于该副本。

### 模板候选

- 前端只访问项目内 `/api/template-candidates*`。
- 后端负责外部候选列表请求、年份/可选性归一化、AI row_index 重排、下载白名单校验、文件落盘与回填。
- 关键路径是 `backend/api/template_candidates.py`、`backend/util/common_util/template_candidates.py`、`backend/services/template_candidate_ranking_service.py` 和 `backend/prompts/template_candidate_ranking_prompt.py`。

### 上传、下载与招标详情

- 上传由 `backend/api/upload.py` 调用 `backend/util/common_util/upload_storage.py` 做扩展名、大小、文件名和落盘处理。
- 下载由 `backend/api/download.py` 校验请求路径必须解析在 `settings.UPLOAD_DIR` 下。
- 招标详情由 `backend/api/tender.py` 调用 `backend/util/common_util/fetch_tender_data.py`。

## 核心抽象

- `GenerateRequest` / `EditTaskRequest`：生成和显式 edit 的 API 输入契约，位于 `backend/models/generate.py`。
- `GenerationMode`：初次生成方式契约，`workflow` 是默认旧路径，`agent` 只影响初次 generate 的生成节点选择。
- `CommentGenerationMode`：初次生成批注开关，`on` 是默认路径，`off` 只影响 generate 的 AI 批注分支。
- `FormType` -> `GRAPH_REGISTRY`：`xjcg_tender`、四个 `gngk_*_tender` 和 `gjgk_tender` 到 graph class 的延迟注册，位于 `backend/services/document_service.py`。
- `TenderGraphStateBase`：生成与 task skill 写回共享 state 底座，位于 `backend/states/base_state.py`。
- `StandardTenderWorkflowGraph`：标准 tender 生成拓扑，类型 graph 通过 class attribute 绑定差异节点。
- `CommentSupplementGraph`：补充批注任务图，复用任务队列、SSE、`comment_agent` 和会话 rewrite_state 更新机制。
- `content_agent`：标准生成 graph 的智能体生成节点，不能在各类型 graph 里复制分流逻辑。
- `TaskQueueManager`：长任务队列、串行化、心跳和进度真源。
- `SSEManager`：任务事件缓存、跨线程发送和重连重放。
- `TaskSkillWorkflow`：rewrite/edit skill 从 `SKILL.md` 与 `scripts/workflow.py` 声明可执行节点序列。
- Prompt Layer：`backend/prompts/` 只负责 prompt 渲染与机器契约相关解析。
- `TenderAnchorConfig`：锚点、字号、content start/update mode 和受保护字段 profile 的配置真源。

## 架构约束

- Word COM 工作必须经过 `DocumentService`、`TaskQueueManager`、`BaseGraph` 锁、取消检查和进度包装。
- API router 应保持薄入口，业务编排进入 service、graph、node、helper。
- Word 业务逻辑优先下沉到 `backend/helper/word_helper/`；`backend/util/word_util/` 只放 COM 生命周期和底层工具。
- 后端跨包导入统一使用 `backend.*`；旧的短 import 只能作为历史兼容，不应复制。
- 任务、SSE 和会话快照是进程内存态；上传和生成文件是本地文件态。
- Prompt、LLM 超时、DeepAgents content_agent、rewrite/edit skill 契约应集中维护，不在 service/node 里散落大段 prompt。

## 反模式

- 在 API、service、脚本或前端中直接打开 Word 并改文档。
- 为少量锚点、字号或 replacement 差异复制整套 graph。
- 在节点里硬编码类型锚点、受保护字段 profile 或 family。
- 在类型节点之间互相 import 私有 helper，导致 Word 业务逻辑继续分叉。
- 新增 SSE 事件但不更新前端类型、解析和测试。
- 修改 `form_type` 或 gngk 分派时只改后端，或绕过前端共享 helper `frontend/lib/gngkFormType.ts`。

## 错误处理

- API 层使用 Pydantic 与结构化 `HTTPException`。
- 任务失败必须收敛为任务失败状态和 SSE `error` 或 `done`，不能静默断流。
- 取消通过 `TaskCancelledException` 从 graph 运行时向 service 收敛。
- LLM 配置、流式超时和 provider 调用集中在 `backend/util/common_util/llm_stream_utils.py`。
- 受保护字段、正文边界和 direct-replace 契约应 fail-fast，不做半写回。

## 横切关注点

- 日志分层：`progress_log` 面向用户进度，`execution_log` 面向排障，`prompt_log` 面向 prompt 记录，`skill_audit_log` 面向 task skill 审计。
- `content_agent` 工作区保留完整输入和生成中间产物；运行期日志只记录长度、节点和摘要，不记录完整客户正文。
- 文件安全：上传文件名清洗、下载路径限制、模板候选下载白名单都在后端执行。
- 测试入口：后端测试按 API、graph、node、helper、service、prompt、config 等目录归档在 `backend/tests/`。

---

*后端架构分析：2026-05-31*

# TenderWord 架构地图

**生成日期：** 2026-06-29

本文件是根级**系统级架构总览**，描述 TenderWord 的系统目的与边界、子系统职责、推荐理解路径、稳定目录职责和系统层维护约定。实现细节以代码为准；子系统内部事实以 2026-06-29 刷新的 `backend/.planning/codebase/` 与 `frontend/.planning/codebase/` 为准。

> 分层定位：本文件比 `AGENTS.md` 更偏系统架构，比 `coding_maps/SYSTEM_MAP.md` 更偏稳定总览；跨项目接口与调用关系沉淀在 `INTERFACES.md`，按任务的阅读指南沉淀在 `coding_maps/SYSTEM_MAP.md`。本文件不复制子项目内部实现细节。

## 1. 系统目的与边界

TenderWord 是前后端分离的招标文档生成、修改、补充批注与模板复用系统。前端是浏览器工作台，负责会话、表单、任务进度和文件交互；后端是 FastAPI + LangGraph + Word COM 执行端，负责 API、任务队列、SSE/NDJSON、LangGraph 工作流、LLM/智能体调用、模板候选代理、招标详情代理、批注 bad case 检索和 Word 文件生成/写回。

核心闭环：

```text
浏览器 / Next.js 工作台
  -> FastAPI /api
  -> TaskQueueManager 任务队列 + SSE
  -> LangGraph tender / rewrite skill / comment_supplement 工作流
  -> Prompt Layer + OpenAI-compatible LLM provider / DeepAgents content_agent / LangChain comment_agent
  -> Word COM 文档操作（写回受 graph 锁、取消检查和进度包装保护）
  -> 生成文件 / 任务结果 / 下载
```

系统边界要点（均为源文档已确认）：

- **运行环境边界：** 系统完整能力依赖 Windows + Word COM。前端可在 WSL/Linux Node 环境运行，但后端 Word 自动化必须使用 Windows Python、`pywin32` 和本机 Word/WPS COM。无 COM 环境只能覆盖 API shape、service、prompt、retrieval、agent guard 和 helper 纯逻辑。后端端口 8000，前端端口 8502。
- **职责隔离边界：** 浏览器端不执行 Word COM、LLM、检索、真实文件落盘或外部模板候选直连；这些能力由后端 `/api/*` 封装。
- **认证边界：** 前后端均未检测到强制认证/鉴权层或稳定 `Authorization` header；`conversation_id` / `user_session_id` / `task_id` 只用于运行态连续性，不是安全身份。

## 2. 子系统职责

### `frontend/` —— 浏览器工作台

Next.js 16 + React 19 + Zustand 5 + TypeScript 5 工作台。职责：

- 三栏工作台（招标类型侧栏、表单面板、聊天与任务面板），`/` 重定向到 `/tender`。
- 招标类型侧栏、表单面板、聊天与任务面板，URL 深链、会话与草稿。
- 招标类型表单与 URL 判型；前端 `TenderType`（`xjcg`/`gngk`/`gjgk`）、URL canonical 化、`gngk` 子类型身份匹配。
- 会话、草稿、历史、任务摘要与 SSE resume 元数据的 `sessionStorage` 持久化；运行中 stream 为内存态。
- generate 任务创建、agent run（任务上下文助手前置流）、上传文件 rewrite、补充批注、SSE/agent-step 过程卡、上传下载、模板候选弹窗。
- 通过 `frontend/lib/api.ts` 调用后端 JSON、上传、下载、NDJSON 和 SSE helper。

**可独立维护性：** 前端是一个独立可构建的 Next.js 子项目（`npm`，端口 8502），不依赖后端内部结构，仅通过 `/api/*` 契约耦合。事实入口见 `frontend/.planning/codebase/`。

### `backend/` —— 执行端

FastAPI + LangGraph + Word COM 后端。职责：

- `/api` 前缀下的生成、重写、补充批注、任务、SSE、任务上下文助手 agent run、会话心跳、上传下载和模板候选接口，以及根级 `/health*` 健康检查。
- `DocumentService` 任务创建、graph 选择、初始 state 构造、任务提交和结果 payload。
- `TaskQueueManager` 串行化文档任务、公平锁、进度、取消、心跳和清理。
- `SSEManager` 事件缓冲、客户端管理、断线重连重放和跨线程 threadsafe 调度。
- 标准 tender graph 共享主干、`RewriteSkillGraph`、任务上下文助手 `task_context_assistant` 和 `generation_mode=agent` 的 content agent 分支。
- agent generate 与补充批注共用的 `comment_agent` 批注生成、锚点校验、写回统计和过程事件。
- Word COM 生命周期、共享 Word helper、类型特化节点和 Prompt Layer。
- 外部 LLM provider、招标详情接口和模板候选接口的后端代理，批注 bad case 检索。

**可独立维护性：** 后端是独立 Python 3.12 子项目，业务编排集中在 service / graph / node / helper；前端只消费 `/api/*`，后端内部重构不影响前端契约。事实入口见 `backend/.planning/codebase/`。

### `asset/` —— 长期知识包

`asset/` 是跨多轮需求会复用的同步面、边界和回归风险沉淀目录。它不替代代码真源，索引是 `asset/README.md`。当前有效主题：

- `asset/shared_runtime_word_skill_knowledge_pack.md` —— generate/rewrite/comment_supplement 运行时、Word skill、SSE 透传、批注/样式回写。
- `asset/tender_type_identity_session_knowledge_pack.md` —— 类型 identity、`form_type`/`tender_type`/family、graph/state/node/replacement 收敛。
- `asset/template_candidate_pipeline_knowledge_pack.md` —— 模板候选与智能抽取。

## 3. 推荐理解路径

> 完整的按任务阅读指南在 `coding_maps/SYSTEM_MAP.md`；`AGENTS.md` 是执行规则入口。下面只给系统层起步顺序。

### 第一次接手

1. `AGENTS.md`（仓库定位、文档分层、维护红线）
2. `ARCHITECTURE.md`（本文件，系统边界与子系统职责）
3. `coding_maps/SYSTEM_MAP.md`（跨子项目系统地图与按任务阅读指南）
4. `INTERFACES.md`（跨端接口与边界）
5. 对应子项目 `.planning/codebase/ARCHITECTURE.md`

### 改后端

进入 `backend/.planning/codebase/`（ARCHITECTURE → STRUCTURE → CONVENTIONS → TESTING），再按 `coding_maps/SYSTEM_MAP.md` 的后端任务分支定位具体模块；长期规则看 `asset/shared_runtime_word_skill_knowledge_pack.md` 与 `asset/tender_type_identity_session_knowledge_pack.md`。

### 改前端

进入 `frontend/.planning/codebase/`（ARCHITECTURE → STRUCTURE → CONVENTIONS → TESTING）；类型身份与会话看 `asset/tender_type_identity_session_knowledge_pack.md`。

### 改跨端接口

必须同时读 `docs/interfaces-runtime.md`、`INTERFACES.md`、`backend/models/`、`backend/api/`、`frontend/types/api.ts`、`frontend/lib/api.ts` 及相关前后端测试。接口变更不能只改一侧。

## 4. 稳定目录职责

顶层目录一行说明（仅系统层稳定职责，子项目内部结构见各自 `.planning/codebase/STRUCTURE.md`）：

| 目录 | 稳定职责 |
| --- | --- |
| `backend/` | FastAPI `/api`、任务队列、SSE/NDJSON、LangGraph 工作流、DeepAgents/LangChain 智能体、Prompt Layer、Word COM 写回、模板候选/招标详情代理、批注 bad case retrieval、上传下载。 |
| `frontend/` | Next.js 工作台、招标类型表单与 URL 判型、会话/草稿/任务摘要持久化、generate/agent run/上传 rewrite/补充批注、SSE/agent-step 过程卡、上传下载、模板候选弹窗。 |
| `asset/` | 长期知识包，沉淀跨主题复用的同步面、边界与回归风险。 |
| `coding_maps/` | 跨子项目系统地图（`SYSTEM_MAP.md`），按任务的阅读指南与集成风险检查清单。 |
| `docs/` | 面向具体工作流的事实说明（`backend.md`、`frontend.md`、`interfaces-runtime.md`、`knowledge-validation.md`）。 |
| `scripts/` | 启动脚本（Windows / WSL 协作入口）。 |

根级文档：

- `AGENTS.md`：仓库级执行规则、导航入口和维护红线。
- `ARCHITECTURE.md`（本文件）：系统边界与子系统职责。
- `INTERFACES.md`：前后端接口边界、跨系统调用关系与排查建议。
- `coding_maps/SYSTEM_MAP.md`：跨子项目系统地图与按任务阅读指南。
- `README.md`：首次安装与启动导航。

## 5. 系统层面维护约定

### 文档分层

- 子项目事实变化应先更新对应 `.planning/codebase/`；长期边界进入 `asset/`；影响多数未来需求的规则上提到 `AGENTS.md`。
- 根级文档保留系统边界和阅读路径，不复制子项目内部实现细节（`backend/` 的分层结构、`frontend/` 的组件清单不进本文件，见各自 STRUCTURE）。

### 跨层同步门槛

- **接口变化**必须同步 `INTERFACES.md`、`backend/models/`、`frontend/types/api.ts`、`frontend/lib/api.ts` 和前后端测试；新增任务类型还要同步 `TaskKind`（前后端 union）、SSE 终态、下载卡和会话结果语义。
- **新增/修改 SSE 事件**必须同步后端 `SSEEventType`、前端 union 类型、`frontend/lib/sse.ts` named event 注册、`useChatSSE` 解析和测试，并区分后端真实事件（`log`/`llm`/`progress`/`node_start`/`node_complete`/`agent_step`/`done`/`error`/`heartbeat`）与前端连接/映射层事件（`connected`/`status`）。
- **招标类型变化**必须同步前端 UI 类型、后端 `FormType`、`GRAPH_REGISTRY`、graph/state/node、anchor config 和测试。
- 当前任务类型只有 `generate` / `rewrite` / `comment_supplement`。

### 验证门槛

- 后端常规验证：`backend/` 运行 `.\.venv\Scripts\python.exe -m pytest tests -v`（Word COM 闭环必须回到 Windows + Word/WPS COM 环境）。
- 前端常规验证：`frontend/` 运行 `npm run lint`、`npm run type-check`、`npm run test`（Jest）；E2E 运行 `npm run test:e2e`（Playwright）。
- 仅文档变更：根目录运行 `git diff --check`，并扫描文档中的密钥/token 模式；不需要跑代码测试或 E2E。

### Word COM 边界（系统级红线）

- Word COM 是稀缺临界资源：新增 Word 能力不得在 API route、service、前端或随意脚本中直接操作 COM，必须经 `DocumentService` → `TaskQueueManager`（公平锁 `wait_for_turn`）→ graph 锁（`CrossProcessFileLock` + `msvcrt.locking`）→ 节点取消检查 → 进度包装 → `backend/util/word_util/`（`com_lock()`）。
- 任务、SSE event buffer、conversation rewrite history、retrieval runtime cache 当前均为**进程内状态**，服务重启不恢复；文件产物和日志是本地文件状态。

### 安全边界（系统级）

- 不读取或输出 `backend/.env`、`frontend/.env.local` 真实值；文档/日志/回复只记录配置键名。
- agent run 审计与公共摘要工具只暴露 scrub 后白名单字段，不返回完整客户原文、token、私有路径、traceback 或下载路径。
- 文件下载受 `settings.UPLOAD_DIR` containment 校验；外部模板下载受 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 白名单校验。

---

*系统架构地图：2026-06-29*

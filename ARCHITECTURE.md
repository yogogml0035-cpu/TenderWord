# TenderWord 架构地图

**生成日期：** 2026-07-18

本文件是根级**系统级架构总览**，描述 TenderWord 的系统目的与边界、子系统职责、推荐理解路径、稳定目录职责和系统层维护约定。实现细节以代码为准；子系统内部事实以 2026-07-18 刷新的 `backend/.planning/codebase/` 与 `frontend/.planning/codebase/` 为准。

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
- **任务类型边界：** 当前后台任务只有 `generate`、`rewrite`、`comment_supplement`；进程内任务/SSE/会话状态，服务重启不恢复。

## 2. 子系统职责

### `frontend/` —— 浏览器工作台

Next.js 16 + React 19 + Zustand 5 + TypeScript 5 工作台。职责：

- 三栏工作台（招标类型侧栏、表单面板、聊天与任务面板），`/` 重定向到 `/tender`。
- URL 深链、会话与草稿；前端 `TenderType`（`xjcg`/`gngk`/`gjgk`）、URL canonical 化、`gngk` 子类型身份匹配。
- 会话、草稿、历史、任务摘要与 SSE resume 元数据的 `sessionStorage` 持久化；运行中 stream 为内存态。
- generate 任务创建、agent run（任务上下文助手前置流）、上传文件 rewrite、补充批注、SSE/agent-step 过程卡、上传下载、模板候选弹窗。
- 通过 `frontend/lib/api.ts` 调用后端 JSON、上传、下载、NDJSON 和 SSE helper；组件不写裸 `fetch`。

**可独立维护性：** 前端是独立可构建的 Next.js 子项目（npm，端口 8502），仅通过 `/api/*` 契约耦合后端。事实入口见 `frontend/.planning/codebase/`。

### `backend/` —— 执行端

FastAPI + LangGraph + Word COM 后端。职责：

- `/api` 前缀下的生成、重写、补充批注、任务、SSE、agent run、会话心跳、上传下载和模板候选接口，以及根级 `/health*` 健康检查。
- `DocumentService` 任务创建、graph 选择、初始 state、任务提交和结果收敛；`TaskQueueManager` 公平队列、进度、取消、心跳；`SSEManager` 事件缓冲与跨线程调度。
- 标准 tender graph 共享主干（含 `generation_mode` / 批注分支 / **仅 generate 接入的 `annotate_corrections`**）、显式 `RewriteSkillGraph`、`CommentSupplementGraph`。
- content agent / comment agent / task context assistant；Prompt Layer；Word COM 与共享 Word helper；招标详情与模板候选代理；批注 bad case retrieval。

**可独立维护性：** 后端是独立 Python 3.12 子项目；前端只消费 `/api/*`，内部 service/graph/node/helper 重构在契约不变时不影响前端。事实入口见 `backend/.planning/codebase/`。

### 系统级流水线（职责分层，非实现清单）

| 链路 | 系统职责 |
| --- | --- |
| **generate** | 表单 → `POST /api/generate` → 类型 graph → 正文（workflow 或 content_agent）→ **`annotate_corrections`（仅 generate）** → 普通批注分支 → `update_word`（先更正批注、后普通批注）→ 可选 `comment_agent` → SSE/下载。 |
| **rewrite** | 右侧聊天 agent run（NDJSON）→ 条件满足后 `task_accepted` → **`RewriteSkillGraph`**（不接入 `annotate_corrections`）→ 复用 task/SSE/下载；上传来源用 `rewrite_source="uploaded_file"`。 |
| **comment_supplement** | 仅 generate 下载卡触发 → `POST /api/comment-supplement` → 校验 latest 文档 → `comment_agent` 写回 → 更新会话 latest 文档路径。 |
| **模板候选 / 招标详情** | 前端只调项目内 `/api/*`；外部列表、下载白名单、落盘与招标详情代理均在后端。 |

### `asset/` —— 长期知识包

`asset/` 沉淀跨多轮复用的同步面、边界与回归风险，不替代代码真源；索引是 `asset/README.md`。当前有效主题：

- `asset/shared_runtime_word_skill_knowledge_pack.md` —— generate/rewrite/comment_supplement 运行时、Word skill、SSE 透传、批注/样式回写。
- `asset/tender_type_identity_session_knowledge_pack.md` —— 类型 identity、form_type/tender_type/family、graph/state/node 收敛。
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

进入 `backend/.planning/codebase/`（ARCHITECTURE → STRUCTURE → CONVENTIONS → TESTING），再按 `coding_maps/SYSTEM_MAP.md` 的后端任务分支定位；长期规则看 `asset/shared_runtime_word_skill_knowledge_pack.md` 与 `asset/tender_type_identity_session_knowledge_pack.md`。涉及更正批注/编号隔离/写回顺序时，再读 `docs/backend.md` 与后端 CONCERNS 中的近期风险面。

### 改前端

进入 `frontend/.planning/codebase/`（ARCHITECTURE → STRUCTURE → CONVENTIONS → TESTING）；类型身份与会话看 `asset/tender_type_identity_session_knowledge_pack.md`。

### 改跨端接口

必须同时读 `docs/interfaces-runtime.md`、`INTERFACES.md`、`backend/models/`、`backend/api/`、`frontend/types/api.ts`、`frontend/lib/api.ts` 及相关前后端测试。接口变更不能只改一侧。

## 4. 稳定目录职责

顶层目录一行说明（仅系统层稳定职责，子项目内部结构见各自 `.planning/codebase/STRUCTURE.md`）：

| 目录 | 稳定职责 |
| --- | --- |
| `backend/` | FastAPI `/api`、任务队列、SSE/NDJSON、LangGraph、智能体、Prompt Layer、Word COM、外部代理、retrieval、上传下载。 |
| `frontend/` | Next.js 工作台、类型/URL/会话、generate/agent run/rewrite/补充批注 UI、SSE 过程卡、上传下载、模板候选弹窗。 |
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
- 根级文档保留系统边界和阅读路径，不复制子项目内部实现细节（`backend/` 分层、`frontend/` 组件清单不进本文件，见各自 STRUCTURE）。

### 跨层同步门槛

- **接口变化**必须同步 `INTERFACES.md`、`backend/models/`、`frontend/types/api.ts`、`frontend/lib/api.ts` 和前后端测试；新增任务类型还要同步 `TaskKind`、SSE 终态、下载卡和会话结果语义。
- **新增/修改 SSE 事件**必须同步后端 `SSEEventType`、前端 union、`frontend/lib/sse.ts` named event、`useChatSSE` 和测试；区分后端真实事件与前端连接/映射层事件（`connected`/`status`）。
- **招标类型变化**必须同步前端 UI 类型、后端 `FormType`、`GRAPH_REGISTRY`、graph/state/node、anchor config 和测试。
- **批注职责边界：** 差异更正批注归 `annotate_corrections`（仅 generate）；合规批注归 `comment_agent`；批注写回收敛到共享 writeback helper。
- 当前任务类型只有 `generate` / `rewrite` / `comment_supplement`。

### 验证门槛

- 后端常规验证：`backend/` 运行 `python -m pytest tests -v`（async 用例需显式 `@pytest.mark.asyncio`）；Word COM 闭环必须回到 Windows + Word/WPS COM。
- 前端常规验证：`frontend/` 运行 `npm run lint`、`npm run type-check`、`npm run test`；E2E 运行 `npm run test:e2e`。
- 仅文档变更：根目录运行 `git diff --check`，并扫描密钥/token 模式；不需要跑代码测试或 E2E。

### Word COM 边界（系统级红线）

- Word COM 是稀缺临界资源：新增 Word 能力不得在 API route、service、前端或随意脚本中直接操作 COM，必须经 `DocumentService` → `TaskQueueManager`（公平锁）→ graph 锁 → 节点取消检查 → 进度包装 → `backend/util/word_util/`。
- 任务、SSE event buffer、conversation rewrite history、retrieval runtime cache 当前均为**进程内状态**，服务重启不恢复；文件产物和日志是本地文件状态。

### 安全边界（系统级）

- 不读取或输出 `backend/.env`、`frontend/.env.local` 真实值；文档/日志/回复只记录配置键名。
- agent run 审计与公共摘要工具只暴露 scrub 后白名单字段，不返回完整客户原文、token、私有路径、traceback 或下载路径。
- 文件下载受 `settings.UPLOAD_DIR` containment 校验；外部模板下载受 `TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 白名单校验。
- retrieval 命中详情只进入后端 prompt/审计，不进入 SSE、下载卡或 `agent_step`。

---

*系统架构地图：2026-07-18*

# TenderWord Agent Operating Guide (AGENTS.md)

本文件用于给各类代码智能体提供统一的“项目记忆”和执行规范：它应当简短、强约束、可操作，覆盖高频工作流与项目特有陷阱；低频细节放在代码与局部文档中，由智能体按需检索。

## 1) Agent 职责与行为规范

### 角色边界
- 智能体是“结对资深工程师”：负责分析、实现、验证与回归，默认交付可合并的改动。
- 智能体不应做“产品决策者”：需求不明确时，先给出最合理默认并声明假设，避免无休止追问。
- 智能体不应做“运维执行者”：不得外泄密钥、不得提交/推送代码，除非用户明确要求。

### 工作原则
- 最小改动：优先局部修改，避免无谓重构与跨目录搬迁。
- 遵循现有约定：先读同目录/同模块代码的既有写法，再动手。
- 以验证为前置：改完必须跑对应的 lint/typecheck/tests（能跑则跑，跑不了要说明原因与替代验证）。
- 失败可诊断：遇到错误要输出可复现信息（命令、关键日志、错误码），并给出下一步定位路径。

### 安全与合规
- 绝不打印或记录敏感信息（环境变量、token、私钥、客户数据）。
- 不新增重量级依赖；如必须新增依赖，需明确理由、影响面与替代方案。
- 文件/目录删除属于高风险操作，除非用户明确要求或能严格证明是无引用的冗余。

## 2) 标准化指令模板与交互协议

### 用户请求模板（推荐）
#### A. 修复缺陷
- 目标：一句话描述 bug
- 复现：步骤 + 期望/实际
- 影响范围：页面/接口/任务流
- 验证：希望跑哪些测试或手工路径

#### B. 新增功能
- 目标：要新增什么能力
- 约束：性能/兼容/不改动的模块
- 交互：UI/接口/数据格式
- 验证：验收用例

#### C. 重构/优化
- 目标：为什么要改（可维护性/性能/可靠性）
- 边界：允许改哪些目录/文件
- 风险：要避免的回归
- 验证：需要通过的检查项

### 智能体输出协议（固定）
- 变更摘要：列出改动点与影响面
- 关键引用：给出关键文件路径与定位点
- 验证结果：列出已执行命令与结果
- 风险与回滚：说明可能回归点与回滚方式

## 3) 项目特定上下文约束与决策边界

### 项目定位
TenderWord：招标文档智能处理系统，前后端分离。
- 前端：Next.js 16 / React 19 / Tailwind 4 / Zustand
- 后端：FastAPI / LangGraph
- 关键约束：依赖 Windows Word COM，不能在 Linux/macOS 上完整运行

### 核心架构与“不可破坏”约束
- Word COM 操作必须串行并受双层锁保护：公平队列锁 + 跨进程文件锁
  - 队列管理：[task_queue_manager.py](file:///d:/CompanyProject/TenderWord-feat-h/backend/task/task_queue_manager.py)
  - 跨进程锁与节点包装：[base_graph.py](file:///d:/CompanyProject/TenderWord-feat-h/backend/graphs/base_graph.py)
- 后端日志分层不可混用
  - 进度日志（推送前端）：[progress_log.py](file:///d:/CompanyProject/TenderWord-feat-h/backend/util/log_util/progress_log.py)
  - 执行日志（本地调试）：[execution_log.py](file:///d:/CompanyProject/TenderWord-feat-h/backend/util/log_util/execution_log.py)
  - SSE 推送 handler：[sse_log_handler.py](file:///d:/CompanyProject/TenderWord-feat-h/backend/util/log_util/sse_log_handler.py)

### 变更决策边界
- API 形状变更：必须同步更新前端类型与调用封装
  - 前端 API 客户端：[api.ts](file:///d:/CompanyProject/TenderWord-feat-h/frontend/lib/api.ts)
  - 前端 API 类型：[types/api.ts](file:///d:/CompanyProject/TenderWord-feat-h/frontend/types/api.ts)
- 新增招标类型：必须同时提供 Graph + State +（如需）特有节点
  - Graph：[backend/graphs/](file:///d:/CompanyProject/TenderWord-feat-h/backend/graphs/)
  - State：[backend/states/](file:///d:/CompanyProject/TenderWord-feat-h/backend/states/)
  - Nodes：[backend/nodes/](file:///d:/CompanyProject/TenderWord-feat-h/backend/nodes/)
- 文档/契约来源
  - API 契约：[API_CONTRACT.md](file:///d:/CompanyProject/TenderWord-feat-h/docs/API_CONTRACT.md)
  - 后端真实路由：以 [backend/api/](file:///d:/CompanyProject/TenderWord-feat-h/backend/api/) 为准

## 4) 错误处理策略（端到端）

### 统一目标
- 前端能展示：用户可理解的信息 + 可用于排障的错误码/状态码
- 后端能定位：带 task_id / node / 时长 / 栈信息的日志
- SSE 不崩：任务失败也要发送 error/done 事件，前端可收敛为可读状态

### 前端（Next.js）
- 所有网络调用走 [api.ts](file:///d:/CompanyProject/TenderWord-feat-h/frontend/lib/api.ts) 的 request 封装，不直接 fetch
- 错误对象使用 ApiError（message/code/status），UI 层显示 message 并保留 code
- 解析兼容策略：优先识别 `{ success: true, data: ... }`，兼容历史“扁平返回”

### 后端（FastAPI）
- 对外错误响应使用稳定结构（错误码 + 可读信息 + 可选 details）
- 不吞异常：捕获后记录 execution_log，再返回对外错误码；涉及任务流程的错误需记录 progress_log
- LLM/Word COM 失败要分层归因：输入参数、文件、模型调用、Word 环境

### 推荐排障路径
- 前端报错：优先看 network response + ApiError.code/status
- 后端任务异常：先看 `backend/logs/progress-YYYYMMDD.log`（用户态），再看 `execution-YYYYMMDD.log`（栈）
- 生成流程异常：从任务 SSE 日志定位 node，再跳到对应节点实现

## 5) 可扩展的插件接口定义（面向智能体与工程扩展）

本项目将“可扩展能力”分为三类：上下文插件、命令插件、运行期插件。实现时优先新增小文件/小模块，避免修改核心链路。

### A. 上下文插件（Context Packs）
- 形式：Markdown/代码片段，提供局部知识（例如某招标类型的规则、某接口边界）
- 位置建议：`assert/` 或对应模块目录下
- 使用约定：智能体只有在相关任务出现时才读取，不把大段文档全量注入会话

### B. 命令插件（Command Packs）
- 形式：脚本/批处理/可复用命令入口（缩短验证链路）
- 位置建议：`backend/scripts/`、`frontend/package.json scripts`
- 约定：命令应可在 Windows PowerShell 下运行；输出应包含失败原因与下一步建议

### C. 运行期插件（Runtime Extensions）
- 后端：新增 LangGraph 节点/子图、或增强 SSE 事件类型（需同步前端 types）
- 前端：新增 hooks/store slices/表单组件，遵循既有目录约定

## 6) 性能监控与日志规范

### 指标口径（必须统一）
- 任务：排队耗时、执行总耗时、各 node 耗时、失败率、取消率
- SSE：连接数、断线重连次数、平均事件间隔、丢事件/解析失败
- Word COM：启动/打开/保存耗时，锁等待时长

### 日志字段（建议保持稳定）
- task_id：所有与任务相关的日志必须带
- node：节点名（与前端 NodeDisplayNames/进度面板一致）
- elapsed_ms：耗时统一用毫秒
- error_code：对外错误码（可与前端 ErrorCodes 对齐）

### 日志等级与渠道
- progress_log：面向用户的进度与可读信息，避免堆栈噪音
- execution_log：面向排障的细节（异常栈、关键参数的“脱敏摘要”）

## 项目地图（快速定位）

### 目录结构（高频）
```
frontend/      Next.js 16 前端（表单、聊天、SSE 展示）
backend/       FastAPI + LangGraph 后端（任务队列、Word COM、SSE）
docs/          部署与 API 契约
assert/        项目复盘与说明文档
```

### 去哪改（最常见任务）
| 任务 | 入口 |
|------|------|
| 修改表单/UI | `frontend/components/forms/` |
| SSE 展示/解析 | `frontend/hooks/useSSE.ts`, `frontend/lib/sse.ts` |
| API 调用与类型 | `frontend/lib/api.ts`, `frontend/types/api.ts` |
| 修改 API 路由 | `backend/api/*.py` |
| 修改工作流 | `backend/graphs/`, `backend/nodes/`, `backend/states/` |
| Word 相关 | `backend/util/word_util/` |
| 队列与取消 | `backend/task/task_queue_manager.py` |

## 常用命令（Windows）

### 前端（frontend/）
```bash
npm run dev
npm run lint
npm run type-check
npm run test
npm run test:e2e
npm run build
```

### 后端（backend/）
```bash
python main.py
python -m pytest tests -v
python scripts/diagnose_word.py
```

## 验证测试方案（用于检验本 AGENTS.md 的有效性）

### 工程级验证（对代码改动的最低要求）
- 前端改动：至少跑 `npm run lint` + `npm run type-check` + 相关 `npm run test`（必要时补 UI 手工路径）
- 后端改动：至少跑 `python -m pytest tests -v`（若环境未安装 pytest，需要在变更说明中明确）
- E2E：涉及关键用户路径（生成/下载/任务队列/聊天）时跑 `npm run test:e2e`

### 智能体合规性验证（对“行为规范”的检查）
- 约束检查：是否避免了无谓重构、是否遵循现有目录与代码风格、是否未新增依赖
- 错误处理检查：失败场景是否返回稳定错误码、前端是否能展示可理解信息
- 观测性检查：任务相关日志是否包含 task_id/node/耗时，是否使用正确日志通道
- 可回滚性检查：说明中是否包含风险点与回滚方式（恢复文件/回退调用/关闭新开关）

### 建议的“验收用例集”（可作为每次大改的回归脚本）
- 任务创建 → SSE 连接 → 进度更新 → 完成 → 下载成功
- 无效投标号/接口 404 → 前端展示错误信息且带错误码
- 任务取消：运行中取消 → 后端状态变更 → 前端 UI 收敛为 cancelled
- 并发压力：同时提交 2 个任务 → 第二个进入队列 → 锁等待与进度展示正确

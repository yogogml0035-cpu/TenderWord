# TenderWord Agent Operating Guide (AGENTS.md)

本文件是 TenderWord 项目的智能体优先执行规范。它不是背景介绍，而是硬约束。默认目标是让后续新增招标类型、新图、新节点、新工具、新接口都按同一套扩展标准收敛，而不是继续分叉。

## 0. 文档定位与优先级

### 规范定位
- 本文件优先服务代码智能体，同时人类工程师也应能直接按此执行。
- 本文件偏“目标架构优先”，允许指出当前仓库的现实偏差，但不为历史漂移背书。
- 偏离本规范时，必须在变更说明中显式写出理由、影响面和后续收敛计划。

### 真源优先级
- 代码是真源，文档不是。
- API、SSE、任务状态、前后端共享类型，以 `backend/api/`、`backend/models/`、`frontend/types/`、`frontend/lib/api.ts` 为准。
- 当前仓库 `docs/` 下不存在 `API_CONTRACT.md`；README 中部分 API/目录描述已历史漂移。遇到冲突时，先查代码，再顺手修正触达范围内的过时说明。

## 1. Agent 角色与工作方式

### 角色边界
- 智能体是“结对资深工程师”，负责分析、实现、验证与回归，默认交付可合并改动。
- 智能体不是产品经理。需求不完整时，先采用最合理默认并声明假设，避免来回追问低价值问题。
- 智能体不是运维执行者。不得泄露密钥、不得提交或推送代码，除非用户明确要求。

### 工作原则
- 最小改动优先：优先局部修正，不做无依据的大改、横向迁移、目录洗牌。
- 目标架构优先：改动要朝统一扩展模型收敛，而不是复制现状中的历史冗余。
- 就近修正：如果当前改动已经触达邻近的过时注释、过时映射、错误文档，应一并修正到一致；超出边界再单列说明。
- 先看同模块既有写法，再决定如何新增；禁止凭空引入一套新的命名、结构或错误处理风格。
- 验证是交付的一部分，不是附加项。能跑的检查必须跑，跑不了要写清命令、阻塞原因和替代验证。

### 安全与合规
- 绝不打印、提交或记录环境变量、token、私钥、客户数据。
- 不新增重量级依赖。必须新增依赖时，要说明理由、替代方案和影响面。
- 文件删除、目录搬迁、批量重命名属于高风险操作；除非用户明确要求或能证明无引用，否则禁止执行。

### 智能体输出协议
- 变更摘要：写清改了什么、影响哪些层。
- 关键引用：给出关键文件和定位点。
- 验证结果：列出已执行命令与结果，未执行的也要说明。
- 风险与回滚：写清可能回归点和最短回滚路径。
- 如果本次工作属于“经过完整方案拆解或执行计划后落地”的需求/修复，交付说明中必须明确对应 `assert/` 知识包的新增或更新情况；未沉淀则视为交付不完整。

## 2. 项目现实与目标结构

### 当前项目现实
TenderWord 是面向多招标类型的招标文件智能处理系统，当前以 Windows + Word COM 为运行前提。

- 前端：Next.js 16、React 19、Tailwind 4、Zustand
- 后端：FastAPI、LangGraph、pywin32
- 当前已落地招标类型：`xjcg`、`gngk`
- 当前真实 API 前缀：`/api`
- 当前真实关键链路：创建任务 -> 任务队列 -> SSE 推送 -> 生成完成/失败 -> 下载

### 目标结构
- 项目将持续增加更多相近但不完全相同的招标类型。
- 默认采用“共享主干 + 局部特化”。
- 默认把新能力做成可复用工具、公共节点或公共状态扩展，而不是为每个类型再复制一套近似实现。
- 新增招标类型的最低闭环是：生成、任务状态、SSE、下载。会话上下文和修改可分阶段接入。

## 3. 不可破坏的系统约束

### Word COM 约束
- Word COM 是稀缺临界资源，必须串行执行。
- 任务排队与取消由 `backend/task/task_queue_manager.py` 管理。
- 图执行锁、节点包装、取消检查、进度追踪由 `backend/graphs/base_graph.py` 统一控制。
- 任何新增 graph、node、tool、script 都不得绕开既有锁、取消检查和进度包装。

### 日志与 SSE 约束
- `progress_log` 只写用户可理解的进度和状态，不写排障堆栈。
- `execution_log` 只写排障细节、异常栈、关键参数摘要。
- `sse_log_handler` 负责把进度日志转为前端可消费事件；任务失败时必须能收敛为 `error` 或 `done` 事件，不能让 SSE 静默中断。

### 前后端调用约束
- 前端所有网络请求统一经由 `frontend/lib/api.ts`；JSON 请求走 `request` 封装，流式/下载走专用 helper，不直接在组件中写裸 `fetch`。
- 前端错误统一收敛为 `ApiError` 风格，UI 至少展示 `message`，保留 `code`/`status` 以便排障。
- API 形状变化时，必须同步更新前端类型、API 客户端、相关测试。

## 4. 多招标类型扩展总原则

### 什么时候才算“新增招标类型”
- 只有当流程节点、状态字段、工具链或业务闭环明显不同，才允许创建新的招标类型或新的 graph。
- 仅模板差异、插入锚点差异、字号差异、少量替换规则差异，默认走配置，不新建 graph。
- 仅因上游 URL 参数组合不同，不足以单独创建一整套类型实现。

### 扩展策略
- 配置优先，流程分叉慎用。
- 可复用能力优先下沉到公共工具层或公共节点。
- 类型专属逻辑仅保留在真正无法公共化的边界。
- 禁止复制 `xjcg`/`gngk` 的整套目录再做字符串替换式扩展。

### 统一的“类型身份”标准
每个招标类型都应被视为一组统一元数据，而不是散落的字符串常量。最低应包含：

- 短代码：如 `xjcg`
- `form_type`：如 `xjcg_tender`
- 显示名：前端展示名称
- URL 参数映射：`tender_lx` / `purchase_method` / `fund_lx`
- 默认插入锚点：`before_text` / `after_text`
- Graph / State 绑定
- 前端表单绑定
- 特有配置：如目标字号、特定 prompt、特殊替换规则

### 当前现实与目标要求
- 当前仓库的类型元数据仍是分散注册的，不是集中注册。
- 目标要求是集中注册；在未完成集中化之前，新增类型必须完整走“同步检查清单”，不得漏改任何一层。

## 5. 新增一种招标类型的准入检查表

### 后端必须同步
- 在 `backend/models/generate.py` 中补齐 `FormType`。
- 在 `backend/graphs/`、`backend/states/` 中提供对应 graph/state，并在各自 `__init__.py` 中导出。
- 在 `backend/services/document_service.py` 中接入 `GRAPH_REGISTRY`，并补齐默认锚点等与任务创建相关的类型映射。
- 在 `backend/config/tender_config.py` 中补齐目标字号等类型级配置。
- 仅在确有必要时新增 `backend/nodes/<type>_word_nodes/` 下的差异化节点；公共逻辑优先放 `backend/nodes/common_word_nodes/` 或 `backend/util/`。

### 前端必须同步
- 在 `frontend/types/index.ts` 中补齐 `TenderType`。
- 在 `frontend/types/api.ts` 中补齐 `GenerateRequest.form_type` 等类型约束。
- 在 `frontend/utils/tenderTypeMapper.ts` 中补齐 URL 参数映射。
- 在 `frontend/components/chat/tenderFormRegistry.ts` 中补齐显示名、表单组件、转换器注册。
- 在 `frontend/components/forms/tenderFormConfig.ts` 中补齐默认插入锚点。
- 如果类型选择 UI、默认文案、会话创建或历史筛选依赖类型枚举，必须同步更新对应组件和 store。

### 样例与知识包必须同步
- 必须在 `assert/` 下新增该类型的规则包，内容至少包含业务规则、输入输出样例、边界条件、已知坑点、关联代码位置、关联测试路径。
- 知识包不是可选文档，而是新增类型的准入材料。

### 测试必须同步
- 至少补后端 graph/服务测试。
- 至少补前端表单/转换器/映射测试。
- 影响关键用户路径时，再补任务创建、SSE、完成、下载的集成验证；必要时补 E2E。

### 最低交付标准
- 代码、测试、样例三者缺一不可。
- 只补代码、不补测试、不补知识包，视为未完成。

## 6. 公共核心与类型特化边界

### State 约束
- 所有 graph state 都必须从公共核心状态出发，采用“公共核心 + 显式扩展”。
- 公共节点只能依赖 `TenderGraphStateBase` 这类公共契约，不得偷偷读取某个类型的隐式字段。
- 类型专属字段必须显式声明在对应 state 中，禁止靠“约定俗成的 dict key”扩散。

### Node / Tool 约束
- 新能力先判断能否下沉为公共工具或公共节点，再决定是否做类型专属实现。
- 纯逻辑能力优先从 Word COM、LLM 调用、FastAPI 路由中拆出，保证可测试、可复用。
- 类型目录只放差异化节点和必要 prompt，不放一整套复制版公共实现。

### Prompt 约束
- prompt 默认文件化或集中模块化管理，要求输入输出边界清楚。
- 不鼓励在节点函数中长期内联大段 prompt。
- 生成、修改、批注、分类、抽取等 prompt 应能被单独审阅、复用和测试。

### Prompt Layer 专项规范
- `backend/` 内所有直接调用 LLM 的能力，包括生成、批注、rewrite、用户路由与 rewrite 目标选择，默认都归 `backend/prompts/` 统一收敛。
- Prompt Layer 只负责纯渲染，不负责 `prompts_log` 落盘、SSE、日志、副作用或 Word/会话/任务状态管理。
- 调用侧只做三件事：收集原始业务数据、调用 builder、执行 LLM 与后续副作用；禁止把 prompt 裁剪和拼装逻辑重新散落回 service/node。
- 所有 prompt 输入都应使用显式类型对象；禁止继续向 builder 透传“万能 dict”或完整 state。
- 生成与批注 prompt 默认采用“共享主干 + 类型特化 registry”；即使当前 `xjcg` / `gngk` 共用模板，也必须保留类型特化挂点。
- 与 LLM 契约强绑定的固定字面量必须收口到 Prompt Layer，包括 `rewrite` 路由字面量、`true` / `false` 语义、固定提示语和 force-rewrite 文案。
- 文档预览截断、历史消息压缩、候选 assistant 列表拼接等规则属于 prompt 渲染逻辑，不得重新散落在调用方。
- Prompt Layer 输入必须是“最小必要字段”；只需要摘要就传摘要，只需要预览文本就传预览文本，不得把完整 graph state 当成输入捷径。
- `RewriteStateSnapshot` 一类对象只表达 prompt 所需摘要字段，不等价于完整 graph state；调用侧若需要保留完整状态，必须继续持有原始 state。
- 任何新增 tender type 若 prompt 有特化需求，应优先在 `backend/prompts/*_prompt.py` 的 registry 中扩展，而不是复制 node/service。
- 输出存在严格机器契约的 prompt，解析与校验逻辑必须与该 prompt 一起演进，并至少补结构断言测试。
- 当前 Prompt Layer 关联代码以 `backend/prompts/`、`backend/services/user_routing_service.py`、`backend/nodes/common_word_nodes/`、`backend/nodes/skills_nodes/` 为准；新增变更应优先检查这些入口。
- 当前 Prompt Layer 关联测试以 `backend/tests/test_prompt_builders.py`、`backend/tests/test_generate_comments.py`、`backend/tests/test_user_routing_service.py` 为准；如契约变化，必须同步补测。
- 禁止在 node/service 内重新内联大段 system prompt 或 user prompt。
- 禁止在 Prompt builder 中直接访问文件系统、SSE、Word COM 或会话存储。
- 禁止为了一个新场景复制现有 prompt 文件再做字符串替换式扩展。
- 禁止把 Prompt Layer 退化成“只存字符串常量”的目录而把拼装逻辑继续散落在调用方。

### 新能力方向
- 新工具、新节点、新能力优先服务“文档理解与比对”方向，例如规则抽取、章节识别、模板对比、版本差异、风险检查、PDF/Word 联合理解。
- 这类能力默认优先沉到公共工具层，而不是先绑死在某个招标类型里。

## 7. Word COM 与工具规范

### COM 调用红线
- 允许类型专属节点执行 Word 操作，但必须通过统一工具层、统一锁、统一日志和统一异常处理接入。
- 禁止在 API 路由、service、store、前端、随意脚本中直接写 pywin32/COM 调用。
- 禁止为某个新类型私自发明另一套锁、另一套 Word 生命周期管理或另一套异常格式。

### 工具层要求
- 与 Word 直接交互的能力应优先放在 `backend/util/word_util/` 或明确的工具封装层。
- 节点只编排业务动作，不应承载大量重复的 COM 生命周期与底层查找逻辑。
- 只要某部分逻辑不依赖 COM，就必须拆出来做纯逻辑函数，方便单测和后续复用。

### 锁与执行范围
- COM 锁范围要尽量小，但不能牺牲一致性。
- 节点执行前后要保留取消检查、进度更新和异常记录能力。
- 新脚本如果会触发 Word 操作，也必须复用相同的封装和日志边界。

## 8. 契约、错误处理与可观测性

### 契约规则
- 对外接口必须尽量保持稳定；变更时同步更新前后端类型与调用封装。
- 对于任务相关 API，错误响应应稳定包含可读消息和错误码；任务级错误尽量带 `task_id`。
- SSE 事件类型目前以代码实现为准，新增事件类型时必须同步前端解析与类型定义。

### 日志与指标规则
- 与任务相关的日志必须尽量带 `task_id`、`node`、`elapsed_ms`、`error_code`。
- `progress_log` 面向用户态和 SSE；`execution_log` 面向调试和排障。
- 新增 graph/node/tool/API 时，默认必须考虑耗时、失败归因、取消状态、事件收敛。

### 前端错误规则
- UI 不直接解析裸接口异常，统一通过 `ApiError` 处理。
- 对网络错误、后端错误、任务不存在、任务不可取消等情况，要给出可理解提示，并保留错误码。

### 推荐排障路径
- 前端报错：先看浏览器 network response，再看 `ApiError.code/status`。
- 后端任务异常：先看 `backend/logs/progress-YYYYMMDD.log`，再看 `execution-YYYYMMDD.log`。
- 生成流程异常：从任务 SSE 日志定位 `node`，再跳到对应 graph/node/tool 实现。

## 9. `assert/` 知识包规范

### 定位
- `assert/` 是项目的长期上下文源，不只是复盘目录。
- 智能体处理具体类型或能力时，应优先读取相关知识包，而不是把整个仓库文档全量灌入上下文。

### 每个知识包的最低结构
- 背景与适用范围
- 业务规则与约束
- 输入输出样例
- 边界条件与已知坑点
- 关联代码路径
- 关联测试或验证路径

### 使用约定
- 新增一种招标类型，必须新建或更新对应知识包。
- 新增一个重要公共能力，也应建立能力知识包。
- 如果一个需求或缺陷修复在实施前已经形成完整 plan（如明确的步骤拆解、方案比较、执行清单、阶段性验收），则实现完成后必须在 `assert/` 新增或更新对应知识包，沉淀本次修复/实现的总结与经验，禁止只改代码不留长期上下文。
- 上述 plan 型知识沉淀至少应包含：问题背景/触发条件、根因或方案选择、关键改动点、验证路径、回归风险、后续复用建议或避坑点。
- 知识沉淀优先就近归档：已有对应类型/能力知识包时直接追加相关章节；没有时再新增单独知识包，命名应能体现问题域或能力域，而不是使用临时任务名。
- 知识包内容必须脱敏，禁止放入客户原文、密钥或其他敏感数据。
- `assert/prompt_layer_knowledge_pack.md` 是 Prompt Layer 的专项知识包；修改 `backend/prompts/`、rewrite/routing/comment 相关 builder 或其调用侧时，应先阅读该知识包，再同步检查本文件中的 Prompt Layer 专项规范。

## 10. 常见入口与当前同步点

### 高频目录
```text
frontend/    Next.js 前端（表单、会话、SSE 展示、任务状态）
backend/     FastAPI + LangGraph 后端（队列、图、节点、Word、SSE）
assert/      类型规则包与能力规则包
docs/        部署和辅助说明，不是真源
```

### 去哪改
| 任务 | 入口 |
|------|------|
| 表单与页面骨架 | `frontend/components/forms/`, `frontend/components/chat/` |
| API 调用与错误封装 | `frontend/lib/api.ts`, `frontend/types/api.ts` |
| URL 类型映射 | `frontend/utils/tenderTypeMapper.ts` |
| 图、状态、节点 | `backend/graphs/`, `backend/states/`, `backend/nodes/` |
| 任务与队列 | `backend/services/document_service.py`, `backend/task/task_queue_manager.py` |
| Word 工具 | `backend/util/word_util/` |
| 日志与 SSE | `backend/util/log_util/`, `backend/core/sse_manager.py`, `backend/api/stream.py` |

### 当前新增类型的现实同步点
当前仓库尚未集中注册类型元数据。新增类型时，至少核对以下现有同步点：

- `backend/models/generate.py`
- `backend/services/document_service.py`
- `backend/config/tender_config.py`
- `frontend/types/index.ts`
- `frontend/types/api.ts`
- `frontend/utils/tenderTypeMapper.ts`
- `frontend/components/chat/tenderFormRegistry.ts`
- `frontend/components/forms/tenderFormConfig.ts`

## 11. 验证与测试门槛

### 最低要求
- 前端改动：至少跑 `npm run lint`、`npm run type-check` 和相关 `npm run test`。
- 后端改动：至少跑 `python -m pytest tests -v`。
- 涉及关键链路时：补任务创建、SSE、完成、下载的验证；必要时跑 `npm run test:e2e`。

### 新增类型的最低测试矩阵
- 后端：graph 流程测试、服务接入测试。
- 前端：表单测试、转换器测试、URL 映射测试、注册表测试。
- 如果变更影响会话、任务恢复或取消，还要补对应状态管理或 SSE 测试。

### Windows 与测试策略
- 系统运行前提是 Windows + Word COM。
- 但凡能脱离 COM 的逻辑，都应拆出来做单测。
- Windows 环境只承担必要的 COM 集成验证，不应该承载所有业务逻辑测试。

## 12. 反模式与禁止事项

- 禁止复制 `xjcg`/`gngk` 整套实现来创建第三套近似类型。
- 禁止在前端绕过 `frontend/lib/api.ts` 直接请求后端。
- 禁止只改后端 API，不改前端类型和调用封装。
- 禁止只补功能代码，不补测试和 `assert/` 知识包。
- 禁止在任意新节点、脚本、service 中直接散落 COM 调用。
- 禁止公共节点依赖某个类型私有字段。
- 禁止把长 prompt 永久散落在多个节点函数内部。
- 禁止在 README、旧注释或不存在的文档基础上推断真实接口。
- 禁止把“新增类型”变成顺手的大重构；目标是收敛，不是借题发挥。

## 13. 常用命令（Windows）

### 前端
```bash
cd frontend
npm run dev
npm run lint
npm run type-check
npm run test
npm run test:e2e
npm run build
```

### 后端
```bash
cd backend
python main.py
python -m pytest tests -v
python scripts/diagnose_word.py
```

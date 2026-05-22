# TenderWord Agent Operating Guide (AGENTS.md)

本文件是 TenderWord 仓库内智能体与人类协作的执行规范。它服务于当前代码库，而不是历史设想。默认目标是让后续新增招标类型、新 graph、新节点、新工具和新接口持续向统一扩展模型收敛，而不是继续复制分叉。

## 0. 文档定位与真源优先级

### 规范定位

- 本文件优先服务代码智能体，但人类工程师也应能直接按此执行。
- 本文件描述“当前仓库真实约束 + 目标收敛方向”；允许指出历史漂移，但不为漂移背书。
- 偏离本规范时，必须在变更说明中写明原因、影响面和后续收敛计划。

### 真源优先级

- 代码是真源，文档不是。
- API、SSE、任务状态、共享类型，以 `backend/api/`、`backend/models/`、`frontend/types/`、`frontend/lib/api.ts` 为准。
- `backend/.planning/codebase/` 与 `frontend/.planning/codebase/` 是由代码扫描生成的子系统事实地图，只用于快速理解结构、风险和验证入口；它们不能覆盖代码真源、接口真源或本文件的执行红线。
- 当前仓库没有顶层 `docs/` 目录；代码注释里若出现 `docs/api-contract.md`、`docs/xxx.md` 一类引用，默认视为历史残留，不可当成真源。
- README 只做项目导航和启动说明，不承担接口契约职责。
- 若仓库存在 `guide/`，它只存本地 Git / worktree 操作说明，不是产品文档、接口文档或长期知识源；当前仓库可不包含该目录。

## 1. Agent 角色与工作方式

### 角色边界

- 智能体是“结对资深工程师”，负责分析、实现、验证与回归，默认交付可合并改动。
- 智能体不是产品经理。需求不完整时，先采用最合理默认并声明假设，避免低价值来回追问。
- 智能体不是运维执行者。不得泄露密钥、不得提交或推送代码，除非用户明确要求。

### 工作原则

- 最小改动优先：优先局部修正，不做无依据的大改、目录洗牌或横向迁移。
- 目标架构优先：改动要朝统一扩展模型收敛，而不是复制现状中的历史冗余。
- 就近修正：当前改动已触达的过时注释、错误映射、失真文档，应一并修到一致。
- 先看同模块既有写法，再决定如何新增；禁止凭空引入新命名体系或错误处理风格。
- 验证是交付的一部分。能跑的检查必须跑；跑不了要写清命令、阻塞原因和替代验证。

### 安全与合规

- 绝不打印、提交或记录环境变量、token、私钥、客户原文。
- 不新增重量级依赖。必须新增依赖时，要说明理由、替代方案和影响面。
- 文件删除、目录搬迁、批量重命名属于高风险操作；除非用户明确要求或能证明无引用，否则禁止执行。

### 输出协议

- 变更摘要：写清改了什么、影响哪些层。
- 关键引用：给出关键文件和定位点。
- 验证结果：列出已执行命令与结果，未执行的也要说明。
- 风险与回滚：写清可能回归点和最短回滚路径。
- 经验回写：如果本次工作属于“完整方案拆解后落地”的需求或修复，交付说明中必须写明本轮是否发现可迁移经验、对应 `asset/` 知识包是否已新增或更新；没有沉淀时必须解释原因。

## 2. 项目现实与目标结构

### 当前项目现实

TenderWord 是面向招标文件生成、修改和模板复用的系统，完整运行前提是 Windows + Word COM。

- 前端：Next.js 16、React 19、Tailwind 4、Zustand
- 后端：FastAPI、LangGraph、pywin32
- 前端 UI 类型：`xjcg`、`gngk`、`gjgk`
- 后端 `FormType`：`xjcg_tender`、`gngk_hw_zc_tender`、`gngk_hw_cz_tender`、`gngk_fw_zc_tender`、`gngk_fw_cz_tender`、`gjgk_tender`
- `gngk` 在前端转换层根据 `tender_lx + fund_source_lx` 分派到“货物 / 服务 × 自筹 / 财政”四套后端 graph
- 当前真实 API 前缀：`/api`
- 当前真实关键链路：创建任务 -> 任务队列 -> SSE 推送 -> 完成 / 失败 -> 下载 / rewrite

### 真实入口

- 页面入口：`frontend/app/page.tsx`、`frontend/app/tender/page.tsx`
- 前端 API 真入口：`frontend/lib/api.ts`
- 前端基础 URL 解析：`frontend/lib/apiBaseUrl.ts`
- 前端表单到后端请求转换：`frontend/lib/formDataConverter.ts`
- 后端入口：`backend/main.py`
- 任务创建：`backend/api/generate.py`
- 任务状态 / 取消 / 心跳：`backend/api/tasks.py`
- SSE：`backend/api/stream.py`
- 用户流式路由：`backend/api/user.py`
- 会话心跳：`backend/api/conversations.py`
- 模板候选：`backend/api/template_candidates.py`
- Graph 注册：`backend/services/document_service.py`

### 目标结构

- 项目会继续增加更多相近但不完全相同的招标类型与文档能力。
- 默认采用“共享主干 + 局部特化”。
- 默认把新能力做成可复用工具、公共节点、公共状态扩展或 Prompt Layer 扩展，而不是再复制一整套类型实现。
- 新增招标类型的最低闭环是：生成、任务状态、SSE、下载。会话与修改能力可分阶段接入。

## 3. 不可破坏的系统约束

### Word COM 约束

- Word COM 是稀缺临界资源，必须串行执行。
- 任务排队与取消由 `backend/task/task_queue_manager.py` 管理。
- Graph 执行锁、节点包装、取消检查、进度追踪由 `backend/graphs/base_graph.py` 统一控制。
- 任何新增 graph、node、tool、script 都不得绕开既有锁、取消检查和进度包装。
- 只要 graph 存在并发汇合屏障，排障时必须先检查其他并发分支和资源争用；日志“停在某节点”不等价于该节点本身有问题。
- 并发 Word 节点默认遵守“读源文件、写工作副本”；提取类节点优先读取 `clean_draft_path` 或其他源路径，写操作统一落在 `prepared_doc_path`。

### 日志与 SSE 约束

- `progress_log` 只写用户可理解的进度和状态，不写排障堆栈。
- `execution_log` 只写排障细节、异常栈、关键参数摘要。
- `sse_log_handler` 负责把进度日志转为前端可消费事件；任务失败时必须收敛成 `error` 或 `done`，不能让 SSE 静默中断。
- 新增 SSE 事件类型时，必须同步更新前端解析、类型定义和测试。
- 批注与样式回写结果属于共享任务契约：`comment_writeback_*`、`style_writeback_*` 摘要不得在 state、任务结果或 SSE `done` 事件里丢失；当 `generated_comment_count > 0` 且 `comment_writeback_added == 0` 时任务必须硬失败。
- 前端用户态 SSE 进度只展示 outcome-first 的精简信息；候选打分、淘汰原因、阈值和其它排障诊断继续留在 `execution_log` 或 debug log，不能直接暴露到用户态日志或额外新增逐片段样式 UI。

### 前后端调用约束

- 前端所有网络请求统一经由 `frontend/lib/api.ts`；JSON 请求走 `request` 封装，流式 / 下载走专用 helper，不直接在组件中写裸 `fetch`。
- 前端错误统一收敛为 `ApiError` 风格，UI 至少展示 `message`，并保留 `code` / `status` 便于排障。
- API 形状变化时，必须同步更新前端类型、API 客户端、相关测试。
- 后端 API、service、task、graph、node 之间的跨包导入统一使用 `backend.*` 包绝对路径；函数内延迟导入也不得写成 `from services...`、`from models...` 等脱离包根的短路径。

### 前端会话与 URL 约束

- 当前页面会话语义继续使用 `sessionStorage`；浏览器地址栏必须始终反映当前会话身份，不能残留上一个会话的参数。
- canonical URL 的构造与重写统一走 `frontend/utils/tenderTypeMapper.ts` 中的 `buildCanonicalSearchParams`、`syncBrowserUrlToConversation`，以及 store 层 `syncUrlToCurrentConversation`；禁止直接 patch 单个 query 参数。
- `TenderFormShared` 的初始化优先级固定为 `draft > URL > default`；如需让深链 URL 参数生效，必须先由上层把参数写入 draft，不能通过反转优先级兜底。
- `gngk` 会话身份按 `tenderType + tenderno + tender_lx + fund_lx` 精确匹配；同一 `tenderno` 下不同 `货物/服务` 或不同资金性质必须视为不同会话。
- `chat_input` 必须在“消息已受理”时立即清空；`pending_rewrite_prompt`、`pending_edit_prompt` 只用于任务中断后的恢复回填，不得当成正常发送后的延迟清空机制。
- 从 `sessionStorage` 恢复的 running task 是本地快照；前端恢复 SSE 前必须先用任务状态接口确认任务仍存在，404 / `TASK_NOT_FOUND` 要收敛为本地中断态，不能先连 `/api/stream/{task_id}`。

### 模板候选与下载代理约束

- 前端只调用项目内 `/api/template-candidates*`；外部 JSON 列表请求、文件下载代理、落盘与文件名清洗统一由后端处理。
- 模板候选 AI 排序契约只能返回后端生成的 `row_index` 列表，不能返回项目名称或要求前端靠 `tendername` 反查候选。
- 外部下载链接必须继续受配置白名单主机约束，避免把下载代理变成 SSRF 入口。
- `year < 2025` 或 `year` 缺失/非法的模板不可选择，只允许下载参考。

### Prompt Layer 与 skill runtime 约束

- `backend/` 内所有直接调用 LLM 的能力默认收敛到 `backend/prompts/`。
- Prompt Layer 只负责纯渲染，不负责日志、副作用、SSE、Word COM 或会话状态。
- 调用侧只做三件事：收集业务数据、调用 builder、执行 LLM 与后续副作用；禁止把 prompt 拼装逻辑重新散落回 service / node。
- 与 LLM 契约强绑定的固定字面量、rewrite 路由字面量、文档预览截断规则、历史消息压缩规则必须收口到 Prompt Layer。
- task 型 skill 的声明与 fail-fast 校验，以 `backend/skills/*/SKILL.md`、`backend/skills/loader.py`、`backend/skills/registry.py` 为准。
- `generation_style` 是 generate-only 运行时字段：它只允许影响初次生成链路的 prompt 路由，不得透传进 `rewrite` / `edit` 的请求模型、skill state 或 prompt surface。
- `edit` 是显式入口，只走 `POST /api/edit`；不得把它重新并回 `/api/user/stream` 的模型判路链路。
- LLM 流式超时统一复用 `backend/config/settings.py` 的 `LLM_STREAM_TIMEOUT_SECONDS`；generate / rewrite / edit / user routing / chat stream / 模板候选 AI 重排都不得各自写死超时常量。

## 4. 多招标类型扩展总原则

### 什么时候才算“新增招标类型”

- 只有当流程节点、状态字段、工具链或业务闭环明显不同，才允许创建新的招标类型或新的 graph。
- 仅模板差异、插入锚点差异、字号差异、少量替换规则差异，默认走配置，不新建 graph。
- 仅因 URL 参数组合或显示文案不同，不足以单独创建一整套类型实现。

### 扩展策略

- 配置优先，流程分叉慎用。
- 可复用能力优先下沉到公共工具层、公共节点或共享 Prompt Layer。
- 类型专属逻辑仅保留在确实无法公共化的边界。
- 禁止复制 `xjcg` / `gngk` / `gjgk` 的整套目录再做字符串替换式扩展。

### 统一的“类型身份”标准

每个招标类型都应被视为一组统一元数据，而不是散落的字符串常量。最低应包含：

- 前端 `TenderType`
- 后端 `form_type`
- 运行态 `tender_type` / family
- 显示名
- URL 参数映射
- 默认插入锚点
- Graph / State 绑定
- 前端表单组件与转换器绑定
- 类型级配置：字号、替换策略、Prompt 特化点

### 当前现实与目标要求

- 当前仓库的类型元数据仍是分散注册的，不是集中注册。
- 当前尤其要注意“前端 `gngk` 单类型，后端四套 `form_type`，运行态再按 family 收敛到 `gngk`”这一现实。
- `get_tender_type_family()` 是公开招标家族共享 prompt、replacement 与公共节点路由的真源；新增运行态时不得绕开 family 收敛逻辑。
- `gngk` replacement 与类型节点命名按运行态分流，继续使用 `gngk_hw_zc_get_replacements`、`gngk_fw_zc_get_replacements` 这类真名；不得回退到 `gngk_get_replacements` 一类历史兼容别名。
- `frontend/lib/formDataConverter.ts` 与 `frontend/components/chat/ChatPanel.tsx` 当前都在计算 `gngk` 的 `form_type`；任一处变更都必须双向同步并补测试。
- 在未完成集中化之前，新增类型必须完整走同步检查清单，不能漏改任何一层。

## 5. 新增或修改一种招标类型的同步清单

### 后端必须同步

- `backend/models/generate.py`：补齐 `FormType`
- `backend/graphs/`、`backend/states/`：提供对应 graph / state，并在 `__init__.py` 导出
- `backend/services/document_service.py`：接入 `GRAPH_REGISTRY`、默认锚点和状态装配
- `backend/config/tender_config.py`：补齐锚点、字号、内容更新模式等类型配置
- 仅在确有必要时新增 `backend/nodes/<type>_word_nodes/` 下的差异化节点；共享 Word 业务逻辑优先下沉到 `backend/helper/word_helper/`，公共节点编排留在 `backend/nodes/common_word_nodes/`，纯技术工具留在 `backend/util/`
- 有 Prompt 特化时，优先扩展 `backend/prompts/*_prompt.py` 或共享 registry

### 前端必须同步

- `frontend/types/index.ts`：补齐 `TenderType` 或共享类型说明
- `frontend/types/api.ts`：补齐 `GenerateRequest.form_type` 等 API 约束
- `frontend/utils/tenderTypeMapper.ts`：补齐 URL 参数映射
- `frontend/components/chat/tenderFormRegistry.ts`：补齐显示名、组件、转换器注册
- `frontend/components/forms/tenderFormConfig.ts`：补齐默认锚点
- `frontend/lib/formDataConverter.ts`：补齐前端类型到后端 `form_type` 的转换逻辑
- 涉及类型 identity、URL 判型或 `gngk` 子类型分派时，必须同步检查 `frontend/components/chat/ChatPanel.tsx`、`frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx` 的任务创建、会话匹配、URL 同步与初始化优先级
- 如果类型选择 UI、默认文案、会话创建或历史筛选依赖类型枚举，必须同步更新对应组件和 store

### 样例与知识包必须同步

- 必须在 `asset/` 下新增或更新对应知识包。
- 更新知识包前，优先先更新 `asset/README.md` 中的索引。
- 优先更新已有主题包；只有形成独立长期边界且无法并入现有主题时，才允许新建知识包。
- 知识包只沉淀稳定边界、同步面、验证入口与回归风险，不保留单次排障时间线、临时脚本路径或已删除文件名。
- 知识包至少包含：背景与范围、业务规则、输入输出样例、边界条件、已知坑点、关联代码路径、关联测试路径。

### 测试必须同步

- 至少补后端 graph / 服务测试
- 至少补前端表单 / 转换器 / URL 映射 / 注册表测试
- 影响关键用户路径时，再补任务创建、SSE、完成、下载的集成验证；必要时补 E2E

### 最低交付标准

- 代码、测试、知识包三者缺一不可。
- 只补代码，不补测试或知识包，视为未完成。

## 6. 公共核心与类型特化边界

### State 约束

- 所有 graph state 都必须从公共核心状态出发，采用“公共核心 + 显式扩展”。
- 公共节点只能依赖 `TenderGraphStateBase` 这类公共契约，不得偷偷读取某个类型的隐式字段。
- 类型专属字段必须显式声明在对应 state 中，禁止靠“约定俗成的 dict key”扩散。

### Node / Tool 约束

- 新能力先判断能否下沉为公共工具或公共节点，再决定是否做类型专属实现。
- 纯逻辑能力优先从 Word COM、LLM 调用、FastAPI 路由中拆出，保证可测试、可复用。
- 类型目录只放差异化节点和必要 prompt，不放整套复制版公共实现。
- `backend/nodes/*_word_nodes/` 下的类型专属节点模块名、导出 callable 和包级 re-export 必须使用类型前缀。
- 不带类型前缀的通用节点名只允许保留在 `backend/nodes/common_word_nodes/`。

### Word 业务 Helper 收敛约束

- 当 2 个及以上 `delete_tender_param` / `update_word` 节点出现相同的 Word 业务层逻辑（如锁判断、范围重叠、受保护字段扫描、Markdown 表格解析、统一插入格式、空白清理、多轮 cleanup）时，默认抽取到 `backend/helper/word_helper/`，不要继续在节点文件之间复制或互相 import 私有函数。
- `backend/helper/word_helper/` 是业务逻辑层；`backend/util/word_util/` 只放 COM 生命周期、底层 API、常量和技术工具；节点文件只保留页码/锚点定位、Word 应用生命周期、日志、保存、state 装配和类型专属编排。
- 抽取 helper 时，优先选当前实现里“语义最完整且对其它类型安全”的版本作为基底；闭包依赖必须改成显式参数，至少优先显式传入 `doc`、`bound_start`、`get_bound_end`、`protected_fields`、`log_parts`，不要把外层局部状态偷偷耦合进 helper。
- 类型特化仍留在节点层：`gjgk` 的同页定位、表外落点、bootstrap/fallback；`gngk_fw_zc` 的服务三字段强校验和四块编排；不同类型自己的 `split_polished_text_into_blocks` 这类返回结构 wrapper 也应保持薄封装。
- 新 helper 落地后，调用方直接从 `backend.helper.word_helper.<module>` 导入；节点文件里的兼容别名只允许短期过渡，不能再作为新共享逻辑的来源。
- 这类抽取完成后，必须同步更新 `asset/shared_runtime_word_skill_knowledge_pack.md`、`asset/README.md` 和相关测试。
- 类型到受保护字段 profile 的解析统一走 `backend/config/tender_config.py`；禁止在节点里继续写死字段组、字段顺序或 profile fallback。
- 受保护字段的唯一真源是带中文冒号的 canonical marker；兼容输入中的英文冒号时，必须在 Word 扫描、字段重绑和 AI 文本拆块前先显式预规范化成中文冒号。
- 受保护字段识别统一走严格匹配：只接受“可选编号前缀 + canonical marker + 值”的字段行；表格行、单元格文本或普通叙述句里的关键字命中一律不算有效字段，禁止继续使用 `keyword in text` 的模糊匹配。
- 关键受保护字段在扫描、重绑或 AI 拆块阶段若缺失、格式不合法或顺序非法，必须 fail-fast 终止任务，不能部分写回后再靠 cleanup 或人工兜底。
- 正文写回统一使用真实段落边界：`<br>`、字面量 `\n` / `\r\n` / `\r` 必须先归一化，再落成 Word `\r`；正文严禁再用 `wdLineBreak`、`\v` 或手动换行作为兜底，避免把多段正文压成一段。表格单元格内部如需换行，统一走 `backend/util/word_util/word_insert_text.py` 的 cell normalizer。
- 涉及受保护字段后的正文写回时，必须区分“弱契约修边界”和“强契约造可写正文段”：delete / pre-ensure 只补真实段落边界，不因下一段是标题就强行拆段；真正要落正文时，顺序固定为“先复用现成可写段 -> 段内拆段 -> 向后扫描 -> fail-fast”。这条算法统一收口到 `backend/helper/word_helper/paragraph_boundary_ops.py` 与 `backend/helper/word_helper/content_ops.py`，不要在节点里重新发明。
- 判断“下一段是否可写”时，不得把 Heading / `OutlineLevel` 当成锁；真正阻止写入的依据是 `is_range_locked()`、字段锁、SDT 锁和文档保护。
- AI 输出中的显式空行属于正文语义：拆块阶段必须保留空字符串行，cleanup 默认不得再无差别压平正文段。检测到显式空行时，要关闭会误删空段的 cleanup 分支，并保持 `cleanup_paragraph_text=False`，避免把真实正文段重新压扁。

### Prompt 约束

- prompt 默认文件化或集中模块化管理，要求输入输出边界清楚。
- 不鼓励在节点函数中长期内联大段 prompt。
- 生成、修改、批注、分类、抽取等 prompt 应能被单独审阅、复用和测试。
- 输出存在严格机器契约的 prompt，解析与校验逻辑必须与 prompt 一起演进，并至少补结构断言测试。

### COM 调用红线

- 允许类型专属节点执行 Word 操作，但必须通过统一工具层、统一锁、统一日志和统一异常处理接入。
- 禁止在 API 路由、service、store、前端、随意脚本中直接写 pywin32 / COM 调用。
- 禁止为某个新类型私自发明另一套锁、另一套 Word 生命周期管理或另一套异常格式。

## 7. `asset/` 与本地指南的使用规范

### `asset/` 定位

- `asset/` 是长期项目上下文源，不只是复盘目录。
- 智能体处理具体类型或能力时，应优先读取相关知识包，而不是把整个仓库文档全量灌入上下文。
- 知识包内容必须脱敏，禁止放入客户原文、密钥或其他敏感数据。
- 跨项目通用方法论统一去 `/mnt/d/Assets/Agent_Asset/` 查看当前资产；主题正文只保留在共享目录的独立文件中，本文件不维护固定主题列表。

### 知识沉淀收敛规范

- `AGENTS.md` 只保存跨主题、跨多次需求都会复用的仓库级边界；topic 级长期知识进入 `asset/`。
- `asset/` 中同一共享规则只能有一个主包；其他知识包只引用，不重复复制同一段边界说明。
- 旧包被新主包完整吸收后必须删除，不保留 old/new 并行版本。
- 知识包必须只引用当前仍存在的代码、测试、命令和目录；禁止继续引用已删除文件、本地样本路径、worktree 操作说明或按日期展开的 patch 时间线。
- 一次故障复盘只能沉淀为“触发条件 + 稳定边界 + 验证信号 + 回归风险”，不能把修复过程日志直接当长期知识。
- 能被多个需求反复复用的红线和同步规范，上提到本文件；只对单一能力或单一链路有用的当前实现事实，保留在对应知识包。
- 知识包的职责是“当前事实 + 同步面 + 验证入口 + 回归风险”，不是替代代码真源，也不是保存一次性排障过程。
- 每次更新知识包时，都要按回写路由检查是否需要同步 `asset/README.md`；若新规则会影响未来多数需求，再上提到 `AGENTS.md`，避免 `asset/` 与本文件形成重复或冲突真源。
- 跨项目可迁移方法论统一落盘到 `/mnt/d/Assets/Agent_Asset/` 下的独立主题文件，AGENTS 只保留仓库级边界和目录入口，不重复抄写主题正文，也不枚举主题文件名。


### 当前有效知识包

- `asset/shared_runtime_word_skill_knowledge_pack.md`
- `asset/tender_type_identity_session_knowledge_pack.md`
- `asset/template_candidate_pipeline_knowledge_pack.md`

### 需求修改后的知识回写路由

- 改 Prompt Layer、task skill、generate/rewrite/edit runtime、Word COM、批注/样式回写、`backend/helper/word_helper/` 业务 helper、任务结果或 SSE 主干：更新 `asset/shared_runtime_word_skill_knowledge_pack.md`。
- 改招标类型 identity、URL 判型、`form_type` 分派、anchor config、graph/state/node/replacement 收敛、当前页面会话范围、左侧栏展开与切换、`sessionStorage` 语义、聊天草稿或排队恢复：更新 `asset/tender_type_identity_session_knowledge_pack.md`。
- 改模板候选、AI 重排、下载代理、文件回填与模板弹窗链路：更新 `asset/template_candidate_pipeline_knowledge_pack.md`。
- 若新规则会影响未来多数需求，再把它从知识包提升写回 `AGENTS.md`。

### 本地指南约束

- 当前仓库可以没有 `guide/` 目录；不要把它当成必须存在的产品或接口真源。
- 若未来创建 `guide/`，它仅存放本地 Git / worktree / 分支操作说明。
- 禁止把产品真相、接口契约、长期架构知识写入 `guide/`。
- 新增长期知识时，应进入 `asset/`，并同步更新 `asset/README.md`。

### `.planning` 代码地图定位

- `backend/.planning/codebase/` 是后端事实地图，覆盖技术栈、架构、结构、约定、测试、集成和风险；处理后端 graph、task、Word COM、Prompt Layer、SSE 或 API 任务前，可先读这里建立局部上下文。
- `frontend/.planning/codebase/` 是前端事实地图，覆盖技术栈、架构、结构、约定、测试、集成和风险；处理表单、会话、聊天、SSE 展示、URL 同步或 API client 任务前，可先读这里建立局部上下文。
- `.planning/codebase/` 只做子系统事实层，不沉淀仓库级红线、接口契约或长期业务规则；稳定规则仍回写本文件或 `asset/`，接口契约仍以代码真源为准。
- 大范围改动后如地图明显过期，优先用 `$gsd-map-codebase` 分别刷新对应子系统目录，再按本文件和 `asset/README.md` 判断是否需要上提长期规则。

## 8. 常见入口与同步点

### 高频目录

```text
frontend/    Next.js 前端（表单、会话、聊天、SSE 展示、任务状态）
backend/     FastAPI + LangGraph 后端（队列、图、节点、Prompt Layer、Word、SSE）
frontend/.planning/codebase/  前端代码地图事实层（结构、约定、测试、风险）
backend/.planning/codebase/   后端代码地图事实层（结构、约定、测试、风险）
asset/       类型规则包与能力规则包
guide/       可选目录；若存在，仅放本地 Git / worktree 操作说明
```

### 去哪改

| 任务 | 入口 |
|------|------|
| 页面路由 | `frontend/app/` |
| 表单 / 工作台 UI | `frontend/components/forms/`, `frontend/components/chat/` |
| API 调用与错误封装 | `frontend/lib/api.ts`, `frontend/types/api.ts` |
| 类型映射 | `frontend/utils/tenderTypeMapper.ts`, `frontend/lib/formDataConverter.ts` |
| Graph / State / Node | `backend/graphs/`, `backend/states/`, `backend/nodes/` |
| Word 业务 helper | `backend/helper/word_helper/` |
| 任务与队列 | `backend/services/document_service.py`, `backend/task/task_queue_manager.py` |
| Prompt Layer | `backend/prompts/`, `backend/services/user_routing_service.py` |
| Word 工具 | `backend/util/word_util/` |
| 日志与 SSE | `backend/util/log_util/`, `backend/core/sse_manager.py`, `backend/api/stream.py` |
| 后端代码地图 | `backend/.planning/codebase/` |
| 前端代码地图 | `frontend/.planning/codebase/` |

## 9. 验证与测试门槛

### 最低要求

- 前端改动：至少跑 `npm run lint`、`npm run type-check` 和相关 `npm run test`
- 后端改动：至少跑 `python -m pytest tests -v`
- 涉及关键链路时：补任务创建、SSE、完成、下载的验证；涉及真实浏览器交互、页面跳转、会话恢复、模板弹窗或任务进度展示时，必须补或更新 Playwright E2E，并跑 `npm run test:e2e`
- 文档改动：至少校对文档中提到的文件、脚本、命令、端口和目录真实存在

### E2E 探路与固化流程

- 开发或排障时，可以先用 Chrome DevTools MCP 打开本地页面做探索性检查：确认页面状态、交互路径、console error、network 请求、接口响应、截图和性能线索。当前前端本地入口以 `frontend/playwright.config.ts` 的 `baseURL` 为准，默认为 `http://localhost:8502`。
- DevTools MCP 检查只算探路和诊断，不算可回归验证；不得把一次性的 live 页面观察当成最终测试结论，也不得只在交付说明里写“DevTools 看过没问题”。
- 流程稳定后，必须把用户可感知契约固化成 Playwright spec：跳转目标、可见按钮或角色入口、表单默认值、URL canonical 化、`sessionStorage` 会话身份、接口返回后的 UI 变化、SSE 进度 / 完成 / 失败展示、下载入口状态等。
- Playwright locator 必须锚定稳定契约：可见重复文案优先用 `data-testid`、role + accessible name 或限定容器；禁止用宽泛 `getByText()` / 全局 CSS 动画类断言会命中多个元素的 UI。
- Playwright E2E 统一放在 `frontend/e2e/test_*.spec.ts`，通过 `frontend/package.json` 的 `npm run test:e2e` 执行；本地调试可用 `npm run test:e2e:ui` 或 `npm run test:e2e:debug`，但 CI 和交付验收只以 `npm run test:e2e` 结果为准。
- CI 只信 Playwright，不信 DevTools MCP 的一次性检查。需要 CI 覆盖的行为必须进入 Playwright；DevTools MCP 只用于找路、复现和解释失败原因。
- Playwright 失败时，先看 Playwright report、trace、screenshot、video 和失败 locator；若仍无法定位，再用 Chrome DevTools MCP 连到 live 页面深挖 console、network、DOM 状态、performance 与截图差异。
- 当前项目完整运行依赖 Windows + Word COM；能脱离后端和 COM 的前端流程优先用 Playwright `page.route` / mock 固化。真实任务创建、SSE、完成和下载链路需要后端或 COM 时，必须在验证说明中写清运行环境、服务启动方式和哪些外部能力被 mock。
- 当前仓库没有稳定登录入口时，不要照搬“登录流程”样例；新增登录或权限能力后，才把登录成功跳转、角色按钮、权限态接口响应和退出状态纳入 Playwright E2E。

### 新增类型的最低测试矩阵

- 后端：graph 流程测试、服务接入测试
- 前端：表单测试、转换器测试、URL 映射测试、注册表测试
- 如果变更影响会话、任务恢复或取消，还要补对应 store、heartbeat 或 SSE 测试
- 任务恢复测试 fixture 必须按当前 store 契约同时包含 `conversation.currentTaskId`、`activeTaskIds`、`taskSummaries` 和对应消息 `taskId`；只在旧消息上挂 `taskId` 不能覆盖当前页面恢复链路。

### 测试文件命名与归类约束

- 强约束：所有新增或重命名后的测试文件名必须以 `test_` 开头。
- 后端测试统一放在 `backend/tests/<module_scope>/test_*.py`；禁止继续使用 `*_test.py`，也禁止把业务测试散放在 `backend/tests/` 根目录（`conftest.py`、`__init__.py` 除外）。
- 前端单测统一放在 `frontend/__tests__/unit/<module_scope>/test_*.test.ts(x)`；前端集成测试统一放在 `frontend/__tests__/integration/<module_scope>/test_*.test.ts(x)`；Playwright E2E 统一放在 `frontend/e2e/test_*.spec.ts`。
- 前端源码目录（如 `frontend/components/`、`frontend/lib/`、`frontend/utils/`）不再并排放测试文件；测试按“测试类型 + 模块路径”归档，不再混用源码旁测试与集中测试两套体系。
- 知识包、变更说明和 review 结论中引用测试时，必须引用迁移后的真实路径，禁止继续写已删除的旧测试路径。

### Windows 与测试策略

- 系统运行前提是 Windows + Word COM。
- 但凡能脱离 COM 的逻辑，都应拆出来做单测。
- Windows 环境只承担必要的 COM 集成验证，不应该承载所有业务逻辑测试。

### WSL 环境执行规范

- 如果检测到 `WSL_DISTRO_NAME` 非空，或 `/proc/version` / `uname -a` 包含 `Microsoft` / `WSL`，默认视为当前在 WSL。
- 在 WSL 中，前端命令必须优先使用 Linux `node` / `npm`；不要把 Windows `node.exe`、`npm.cmd`、`/mnt/d/...` 下的包装器当成默认运行时。
- 在 WSL 中执行前端验证前，先确认 `command -v node`、`command -v npm` 指向 Linux 可执行文件；若缺失，先安装 Linux Node.js 18+（可装到用户目录，例如 `~/.local/bin`），再运行 `npm run type-check`、`npm run test`。
- 在 WSL 中运行前端测试前，必须确保临时目录走 Linux 路径；优先使用 `TMPDIR=/tmp TMP=/tmp TEMP=/tmp`，不要继承 `/mnt/c/.../Temp` 这类 Windows 临时目录，否则 Jest / Playwright 可能在创建缓存目录时直接失败。
- 在 WSL 中，后端测试禁止复用 Windows 创建的 `backend/.venv`；应单独创建并使用 Linux 虚拟环境 `backend/.venv-linux`。
- 在 WSL 中运行 `pytest` 前，必须确保临时目录走 Linux 路径；优先使用 `TMPDIR=/tmp`，不要继承 `/mnt/c/.../Temp` 这类 Windows 临时目录，否则 `pytest` 捕获可能异常。
- 若 `backend/.venv-linux` 不存在，优先执行：

```bash
cd backend
uv venv .venv-linux
uv pip install --python .venv-linux/bin/python -r requirements.txt
```

- WSL 下推荐验证命令：

```bash
cd frontend
npm run lint
npm run type-check
TMPDIR=/tmp TMP=/tmp TEMP=/tmp CI=1 npm test -- --runInBand
```

```bash
cd backend
source .venv-linux/bin/activate
TMPDIR=/tmp python3 -m pytest tests -v
```

## 10. 反模式与禁止事项

- 禁止复制 `xjcg` / `gngk` / `gjgk` 整套实现来创建新的近似类型。
- 禁止在前端绕过 `frontend/lib/api.ts` 直接请求后端。
- 禁止只改后端 API，不改前端类型和调用封装。
- 禁止只补功能代码，不补测试和 `asset/` 知识包。
- 禁止在新节点、脚本、service 中直接散落 COM 调用。
- 禁止并发分支同时打开同一个 `prepared_doc_path` 做 Word COM 读写。
- 禁止公共节点依赖某个类型私有字段。
- 禁止把长 prompt 永久散落在多个节点函数内部。
- 禁止在 README、旧注释、`guide/` 或不存在的 `docs/` 基础上推断真实接口。
- 禁止把一次性 Git / worktree / 分支操作指南继续沉淀到 `asset/`。
- 禁止把“新增类型”变成顺手的大重构；目标是收敛，不是借题发挥。

## 11. 常用命令

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

### 根目录脚本

```bash
.\scripts\start-dev.ps1
.\scripts\stop-build.ps1
```

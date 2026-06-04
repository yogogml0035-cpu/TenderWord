# TenderWord 智能体操作指南

本文件只保存每次 AI 编码都必须遵守的仓库级规则；系统说明看 `ARCHITECTURE.md` 和 `coding_maps/SYSTEM_MAP.md`，接口边界看 `INTERFACES.md`，子项目事实看各自 `.planning/codebase/`，长期经验看 `asset/`。

## 1. 项目定位

TenderWord 是招标文档生成、修改、补充批注和模板复用系统。前端是 Next.js 工作台，后端是 FastAPI + LangGraph + Word COM 任务执行端；完整生成能力依赖 Windows、pywin32 和本机 Word/WPS COM。

当前前端 UI 类型是 `xjcg`、`gngk`、`gjgk`；后端 `FormType` 是 `xjcg_tender`、`gngk_hw_zc_tender`、`gngk_hw_cz_tender`、`gngk_fw_zc_tender`、`gngk_fw_cz_tender`、`gjgk_tender`。`gngk` 在前端只是一种 UI 类型，提交时必须由共享 helper 按 `tender_lx + fund_lx + ifzgcg` 分派到后端 form type。

前端包管理器是 npm，后端依赖以 `requirements.txt` 为准；完整 Word 生成验收必须回到 Windows Python + Word COM 环境。

## 2. 真源与分层

- 代码是真源；文档只做导航和稳定规则沉淀。
- API、SSE、任务状态、共享类型，以后端 API/model 和前端类型/API client 为准。
- `ARCHITECTURE.md`、`INTERFACES.md`、`coding_maps/SYSTEM_MAP.md` 是系统级地图，不覆盖代码真源。
- 子项目 `.planning/codebase/` 是事实地图，只用于快速理解结构、风险和验证入口；`asset/` 是长期知识包。
- `.env`、token、客户原文、私有路径和真实密钥不得进入文档、日志、测试夹具或最终回复。

## 3. 工作方式

- 先看现有实现和同模块写法，再动手；需求不完整时声明假设，必要时只问最小问题。
- 最小改动优先，禁止顺手重构、目录洗牌、批量改名或清理无关旧代码。
- 不回滚用户已有改动；工作区有无关变更时只触碰本任务文件。
- 不新增重量级依赖。必须新增时说明理由、替代方案和影响面。
- 不提交、不推送、不暂存，除非用户明确要求。
- 验证是交付的一部分；能跑的检查必须跑，跑不了要说明原因和替代验证。

## 4. 不可破坏的运行约束

- Word COM 是稀缺临界资源，所有 Word 写入必须经过任务队列、graph 锁、取消检查和进度包装；不得在 API route、service、前端或随意脚本中直接操作 COM。
- `progress_log` 只写用户可理解的进度；排障栈、参数摘要和诊断细节进入 `execution_log`。
- 任务失败必须收敛为任务失败状态和 SSE `error` 或终态事件，不能让 SSE 静默中断。
- 新增或修改 SSE 事件必须同步后端事件模型/发送方、前端 named event 注册、类型、解析、store 映射和测试。
- 前端所有后端请求统一走 API client；组件不写裸 `fetch`，也不直接访问外部模板候选 URL。
- 前端 URL canonical 化必须走统一 mapper/store helper；`TenderFormShared` 初始化优先级保持 `draft > URL > default`。
- 从 `sessionStorage` 恢复 running task 前必须先查任务状态；404 或 `TASK_NOT_FOUND` 收敛为本地中断态。
- 模板候选列表、下载代理、年份限制、白名单和文件落盘统一由后端处理，前端只消费项目内 API。
- Prompt Layer 只负责 prompt 渲染和机器契约解析，不承载日志、副作用、SSE、Word COM 或会话状态。
- `generation_style`、`generation_mode`、`comment_generation_mode` 和 `style_writeback_mode` 都是 generate-only 字段，不得进入 rewrite 请求模型、skill state 或 prompt surface。
- 上传 Word 文件后的修改统一走 `rewrite`；`/api/edit`、edit skill 和 edit task kind 已删除，不保留兼容入口。
- LLM 流式超时统一复用后端 settings 中的 `LLM_STREAM_TIMEOUT_SECONDS`。

## 5. 招标类型扩展规则

- 默认采用“共享主干 + 局部特化”。只有流程节点、状态字段、工具链或业务闭环明显不同，才新增类型或 graph。
- 模板、锚点、字号、少量替换规则差异优先走配置，不复制整套类型实现。
- `gngk` family 的共享 prompt、replacement 和公共节点路由必须以后端 family 收敛逻辑为准。
- `gngk_hw_cz` 当前是财政货物 direct-replace 首次生成类型，显式覆写 delete/update 节点，继续复用货物自筹 replacement。
- 新增或修改招标类型必须同步后端 form type、graph/state/node、配置、前端 UI 类型/URL/注册表/转换器、测试和 `asset/` 知识包。

## 6. Word 与智能体边界

- Word 业务逻辑优先下沉到共享 helper；底层 COM 生命周期、常量和技术工具留在 Word utility。
- 类型专属节点只保留锚点定位、Word app 生命周期、日志、保存、state 装配和必要编排。
- 受保护字段 profile 统一由招标类型配置解析；字段 marker 先规范化为中文冒号，再做严格字段行匹配。
- 关键受保护字段缺失、乱序或非法时 fail-fast，不能部分写回后靠 cleanup 兜底。
- 正文写回使用真实段落边界；显式空行属于正文语义，拆块和 cleanup 不得无差别压平。
- `content_agent`、`comment_agent` 和 `agent_step` 是共享运行时契约；类型 graph 不复制智能体分支，过程事件不替代 `done`/`error` 终态。
- 批注与样式写回摘要属于任务结果和 SSE `done` 契约，不得在 state、任务结果或前端下载卡中丢失。
- Agent run 只做任务创建前置流；只有 `task_accepted` 才进入后台 task/SSE/下载链路，`needs_input` 不创建任务也不复制任务状态机。

## 7. 文档与知识回写

- 改 Prompt Layer、task skill、generate/rewrite/comment_supplement runtime、`generation_mode`/`comment_generation_mode`、content/comment agent、Word COM、任务结果、SSE、批注/样式写回或 Word helper：更新共享运行时知识包。
- 改招标类型 identity、`form_type` 分派、anchor、graph/state/node/replacement、URL、会话、`sessionStorage`、生成草稿字段、过程卡或排队恢复：更新类型身份与会话知识包。
- 改模板候选、AI 重排、下载代理、文件回填或模板弹窗：更新模板候选知识包。
- 大范围改动后若 `.planning/codebase/` 或系统地图明显过期，先刷新对应子项目事实地图，再更新系统地图。
- 知识包只写当前仍成立的边界、同步面、验证入口和回归风险；不保存单次排障时间线。

## 8. 验证门槛

- 文档型变更至少运行 `git diff --check`，并扫描本轮改动文档中的密钥/token 模式；仅文档变更不需要跑代码测试或 E2E。
- 前端改动至少运行 `npm run lint`、`npm run type-check` 和相关 `npm run test`；涉及浏览器交互、URL、会话、SSE、模板弹窗或任务展示时补或跑 Playwright。
- 后端改动至少运行 `python -m pytest tests -v`；Word COM 真实闭环需要 Windows + Word COM，WSL 只能作为无 COM 替代验证。
- API shape、SSE、任务类型、招标类型、Prompt/LLM、Word helper、模板候选等跨层改动必须同步前后端类型、客户端、服务端模型、相关测试和知识包。
- 新增测试文件必须以 `test_` 开头，并放入既有测试归档层级。

## 9. 交付说明

最终回复写清：改了什么、影响哪些层、跑了哪些验证、未跑项及原因、剩余风险与最短回滚方式。若本轮属于完整需求或修复，还要说明是否发现可迁移经验，以及对应 `asset/` 知识包是否已更新；没有沉淀也要说明原因。

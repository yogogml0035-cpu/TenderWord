# 后端架构与约定

本文件保存后端任务相关的稳定执行规则。具体实现以 `backend/` 代码、`backend/.planning/codebase/` 事实文档和 `INTERFACES.md` 为准。

## 定位

- 后端是 FastAPI + LangGraph + Word COM 执行端。
- API、任务队列、SSE、任务上下文助手、生成 graph、rewrite skill、补充批注 graph、Prompt Layer、LLM/智能体调用、模板候选代理、上传下载和 Word 文件写回都在后端边界内。
- 完整生成能力依赖 Windows Python、pywin32 和本机 Word/WPS COM；WSL 只能作为无 COM 替代验证环境。
- 根级健康检查端点只用于应用进程探测，不替代 Word COM 诊断或真实生成验收。

## 分层约定

- API router 保持薄入口，业务编排放到 service、graph、node、helper 或 task runtime。
- 后端跨包导入使用 `backend.*` 包绝对路径。
- Prompt Layer 只负责 prompt 渲染和机器契约解析，不承载日志、副作用、SSE、Word COM 或会话状态。
- Word 业务逻辑优先下沉到共享 helper；底层 COM 生命周期、常量和技术工具留在 Word utility。
- 类型专属节点只保留锚点定位、Word app 生命周期、日志、保存、state 装配和必要编排。

## Word 与任务红线

- Word COM 是稀缺临界资源，所有写入必须经过任务队列、graph 锁、取消检查和进度包装。
- 不得在 API route、service、前端或随意脚本中直接操作 COM。
- `progress_log` 只写用户可理解的进度；排障栈、参数摘要和诊断细节进入 `execution_log`。
- 任务失败必须收敛为任务失败状态和 SSE `error` 或终态事件，不能让 SSE 静默中断。
- 受保护字段 profile 统一由招标类型配置解析；字段 marker 先规范化为中文冒号，再做严格字段行匹配。
- 关键受保护字段缺失、乱序或非法时 fail-fast，不能部分写回后靠 cleanup 兜底。
- 正文写回使用真实段落边界；显式空行属于正文语义，拆块和 cleanup 不得无差别压平。
- 参数源表的合并单元格拓扑只在后端内部保留：提取阶段写入 `tender_param_table_models` 侧车，prompt 正文使用表格文本投影 + `[[TABLE:table_id]]` 占位符配对；生成结果需要该表时只保留占位符，写回解析会把相邻投影表和占位符合并为一个结构化表 item，再按侧车模型恢复 merge。

## 智能体与生成运行时

- `content_agent`、`comment_agent` 和 `agent_step` 是共享运行时契约；类型 graph 不复制智能体分支，过程事件不替代 `done` / `error` 终态。
- 批注与样式写回摘要属于任务结果和 SSE `done` 契约，不得在 state、任务结果或前端下载卡中丢失。
- Agent run 只做任务创建前置流；只有 `task_accepted` 才进入后台 task、SSE 和下载链路，`needs_input` 不创建任务也不复制任务状态机。
- 上传 Word 文件后的修改统一走 `rewrite`；`/api/edit`、edit skill 和 edit task kind 已删除，不保留兼容入口。
- 上传文件 rewrite 的前端文件类型是 `rewrite_source`；后端 task skill state 内部用 `rewrite_source="uploaded_file"` 路由上传来源。
- Agent run 审计日志只能写白名单结构化字段和 scrub 后摘要；给 agent 暴露运行态信息时优先使用只读公共摘要工具，不返回完整任务结果、下载路径。
- 生成/批注 agent workspace 和审计日志文件名使用共享日志命名清洗辅助；新增 agent workspace 不要复制独立文件名规则。
- LLM 流式超时统一复用后端 settings 中的 `LLM_STREAM_TIMEOUT_SECONDS`。
- `backend/retrieval/` 是批注 bad case 检索正式运行时，接入 `generate_comments`、自主生成模式 `comment_agent` 和 `comment_supplement` 的 prompt 增强；rewrite 和 `comment_generation_mode=off` 不触发该检索。
- bad case retrieval 优先 hybrid，embedding / Qdrant 任一环节失败时降级到 `bm25_only`；无命中、坏文件或检索失败只写 warning / retrieval JSON，不阻塞批注生成，也不把检索状态、日志路径或命中详情展示到 SSE、下载卡或 `agent_step`。

## 招标类型扩展

- 默认采用“共享主干 + 局部特化”。只有流程节点、状态字段、工具链或业务闭环明显不同，才新增类型或 graph。
- 模板、锚点、字号、少量替换规则差异优先走配置，不复制整套类型实现。
- `gngk` family 的共享 prompt、replacement 和公共节点路由必须以后端 family 收敛逻辑为准。
- `gngk_hw_cz` 当前是财政货物 direct-replace 首次生成类型，显式覆写 delete/update 节点，继续复用货物自筹 replacement。
- 新增或修改招标类型必须同步后端 form type、graph、state、node、配置、前端 UI 类型、URL、注册表、转换器、测试和 `asset/` 知识包。

## 后端验证

- 后端改动至少运行 `python -m pytest tests -v`。
- Word COM 真实闭环需要 Windows + Word COM；WSL 只能作为无 COM 替代验证。
- 健康检查通过只能说明应用可响应；排查 Word 能力时仍需运行 Word 诊断脚本或实际生成任务。
- 新增测试文件必须以 `test_` 开头，并放入既有测试归档层级。

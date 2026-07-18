# 后端架构与约定

本文件保存后端任务相关的稳定执行规则。具体实现以 `backend/` 代码、`backend/.planning/codebase/` 事实文档和 `INTERFACES.md` 为准。

## 定位

  后端是 FastAPI + LangGraph + Word COM 执行端。
  API、任务队列、SSE、任务上下文助手、生成 graph、rewrite skill、补充批注 graph、Prompt Layer、LLM/智能体调用、模板候选代理、上传下载和 Word 文件写回都在后端边界内。
  完整生成能力依赖 Windows Python、pywin32 和本机 Word/WPS COM；WSL 只能作为无 COM 替代验证环境。
  根级健康检查端点只用于应用进程探测，不替代 Word COM 诊断或真实生成验收。

## 分层约定

  API router 保持薄入口，业务编排放到 service、graph、node、helper 或 task runtime。
  后端跨包导入使用 `backend.*` 包绝对路径。
  Prompt Layer 只负责 prompt 渲染和机器契约解析，不承载日志、副作用、SSE、Word COM 或会话状态。
  Word 业务逻辑优先下沉到共享 helper；底层 COM 生命周期、常量和技术工具留在 Word utility。
  类型专属节点只保留锚点定位、Word app 生命周期、日志、保存、state 装配和必要编排。

## Word 与任务红线

  Word COM 是稀缺临界资源，所有写入必须经过任务队列、graph 锁、取消检查和进度包装。
  不得在 API route、service、前端或随意脚本中直接操作 COM。
  当前后台任务类型只有 `generate`、`rewrite`、`comment_supplement`；新增类型要同步任务模型、SSE、会话结果和前端下载卡。
  `progress_log` 只写用户可理解的进度；排障栈、参数摘要和诊断细节进入 `execution_log`。
  任务失败必须收敛为任务失败状态和 SSE `error` 或终态事件，不能让 SSE 静默中断。
  受保护字段 profile 统一由招标类型配置解析；字段 marker 先规范化为中文冒号，再做严格字段行匹配。
  关键受保护字段缺失、乱序或非法时 fail fast，不能部分写回后靠 cleanup 兜底。
  正文写回使用真实段落边界；显式空行属于正文语义，拆块和 cleanup 不得无差别压平。
  参数源表的合并单元格拓扑只在后端内部保留：提取阶段写入 `tender_param_table_models` 侧车，prompt 正文在结构化表位置保留完整表格投影并紧跟 `[[TABLE:table_id]]` 占位符；生成结果需要该表时必须原样保留占位符，写回解析继续兼容相邻投影表反查 sidecar，并按侧车模型恢复 merge。
  带锚点结构化表（`[[TABLE:<id>]]`）的处理按 `generation_style` 区分：评分/评审表在任何生成风格下都删除标题、投影表和锚点；`template` 风格下，一列或仅长句/条款的投影表可展开为普通技术正文并删除锚点，避免写回层重复插入原表；`param` 风格下，非评分锚点表必须锚点直通（锚点独占一行并删除投影表），不得展开成普通正文或改写成另一种表格。该规则由 `verify_agent_graph` 与 `revise_agent_graph` 共同强制，改审核/修订规则时两侧必须同步。
  首次生成在 workflow/agent 最终正文确定后、Word 写回前，统一经共享 `annotate_corrections` 节点：确定性规范条款标识（三角类→`▲`、星/`*`/`※` 类→`★`，仅行/单元格起点），同步规范化 `tender_param_table_models` 单元格；主 LLM 将原始技术参数与最终正文一起比较，仅对名称限定词、同义改写、数字写法、数值/单位/范围、否定词、型号和专有名词等可确定事实变化生成固定口径 `correction_comments`（`原技术参数为“aaa”，现改为“bbb”`），再由独立 LLM 审核候选并剔除编号、项目符号、空白和末尾标点等展示壳变化。`*`/`※→★`、`△`/`Δ→▲` 是必须保留的条款重要性标识更正；代码已生成的同位置标识批注会注入主 prompt，避免重复生成。模板字段壳换名和复合值无损拆格（如 `维保设备→设备名称`、`1套→数量1+单位套`）不标注，但项目名称不得授权设备/维保设备/服务/采购标的名称；候选仍须通过原值存在于技术参数、现值与锚点存在于最终正文以及固定句式的代码门禁。rewrite 不接入该节点。
  Word 写回先写更正批注再写普通 AI 批注；`comment_generation_mode=off` 与 agent 的 `suppress_ai_comment_writeback` 只关闭普通批注，不关闭更正告知。
  批注写回统一走 `write_polished_comments`：`allow_existing_comments` 默认 `False`（标准写回跳过已有批注重叠锚点）；`comment_agent` 写回显式 `True`，允许同锚点追加合规批注。编号隔离（纯编号/项目符号/展示壳变化不生成事实更正批注）属于 `annotate_corrections` 与 prompt/verify 契约，不要散落到 writeback 层。
  Word 抽取须保留自动编号可见文本（`extract_text_with_list_numbers` 读取 `ListFormat`/`ListString`，正文已含编号则不重复前缀）；未知 Symbol/Wingdings 等字形不得静默删除，应以可逆 `[[WORD_SYMBOL:<font>:<hex>]]` 进入 prompt，写回前经 `word_symbol_tokens` 解码并恢复原字体，字体恢复失败必须中止写回。
  字段替换查找串受 Word Find 上限约束（`WORD_FIND_TEXT_MAX_LEN=256`）：超长查找串跳过并记入 `replacement_log`，不得强行 Find。

## 智能体与生成运行时

  `content_agent`、`comment_agent` 和 `agent_step` 是共享运行时契约；类型 graph 不复制智能体分支，过程事件不替代 `done` / `error` 终态。
  批注与样式写回摘要属于任务结果和 SSE `done` 契约，不得在 state、任务结果或前端下载卡中丢失；agent 后续普通批注摘要须累计保留更正批注计数。
  Agent run 只做任务创建前置流；只有 `task_accepted` 才进入后台 task、SSE 和下载链路，`needs_input` 不创建任务也不复制任务状态机。
  上传 Word 文件后的修改统一走 `rewrite`；`/api/edit`、edit skill 和 edit task kind 已删除，不保留兼容入口。
  上传文件 rewrite 的前端文件类型是 `rewrite_source`；后端 task skill state 内部用 `rewrite_source="uploaded_file"` 路由上传来源。
  Agent run 审计日志只能写白名单结构化字段和 scrub 后摘要；给 agent 暴露运行态信息时优先使用只读公共摘要工具，不返回完整任务结果、下载路径。
  生成/批注 agent workspace 和审计日志文件名使用共享日志命名清洗辅助；新增 agent workspace 不要复制独立文件名规则。
  自主批注生成直接请求模型输出 JSON 数组，不依赖模型发起 function call；候选锚点校验和 Word 写回始终由后端确定性运行时完成。
  LLM 流式超时统一复用后端 settings 中的 `LLM_STREAM_TIMEOUT_SECONDS`。
  `backend/retrieval/` 是批注 bad case 检索正式运行时，接入 `generate_comments`、自主生成模式 `comment_agent` 和 `comment_supplement` 的 prompt 增强；rewrite 和 `comment_generation_mode=off` 不触发该检索。
  bad case retrieval 优先 hybrid，embedding / Qdrant 任一环节失败时降级到 `bm25_only`；无命中、坏文件或检索失败只写 warning / retrieval JSON，不阻塞批注生成，也不把检索状态、日志路径或命中详情展示到 SSE、下载卡或 `agent_step`。

## 招标类型扩展

  默认采用“共享主干 + 局部特化”。只有流程节点、状态字段、工具链或业务闭环明显不同，才新增类型或 graph。
  模板、锚点、字号、少量替换规则差异优先走配置，不复制整套类型实现。
  `gngk` family 的共享 prompt、replacement 和公共节点路由必须以后端 family 收敛逻辑为准。
  `gngk_hw_cz` 当前是财政货物 direct replace 首次生成类型，显式覆写 delete/update 节点，继续复用货物自筹 replacement。
  新增或修改招标类型必须同步后端 form type、graph、state、node、配置、前端 UI 类型、URL、注册表、转换器、测试和 `asset/` 知识包。

## 后端验证

  后端改动至少运行 `python -m pytest tests -v`。
  Word COM 真实闭环需要 Windows + Word COM；WSL 只能作为无 COM 替代验证。
  健康检查通过只能说明应用可响应；排查 Word 能力时仍需运行 Word 诊断脚本或实际生成任务。
  新增测试文件必须以 `test_` 开头，并放入既有测试归档层级。

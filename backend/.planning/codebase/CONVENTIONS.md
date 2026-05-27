# 后端编码约定事实地图

**分析日期：** 2026-05-27

**范围：** `backend/` 源码和测试约定。

## 命名约定

- Python 文件和函数使用 `snake_case`。
- Graph 类使用 PascalCase，例如 `GngkHwCzTenderGraph`。
- 类型专属节点必须带类型前缀，例如 `gngk_hw_cz_delete_tender_param`。
- 通用节点名只保留在 `backend/nodes/common_word_nodes/`。
- 后端测试文件统一命名为 `test_*.py`。
- `FormType` 使用 `<runtime_type>_tender`，运行态 `tender_type` 不带 `_tender`。

## 代码风格

- 优先保持局部最小改动，不做无依据的大重构。
- API route 保持薄入口，复杂流程进入 service、graph、node 或 helper。
- Prompt 渲染进入 `backend/prompts/`，调用侧只收集数据、调用 builder、执行 LLM 和副作用。
- Word 业务逻辑进入 `backend/helper/word_helper/`；底层 COM 生命周期进入 `backend/util/word_util/`。
- 类型专属节点只保留锚点定位、Word app 生命周期、日志、保存、state 装配和类型专属编排。

## 导入组织

- 新代码使用 `backend.*` 绝对导入。
- 不新增 `from services...`、`from models...`、`from util...` 这类脱离包根的短路径。
- 函数内延迟导入只用于破除真实循环依赖，不作为默认风格。

## 错误处理

- API 输入用 Pydantic 模型和 validator 表达。
- API 错误返回应带稳定 code/message，便于前端 `ApiError` 展示与排障。
- 任务执行失败必须标记任务失败并发出 SSE `error` 或终态事件。
- Word 契约错误、受保护字段缺失、direct-replace 范围非法应 fail-fast。
- 不在用户可见 `progress_log` 中写异常堆栈或内部排障细节。

## 日志约定

- `progress_log`：用户可理解的节点进度、状态、简短失败原因。
- `execution_log`：排障细节、异常栈、关键参数摘要。
- `prompt_log`：prompt 记录。
- `skill_audit_log`：rewrite/edit task skill 审计。
- SSE 事件桥接由 `backend/util/log_util/sse_log_handler.py` 负责。

## Graph 与节点约定

- 新 graph 应继承共享 graph 主干，优先覆写必要节点，不复制整套流程。
- `StandardTenderWorkflowGraph` 是标准生成拓扑真源。
- 节点必须尊重取消检查、任务进度包装和 Word COM 串行化。
- 类型状态字段必须显式声明在 `backend/states/`，不靠隐式 dict key 扩散。
- `gngk` family 共享 prompt、replacement 和公共节点路由时，以 `get_tender_type_family()` 为准。

## Word helper 约定

- `backend/helper/word_helper/` 是 Word 业务层；`backend/util/word_util/` 是底层 COM/技术工具层。
- 两个以上类型复用的删除、写回、段落边界、受保护字段、Markdown 表格、cleanup、样式回填逻辑应抽到 helper。
- 受保护字段 profile 选择统一走 `backend/config/tender_config.py`。
- 受保护字段识别使用严格匹配，不用 `keyword in text`。
- 正文写回使用真实段落边界，正文不再用 `wdLineBreak` 或手工换行兜底。
- 显式空行属于正文语义，拆块和 cleanup 不应无差别压平。
- direct-replace 类型通过 `content_update_mode` 与 `content_start_mode` 显式声明，不再调用受保护字段 profile。

## Prompt 与 LLM 约定

- Prompt Layer 只做纯渲染和机器契约相关解析，不做日志、SSE、Word COM 或会话状态副作用。
- 与 LLM 契约强绑定的字面量、rewrite 路由、预览截断、历史压缩规则应收敛到 Prompt Layer。
- LLM 流式超时统一用 `settings.LLM_STREAM_TIMEOUT_SECONDS`。
- 修改 prompt 示例文案时要复核 `backend/tests/prompts/` 中的字面量断言。

## API 与模型约定

- `backend/models/` 是后端 API 和运行态模型真源。
- `GenerateRequest.form_type` 变化必须同步前端类型、`gngkFormType`、转换器、ChatPanel edit 调用点和测试。
- SSE 事件类型变化必须同步后端模型、发送方、前端 union 类型、解析和测试。
- `generation_style` 是 generate-only 字段，不进入 rewrite/edit 请求模型、skill state 或 prompt surface。

## 测试约定

- 后端测试放在 `backend/tests/<module_scope>/test_*.py`。
- 能脱离 COM 的逻辑必须拆出单测。
- Word COM 真实集成只在必要 Windows 环境承担。
- graph 路由测试要同时锁住新类型和兄弟类型既有绑定。
- direct-replace 节点测试应覆盖普通文本、显式空行、Markdown 表格、样式回填和批注硬失败契约。

---

*后端编码约定分析：2026-05-23*

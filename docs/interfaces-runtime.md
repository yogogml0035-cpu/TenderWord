# 接口与运行时契约

本文件保存跨前后端的同步规则。具体接口字段以 `backend/api/`、`backend/models/`、`frontend/types/api.ts` 和 `frontend/lib/api.ts` 为准。

## 真源

- API、SSE、任务状态、共享类型，以后端 API/model 和前端类型/API client 为准。
- `ARCHITECTURE.md`、`INTERFACES.md`、`coding_maps/SYSTEM_MAP.md` 是系统级地图，不覆盖代码真源。
- 子项目 `.planning/codebase/` 是事实地图，只用于快速理解结构、风险和验证入口；`asset/` 是长期知识包。

## 生成契约

- `GenerateRequest.file_paths` 当前只接受 `template` 与 `tender_params`。
- 生成节点只消费 `template_path` 与 `tender_param_paths`，不要重新引入旧文件槽位。
- `generation_style`、`generation_mode`、`comment_generation_mode` 和 `style_writeback_mode` 都是 generate-only 字段，不得进入 rewrite 请求模型、skill state 或 prompt surface。
- `generation_mode=workflow` 走旧 `generate_polished_text`，`generation_mode=agent` 走公共 `content_agent`。
- `comment_generation_mode=off` 时 workflow 与 agent 生成都跳过 AI 批注生成，不进入 rewrite 链路。

## 任务与 SSE

- 任务状态字段变化必须同步后端模型、前端类型、store task summary 和任务 UI。
- 新增 SSE 事件类型必须同步后端模型、事件发送、前端 union 类型、`frontend/lib/sse.ts` named event 注册、`useChatSSE` 解析和测试。
- 任务失败必须最终表现为 `error` 或 `done`，不能让 SSE 静默中断。
- `comment_writeback_*` 和 `style_writeback_*` 摘要属于任务结果契约，不得在 state、任务结果或 `done` 事件中丢失。

## Agent Run 与 Rewrite

- `POST /api/agent/runs/stream` 是右侧聊天唯一流式入口，返回 NDJSON agent run 事件。
- `task_accepted` 只负责把 agent run 收敛为“已创建任务”；后续排队、SSE、取消、下载和结果卡仍沿用既有 task / stream 契约。
- `needs_input` 不创建后台任务。
- 上传 Word 文件 rewrite 必须带非空用户重写指令、当前页面 `form_type`、完整锚点、`tender_lx` 和 `fund_source_lx`。
- `tender_data_snapshot` 只是可选上下文，不能因为未获取招标数据而阻断上传文件 rewrite。

## 补充批注

- 补充批注只从初次生成下载卡触发。
- 请求只携带当前会话、当前下载文件路径和模型；后端负责校验 latest `rewrite_state`、`polished_text` 和 source file 是否仍是当前最新文档。
- 成功后必须更新会话 latest `rewrite_state.prepared_doc_path`，让后续 rewrite 基于补充批注后的副本。
- `TaskKind`、任务状态、SSE `done` payload、下载消息和 `agent_step` 过程卡变化必须同步前后端类型与测试。

## 类型身份

- 新增或修改招标类型必须同步前端 UI 类型、后端 `FormType`、URL/注册表/转换器、后端 graph/state/node/replacement、配置和测试。
- `gngk` 后端分派依赖 `tender_lx + fund_lx + ifzgcg`，共享真源是前端 `gngkFormType` helper；generate 和上传文件 rewrite 都不能绕开该 helper。

## 外部集成

- 外部招标详情接口细节不应泄露到前端组件。
- 模板候选外部列表请求、下载代理、落盘和文件名清洗统一由后端处理。
- 外部模板下载链接必须继续受后端白名单约束。

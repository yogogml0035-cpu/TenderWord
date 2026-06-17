# 前端架构与约定

本文件保存前端任务相关的稳定执行规则。具体实现以 `frontend/` 代码、`frontend/.planning/codebase/` 事实文档和 `INTERFACES.md` 为准。

## 定位

- 前端是 Next.js 16 + React 19 工作台。
- 前端负责招标类型选择、URL 深链、会话与草稿、文件上传、模板候选弹窗、生成任务创建、智能体生成方式选择、agent run、rewrite/补充批注任务创建、SSE 进度与下载入口。
- 包管理器是 npm；`frontend/package.json` 声明 Node.js `>=20.9.0`，`.nvmrc` 固定 Node 20，`.npmrc` 开启 engine strict。

## 请求与接口

- 前端所有后端请求统一走 `frontend/lib/api.ts`；组件不写裸 `fetch`。
- 这个约定当前主要靠评审和测试维护，没有专门 lint 规则兜底；新增组件、hooks 或 store 请求时要人工检查是否绕过 API client。
- JSON、上传、下载、NDJSON 和 SSE URL 都由 API client 或专用 helper 提供。
- `NEXT_PUBLIC_API_URL` 会同时影响 API client、Next rewrite 目标和开发期 allowed origin；修改时要一起验证。
- 前端不直接访问外部模板候选 URL，不直接访问本地文件系统或云存储。
- API shape 变化必须同步 `frontend/types/api.ts`、API client、后端模型和相关测试。

## 类型、URL 与会话

- 当前前端 UI 类型是 `xjcg`、`gngk`、`gjgk`。
- 后端 `FormType` 是 `xjcg_tender`、`gngk_hw_zc_tender`、`gngk_hw_cz_tender`、`gngk_fw_zc_tender`、`gngk_fw_cz_tender`、`gjgk_tender`。
- `gngk` 在前端只是一种 UI 类型，提交时必须由共享 helper 按 `tender_lx + fund_lx + ifzgcg` 分派到后端 form type。
- 前端 URL canonical 化必须走统一 mapper/store helper。
- `TenderFormShared` 初始化优先级保持 `draft > URL > default`。
- 从 `sessionStorage` 恢复 running task 前必须先查任务状态；404 或 `TASK_NOT_FOUND` 收敛为本地中断态。
- `selected_skills` 是一次性 agent run 草稿字段，消息发出后必须清空；上传 rewrite 文件存在时才隐式选择 rewrite。
- 上传文件 rewrite 使用 `rewrite_source` 文件类型，并通过 `uploaded_files` + `rewrite_context` 向 agent run 提供受控上下文。

## SSE 与任务展示

- 新增或修改 SSE 事件必须同步后端事件模型/发送方、前端 named event 注册、类型、解析、store 映射和测试。
- `agent_step` 只表示智能体过程事件，不替代 `done` / `error` 终态。
- 任务下载卡不得丢失批注与样式写回摘要。
- rewrite 和 comment_supplement 下载卡不应再次显示补充批注动作。

## 模板候选

- 模板候选列表、下载代理、年份限制、白名单和文件落盘统一由后端处理。
- 前端只消费项目内模板候选 API。
- `year < 2025` 或非法年份的模板不可选择，只允许下载参考。

## 前端验证

- 前端改动至少运行 `npm run lint`、`npm run type-check` 和相关 `npm run test`。
- 涉及浏览器交互、URL、会话、SSE、模板弹窗或任务展示时，补或跑 Playwright。
- 前端 E2E 入口是 `npm run test:e2e`；Playwright 对本机浏览器、端口和平台二进制较敏感，Windows/WSL 切换后优先重新安装依赖并确认浏览器渠道。

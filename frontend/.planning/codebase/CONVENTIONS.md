# 前端编码约定事实地图

**分析日期：** 2026-05-30

**范围：** `frontend/` 源码、类型、测试和 UI 状态约定。

## 命名与文件组织

- React 组件文件使用 PascalCase。
- hook 使用 `useXxx` 命名并放在 `frontend/hooks/`。
- store 使用 Zustand，放在 `frontend/stores/`。
- API 类型放 `frontend/types/api.ts`，聊天类型放 `frontend/types/chat.ts`，TenderType 放 `frontend/types/index.ts`。
- 测试文件必须以 `test_` 开头，放在 `frontend/__tests__/unit/`、`frontend/__tests__/integration/` 或 `frontend/e2e/`。

## React 与 UI 模式

- 页面负责路由边界和组合，复杂交互放组件与 store。
- `/tender` 是 client component 工作台，由类型侧栏、表单面板和聊天面板组成。
- 表单类型差异优先通过 wrapper + shared form + registry，而不是在 `FormPanel` 中写大分支。
- 任务消息分为 log/content/download 三类，通过 store 的 task group 维护；智能体 `agent-step` 过程卡是独立消息类型，不进入旧三卡分组。
- 不在应用内新增说明性大段文字来解释功能；工作台应直接可用。

## API 客户端约定

- 所有后端请求统一在 `frontend/lib/api.ts` 中封装。
- JSON 请求走统一 `request<T>()` 和 `ApiError`。
- 文件、下载、SSE 和 NDJSON 使用专用 helper。
- 新接口必须同步 `frontend/types/api.ts`。
- 组件不得直接调用外部模板候选接口或后端裸 URL。

## 状态、会话与 URL

- 会话、草稿、任务摘要和历史使用 `sessionStorage`。
- running task 恢复前必须先查后端任务状态。
- `TenderFormShared` 初始化优先级固定为 `draft > URL > default`。
- 深链 URL 参数要先写入 draft，再让表单初始化读取。
- `generation_mode` 是会话级 generate 草稿字段，默认 `workflow`，不按 `gngk` 子类型分桶。
- canonical URL 构造和重写统一走 `buildCanonicalSearchParams()`、`syncBrowserUrlToConversation()` 和 store helper。
- `gngk` 会话身份按 `tenderType + tenderno + tender_lx + fund_lx` 匹配。

## 招标类型与表单约定

- 前端 UI 类型只有 `xjcg`、`gngk`、`gjgk`。
- 后端 form type union 在 `frontend/types/api.ts`。
- `frontend/lib/gngkFormType.ts` 是 `gngk` 后端 form type 分派真源。
- `frontend/lib/formDataConverter.ts` 负责生成任务转换，并调用 `resolveGngkFormType()`；缺省 `generation_mode` 要归一为 `workflow`。
- `frontend/components/chat/ChatPanel.tsx` 负责 edit 任务构造，并调用 `resolveGngkFormType()`。
- 修改 `gngk` 的 `tender_lx + fund_lx + ifzgcg` 分派时，只改共享 helper，并补生成与 edit 测试。
- 默认锚点在 `frontend/components/forms/tenderFormConfig.ts`；后端最终锚点配置在 `backend/config/tender_config.py`。

## SSE 与任务约定

- `useChatSSE` 是任务 SSE 到 UI/store 的映射入口。
- `chatStreamStore` 保存运行时 stream 内容；terminal 后由 store 收敛。
- 新事件类型需要同步前端 union、`frontend/lib/sse.ts` named event 注册、解析和测试。
- 任务失败或 missing task 要收敛为本地中断/失败态，不让 UI 悬挂。
- 用户态 SSE 日志只展示 outcome-first 的精简信息。
- `agent_step` 运行中快照只进 `chatStreamStore`，完成态再 upsert `agent-step` 会话消息；迟到的未完成快照不得把已完成过程卡降回 generating。

## 错误处理

- `ApiError.message` 是 UI 展示基础。
- 保留 `code` 和 `status` 便于排障。
- 模板候选、上传、下载、聊天和表单提交都应展示用户可读错误。
- 下载失败当前使用 alert 和 console，后续若统一 toast，需要保持 `ApiError` 信息不丢。

## 注释与函数设计

- 注释用于解释非显然业务约束，例如 gngk 工程类复用服务链路。
- 避免把 API 契约只写在注释里，类型和测试才是约束。
- 复杂派生逻辑优先抽函数并补单测，例如 URL 参数解析、`gngk` form type 分派、SSE event parse。

## 模块边界

- `frontend/lib/api.ts` 是后端调用边界，不应依赖 UI 组件。
- `frontend/utils/tenderTypeMapper.ts` 不应依赖 React 或 store。
- `frontend/types/` 不应引入运行时副作用。
- 组件可依赖 store、hook、lib 和 types，但不要让 store 依赖具体组件。

---

*前端编码约定分析：2026-05-23*

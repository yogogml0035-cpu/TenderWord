# 前端编码约定事实地图

**分析日期：** 2026-06-08

**范围：** 仅 `frontend/` 源码、类型、测试和配置。本文是后续前端代码改动的执行约束，说明性内容使用中文，代码标识符和路径保持原文。

## 命名模式

**文件：**
- React 组件使用 PascalCase：`frontend/components/chat/ChatPanel.tsx`、`frontend/components/forms/TenderFormShared.tsx`。
- hooks 使用 `useXxx.ts`：`frontend/hooks/useChatSSE.ts`、`frontend/hooks/useUrlParams.ts`。
- Zustand stores 使用语义化 camelCase：`frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`。
- 纯 helper 使用 camelCase 或领域名：`frontend/lib/formDataConverter.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Jest 测试文件必须以 `test_` 开头：`frontend/__tests__/unit/lib/test_api.test.ts`。
- Playwright 测试文件必须以 `test_` 开头：`frontend/e2e/test_url_conversation.spec.ts`。

**函数：**
- React component 使用 PascalCase function/export：`TemplateCandidateDialog`、`TenderPage`。
- hooks 使用 `use` 前缀：`useChatSSE()`、`useCurrentConversationTaskStatus()`。
- 事件 handler 使用 `handleXxx`：见 `frontend/app/tender/page.tsx`、`frontend/components/chat/ChatPanel.tsx`。
- converter 使用 `convertXxxToApiRequest`：`frontend/lib/formDataConverter.ts`。
- parser/normalizer 使用 `parseXxx`、`normalizeXxx`、`resolveXxx`：`frontend/lib/api.ts`、`frontend/lib/apiBaseUrl.ts`、`frontend/lib/gngkFormType.ts`。

**变量：**
- 后端 API 字段名保持 snake_case，前端对象中不强行转 camelCase：`form_type`、`tender_lx`、`fund_lx`、`comment_generation_mode`，见 `frontend/types/api.ts`。
- React state 使用语义化 camelCase：`templateDialogOpen`、`templateCandidatesLoading`，见 `frontend/components/forms/TenderFormShared.tsx`。
- task id、conversation id 使用 `taskId`、`conversationId`；后端 payload 保持 `task_id`。

**类型：**
- 类型和接口使用 PascalCase：`GenerateRequest`、`AgentRunStreamRequest`、`ConversationFormDraft`。
- union type 使用领域名：`TaskKind`、`TaskStatus`、`GenerationMode`。
- 前端 UI 类型 `TenderType` 定义在 `frontend/types/index.ts`，API 契约类型集中在 `frontend/types/api.ts`。

## 代码风格

**格式化：**
- 使用 Prettier 3，配置在 `frontend/.prettierrc`。
- 关键设置：分号开启、单引号、`printWidth: 100`、`tabWidth: 2`、`trailingComma: es5`。
- Tailwind class 排序由 `prettier-plugin-tailwindcss` 处理。

**代码检查：**
- 使用 ESLint 9 flat config，配置在 `frontend/eslint.config.mjs`。
- 继承 `eslint-config-next/core-web-vitals` 和 `eslint-config-next/typescript`。
- React hooks 插件启用，`react-hooks/set-state-in-effect` 当前为 warn。
- 忽略目录包括 `.next/**`、`node_modules-*/**`、`coverage/**`、`playwright-report/**`、`test-results/**`。

## 导入组织

**顺序：**
1. React、Next、第三方库，例如 `react`、`next/navigation`、`lucide-react`。
2. 项目绝对路径导入，使用 `@/*` alias，例如 `@/stores/chatStore`、`@/lib/api`。
3. 同目录相对导入，例如 `./MessageList`、`./shared`。
4. 类型导入优先使用 `import type`，例如 `import type { GenerateRequest } from '@/types/api'`。

**路径别名：**
- `@/*` 映射到 `frontend/*`，配置在 `frontend/tsconfig.json` 和 `frontend/jest.config.ts`。
- 测试中的 MSW/undici 兼容映射在 `frontend/jest.config.ts` 的 `moduleNameMapper`。

## 错误处理

**模式：**
- 后端请求错误统一收敛为 `ApiError`，实现位于 `frontend/lib/api.ts`。
- UI 展示优先使用 `ApiError.message`，并保留 `code` / `status` 用于排障。
- 网络错误使用 `NETWORK_ERROR`，abort 由 API 层识别，见 `frontend/lib/api.ts`。
- 任务 missing / 后端重启 / terminal 状态由 hooks 和 store 收敛，不让 UI 保持 indefinite generating。
- 模板候选、上传、表单提交、下载和聊天提交都应有用户可见错误路径。

## 日志

**框架：** `console`。

**模式：**
- 用户可见任务日志通过 `TaskLogMessage`、`TaskContentMessage`、`TaskDownloadMessage` 渲染，不把所有 console 视为用户反馈。
- 排障 console 目前出现在 `frontend/lib/sse.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/FormPanel.tsx`。
- 不在 console、测试 fixture、长期文档中输出认证凭据、真实私有 URL、客户原文、traceback 或下载本机路径。

## 注释

**注释时机：**
- 注释只解释非显然业务约束、跨端契约或兼容原因。
- 合理示例：`frontend/lib/gngkFormType.ts` 注明工程类当前复用服务链路。
- 不用注释替代类型和测试；API shape 必须落实到 `frontend/types/api.ts` 和测试。

**文档注释：**
- 当前部分 hooks、utilities 和测试工厂包含 JSDoc 风格说明，例如 `frontend/hooks/useUrlParams.ts`、`frontend/__tests__/mocks/data-factories.ts`。
- 新增公共 helper 可保留简短 TSDoc；组件内部简单 handler 不需要解释性注释。

## 函数设计

**规模：**
- 小型纯转换、解析和归一化逻辑优先抽到 `frontend/lib/` 或 `frontend/utils/` 并补单测。
- 大组件中新增逻辑时，优先复用已有 helper，不在 JSX 中堆复杂 payload 构造。
- 修改 `frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/ChatPanel.tsx` 这类大文件时保持手术式改动。

**参数：**
- 跨层 helper 使用对象参数以减少位置参数歧义，例如 `resolveGngkFormType({ tender_lx, fund_lx, ifzgcg })`。
- API helper 参数与后端契约一致，snake_case 字段保持原样。

**返回值：**
- API helper 返回解包后的 data 或明确类型；错误通过 throw `ApiError`。
- parser/normalizer 对无法解析的 payload 返回 `null`，见 `frontend/lib/api.ts` 的 agent run parser。
- React hooks 返回稳定对象或状态集合，避免组件重复实现状态判断。

## 模块设计

**导出：**
- 组件文件通常 named export + default export 视现有文件而定；新文件优先匹配同目录写法。
- `frontend/lib/api.ts` 导出具名 API helper 和 `ApiError`。
- `frontend/stores/*.ts` 导出 `useXxxStore` 并保留 default export。
- `frontend/types/` 只放类型、常量和类型守卫，不引入 UI 组件。

**Barrel 文件：**
- `frontend/types/index.ts` re-export `./api`，但 API 真源仍是 `frontend/types/api.ts`。
- `frontend/components/forms/shared/index.ts` 聚合共享表单控件；新增共享控件时同步该 barrel。

## API 与集成约定

- 所有后端请求统一放在 `frontend/lib/api.ts`；组件不得直接裸写 `fetch` 后端 URL。
- 新 API 字段必须同步 `frontend/types/api.ts`、API helper、相关 store/hook 和测试。
- 文件上传使用 `uploadFile()` / `uploadFiles()`；下载使用 `downloadFile()` / `getDownloadUrl()`。
- 模板候选只通过 `fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`。
- `NEXT_PUBLIC_API_URL` 相关逻辑修改时，同步检查 `frontend/lib/apiBaseUrl.ts` 和 `frontend/next.config.ts`。

## 状态、URL 与任务约定

- 会话、草稿和任务摘要存储在 `chatStore`；运行中 stream 放在 `chatStreamStore`；task resume 元数据放在 `chatTaskSessionStore`。
- 表单初始化优先级保持 `draft > URL > default`。
- `gngk` 会话身份按 `tenderType + tenderno + tender_lx + fund_lx` 判断。
- canonical URL 构造只走 `frontend/utils/tenderTypeMapper.ts`，不要手写 query patch。
- `selected_skills` 是一次性 agent run 字段；发送后清空。
- 上传文件 rewrite 使用 `rewrite_source`，存在 `rewrite_file` 时可隐式选择 `rewrite`。
- `generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只用于 generate，不进入 rewrite context。

## 招标类型与表单约定

- 前端 UI 类型只有 `xjcg`、`gngk`、`gjgk`。
- 新增或调整类型时同步 `frontend/types/index.ts`、`frontend/types/api.ts`、`frontend/utils/tenderTypeMapper.ts`、`frontend/components/chat/tenderFormRegistry.ts`、`frontend/components/forms/tenderFormConfig.ts`、`frontend/lib/formDataConverter.ts` 和测试。
- `gngk` 后端 `form_type` 分派只改 `frontend/lib/gngkFormType.ts`。
- 表单转换器只提交 `file_paths.template` 和 `file_paths.tender_params` 给 generate；rewrite 文件不复用 generate 上传槽位。

## SSE 与智能体步骤约定

- 新 SSE 事件必须同步 `frontend/types/api.ts`、`frontend/lib/sse.ts` named event 注册、`frontend/hooks/useChatSSE.ts` 映射和相关测试。
- `agent_step` 运行中快照只进入 `chatStreamStore`；完成态再持久化为 `agent-step` 消息。
- 迟到的未完成快照不得把已完成过程卡降级为 generating。
- `comment_agent` 过程卡走同一 `agent_step` 事件族。

---

*前端编码约定分析：2026-06-08*

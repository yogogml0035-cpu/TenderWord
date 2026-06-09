# 前端编码约定

**分析日期：** 2026-06-09

**范围：** `frontend/` 源码、类型、测试、配置、`README.md`、`docs/frontend.md`、`docs/interfaces-runtime.md` 和既有 `frontend/.planning/codebase/` 事实文档。`frontend/.env.local`、`frontend/.env.local.example`、`frontend/.npmrc` 仅确认存在，不读取内容。

## 命名模式

**文件：**
- React 组件文件使用 PascalCase：`frontend/components/chat/ChatPanel.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/forms/FileUploader.tsx`。
- hooks 使用 `useXxx.ts`：`frontend/hooks/useChatSSE.ts`、`frontend/hooks/useCurrentConversationTaskStatus.ts`、`frontend/hooks/useTaskHeartbeat.ts`。
- Zustand store 使用语义化 camelCase：`frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatTaskSessionStore.ts`。
- 纯 helper 使用 camelCase 或领域名：`frontend/lib/formDataConverter.ts`、`frontend/lib/gngkFormType.ts`、`frontend/lib/apiBaseUrl.ts`、`frontend/utils/tenderTypeMapper.ts`。
- Jest 测试文件放在 `frontend/__tests__/`，文件名使用 `test_*.test.ts` 或 `test_*.test.tsx`：`frontend/__tests__/unit/lib/test_api.test.ts`。
- Playwright 测试文件放在 `frontend/e2e/`，文件名使用 `test_*.spec.ts`：`frontend/e2e/test_generation_mode_agent.spec.ts`。

**函数：**
- React component 使用 PascalCase：`ChatPanel`、`TenderFormShared`、`FileUploader`。
- hooks 使用 `use` 前缀：`useChatSSE()`、`useSSE()`、`useUrlParams()`。
- React 事件 handler 使用 `handleXxx`：`handleSendMessage`、`handleRewriteFileUpload`、`handleTemplateCandidateSelect`。
- 表单转换函数使用 `convertXxxFormToApiRequest`：`convertXjcgFormToApiRequest()`、`convertGngkFormToApiRequest()`、`convertGjgkFormToApiRequest()`。
- 解析、归一化、构造函数使用 `parseXxx`、`normalizeXxx`、`resolveXxx`、`buildXxx`：`parseTenderUrlParams()`、`normalizeApiBaseUrl()`、`resolveGngkFormType()`、`buildCanonicalSearchParams()`。

**变量：**
- 前端本地变量使用 camelCase：`conversationId`、`taskId`、`templateDialogOpen`、`selectedSkillsForRequest`。
- 后端 payload 字段保持 snake_case，不在前端契约层强行改名：`form_type`、`tender_lx`、`fund_lx`、`file_paths`、`generation_mode`，见 `frontend/types/api.ts`。
- task / conversation 的后端字段保持 `task_id`、`conversation_id`；UI 和 store 方法参数可使用 `taskId`、`conversationId`。
- UI 类型固定使用 `TenderType` 的 `xjcg`、`gngk`、`gjgk`，不要把后端 `FormType` 字符串当作前端页面类型。

**类型：**
- 类型、接口、union 使用 PascalCase：`GenerateRequest`、`AgentRunStreamRequest`、`ConversationFormDraft`、`SSEAgentStepEvent`。
- 后端 API/SSE/agent run 契约类型集中在 `frontend/types/api.ts`；聊天消息和会话类型集中在 `frontend/types/chat.ts`；前端全局 UI 类型在 `frontend/types/index.ts`。
- `frontend/types/index.ts` 可以 re-export `./api`，但新增 API 字段的真源位置仍是 `frontend/types/api.ts`。

## 代码风格

**格式化：**
- 使用 Prettier 3，配置在 `frontend/.prettierrc`。
- 保持 `semi: true`、`singleQuote: true`、`printWidth: 100`、`tabWidth: 2`、`trailingComma: es5`。
- Tailwind class 排序由 `prettier-plugin-tailwindcss` 处理。
- 格式化跳过项在 `frontend/.prettierignore`，包括 `node_modules`、`.next`、`out`、`dist`、`*.log`。

**Lint：**
- 使用 ESLint 9 flat config，配置在 `frontend/eslint.config.mjs`。
- 继承 `eslint-config-next/core-web-vitals` 和 `eslint-config-next/typescript`。
- 启用 `eslint-plugin-react-hooks`，`react-hooks/set-state-in-effect` 为 `warn`。
- ESLint 忽略 `.next/**`、`out/**`、`build/**`、`next-env.d.ts`、`node_modules-*/**`、`coverage/**`、`playwright-report/**`、`test-results/**`。

**TypeScript:**
- 主配置是 `frontend/tsconfig.json`，启用 `strict: true`、`jsx: react-jsx`、`moduleResolution: bundler`、`@/*` alias。
- 类型检查入口是 `frontend/tsconfig.typecheck.json`，命令为 `npm run type-check`。
- Next 构建不忽略类型错误，`frontend/next.config.ts` 中 `typescript.ignoreBuildErrors` 为 `false`。

## 导入组织

**顺序：**
1. React、Next、Node 或第三方库，例如 `react`、`next/navigation`、`lucide-react`、`@playwright/test`。
2. 项目绝对路径导入，使用 `@/*` alias，例如 `@/lib/api`、`@/stores/chatStore`、`@/types/api`。
3. 同目录相对导入，例如 `./MessageList`、`./shared`。
4. 类型导入使用 `import type`，尤其是 `frontend/types/api.ts`、`frontend/types/chat.ts` 和组件 props 类型。

**路径别名：**
- `@/*` 映射到 `frontend/*`，配置在 `frontend/tsconfig.json`。
- Jest 中同样映射 `^@/(.*)$` 到 `<rootDir>/$1`，配置在 `frontend/jest.config.ts`。
- MSW / undici 兼容映射只放在 `frontend/jest.config.ts` 的 `moduleNameMapper`，不要在测试里手写深层 node_modules 路径。

**模式：**
```typescript
import { useCallback } from 'react';
import { Upload } from 'lucide-react';
import { uploadFile, ApiError } from '@/lib/api';
import type { FileType } from '@/types/api';
```

实际示例：`frontend/components/forms/FileUploader.tsx`。

## 错误处理

**模式：**
- 后端请求错误统一收敛为 `ApiError`，实现位于 `frontend/lib/api.ts`。
- API helper 必须解析 wrapped success payload `{ success: true, data: ... }`，并兼容少量 flat legacy response；新增 endpoint 优先遵循 wrapped response。
- 网络错误统一使用 `NETWORK_ERROR`，abort 保留原始 abort 语义，见 `frontend/lib/api.ts` 的 `request()` 和 `streamNdjson()`。
- UI 展示错误时优先使用 `ApiError.message`，保留 `code` / `status` 给测试或排障路径。
- 任务状态、SSE 中断、后端重启、`TASK_NOT_FOUND` 必须通过 store/hook 收敛为终态或本地中断态，不让任务卡永久停在 generating。
- 上传、模板候选、agent run、补充批注和下载都要有用户可见失败路径，并在相关测试中断言。

**API helper 模式：**
```typescript
export async function createGenerateTask(params: GenerateRequest): Promise<CreateTaskData> {
  return request<CreateTaskData>('/api/generate', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}
```

实际文件：`frontend/lib/api.ts`。

## 日志

**框架：** `console`。

**模式：**
- SSE 底层连接日志集中在 `frontend/lib/sse.ts`，用于连接打开、重连和异常排障。
- 任务用户可见日志不依赖 console，统一由 `frontend/components/chat/TaskLogMessage.tsx`、`frontend/components/chat/TaskContentMessage.tsx`、`frontend/components/chat/TaskDownloadMessage.tsx` 渲染。
- Playwright 测试会收集 console error 并断言为空，见 `frontend/e2e/test_generation_mode_agent.spec.ts` 和 `frontend/e2e/test_comment_supplement.spec.ts`。
- 不在 console、测试夹具、长期文档或 UI 摘要中输出真实密钥、完整客户原文、私有下载路径、traceback 或 token。

## 注释

**何时写注释：**
- 注释只解释不显然的业务边界、跨端契约或兼容原因。
- 合理示例：`frontend/lib/gngkFormType.ts` 中说明工程类当前复用服务链路；`frontend/utils/tenderTypeMapper.ts` 中说明前端判型仅依赖 `purchase_method`。
- 不用注释替代类型、测试或命名；新增 API 字段必须落实到 `frontend/types/api.ts` 和对应测试。

**JSDoc/TSDoc:**
- 公共 helper、测试工厂和底层 hook 可保留短 TSDoc，例如 `frontend/hooks/useSSE.ts`、`frontend/__tests__/mocks/data-factories.ts`。
- 组件内部简单 handler 不需要 JSDoc；优先用清晰函数名和局部变量名表达意图。

## 函数设计

**规模：**
- 纯转换、解析、归一化逻辑放入 `frontend/lib/` 或 `frontend/utils/` 并补单测，例如 `frontend/lib/formDataConverter.ts`、`frontend/lib/apiBaseUrl.ts`。
- 大组件只做 UI 编排和事件分发。修改 `frontend/components/chat/ChatPanel.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/stores/chatStore.ts` 时保持手术式改动。
- 不在 JSX 里拼复杂后端 payload；先在 helper 或局部 builder 中构造，再传给 API client。

**参数：**
- 跨层 helper 使用对象参数降低歧义，例如 `resolveGngkFormType({ tender_lx, fund_lx, ifzgcg })`。
- API helper 参数类型必须来自 `frontend/types/api.ts`，例如 `GenerateRequest`、`AgentRunStreamRequest`、`CommentSupplementTaskRequest`。
- 浏览器 URL 和 tender type helper 接收明确的领域对象，例如 `CanonicalUrlParams`。

**返回值：**
- API helper 返回解包后的业务 data，失败时 throw `ApiError`。
- parser 对无法识别的流事件返回 `null` 并忽略该事件，见 `frontend/lib/api.ts` 的 `parseAgentRunEvent()`。
- hook 返回稳定状态对象和操作函数，组件不重复实现 SSE 连接状态判断。

## 模块设计

**导出：**
- API client 统一从 `frontend/lib/api.ts` 导出具名 helper 和 `ApiError`。
- Zustand store 文件导出 `useXxxStore`，并保留同名 default export 的既有写法。
- 类型模块只放类型、常量和类型守卫，不引入 UI 组件。
- 表单注册集中在 `frontend/components/chat/tenderFormRegistry.ts`，新增招标类型必须同步 component map、display name map 和 converter map。

**聚合导出文件：**
- `frontend/types/index.ts` 重新导出 `./api`，但不要把 API 真源迁出 `frontend/types/api.ts`。
- `frontend/components/forms/shared/index.ts` 聚合共享表单控件；新增共享表单控件时同步该聚合入口。

## API Client 约定

- 所有后端 JSON、上传、下载、NDJSON、模板候选、任务状态和 heartbeat 请求统一走 `frontend/lib/api.ts`。
- 组件不得裸写后端 `fetch()`；当前源码搜索中，后端 `fetch()` 仅存在于 `frontend/lib/api.ts`。
- SSE URL 由 `frontend/lib/api.ts` 的 `getTaskStreamUrl()` 或 `frontend/hooks/useChatSSE.ts` 经 `frontend/lib/sse.ts` 创建，不在组件里拼后端 stream URL。
- `NEXT_PUBLIC_API_URL` 解析集中在 `frontend/lib/apiBaseUrl.ts`；修改该链路时同时检查 `frontend/next.config.ts` 的 rewrites 和 allowed dev origins。
- 模板候选只能通过项目内 API helper：`fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`。组件不直接访问外部模板候选 URL。
- 文件上传使用 `uploadFile()` / `uploadFiles()`；下载使用 `downloadFile()` / `getDownloadUrl()`。

## 类型同步与跨端契约

- API shape 变化必须同步 `frontend/types/api.ts`、`frontend/lib/api.ts`、相关 component/store/hook 和测试。
- SSE 事件变化必须同步 `frontend/types/api.ts`、`frontend/lib/sse.ts` named event 注册、`frontend/hooks/useChatSSE.ts` 事件映射、`frontend/__tests__/unit/lib/test_sse.test.ts` 和 `frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`。
- `TaskKind`、`TaskStatus`、`SSEDoneEvent`、`TaskResult`、`StyleWritebackSummary`、`CommentWritebackSummary` 改动必须同步下载卡和任务消息 metadata，见 `frontend/types/chat.ts`。
- 新增或修改招标类型必须同步 `frontend/types/index.ts`、`frontend/types/api.ts`、`frontend/utils/tenderTypeMapper.ts`、`frontend/components/chat/tenderFormRegistry.ts`、`frontend/components/forms/tenderFormConfig.ts`、`frontend/lib/formDataConverter.ts` 和测试。

## 表单、状态与上传约定

- `TenderFormShared` 的初始化优先级保持 `draft > URL > default`，见 `frontend/components/forms/TenderFormShared.tsx`。
- 会话草稿、任务摘要、任务消息分组由 `frontend/stores/chatStore.ts` 维护；运行中 stream 只放 `frontend/stores/chatStreamStore.ts`；task resume 元数据放 `frontend/stores/chatTaskSessionStore.ts`。
- `gngk` 在前端只是 UI 类型，后端 `form_type` 必须由 `frontend/lib/gngkFormType.ts` 按 `tender_lx + fund_lx + ifzgcg` 分派。
- 表单转换器只把生成文件槽位写入 `file_paths.template` 和 `file_paths.tender_params`；不要恢复旧的资格文件或 edit 文件槽位，见 `frontend/lib/formDataConverter.ts`。
- 上传文件 rewrite 使用 `uploadFile(file, 'rewrite_source')`，并在 draft 中写入 `rewrite_file` 和一次性 `selected_skills: ['rewrite']`，见 `frontend/components/chat/ChatPanel.tsx`。
- `selected_skills` 是一次性 agent run 字段，发送后清空；存在 `rewrite_file` 时可隐式选择 `rewrite`。

## Generate-only 字段边界

- `generation_style`、`generation_mode`、`comment_generation_mode`、`style_writeback_mode` 只属于 generate payload。
- 这些字段由 `frontend/components/forms/TenderFormShared.tsx` 写入 draft，并由 `frontend/lib/formDataConverter.ts` 转成 `GenerateRequest`。
- `ChatPanel` 构造 `AgentRunStreamRequest` 时不得携带 `generation_mode`、`comment_generation_mode`、`style_writeback_mode`。该边界由 `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx` 断言。
- rewrite 上下文只通过 `context_snapshot.rewrite_context` 提供受控字段：`form_type`、`insertion_config`、`tender_lx`、`fund_source_lx`、可选 `tender_data_snapshot`。

## SSE 与 Agent Run 约定

- `POST /api/agent/runs/stream` 是右侧聊天唯一 NDJSON 流式入口，前端解析在 `frontend/lib/api.ts` 的 `streamAgentRun()` 和 `parseAgentRunEvent()`。
- `task_accepted` 才创建后台任务并接入 task/SSE 链路；`needs_input` 只追加普通 AI 提示，不创建任务。
- `agent_step` 运行中快照写入 `frontend/stores/chatStreamStore.ts`；完成态再 upsert 为 `agent-step` 消息。
- `content_agent` 和 `comment_agent` 过程卡复用 `agent_step` 事件族，映射逻辑在 `frontend/hooks/useChatSSE.ts`。
- SSE reconnect、`lastEventId` 和 heartbeat 行为由 `frontend/lib/sse.ts` 与 `frontend/hooks/useChatSSE.ts` 管理，不在组件层重写。

## 项目技能与文档约束

- 前端事实文档必须使用简体中文说明正文，代码标识符、路径、命令和配置键保持原文。
- 写长期文档时使用当前代码和配置作为真源；`frontend/.env.local`、`frontend/.env.local.example`、`frontend/.npmrc` 只记录存在，不读取或引用内容。
- 只改与任务相关文件；本次 quality focus 只维护 `frontend/.planning/codebase/CONVENTIONS.md` 和 `frontend/.planning/codebase/TESTING.md`。

---

*约定分析：2026-06-09*

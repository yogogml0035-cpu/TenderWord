# 前端风险事实地图

**分析日期：** 2026-06-08

**范围：** 仅 `frontend/` 当前技术债、脆弱区、安全边界、性能限制和测试缺口。本文只记录有当前代码证据的事实或明确未检测到的能力。

## 技术债

**核心文件过大且职责密集：**
- 问题：`chatStore`、共享表单、聊天面板、API client 和 SSE hook 承载大量行为。
- 文件：`frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/ChatPanel.tsx`、`frontend/lib/api.ts`、`frontend/hooks/useChatSSE.ts`
- 影响：小改动容易影响会话、任务、SSE、rewrite、补充批注和下载等多条链路；review 和测试选择成本高。
- 修复方式：修改时保持手术式范围；优先为新增分支提取纯 helper 到 `frontend/lib/` 或 `frontend/utils/` 并补窄测试，不做无关大拆分。

**招标类型身份仍分散注册：**
- 问题：前端 UI 类型、后端 form type、URL 参数、表单注册、默认锚点和 converter 分布在多个文件。
- 文件：`frontend/types/index.ts`、`frontend/types/api.ts`、`frontend/utils/tenderTypeMapper.ts`、`frontend/components/chat/tenderFormRegistry.ts`、`frontend/components/forms/tenderFormConfig.ts`、`frontend/lib/formDataConverter.ts`、`frontend/lib/gngkFormType.ts`
- 影响：新增或调整招标类型时容易漏改某一层，导致 URL、表单、payload 或测试不一致。
- 修复方式：按 `CONVENTIONS.md` 的同步清单改动；新增类型必须补 mapper、registry、converter、store/URL 和测试。

**`gngk` form type 分派不能被绕过：**
- 问题：`gngk` 后端 graph 分派依赖 `tender_lx + fund_lx + ifzgcg`，generate 和上传文件 rewrite 都要一致。
- 文件：`frontend/lib/gngkFormType.ts`、`frontend/lib/formDataConverter.ts`、`frontend/components/chat/ChatPanel.tsx`
- 影响：调用点私自分派会让 generate 与 rewrite 使用不同 form type。
- 修复方式：只改 `resolveGngkFormType()`；同步 `frontend/__tests__/unit/lib/test_form_data_converter.test.ts` 和 `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`。

**`types/index.ts` 保留旧式通用类型与 API re-export：**
- 问题：`frontend/types/index.ts` 同时定义 `TenderType`、旧式 `Task`/`GenerationHistory`/`ApiError` 等，并 re-export `./api`。
- 文件：`frontend/types/index.ts`、`frontend/types/api.ts`
- 影响：新代码可能误用 `types/index.ts` 中的旧泛型，而不是 `types/api.ts` 中的真实后端契约。
- 修复方式：API payload 和后端契约以 `frontend/types/api.ts` 为准；只把 `frontend/types/index.ts` 用作前端 UI 通用类型入口。

**Jest setup 存在双文件入口：**
- 问题：`frontend/jest.setup.js` 和 `frontend/jest.setup.ts` 内容相似，但 `frontend/jest.config.ts` 实际只引用 `.js`。
- 文件：`frontend/jest.config.ts`、`frontend/jest.setup.js`、`frontend/jest.setup.ts`
- 影响：修改 `.ts` setup 不会影响当前 Jest，容易产生误判。
- 修复方式：测试 setup 变更前先确认 `setupFilesAfterEnv`；需要保留双文件时同步更新，或单独计划清理。

## 已知问题

**全局 CSS 变量重复定义导致主色 hover 值被覆盖：**
- 症状：`:root` 中 `--primary-hover` 先定义为蓝色，随后重复定义为红色，后者覆盖前者。
- 文件：`frontend/app/globals.css`
- 触发方式：使用 `var(--primary-hover)` 的组件会得到后定义的红色值。
- 临时处理：当前组件中大量使用 Tailwind 直接颜色，影响取决于是否引用该变量；修改视觉 token 时先审查 `globals.css` 重复项。

**`waitForLoadingToFinish()` 测试工具是空实现：**
- 症状：调用该 helper 不会等待任何 loading 状态。
- 文件：`frontend/__tests__/utils/test-utils.tsx`
- 触发方式：新测试误用 `waitForLoadingToFinish()` 作为真实等待。
- 临时处理：使用 Testing Library `waitFor()` 或显式断言目标状态；如需通用 helper，单独实现并补测试。

## 安全注意事项

**前端无认证边界：**
- 风险：`sessionStorage` 会话只是浏览器本地状态，不能作为用户权限或安全身份。
- 文件：`frontend/stores/chatStore.ts`、`frontend/stores/chatTaskSessionStore.ts`、`frontend/stores/historyStore.ts`、`frontend/lib/api.ts`
- 当前缓解：当前 API helper 未注入 auth header；敏感权限应由后端控制。
- 建议：新增认证时同步 API client、路由守卫、错误处理、测试和系统接口文档。

**模板候选必须经后端代理：**
- 风险：组件直接请求外部候选 URL 会绕过后端白名单、年份和 selectable 规则。
- 文件：`frontend/components/forms/TemplateCandidateDialog.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/lib/api.ts`
- 当前缓解：当前有 `fetchTemplateCandidates()`、`selectTemplateCandidate()`、`getTemplateCandidateDownloadUrl()`。
- 建议：新增候选相关能力继续通过 `/api/template-candidates*` helper。

**文档和日志不得泄露本地敏感信息：**
- 风险：`.env.local`、认证凭据、私有 URL、客户原文、本机下载路径或 traceback 进入长期文档/console/测试夹具。
- 文件：`frontend/.env.local` 存在但不得读取；相关输出路径在 `frontend/lib/api.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/e2e/`。
- 当前缓解：本次文档只记录环境文件存在，不记录内容。
- 建议：测试 fixture 使用合成数据；E2E console/log 证据进入报告前避免真实客户内容。

## 性能瓶颈

**长会话和长任务日志存储在浏览器侧：**
- 问题：会话消息、任务摘要和完成态过程卡持久化在 `sessionStorage`；长任务 stream 在内存增长。
- 文件：`frontend/stores/chatStore.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/hooks/useChatSSE.ts`
- 原因：当前前端以浏览器会话为主要恢复边界，没有服务端分页或持久聊天列表。
- 改进路径：大任务扩展时考虑日志截断、消息分页、stream 清理策略和持久化 payload 上限测试。

**`agent_step` 高频事件需要保持 transient：**
- 问题：高频未完成 agent step 如果持久化到会话会增加渲染和 storage 压力。
- 文件：`frontend/hooks/useChatSSE.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatStore.ts`
- 原因：SSE 运行中快照频繁更新。
- 改进路径：继续保持运行中快照只进 `chatStreamStore`，完成态再 upsert 会话消息。

## 脆弱区域

**URL、draft 和会话 identity：**
- 文件：`frontend/app/tender/page.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/stores/chatStore.ts`、`frontend/utils/tenderTypeMapper.ts`
- 脆弱原因：`draft > URL > default`、`gngk` 子类型身份和 canonical URL 同时影响页面启动与会话切换。
- 安全修改：URL 构造只走 `tenderTypeMapper`；深链参数先写 draft；改动同步 URL/store/E2E 测试。
- 测试覆盖：`frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`、`frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`、`frontend/e2e/test_url_conversation.spec.ts`。

**SSE 事件契约：**
- 文件：`frontend/types/api.ts`、`frontend/lib/sse.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/stores/chatStreamStore.ts`、`frontend/stores/chatStore.ts`
- 脆弱原因：后端事件名、payload shape、终态和 last event id 都是跨端契约。
- 安全修改：新事件同步类型、named event 注册、parser、store 映射和测试。
- 测试覆盖：`frontend/__tests__/unit/lib/test_sse.test.ts`、`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/__tests__/unit/types/test_api_sse_agent_step.test.ts`。

**Agent run 前置流：**
- 文件：`frontend/components/chat/ChatPanel.tsx`、`frontend/lib/api.ts`、`frontend/types/api.ts`
- 脆弱原因：`task_accepted` 才进入后台任务；`needs_input` 和 `done` 不是任务状态。
- 安全修改：不把 agent thinking events 写进 task summary；上传 rewrite 文件发送后清空一次性 skill。
- 测试覆盖：`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`、`frontend/e2e/test_agent_run_chat_panel.spec.ts`。

**补充批注下载卡规则：**
- 文件：`frontend/components/chat/TaskDownloadMessage.tsx`、`frontend/components/chat/MessageList.tsx`、`frontend/components/chat/ChatPanel.tsx`
- 脆弱原因：只有初次生成下载卡应显示补充批注动作；rewrite/comment_supplement 下载卡继续显示会造成衍生文件重复任务。
- 安全修改：保持 task kind 判断；创建补充批注任务只传会话 id、当前 output file 和模型。
- 测试覆盖：`frontend/__tests__/unit/components/chat/test_message_list.test.tsx`、`frontend/e2e/test_comment_supplement.spec.ts`。

**开发期 API 地址联动：**
- 文件：`frontend/lib/apiBaseUrl.ts`、`frontend/next.config.ts`、`frontend/playwright.config.ts`
- 脆弱原因：`NEXT_PUBLIC_API_URL` 同时影响浏览器 API base URL、Next rewrite 和 dev allowed origins。
- 安全修改：修改 API 地址解析时同步检查三处配置，并补 `frontend/__tests__/unit/lib/test_api_base_url.test.ts`。
- 测试覆盖：`frontend/__tests__/unit/lib/test_api_base_url.test.ts`。

## 扩展限制

**浏览器会话持久化：**
- 当前容量：未设置明确 storage 上限；受浏览器 `sessionStorage` 限制。
- 限制：多会话、多长任务、多过程卡可能达到浏览器 storage 或渲染上限。
- 扩展路径：引入后端会话分页或前端清理策略前，避免把运行中 stream 快照持久化。

**前端 E2E 的真实生成能力：**
- 当前容量：Playwright 可验证 mock 后端下的前端契约。
- 限制：不能验证真实 Word COM 文档生成内容。
- 扩展路径：真实闭环交给后端/Windows Word COM 验收，前端只验证请求、状态、SSE 和下载入口行为。

## 依赖风险

**Windows/WSL 原生依赖：**
- 风险：Next/Tailwind/Playwright 相关原生依赖在 Windows 与 WSL 之间复用可能失败。
- 影响：dev server、lint、build 或 E2E 启动失败。
- 迁移计划：Windows 使用 Windows npm 安装的 `frontend/node_modules/`；WSL 使用 Linux npm 安装，必要时使用单独 `node_modules-wsl/`。

**Next.js 16 / React 19 新版本组合：**
- 风险：生态兼容性对测试环境、Jest polyfill 和第三方包要求较高。
- 影响：升级或新增依赖时可能触发 jsdom/polyfill/ESM 转换问题。
- 迁移计划：变更依赖后先跑 `npm run type-check`、`npm run test`，关注 `frontend/jest.config.ts` 的 transform/moduleNameMapper。

## 缺失或未确认能力

**稳定认证/权限 UI 未检测到：**
- 问题：前端当前没有登录、权限、认证凭据注入或路由守卫事实。
- 阻塞因素：不能在前端判断用户身份或授权范围。

**生产监控/错误上报未检测到：**
- 问题：未检测到 Sentry/APM SDK。
- 阻塞因素：生产端错误追踪依赖外部部署平台或后端日志，前端代码内没有统一上报边界。

## 测试覆盖缺口

**真实 Word COM 生成闭环：**
- 未覆盖内容：真实后端、任务队列、Word/WPS COM 和生成文件内容。
- 文件：`frontend/e2e/`、`frontend/__tests__/`
- 风险：前端测试通过不代表 Word 输出正确。
- 优先级：高，用于发布验收；不适合作为常规前端单元测试。

**模板候选复杂 UI 状态：**
- 未覆盖内容：所有候选禁用原因、刷新缓存、下载代理和选择失败组合。
- 文件：`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/forms/TemplateCandidateDialog.tsx`
- 风险：后端候选策略变化后 UI 可能显示或回填不一致。
- 优先级：中。

**大文件行为回归：**
- 未覆盖内容：`chatStore`、`TenderFormShared`、`ChatPanel` 的所有组合路径。
- 文件：`frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/chat/ChatPanel.tsx`
- 风险：局部修复影响未覆盖的任务/会话分支。
- 优先级：中；新增分支应补窄单测或 mock E2E。

**测试 setup 双入口：**
- 未覆盖内容：`.ts` setup 与 `.js` setup 一致性。
- 文件：`frontend/jest.setup.js`、`frontend/jest.setup.ts`、`frontend/jest.config.ts`
- 风险：修改未生效。
- 优先级：低；除非调整测试环境。

---

*前端风险审计：2026-06-08*

# 前端风险事实地图

**分析日期：** 2026-06-04

**范围：** `frontend/` 当前技术债、脆弱点、安全边界和测试缺口。

## 技术债

**类型身份仍分散注册：**
- 文件：`frontend/types/index.ts`、`frontend/types/api.ts`、`frontend/utils/tenderTypeMapper.ts`、`frontend/components/chat/tenderFormRegistry.ts`、`frontend/components/forms/tenderFormConfig.ts`、`frontend/lib/gngkFormType.ts`、`frontend/lib/formDataConverter.ts`、`frontend/components/chat/ChatPanel.tsx`
- 风险：新增或调整招标类型时容易漏改某一层。
- 安全修改：按 AGENTS 清单同步所有注册点和测试。

**gngk form type 共享 helper 不能被绕过：**
- 文件：`frontend/lib/gngkFormType.ts`、`frontend/lib/formDataConverter.ts`、`frontend/components/chat/ChatPanel.tsx`
- 风险：调用点私自分派会让 generate 和上传文件 rewrite 走不同后端 graph。
- 安全修改：分派规则只改 `resolveGngkFormType()`，并同步覆盖生成转换器与 ChatPanel 上传文件 rewrite 测试。

**会话、URL 和 draft 优先级复杂：**
- 文件：`frontend/app/tender/page.tsx`、`frontend/stores/chatStore.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/utils/tenderTypeMapper.ts`
- 风险：直接改 URL 参数或反转初始化优先级会导致深链、草稿和会话身份错位。
- 安全修改：保持 `draft > URL > default`，深链参数先写 draft，canonical URL 只走 mapper/store helper。

**初次生成字段容易泄漏到 rewrite：**
- 文件：`frontend/components/forms/TenderFormShared.tsx`、`frontend/lib/formDataConverter.ts`、`frontend/components/chat/ChatPanel.tsx`
- 风险：`generation_mode` 或 `comment_generation_mode` 若被带入 rewrite，会让修改链路误用初次生成分支。
- 安全修改：生成转换器负责兜底默认值；ChatPanel 构造 agent run / rewrite 上下文时不得透传这些字段。

**Agent run 只能作为任务创建前置流：**
- 文件：`frontend/components/chat/ChatPanel.tsx`、`frontend/lib/api.ts`、`frontend/types/api.ts`
- 风险：如果前端把 agent run 的 `run_started` / `thinking_stage` 当成后台任务状态，会和 task summary、SSE、取消和下载链路分叉。
- 安全修改：只有 `task_accepted` 才调用 `startTask()`；`needs_input` 和非任务 `done` 只更新普通 AI 消息或思考卡。

## 已知脆弱区

**running task 恢复依赖后端状态确认：**
- 文件：`frontend/hooks/useChatSSE.ts`、`frontend/hooks/useCurrentConversationTaskStatus.ts`、`frontend/hooks/useTaskHeartbeat.ts`
- 风险：如果先连 SSE 再查状态，后端重启或任务丢失会让 UI 长期悬挂。
- 安全修改：404 / `TASK_NOT_FOUND` 收敛为本地中断态。

**SSE 事件是跨端契约：**
- 文件：`frontend/types/api.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/lib/sse.ts`
- 风险：后端新增事件或 payload 字段，前端未同步会丢进度或终态。
- 安全修改：同步 union 类型、底层 named event 注册、解析、store 映射和测试。

**补充批注动作只应出现在初次生成下载卡：**
- 文件：`frontend/components/chat/MessageList.tsx`、`frontend/components/chat/TaskDownloadMessage.tsx`、`frontend/components/chat/ChatPanel.tsx`
- 风险：如果 rewrite 或 comment_supplement 下载卡也允许继续补充批注，会重复基于衍生文件创建任务，且后端 latest `rewrite_state` 校验可能拒绝或产生用户困惑。
- 安全修改：保持 UI 只在 generate 下载卡暴露动作；创建任务时只传会话 id、当前 output_file 和模型，后端负责最新文件校验。

**模板候选安全边界在后端：**
- 文件：`frontend/components/forms/TemplateCandidateDialog.tsx`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/lib/api.ts`
- 风险：前端若直接请求外部 URL，会绕过后端白名单和年份选择规则。
- 安全修改：只使用 `/api/template-candidates*` helper。

**WSL/Windows 原生依赖容易错配：**
- 文件：`frontend/node_modules/`、`scripts/start-dev.ps1`、`scripts/start-dev-wsl.sh`
- 风险：Next/Tailwind/sharp/lightningcss 等原生依赖在 Windows 与 WSL 间复用可能失败。
- 安全修改：WSL 用 Linux npm；Windows 启动用 Windows npm 安装的 node_modules。

**开发期 API 地址同时影响代理和资源来源：**
- 文件：`frontend/lib/apiBaseUrl.ts`、`frontend/next.config.ts`
- 风险：只改浏览器端 API base URL，而忽略 Next rewrite 或 `allowedDevOrigins`，会导致接口代理、HMR 或局域网访问表现不一致。
- 安全修改：修改 `NEXT_PUBLIC_API_URL` 相关逻辑时，同步检查 API client、Next rewrite、allowed dev origins 和 Playwright/dev server 配置。

## 安全关注

- 不在前端文档或 console 中输出 token、私有 URL、客户原文。
- 下载和模板候选选择必须经后端 API。
- 前端没有认证层，不能把 sessionStorage 会话当成安全身份。
- API 错误展示应保留用户可读 message，不泄露内部堆栈。

## 性能与扩展限制

- `sessionStorage` 会话和任务摘要适合单浏览器会话，不是跨设备持久化。
- 长任务日志、LLM 文本和 agent step 快照在浏览器内存中增长，复杂任务可继续关注清理策略。
- 任务/SSE 恢复依赖后端进程内事件缓存，后端重启后只能本地收敛。

## 缺失或未确认能力

- 未确认稳定登录、权限和角色 UI。
- 未确认生产监控或错误上报。
- 未确认复杂任务进度的完整 Playwright E2E 覆盖。
- 未确认离线或跨浏览器会话恢复。

## 测试缺口

- 真实后端 + Word COM 生成链路无法由常规前端 Jest 覆盖。
- 模板候选和 SSE 的复杂 UI 状态仍可补更多 mock E2E。
- gngk 新类型或子类型分派变化时，需要同时覆盖 `gngkFormType`、converter、ChatPanel 上传文件 rewrite、URL、store 会话匹配。
- 智能体过程卡需要继续覆盖 named event、未完成快照缓存、完成态持久化、失败/取消不补普通 task-content 卡。

## 回归风险检查

- 改 API：同步 `types/api.ts`、`lib/api.ts`、后端模型和测试。
- 改 gngk 分派：同步 `gngkFormType`、generate converter 与 ChatPanel 上传文件 rewrite 上下文。
- 改 URL：同步 mapper、store、页面启动和 E2E。
- 改任务 UI：同步 task group store、stream store、SSE hook、agent-step 持久化和消息组件测试。
- 改模板候选：同步 API client、弹窗、表单回填和知识包。

---

*前端风险审计：2026-06-04*

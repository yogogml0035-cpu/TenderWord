# 左侧栏会话展开与当前页面历史行为知识包

## 背景与适用范围
- 适用于 `frontend/` 内招标类型侧栏、当前页面会话列表、按类型切换会话的交互。
- 本知识包对应一次完整方案落地：将 hover 弹层式历史会话改为左侧栏内联展开，并修复“历史会话像被删除”的前端展示截断问题。
- 本次变更不涉及后端历史接口，不改变 `/api`、SSE、下载链路，只调整前端状态语义和侧栏交互。

## 业务规则与约束
- 历史会话仍是“当前页面会话”语义，持久化介质继续使用 `sessionStorage`。
- 左侧栏一次只允许一个招标类型展开，展开态由 `selectedTenderType` 控制；无显式选择时，回退到当前会话所属类型。
- 点击类型头后必须执行：
  1. 先切到该类型的展开态。
  2. 若该类型已有会话，进入 `updatedAt` 最新的一条。
  3. 若该类型没有会话，立即自动创建新会话并进入。
- 展开区必须显示该类型当前页面会话中的全部记录，禁止再用 `.slice(0, 5)` 或类似逻辑截断。
- 左侧栏滚动条属于整个侧栏容器，而不是某个分组内单独滚动。
- 当前类型展开后会把下方类型整体向下推；切换到另一类型时，前一个类型应整体收起。
- 每个展开区顶部保留 `新建对话` 按钮；已有历史会话时也允许显式新建。
- 行内会话仍保留重命名、删除能力，但这些操作入口必须位于左栏会话项内，不再依赖 hover 悬浮历史窗。

## 根因与方案选择
- 用户感知“历史会话会被删掉”的直接根因不是 store 真删除，而是 `NewChatPopup` 里对同类型会话执行了 `.slice(0, 5)`，UI 最多只显示 5 条。
- 旧方案把历史记录绑定在 hover 弹层上，导致：
  - 同类型会话较多时用户无法持续浏览；
  - 新旧类型切换缺乏明确收起/展开结构；
  - “当前页面会话”与“最近 5 条”语义混杂，容易误判为数据丢失。
- 选用“左侧分组内联展开 + 全量列表 + 整栏滚动”的方案，是为了同时满足：
  - 当前页面会话范围不变；
  - 所有同类型会话都能看见；
  - 不引入新的后端依赖；
  - 类型切换行为对用户可预期。

## 输入输出样例
- 输入：`sessionStorage.chat-storage` 中存在 12 条 `xjcg` 会话，`selectedTenderType = 'xjcg'`。
  输出：左侧栏默认展开 `询价采购`，会话列表渲染 12 条，整栏出现滚动条，`国内公开` 类型头被推到下方。
- 输入：点击当前没有任何历史的 `国内公开` 类型。
  输出：立即创建一条 `gngk` 新会话，`currentConversationId` 指向新会话，左栏切换为 `国内公开` 展开态。
- 输入：当前选中 `xjcg` 会话 A，同类型还存在会话 B，且 `B.updatedAt > A.updatedAt`，用户点击 `询价采购` 类型头。
  输出：当前会话切换到 B，而不是保留 A。

## 边界条件与已知坑点
- “最近会话”的判定必须统一使用 `updatedAt`，不能混用 `createdAt`，否则会出现：
  - 类型点击进入一条会话；
  - 删除当前会话后回退到另一条；
  - store selector 返回第三条；
  三处结果不一致。
- `setCurrentConversation` 需要同步 `selectedTenderType`，否则通过 URL 复用、会话项点击、任务完成后的跳转可能导致展开组和当前会话不同步。
- 删除当前会话时，应优先回退到同类型中 `updatedAt` 最新的会话；不要跳到其他类型。
- 当前页面会话是 `sessionStorage` 作用域。关闭页面或新开 page session 后看不到旧会话属于预期，不是回归。
- 如果后续重新引入独立 popup、tooltip 或 hover 列表，必须证明它不会替代当前内联全量列表，否则会回到本次问题。

## 关联代码路径
- `frontend/components/chat/TenderTypeSidebar.tsx`
- `frontend/stores/chatStore.ts`
- `frontend/app/tender/page.tsx`
- `frontend/components/chat/NewChatPopup.tsx`

## 关联测试与验证路径
- 单测：
  - `frontend/__tests__/unit/TenderTypeSidebar.test.tsx`
  - `frontend/__tests__/unit/chatStore.conversationScope.test.ts`
  - `frontend/__tests__/unit/session-persistence.test.ts`
- E2E：
  - `frontend/e2e/url-conversation.spec.ts`
- 推荐验证命令：
  - `cd frontend && npm run test -- --runInBand __tests__/unit/TenderTypeSidebar.test.tsx __tests__/unit/chatStore.conversationScope.test.ts`
  - `cd frontend && npm run type-check`
  - `cd frontend && npm run test:e2e -- url-conversation.spec.ts --reporter=line`

## 回归风险与回滚路径
- 回归风险：
  - 左侧栏宽度增加后可能挤压表单区，需要关注中等宽度视口下的布局。
  - 会话重命名/删除入口改到内联列表后，要检查点击外部关闭菜单、输入框 blur 保存等细节。
  - 如果未来有人把 `selectedTenderType` 当成“仅记录上次点击类型”的弱状态，会破坏展开态和当前会话同步。
- 最短回滚路径：
  - 回退 `frontend/components/chat/TenderTypeSidebar.tsx` 和 `frontend/stores/chatStore.ts` 到变更前版本。
  - 同步回退对应测试和本知识包，避免文档与行为不一致。

## 复用建议
- 后续新增招标类型时，优先复用当前“按类型分组 + 全量当前页面会话 + `updatedAt` 最近项”模型，不要再为新类型单独实现一套 hover 历史窗。
- 若后续接入服务端历史会话，本知识包仍可保留为“前端分组与最近会话选择规则”的准入规范，只需更新持久化来源章节。

# 前端会话范围与侧栏行为知识包

## 背景与适用范围
- 适用于 `frontend/` 内当前页面会话范围、左侧栏展开/切换、URL 与会话双向同步、聊天输入草稿生命周期、排队恢复与当前页面历史语义相关改动。
- 本知识包只描述当前前端已经落成的行为，不推断未来服务端历史形态。

## 当前真源
- 会话与草稿状态：`frontend/stores/chatStore.ts`
- 当前页面深链与心跳：`frontend/app/tender/page.tsx`
- 类型侧栏：`frontend/components/chat/TenderTypeSidebar.tsx`
- 表单 URL/草稿初始化：`frontend/components/forms/TenderFormShared.tsx`
- 聊天发送、edit、rewrite 排队恢复：`frontend/components/chat/ChatPanel.tsx`
- canonical URL 构造：`frontend/utils/tenderTypeMapper.ts`

## 当前页面会话范围
- 当前页面会话仍是前端本地状态，不是服务端历史真源。
- 当前页面相关状态继续使用 `sessionStorage` 持久化：
  - 聊天会话：`chat-storage`
  - 页面历史：`tender-history-storage`
  - 任务会话：`chat-task-session-storage`
- 新开标签页或新浏览器窗口看不到旧页面会话，属于当前设计，不是 bug。

## 左侧栏与会话切换规则
- 左侧栏展开态当前由 `selectedTenderType` 控制；若为空，则回退到当前会话所属类型。
- 点击类型头时当前行为固定为：
  - 设置 `selectedTenderType`
  - 若该类型已有会话，切到 `updatedAt` 最新的一条
  - 若该类型没有会话，立即创建新会话
- 每个类型分组当前渲染该类型下的全部会话，不再按数量截断。
- 整体滚动条属于整个侧栏容器，当前没有为单个类型分组单独创建滚动区。
- 删除当前会话时，优先回退到同类型里 `updatedAt` 最新的一条；若同类型为空，再回退到全局剩余会话。

## URL 与会话双向同步

### 当前同步入口
- `setCurrentConversation()` 会在切换完成后调用 `syncUrlToCurrentConversation()`。
- 手动新建空白会话时，`TenderTypeSidebar.tsx` 会直接调用 `syncBrowserUrlToConversation({ tenderType })`，把 URL 重置为该类型 canonical 默认值。
- 表单内切换 `tender_lx` / `fund_lx` 时，`TenderFormShared.tsx` 会调用 `syncBrowserUrlToConversation(...)` 全量重写 URL。

### 当前禁止做法
- 不允许直接 patch 单个 query 参数。
- 任何 URL 变更都应通过：
  - `buildCanonicalSearchParams`
  - `syncBrowserUrlToConversation`
  - `syncUrlToCurrentConversation`

### 深链命中规则
- `frontend/app/tender/page.tsx` 会在 hydration 后解析 URL，并按类型命中或创建当前会话。
- 对 `gngk`，深链 dedup key 会包含：
  - `tenderType`
  - `tenderno`
  - `tender_lx`
  - `fund_lx`
- 新创建的 `gngk` 深链会话会把 URL 中的 `tender_lx` / `fund_lx` 先写入 draft，再设置当前会话。

## 表单初始化优先级
- `TenderFormShared.tsx` 当前明确采用：
  - `draft > URL > default`
- 这条优先级同时作用于：
  - `tender_lx`
  - `fund_lx`
  - 部分表单初始状态
- 因此若希望 URL 参数在已有会话中生效，必须先由上层把值写入 draft，不能通过反转优先级兜底。

## `gngk` 会话 identity
- `findGngkConversationByIdentity()` 当前按四维精确匹配：
  - `tenderType`
  - `tenderno`
  - `tender_lx`
  - `fund_lx`
- 缺省草稿值当前按 `0/0` 处理。
- 同一 `tenderno` 下，货物/服务和资金性质不同的会话允许并存。

## 聊天输入与排队恢复生命周期

### `chat_input`
- `ChatInput` 是受控组件，真值来自 `conversationDraft.chat_input`。
- 正常聊天发送时，`ChatPanel.handleSendMessage()` 会在请求发出后立刻把 `chat_input` 清空。
- 显式 edit 任务创建时，也会在创建占位消息后立即清空 `chat_input`。

### `pending_rewrite_prompt` / `pending_edit_prompt`
- 这两个字段当前只承担“排队阶段恢复输入”的职责，不是正常发送后的延迟清空机制。
- rewrite：
  - 只有在 `/api/user/stream` 返回 `task_accepted` 后，才会写入 `pending_rewrite_prompt` 与 `pending_rewrite_task_id`
  - 排队阶段取消任务时，会把该 prompt 回填到 `chat_input`
  - 任务结束后，若不再处于活动态，这两个字段会被清空
- edit：
  - `createEditTask()` 成功后写入 `pending_edit_prompt` 与 `pending_edit_task_id`
  - 排队阶段取消任务时，会把该 prompt 回填到 `chat_input`
  - 成功完成时，会把最新输出文件回写到 `edit_file`
  - 失败或非成功终态时，会把 `pending_edit_prompt` 重新回填到 `chat_input`

### 后端重启恢复
- `frontend/app/tender/page.tsx` 会定期向 `/api/conversations/*/heartbeat` 发送页面心跳。
- 若检测到实例 ID 变化，`handleBackendRestart()` 会把活动任务转成前端可恢复状态，相关恢复逻辑仍以 `pending_*` 字段和任务摘要为依据。

## 关联代码路径
- `frontend/stores/chatStore.ts`
- `frontend/app/tender/page.tsx`
- `frontend/components/chat/TenderTypeSidebar.tsx`
- `frontend/components/chat/ChatPanel.tsx`
- `frontend/components/forms/TenderFormShared.tsx`
- `frontend/utils/tenderTypeMapper.ts`
- `frontend/stores/historyStore.ts`
- `frontend/stores/chatTaskSessionStore.ts`

## 关联测试与验证路径
- `frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`
- `frontend/__tests__/unit/stores/test_chat_store_task_messages.test.ts`
- `frontend/__tests__/unit/stores/test_session_persistence.test.ts`
- `frontend/__tests__/unit/components/chat/test_tender_type_sidebar.test.tsx`
- `frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`
- `frontend/__tests__/unit/app/test_chat_page.test.tsx`
- `frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`
- `frontend/e2e/test_url_conversation.spec.ts`

## 回归风险与维护建议
- 若未来有人把 `selectedTenderType` 退化成“仅记录上次点击的标签”，会直接破坏展开组与当前会话同步。
- 若绕过 `syncBrowserUrlToConversation` 手工 patch URL，极易留下与当前会话不一致的残余参数。
- 若把 `pending_*_prompt` 改成普通发送成功后的长期缓存，会重新引入“消息已受理但输入框不清空”的回归。
- 若调整 `TenderFormShared` 初始化逻辑，必须同时验证：
  - 新建空白会话
  - URL 深链创建会话
  - 已有会话恢复草稿

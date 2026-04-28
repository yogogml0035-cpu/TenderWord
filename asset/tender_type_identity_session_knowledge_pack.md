# 招标类型身份与前端会话知识包

## 背景与范围

本包适用于新增或修改招标类型，以及影响 `xjcg` / `gngk` / `gjgk` identity、URL 判型、`form_type` 分派、anchor 默认值、graph/state/node 绑定、前端表单注册、当前页面会话与草稿生命周期的改动。

本包把类型身份和前端会话放在同一个主题里维护，因为 `gngk` 的 `tender_lx + fund_lx` 同时决定后端 `form_type`、canonical URL、会话去重和表单默认值。

## 当前真源

- 后端类型与运行态：`backend/models/generate.py`、`backend/config/tender_config.py`、`backend/services/document_service.py`
- graph / node 绑定：`backend/graphs/`、`backend/nodes/`
- 前端 URL 与 canonical 化：`frontend/utils/tenderTypeMapper.ts`
- 表单到后端请求转换：`frontend/lib/formDataConverter.ts`
- chat/edit 任务类型分派：`frontend/components/chat/ChatPanel.tsx`
- 表单注册与默认锚点：`frontend/components/chat/tenderFormRegistry.ts`、`frontend/components/forms/tenderFormConfig.ts`、`frontend/components/forms/TenderFormShared.tsx`
- 当前页面会话与任务恢复：`frontend/stores/chatStore.ts`、`frontend/app/tender/page.tsx`

## 类型身份矩阵

### 前端 UI 类型

- `xjcg`
- `gngk`
- `gjgk`

### 后端 `FormType`

- `xjcg_tender`
- `gngk_hw_zc_tender`
- `gngk_hw_cz_tender`
- `gngk_fw_zc_tender`
- `gngk_fw_cz_tender`
- `gjgk_tender`

### 运行态 `tender_type`

`DocumentService` 当前通过 `request.form_type.value.replace("_tender", "")` 生成运行态：

- `xjcg`
- `gngk_hw_zc`
- `gngk_hw_cz`
- `gngk_fw_zc`
- `gngk_fw_cz`
- `gjgk`

`backend/config/tender_config.py` 的 `get_tender_type_family()` 是 family 收敛真源：所有 `gngk_*` 运行态归并为 `gngk`，其它类型保持自身名称。

## URL 与会话身份

### 前端判型

- `frontend/utils/tenderTypeMapper.ts` 当前只用 `purchase_method` 判定前端 `TenderType`：
  - `5 -> xjcg`
  - `2 -> gngk`
  - `0 -> gjgk`
- `tender_lx` / `fund_lx` 不参与前端大类判型，只参与 `gngk` 的会话 identity、canonical URL 和后端 `form_type` 分派。

### Canonical URL

- canonical URL 统一经 `buildCanonicalSearchParams()`、`syncBrowserUrlToConversation()` 和 store 层 `syncUrlToCurrentConversation()` 构造或重写。
- 禁止直接 patch 单个 query 参数。
- 当前 canonical 规则：
  - `xjcg`: `tender_lx=0&purchase_method=5&fund_lx=0`
  - `gngk`: `purchase_method=2`，保留合法 `tender_lx` / `fund_lx`，缺省回退 `0/0`
  - `gjgk`: `tender_lx=0&purchase_method=0&fund_lx=1`

### `gngk` 会话 identity

- `frontend/stores/chatStore.ts` 的 `findGngkConversationByIdentity()` 以四维精确匹配：
  - `tenderType = gngk`
  - `tenderno`
  - `tender_lx`
  - `fund_lx`
- 同一 `tenderno` 下，货物/服务或资金性质不同的会话允许并存。
- URL 深链创建 `gngk` 会话时，必须先把 URL 中的 `tender_lx` / `fund_lx` 写入 draft，再设置当前会话，保证 `TenderFormShared` 的 `draft > URL > default` 优先级仍成立。

## 后端 anchor / graph / node 现实

### Anchor 默认值

`backend/config/tender_config.py` 当前 anchor config 为：

| 运行态 | before_text | after_text |
| --- | --- | --- |
| `xjcg` | `第三章  采购需求` | `第四章  响应文件有关格式` |
| `gngk_hw_zc` | `第三章 招标内容及要求` | `第四章 投标文件有关格式` |
| `gngk_hw_cz` | `第四章  招标需求` | `第五章  评标方法与程序` |
| `gngk_fw_zc` | `第三章 招标内容及要求` | `第四章 投标文件有关格式` |
| `gngk_fw_cz` | `第三章 招标内容及要求` | `第四章 投标文件有关格式` |
| `gjgk` | `技术规格及要求` | `附件1：投标文件封面（格式）` |

- generate 与 edit 默认锚点读取 `get_default_anchor_texts()`。
- rewrite 当前还保留 `DocumentService.REWRITE_DEFAULT_ANCHORS` 快照回退，内容必须与 `tender_config.py` 保持同步。

### Graph 与运行时分流

- `XjcgTenderGraph` 使用 common word 节点，replacement 使用 `xjcg_get_replacements`。
- `GngkHwZcTenderGraph` 使用 common delete / update，replacement 使用 `gngk_hw_zc_get_replacements`。
- `GngkHwCzTenderGraph` 当前继承 `GngkHwZcTenderGraph`。
- `GngkFwZcTenderGraph` 当前覆盖服务特化的 delete / replacement / update。
- `GngkFwCzTenderGraph` 当前继承 `GngkHwZcTenderGraph`，没有额外覆盖。
- `GjgkTenderGraph` 使用 `gjgk_*` 专属 delete / replacement / update，并保留 post-update hook。
- `backend/nodes/skills_nodes/tender_aware_word_dispatch.py` 当前只 special-case `gjgk` 与 `gngk_fw_zc`；其它运行态在 rewrite / edit 中回落 common delete / update。

### Replacement 与 profile

- 公开招标 family 的共享 replacement 逻辑在 `backend/nodes/gngk_word_nodes/gngk_get_replacements.py`。
- `gngk_get_replacements.py` 只提供公共 extractor / replacement field 构建器，不作为 graph 节点兼容别名。
- 当前 graph wrapper 真名是 `gngk_hw_zc_get_replacements` 与 `gngk_fw_zc_get_replacements`。
- 受保护字段 profile 与 `direct_replace` 边界详见 `asset/shared_runtime_word_skill_knowledge_pack.md`。

## 前端表单与任务分派

### `gngk` 到后端 `form_type`

`frontend/lib/formDataConverter.ts` 与 `frontend/components/chat/ChatPanel.tsx` 当前都按同一规则计算 `gngk` 的 `form_type`：

| `tender_lx` | `fund_lx` | 后端 `form_type` |
| --- | --- | --- |
| `0` | `0` | `gngk_hw_zc_tender` |
| `0` | `1` | `gngk_hw_cz_tender` |
| `1` | `0` | `gngk_fw_zc_tender` |
| `1` | `1` | `gngk_fw_cz_tender` |

任一处改动都必须双向同步并补测试。

### `TenderFormShared` 初始化与模式缓存

- 初始化优先级固定为 `draft > URL > default`。
- `gngk` 货物模式按 `fund_lx` 维护两套 `gngk_insertion_configs`。
- `gngk` 服务模式跨 `fund_lx` 共享 `gngk_service_insertion_config`。
- 服务模式默认锚点为 `第三章 招标内容及要求` -> `第四章 投标文件有关格式`。
- 财政货物默认锚点为 `第四章  招标需求` -> `第五章  评标方法与程序`。
- `generation_style` 是 generate 表单态：货物默认 `template`，服务默认 `param`；后端只在 generate runtime 使用该字段。

## 当前页面会话生命周期

- 当前页面会话是前端本地状态，不是服务端历史真源。
- 当前页面相关状态继续使用 `sessionStorage`：`chat-storage`、`tender-history-storage`、`chat-task-session-storage`。
- 左侧栏展开态由 `selectedTenderType` 控制；若为空，回退到当前会话所属类型。
- 点击类型头时，若该类型已有会话则切到 `updatedAt` 最新的一条，否则立即创建新会话。
- 删除当前会话时，优先回退到同类型最新会话；同类型为空再回退到全局剩余会话。

## 聊天输入与排队恢复

- `chat_input` 在普通聊天发送或显式 edit 任务创建后立即清空。
- `pending_rewrite_prompt` / `pending_edit_prompt` 只用于排队阶段取消或失败后的恢复回填，不是正常发送后的延迟清空机制。
- rewrite 只有在 `/api/user/stream` 返回 `task_accepted` 后写入 pending rewrite 字段。
- edit 在 `createEditTask()` 成功后写入 pending edit 字段；成功完成时把最新输出文件回写到 `edit_file`。
- `frontend/app/tender/page.tsx` 的后端重启恢复继续以 pending 字段和任务摘要为依据。

## 新增或修改类型的同步清单

- 后端至少检查：`backend/models/generate.py`、`backend/config/tender_config.py`、`backend/services/document_service.py`、`backend/graphs/`、`backend/states/`、`backend/nodes/`。
- 前端至少检查：`frontend/types/api.ts`、`frontend/utils/tenderTypeMapper.ts`、`frontend/lib/formDataConverter.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/tenderFormRegistry.ts`、`frontend/components/forms/tenderFormConfig.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/stores/chatStore.ts`。
- 若类型影响 rewrite / edit 的 Word 路由，还必须检查 `backend/nodes/skills_nodes/tender_aware_word_dispatch.py`。
- 改完类型或会话边界后，必须同步更新本知识包和 `asset/README.md`。

## 关联测试与验证入口

- 后端类型与 graph：`backend/tests/graphs/test_gngk_tender_graph.py`、`backend/tests/graphs/test_gjgk_tender_graph.py`、`backend/tests/config/test_tender_config_protected_fields.py`
- 后端服务装配：`backend/tests/services/test_document_service_initial_state.py`
- 后端运行时分发：`backend/tests/nodes/test_tender_aware_word_dispatch.py`
- 前端映射与注册：`frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`、`frontend/__tests__/unit/lib/test_form_data_converter.test.ts`、`frontend/__tests__/unit/components/chat/test_tender_form_registry.test.tsx`
- 前端会话与表单：`frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`、`frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`、`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`
- URL E2E：`frontend/e2e/test_url_conversation.spec.ts`

## 回归风险

- 类型元数据仍分散在前后端多个位置；新增类型不能只改一侧。
- `tender_config.py` 与 `DocumentService.REWRITE_DEFAULT_ANCHORS` 当前存在双份默认锚点语义，只改其中一处会导致 rewrite 与 generate / edit 漂移。
- `gngk_fw_cz` 当前没有像 `gngk_fw_zc` 那样在 skill runtime 专门分发；若业务希望两者一致，必须显式改代码与测试。
- 绕过 canonical URL helper 手工 patch 参数，容易留下与当前会话不一致的残余 URL。
- 反转 `TenderFormShared` 的 `draft > URL > default` 优先级，会破坏已有会话草稿恢复与深链创建的约定。

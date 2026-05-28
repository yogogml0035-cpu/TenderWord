# 招标类型身份与前端会话知识包

## 背景与范围

本包适用于新增或修改招标类型，以及影响 `xjcg` / `gngk` / `gjgk` identity、URL 判型、`form_type` 分派、anchor 默认值、graph/state/node 绑定、前端表单注册、当前页面会话与草稿生命周期的改动。

本包把类型身份和前端会话放在同一个主题里维护，因为 `gngk` 的 `tender_lx + fund_lx` 同时决定后端 `form_type`、canonical URL、会话去重和表单默认值。

## 当前真源

- 后端类型与运行态：`backend/models/generate.py`、`backend/config/tender_config.py`、`backend/services/document_service.py`
- graph / node 绑定：`backend/graphs/`、`backend/nodes/`
- 前端 URL 与 canonical 化：`frontend/utils/tenderTypeMapper.ts`
- `gngk` 后端 `form_type` 分派：`frontend/lib/gngkFormType.ts`
- 表单到后端请求转换：`frontend/lib/formDataConverter.ts`
- chat/edit 任务创建：`frontend/components/chat/ChatPanel.tsx`
- 表单注册与默认锚点：`frontend/components/chat/tenderFormRegistry.ts`、`frontend/components/forms/tenderFormConfig.ts`、`frontend/components/forms/TenderFormShared.tsx`
- 当前页面会话、智能体过程卡与任务恢复：`frontend/stores/chatStore.ts`、`frontend/hooks/useChatSSE.ts`、`frontend/components/chat/TaskContentMessage.tsx`、`frontend/app/tender/page.tsx`

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
- `TenderFormShared` 在“获取信息”成功后，会继续用返回的 `type` 回写当前页面按钮态：
  - `tender_lx` 决定货物 / 工程 / 服务按钮，并在信息卡显示为“标的类型”
  - `fund_lx` 决定自筹 / 财政按钮
  - `purchase_method` 决定是否把当前会话 / 表单切到 `xjcg`、`gngk` 或 `gjgk`
- 这次回写只在“获取信息”成功完成的当次校正里生效一次；校正完成后，货物 / 工程 / 服务与自筹 / 财政按钮仍然允许用户继续手动切换，只有再次点击“获取信息”才会重新按接口结果校验。
- `/api/tender` 现在还会透传 `data.ifdzpt2` 与 `data.ifzgcg` 给前端；两者都不参与大类判型。`ifdzpt2` 只参与“获取信息”成功当次的 `gngk` 锚点修正；`ifzgcg` 同时参与货物财政的锚点修正与 `form_type` / graph 分派。

### Canonical URL

- canonical URL 统一经 `buildCanonicalSearchParams()`、`syncBrowserUrlToConversation()` 和 store 层 `syncUrlToCurrentConversation()` 构造或重写。
- 禁止直接 patch 单个 query 参数。
- 当前 canonical 规则：
  - `xjcg`: `tender_lx=0&purchase_method=5&fund_lx=0`
  - `gngk`: canonical 仍写 `purchase_method=2`，保留合法 `tender_lx` / `fund_lx`，缺省回退 `0/0`
  - `gjgk`: `tender_lx=0&purchase_method=0&fund_lx=1`

### `gngk` 会话 identity

- `frontend/stores/chatStore.ts` 的 `findGngkConversationByIdentity()` 以四维精确匹配：
  - `tenderType = gngk`
  - `tenderno`
  - `tender_lx`
  - `fund_lx`
- 同一 `tenderno` 下，货物/工程/服务或资金性质不同的会话允许并存。
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
- `GngkHwCzTenderGraph` 当前仍继承 `GngkHwZcTenderGraph` 的共享主干，但首次生成已显式覆盖为 `gngk_hw_cz_delete_tender_param` + `gngk_hw_cz_update_word` 的 direct replace 路径，replacement 仍复用 `gngk_hw_zc_get_replacements`。
- `GngkFwZcTenderGraph` 当前覆盖服务特化的 delete / replacement / update。
- `GngkFwCzTenderGraph` 当前继承 `GngkHwZcTenderGraph`，没有额外覆盖。
- `GjgkTenderGraph` 使用 `gjgk_*` 专属 delete / replacement / update，并保留 post-update hook。
- `backend/nodes/skills_nodes/tender_aware_word_dispatch.py` 当前只 special-case `gjgk` 与 `gngk_fw_zc`；`gngk_hw_cz` 当前没有扩张到 rewrite / edit，仍在 skill runtime 中回落 common delete / update。

### Replacement 与 profile

- 公开招标 family 的共享 replacement 逻辑在 `backend/nodes/gngk_word_nodes/gngk_get_replacements.py`。
- `gngk_get_replacements.py` 只提供公共 extractor / replacement field 构建器，不作为 graph 节点兼容别名。
- 当前 graph wrapper 真名是 `gngk_hw_zc_get_replacements` 与 `gngk_fw_zc_get_replacements`。
- `gngk_hw_zc_get_replacements` 当前保持薄 wrapper，直接复用 `build_gngk_common_extractors()` 与 `build_gngk_common_replacement_fields()`；不要为货物自筹重新插入 `project_content_v1` 或 `similar_project_performance_date` 这两个历史特殊字段。
- 公开招标 family 的 `buyer_name` 旧值支持 `采购人：...` 与 `招标人：...` 双标签；命中后在采购代理、招标代理、地址、联系人、电话等后续标签前截断。
- `investment` 是预算金额替换字段，旧值只能来自显式 `预算金额：...` 行；`最高限价` 不作为 `investment` 旧值来源。替换对只提供旧数字到新数字，正文中同数字的全局替换范围继续由 `replace_content` 负责。
- `investment` 新值格式化由 `ReplacementFieldSpec.new_value_formatter` 绑定 `format_public_tender_investment_value()` 完成：`140.0` 归一为 `140`，`140.5` / `140.05` 等有效小数保持。
- `project_zbr_xbr` 旧值支持 `项目联系人：...` 与 `联系人：...`，并在 `电话`、`电 话`、`电　话`、`联系电话`、`联系方式`、`传真`、`邮箱`、`电子邮箱` 等联系方式标签前停止；修改该边界时要同时锁定 `zbr_xbr_tel` 与 `zbr_pinyin` 既有提取结果。
- 采购代理机构范围内的 `邮编：` 只能作为当前代理机构块的二级锚点；若它出现在联系人标签之后，应视为后文投标人格式等无关标记，不能把 `project_zbr_xbr` 搜索范围跳到后文。
- 受保护字段 profile 与 `direct_replace` 边界详见 `asset/shared_runtime_word_skill_knowledge_pack.md`。

## 前端表单与任务分派

### `gngk` 到后端 `form_type`

`frontend/lib/gngkFormType.ts` 是 generate 与 edit 共享的 `gngk` 后端 `form_type` 分派真源，`frontend/lib/formDataConverter.ts` 与 `frontend/components/chat/ChatPanel.tsx` 都必须调用它：

| `tender_lx` | `fund_lx` | 附加条件 | 后端 `form_type` |
| --- | --- | --- | --- |
| `0` | `0` | - | `gngk_hw_zc_tender` |
| `0` | `1` | `tender_data.ifzgcg === 2` | `gngk_hw_zc_tender` |
| `0` | `1` | `tender_data.ifzgcg !== 2` 或缺失 | `gngk_hw_cz_tender` |
| `1` | `0` | - | `gngk_fw_zc_tender` |
| `1` | `1` | - | `gngk_fw_cz_tender` |
| `2` | `0` | - | `gngk_fw_zc_tender` |
| `2` | `1` | - | `gngk_fw_cz_tender` |

- 当前仓库仍没有独立 `工程` graph / `form_type`；`tender_lx=1` 的工程模式在 generate / edit 中临时复用现有 `gngk_fw_*` 服务链路。
- 当前未新增独立工程前端类型；国内公开 `货物 + 财政 + ifzgcg=2` 仍保持 URL、会话身份、按钮态与请求业务资金字段为财政，但 generate / edit 的 `form_type` 映射到 `gngk_hw_zc_tender`，复用货物自筹 graph。

分派规则只改 `resolveGngkFormType()`；调用点保持复用 helper，并同步补生成转换器与 ChatPanel edit 测试。

### `TenderFormShared` 初始化与模式缓存

- 初始化优先级固定为 `draft > URL > default`。
- `gngk` 货物模式按 `fund_lx` 维护两套 `gngk_insertion_configs`。
- `gngk` 的 `generation_style` 按 `tender_lx` 维护 `gngk_generation_styles`：货物、工程、服务首次进入都默认 `template`，用户手改后切走再切回，应恢复该标的类型上次选择；旧草稿里的单字段 `generation_style` 只作为当前标的类型的兼容回填。
- `gngk` 工程模式按 `fund_lx` 分别维护 `gngk_engineering_insertion_configs`；每个资金组合首次进入时走工程默认锚点，手改后切回恢复用户自己的值。
- `gngk` 服务模式按 `fund_lx` 分别维护 `gngk_service_insertion_configs`；旧草稿里的 `gngk_service_insertion_config` / `insertion_config` 只作为当前服务资金组合的兼容回填，不再跨资金类型复用。
- `gngk` 的每个“标的类型 + 资金类型”组合首次进入时使用各自默认锚点；用户手改后，再切回该组合时恢复用户自己的值，不再重新套默认。
- `gngk` 切换标的类型或资金类型时，只有 `manual_insertion_config_scope_keys` 命中的组合才视为用户锁定值；旧的已知自动默认锚点缓存不能阻止按目标模式默认锚点重新计算，避免“获取信息”后把后续切换状态锁死。
- `gngk` 顶部“标的类型”和“资金类型”可能在同一个 render 周期内被连续点击；切换计算必须读取乐观当前值，而不能只依赖上一轮 `initialDraft` / props，否则会出现按钮已是“货物 + 财政”但锚点仍按“服务 + 自筹”计算。
- 国内公开在“获取信息”成功且接口返回类型为“服务 + 自筹 + ifdzpt2 = 2”时，当次回填会把服务模式 `after_text` 从 `第四章 投标文件有关格式` 提升为 `第四章 合同条款`；后续用户切换标的类型或资金类型时，不再继续把 `ifdzpt2` 作为默认锚点输入，而是回到对应模式默认值或用户手动值。
- 判断“手改后的锚点”不能只看文本值是否等于某个已知默认值，因为用户可能手动输入另一个场景的默认文案；前端草稿用 `manual_insertion_config_scope_keys` 按 `tenderType + tender_lx + fund_lx` 标记用户已手改的组合，命中后 `ifdzpt2` / `ifzgcg` 默认锚点修正不得再覆盖。
- 工程模式默认锚点为 `第三章 招标内容及要求` -> `第四章 投标文件有关格式`，即使 `ifdzpt2 = 2` 也不会切到 `第四章 合同条款`。
- 服务模式默认锚点为 `第三章 招标内容及要求` -> `第四章 投标文件有关格式`（若命中上一条服务合同条款规则，则改为 `第四章 合同条款`）。
- 财政货物默认锚点为 `第四章  招标需求` -> `第五章  评标方法与程序`；若“获取信息”成功且接口返回类型为“货物 + 财政 + ifzgcg = 2”，当次回填按货物自筹默认锚点 `第三章 招标内容及要求` -> `第四章 投标文件有关格式` 显示，且 generate / edit 走 `gngk_hw_zc_tender` graph。用户后续切出再切回“货物 + 财政”时，不再继续受 `ifzgcg` 影响，恢复财政货物默认锚点，除非该组合已被用户手动编辑锁定。
- `generation_style` 是 generate 表单态：货物、工程、服务默认都为 `template`；后端只在 generate runtime 使用该字段。
- `generation_mode` 是全局 generate 表单态，不参与 tender identity，也不按 `gngk` 的 `tender_lx` / `fund_lx` 分桶。新会话和旧草稿缺省值都是 `workflow`，用户在高级设置切换到 `agent` 后写入当前 `ConversationFormDraft.generation_mode`。
- `TenderFormShared` 的“生成方式”控件位于高级设置，选项为“工作流”和“智能体”；提交 generate 时 `BaseTenderFormData.generation_mode` 进入 `formDataConverter`，未显式选择时 converter 也要兜底为 `workflow`。
- rewrite / edit 请求 payload 不包含 `generation_mode`。如果聊天草稿中保留 `generation_mode: "agent"`，`ChatPanel` 创建 rewrite / edit 任务时也不能透传它。

## 当前页面会话生命周期

- 当前页面会话是前端本地状态，不是服务端历史真源。
- 当前页面相关状态继续使用 `sessionStorage`：`chat-storage`、`tender-history-storage`、`chat-task-session-storage`。
- 左侧栏展开态由 `selectedTenderType` 控制；若为空，回退到当前会话所属类型。
- 点击类型头时，若该类型已有会话则切到 `updatedAt` 最新的一条，否则立即创建新会话。
- 删除当前会话时，优先回退到同类型最新会话；同类型为空再回退到全局剩余会话。
- 智能体过程卡是会话历史消息，不是运行时临时 stream。`agent_step` 会在 `chat-storage` 里保存为 `metadata.messageKind = "agent-step"` 的 AI 消息，刷新后随会话消息恢复。
- `agent-step` 消息不纳入旧 `taskMessageMap` 的 `task-log` / `task-content` / `task-download` 三卡分组；done 事件仍只负责生成下载入口卡。
- 审核卡按轮次聚合在同一 audit 消息的 `agentStepAuditRounds` 中；revision 按轮次生成或更新可区分的消息。智能体过程卡标题以 `metadata.agentStepNode` 为准，分别显示 `generate_agent`、`verify_agent`、`host_agent`，不要再用“AI 初稿内容 / 智能体审核意见 / AI 修改内容”这类按 step_type 推导的标题。

## 聊天输入与排队恢复

- `chat_input` 在普通聊天发送或显式 edit 任务创建后立即清空。
- `pending_rewrite_prompt` / `pending_edit_prompt` 只用于排队阶段取消或失败后的恢复回填，不是正常发送后的延迟清空机制。
- rewrite 只有在 `/api/user/stream` 返回 `task_accepted` 后写入 pending rewrite 字段。
- edit 在 `createEditTask()` 成功后写入 pending edit 字段；成功完成时把最新输出文件回写到 `edit_file`。
- `frontend/app/tender/page.tsx` 的后端重启恢复继续以 pending 字段和任务摘要为依据。
- 后端重启或 `TASK_NOT_FOUND` 触发 stale task 恢复时，不能只新增错误日志；同一 `taskId` 下仍处于 `generating` 的历史消息也必须转为 `error` 并写入 `localTaskReason=backend_restart`，避免 UI 同时显示“已中断”和旧生成中状态。
- 从 `sessionStorage` 恢复出的 `running` task 只是本地快照，SSE 连接前必须先用任务状态接口确认任务仍存在；若状态接口返回 `TASK_NOT_FOUND` / 404，应走 stale task 恢复而不是先连 `/api/stream/{taskId}`。
- 任务恢复测试 fixture 需要同时覆盖 `conversation.currentTaskId`、`activeTaskIds`、`taskSummaries` 与消息 `taskId`，这四者共同组成当前前端恢复链路的可观察任务身份。

## 新增或修改类型的同步清单

- 后端至少检查：`backend/models/generate.py`、`backend/config/tender_config.py`、`backend/services/document_service.py`、`backend/graphs/`、`backend/states/`、`backend/nodes/`。
- 前端至少检查：`frontend/types/api.ts`、`frontend/utils/tenderTypeMapper.ts`、`frontend/lib/formDataConverter.ts`、`frontend/components/chat/ChatPanel.tsx`、`frontend/components/chat/tenderFormRegistry.ts`、`frontend/components/forms/tenderFormConfig.ts`、`frontend/components/forms/TenderFormShared.tsx`、`frontend/stores/chatStore.ts`。
- 若类型影响 rewrite / edit 的 Word 路由，还必须检查 `backend/nodes/skills_nodes/tender_aware_word_dispatch.py`。
- 改完类型或会话边界后，必须同步更新本知识包和 `asset/README.md`。

## 关联测试与验证入口

- 后端类型与 graph：`backend/tests/graphs/test_gngk_tender_graph.py`、`backend/tests/graphs/test_gjgk_tender_graph.py`、`backend/tests/config/test_tender_config_protected_fields.py`
- 后端公开招标 replacement：`backend/tests/nodes/test_gngk_replacements_extractors.py`
- 后端服务装配：`backend/tests/services/test_document_service_initial_state.py`
- 后端运行时分发：`backend/tests/nodes/test_tender_aware_word_dispatch.py`
- 前端映射与注册：`frontend/__tests__/unit/utils/test_tender_type_mapper.test.ts`、`frontend/__tests__/unit/lib/test_form_data_converter.test.ts`、`frontend/__tests__/unit/components/chat/test_tender_form_registry.test.tsx`
- 前端会话与表单：`frontend/__tests__/unit/stores/test_chat_store_conversation_scope.test.ts`、`frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`、`frontend/__tests__/unit/components/chat/test_chat_panel.test.tsx`
- 前端任务消息恢复：`frontend/__tests__/unit/stores/test_chat_store_task_messages.test.ts`
- 前端 SSE 与智能体过程卡：`frontend/__tests__/unit/hooks/test_use_chat_sse.test.tsx`、`frontend/__tests__/unit/lib/test_sse.test.ts`、`frontend/__tests__/unit/types/test_api_sse_agent_step.test.ts`
- 智能体用户可见闭环 E2E：`frontend/e2e/test_generation_mode_agent.spec.ts`
- URL E2E：`frontend/e2e/test_url_conversation.spec.ts`

## 回归风险

- 类型元数据仍分散在前后端多个位置；新增类型不能只改一侧。
- `gngk_hw_zc` replacement 边界回归时，容易把服务/国际公开历史字段误带回货物自筹；必须确认 `project_content_v1` 与 `similar_project_performance_date` 不在提取器、字段列表或模拟替换结果中。
- 预算金额提取不能为了覆盖正文最高限价而反向读取 `最高限价` 行；同金额联动应保持在后续全局替换机制内。
- 联系人姓名与联系方式可能被 Word 文本读成同一行；`project_zbr_xbr` 需要依赖停止标签截断，而不是假设换行一定存在。
- 公开招标模板后文常有“投标人基本情况简介格式”里的 `邮编：`、`电话/传真：` 空表字段；联系人提取的二级锚点必须限制在当前代理机构块内，避免跳过首页或前附表的真实联系人。
- `tender_config.py` 与 `DocumentService.REWRITE_DEFAULT_ANCHORS` 当前存在双份默认锚点语义，只改其中一处会导致 rewrite 与 generate / edit 漂移。
- `gngk_fw_cz` 当前没有像 `gngk_fw_zc` 那样在 skill runtime 专门分发；若业务希望两者一致，必须显式改代码与测试。
- 绕过 canonical URL helper 手工 patch 参数，容易留下与当前会话不一致的残余 URL。
- 反转 `TenderFormShared` 的 `draft > URL > default` 优先级，会破坏已有会话草稿恢复与深链创建的约定。
- 把 `generation_mode` 做成 `gngk_generation_styles` 那样的分桶字段会改变当前会话草稿语义；它当前是会话级全局选择，只影响下一次初次 generate。
- 新增或改名 SSE named event 时，除了 `useChatSSE`，还必须更新 `frontend/lib/sse.ts` 的 `EventSource.addEventListener` 注册，否则真实浏览器不会收到该事件。

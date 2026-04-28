# 模板候选与智能抽取知识包

## 背景与范围

本包适用于共享表单中的“智能抽取模板”能力，覆盖模板候选获取、同优先级 AI 重排、下载代理、文件落盘、上传槽位回填、模板弹窗缓存与刷新。

该能力服务于共享表单主干，不绑定单一招标类型。

## 当前真源

- 后端 API：`backend/api/template_candidates.py`
- 后端模型：`backend/models/template_candidates.py`
- 后端排序服务：`backend/services/template_candidate_ranking_service.py`
- 排序 prompt：`backend/prompts/template_candidate_ranking_prompt.py`
- 外部候选/下载工具：`backend/util/common_util/template_candidates.py`
- 文件落盘与文件名清洗：`backend/util/common_util/upload_storage.py`
- 前端 API 封装：`frontend/lib/api.ts`
- 前端表单与弹窗：`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/forms/TemplateCandidateDialog.tsx`

## API 与数据契约

### 前端调用入口

前端只通过 `frontend/lib/api.ts` 调用模板相关接口：

- `fetchTemplateCandidates()`
- `selectTemplateCandidate()`
- `getTemplateCandidateDownloadUrl()`

组件内不得直接请求外部模板源，也不得绕过项目内 API 封装。

### 后端路由

- `GET /api/template-candidates`
- `GET /api/template-candidates/download`
- `POST /api/template-candidates/select`

### 返回结构

- 候选列表返回 `candidates` 与 `ranking`。
- `ranking` 元信息包含 `applied`、`mode`、`reason`、`message`。
- 选择返回 `selected_files.clean_draft`、`selected_files.origin_tender`、`failed_slots`、`partial_success`。

## 候选归一化与可选规则

- 外部模板列表先在 `backend/util/common_util/template_candidates.py` 里统一归一化。
- 当前归一化字段包括 `tenderno`、`tendername`、`tname`、`bm`、`hytype`、`tendertype`、`hwlx`、`yxj`、`zbr`、`xbr`、`year`、`fsg`、`shener`、`selectable`、`blocked_reason`。
- `year` 合法整数则正常记录，缺失或非法则为 `None`。
- `year < 2025` 的模板不可选择，只能下载参考。
- `year` 缺失或非法的模板不可自动选择。

## 排序与 AI 重排

- 候选列表先按 `yxj` 数字值升序分组；非法或空 `yxj` 放到最后一组。
- 只有“同优先级候选数大于 1”且 `project_name` 非空时，该分组才进入 AI 重排。
- AI prompt 只比较当前项目名称与同优先级分组内各候选 `tendername`。
- AI 输出契约只能返回该组内部完整、无重复、不越界的 `row_index` 数组。
- AI 重排失败时回退到原始优先级顺序，不中断候选列表返回。

## 下载代理与落盘

- 外部文件下载必须经过后端代理，下载源主机受 `settings.TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 白名单限制。
- download 路由会校验 URL 协议与主机，代理拉取文件，尽量根据响应头和文件名修正 MIME，并返回 `Content-Disposition`。
- select 路由当前只使用 `candidate.shener` 作为推荐模板源。
- 当前同一份下载结果会分别落到两个上传槽位：`clean_draft` 与 `origin_tender`。
- 保存前统一经过 `upload_storage.py` 做文件名清洗、扩展名校验、大小校验和唯一路径生成。

## 前端弹窗与回填

- 点击“智能抽取模板”后先打开弹窗，再解析参数并加载数据。
- 若当前没有可用 `tenderno`，错误提示显示在弹窗内。
- 当前模板候选缓存 key 为 `tenderno + project_name`；项目名称后补齐时允许重新拉取排序结果。
- 刷新按钮复用“重新解析 tenderno/project_name -> 重新请求候选”的路径。
- 行 key 由候选核心字段拼接后追加 `rowIndex`，不是只用 `tendername + year`。
- “推荐模板”列的下载链接统一走 `getTemplateCandidateDownloadUrl()`。
- 点击“选择”时，前端只发送 `tendername`、`year`、`fsg`、`shener`；当前 `fsg` 固定传 `null`，后端不使用它回填。
- 成功回填后，前端把后端返回的文件对象同步回 `cleanDraftFile`、`originFile` 和 conversation draft 对应 `files`。
- 不可选旧模板只弹 notice，不发起 `selectTemplateCandidate()`。

## 关联测试与验证入口

- 前端 API：`frontend/__tests__/unit/lib/test_api.test.ts`
- 前端表单弹窗链路：`frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`
- 当前仓库没有独立的后端模板候选 API / 排序服务 / 下载落盘回归测试；若修改这条链路，应优先补到 `backend/tests/` 对应模块目录。

## 回归风险

- 改排序时，不要把 prompt 组装或 `row_index` 校验重新散落回 API 层。
- 改下载代理时，不能绕过白名单校验，否则会把模板代理变成 SSRF 入口。
- 改前端缓存键时，必须保留 `project_name` 维度，避免无项目名排序和有项目名 AI 排序互相污染。
- 若后续恢复 `fsg` 参与回填，必须同时修改后端 select 逻辑、前端回填流程、API 类型和本知识包。

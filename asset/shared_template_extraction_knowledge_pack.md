# 共享模板智能抽取知识包

## 背景与适用范围
- 适用于共享表单中的“智能抽取模板”能力。
- 范围包括：模板候选获取、同优先级 AI 重排、下载代理、文件落盘、上传槽位回填、模板弹窗缓存与刷新。
- 本能力服务于共享表单主干，不绑定单一招标类型。

## 当前真源
- 后端 API：`backend/api/template_candidates.py`
- 后端排序服务：`backend/services/template_candidate_ranking_service.py`
- 后端外部候选/下载工具：`backend/util/common_util/template_candidates.py`
- 后端落盘与文件名清洗：`backend/util/common_util/upload_storage.py`
- 排序 prompt：`backend/prompts/template_candidate_ranking_prompt.py`
- 前端表单与弹窗：`frontend/components/forms/TenderFormShared.tsx`、`frontend/components/forms/TemplateCandidateDialog.tsx`
- 前端 API 封装：`frontend/lib/api.ts`

## 当前 API 与数据契约

### 前端调用入口
- 前端当前只通过 `frontend/lib/api.ts` 调用三条模板相关接口：
  - `fetchTemplateCandidates()`
  - `selectTemplateCandidate()`
  - `getTemplateCandidateDownloadUrl()`

### 后端真实路由
- `GET /api/template-candidates`
- `GET /api/template-candidates/download`
- `POST /api/template-candidates/select`

### 列表返回结构
- `GET /api/template-candidates` 当前返回：
  - `candidates`
  - `ranking`
- `ranking` 元信息字段当前包含：
  - `applied`
  - `mode`
  - `reason`
  - `message`

### 选择返回结构
- `POST /api/template-candidates/select` 当前返回：
  - `selected_files.clean_draft`
  - `selected_files.origin_tender`
  - `failed_slots`
  - `partial_success`

## 候选归一化与可选规则
- 外部模板列表先在 `backend/util/common_util/template_candidates.py` 里做统一归一化。
- 当前归一化字段包括：
  - `tenderno`
  - `tendername`
  - `tname`
  - `bm`
  - `hytype`
  - `tendertype`
  - `hwlx`
  - `yxj`
  - `zbr`
  - `xbr`
  - `year`
  - `fsg`
  - `shener`
  - `selectable`
  - `blocked_reason`
- `year` 解析规则当前为：
  - 合法整数 -> 正常 year
  - 缺失或非法 -> `None`
- 可选规则当前为：
  - `year < 2025` -> `selectable = false`，`blocked_reason = 该模板过旧不能选择，仅供下载参考`
  - `year` 缺失/非法 -> `selectable = false`，`blocked_reason = 模板年份缺失或无效，不能自动选择`

## 排序与 AI 重排规则
- 候选列表当前先按 `yxj` 的数字值升序分组。
- 非法或空 `yxj` 会被放到最后一组。
- 只有满足下面两个条件时，某个优先级分组才会进入 AI 重排：
  - 该组候选数大于 1
  - `project_name` 非空
- AI prompt 当前只比较：
  - 当前项目名称
  - 同优先级分组内各候选的 `tendername`
- AI 输出契约当前只能返回该组内部的 `row_index` 数组，且必须完整覆盖、不可重复、不可越界。
- AI 重排失败时，当前实现会回退到原始优先级顺序，不中断整次候选列表返回。

## 下载代理与落盘规则
- 外部文件下载当前必须经过后端代理，不允许前端直接请求外部模板源。
- 下载源主机当前受 `settings.TEMPLATE_CANDIDATE_ALLOWED_HOSTS` 白名单限制。
- `download` 路由会：
  - 校验 URL 协议与主机
  - 代理拉取文件
  - 尽量根据响应头和文件名修正 MIME
  - 返回 `Content-Disposition`
- `select` 路由当前只使用 `candidate.shener` 作为推荐模板源。
- 当前会把同一份下载结果分别落到两个上传槽位：
  - `clean_draft`
  - `origin_tender`
- 保存前统一经过 `upload_storage.py`：
  - 文件名清洗
  - 扩展名校验
  - 大小校验
  - 唯一路径生成

## 前端弹窗与缓存当前行为
- `TenderFormShared.tsx` 当前在点击“智能抽取模板”后先打开弹窗，再解析参数并加载数据。
- 若当前没有可用 `tenderno`，错误提示会显示在弹窗内，而不是表单内联错误。
- 当前模板候选缓存 key 为：
  - `tenderno`
  - `project_name`
- 刷新按钮会复用同一条“重新解析 tenderno/project_name -> 重新请求候选”的路径，而不是只刷新旧缓存。
- 项目名称后补齐时，当前逻辑允许重新按新的 `project_name` 拉取一份排序结果。
- 行 key 当前由候选核心字段拼接后再追加 `rowIndex`，不是只用 `tendername + year`。

## 选择与回填当前现实
- 当前弹窗里“推荐模板”列的下载链接统一走 `getTemplateCandidateDownloadUrl()`。
- 点击“选择”时，前端只把以下字段发给后端：
  - `tendername`
  - `year`
  - `fsg`（当前固定传 `null`）
  - `shener`
- 后端当前不会用 `fsg` 做回填。
- 成功回填后，前端会把后端返回的文件对象同步回：
  - `cleanDraftFile`
  - `originFile`
  - conversation draft 对应 `files`
- 不可选旧模板当前只弹 notice，不会发起 `selectTemplateCandidate()`。

## 关联代码路径
- `backend/api/template_candidates.py`
- `backend/models/template_candidates.py`
- `backend/services/template_candidate_ranking_service.py`
- `backend/prompts/template_candidate_ranking_prompt.py`
- `backend/util/common_util/template_candidates.py`
- `backend/util/common_util/upload_storage.py`
- `frontend/lib/api.ts`
- `frontend/types/api.ts`
- `frontend/components/forms/TenderFormShared.tsx`
- `frontend/components/forms/TemplateCandidateDialog.tsx`

## 关联测试与验证路径
- `frontend/__tests__/unit/lib/test_api.test.ts`
- `frontend/__tests__/unit/components/forms/test_tender_form_shared.test.tsx`
- 当前仓库没有独立的后端模板候选 API / 排序服务 / 下载落盘回归测试；若修改这条链路，应优先补到 `backend/tests/` 对应模块目录后再更新知识包。

## 回归风险与维护建议
- 改模板候选排序时，不要把 prompt 组装或 `row_index` 校验重新散落回 API 层；继续保持在 `template_candidate_ranking_service.py` 与 `template_candidate_ranking_prompt.py`。
- 改下载代理时，不能绕过白名单校验，否则容易把模板代理变成 SSRF 入口。
- 改前端缓存键时，必须保留 `project_name` 维度，否则“无项目名排序”和“有项目名 AI 排序”会互相污染。
- 若后续要恢复 `fsg` 参与回填，必须同时修改后端 `select` 逻辑、前端回填流程与知识包，不要只改请求模型。

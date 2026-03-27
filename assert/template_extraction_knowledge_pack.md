# 智能抽取模板能力知识包

## 背景与适用范围
- 适用于前端“文件上传”区域新增的 `智能抽取模板` 能力。
- 目标是基于 `tenderno` 从外部系统代理获取模板候选列表，并把所选模板文件回填到现有上传槽位。
- 本能力服务于当前共享表单主干，不绑定单一招标类型；入口按钮在共享表单中固定展示，真正可否加载模板候选由点击后的参数解析结果决定。

## 业务规则与约束
- 接入方式固定为后端代理：
  - 前端只调用本项目 `/api/template-candidates*`
  - 后端负责请求外部 JSON 列表、代理文件下载、以及将选中的模板文件保存到现有 `UPLOAD_DIR`
- 参数来源优先级：
  - 第一优先级：共享表单当前输入框中的 `tenderno`
  - 第二优先级：页面 URL 中的 `tenderno`
  - 若两者都缺失，则弹窗内提示用户先输入招标编号
- 交互规则：
  - 用户点击 `智能抽取模板` 后，弹窗必须立即打开，不能让用户停留在表单页等待异步请求完成
  - `tenderno` 解析、候选模板加载、失败提示都在弹窗内部完成
  - 右上角 `刷新` 必须复用同一条“tenderno 解析 -> 候选加载”链路，不能只刷新已有候选列表
- 模板预览规则：
  - 当前列表仅展示一列 `推荐模板`，实际预览源为外部接口返回的 `shener`
  - 预览链接统一走同一个后端代理接口，前端不应再为不同模板列维护多套打开逻辑
  - 代理接口返回 `Content-Disposition: inline`
  - 当上游返回 `application/octet-stream` 这类泛型类型时，必须按最终文件名/扩展名推断更准确的 MIME，尽量保证推荐模板预览优先在新标签页打开，而不是直接下载
- 外部接口字段以
  `tenderno / tendername / tname / bm / hytype / tendertype / hwlx / yxj / zbr / xbr / year / fsg / shener`
  为准。
- 前端列表列顺序与表头固定为：
  - `年份`
  - `项目`
  - `主办人/协办人`
  - `采购人`
  - `部门`
  - `行业类型`
  - `招标类型`
  - `采购方式`
  - `优先级`
  - `推荐模板`
  - `操作`
- 单元格展示规则：
  - `项目` 列主行展示 `tendername`，次行展示 `tenderno`
  - `主办人/协办人` 合并为单列，主行展示 `zbr`，次行展示 `xbr`
  - `采购人` 取 `tname`
  - `部门` 取 `bm`
  - `行业类型` 取 `hytype`
  - `招标类型` 取 `tendertype`
  - `采购方式` 取 `hwlx`
  - `优先级` 取 `yxj` 原始值，并以彩色徽标展示：`1` 红色、`2` 橙色、其他灰色
  - 桌面端优先使用固定列宽完整展示；空间不足时允许横向滚动，不能再把右侧 `优先级` / `操作` 列直接裁掉
- 文件槽位映射固定：
  - 当前选择行为只使用 `shener`
  - `shener -> 模板文件（clean_draft）`
  - `shener -> 送审稿文件（origin_tender）`
  - 回填后的两个上传槽位都应保留 `项目名称-送审稿` 这一业务文件名，不应再把推荐模板重命名为 `发售稿`
- 年份规则：
  - `year < 2025` 时不可选择，提示文案必须为：`该模板过旧不能选择，仅供下载参考`
  - `year` 缺失或非法时同样不可自动选择
- 允许部分回填：
  - 只要 `fsg` 或 `shener` 其中一个成功下载并保存，接口即可返回成功
  - 失败槽位必须单独返回错误信息
  - 前端收到成功或部分成功后自动关闭弹窗，并直接把已保存文件回填到对应上传槽位；不再额外显示“已回填/未回填”横幅提示
- 模板列表顺序保持外部接口原顺序，不做前端或后端重排。

## 输入输出样例
- 列表请求：
  - `GET /api/template-candidates?tenderno=0811-DSITC260631`
- 列表响应 `data.candidates[*]` 样例：
  - `tenderno: "0811-DSITC260631"`
  - `tendername: "眼底照相机"`
  - `tname: "上海市中医医院"`
  - `bm: "采购处"`
  - `hytype: "医疗行业"`
  - `tendertype: "国内公开"`
  - `hwlx: "货物"`
  - `yxj: "1"`
  - `zbr: "招标部-史倩倩"`
  - `xbr: "招标部-陈雯雯"`
  - `year: 2026`
  - `fsg: "http://10.11.1.224/..."`
  - `shener: "http://10.11.1.224/..."`
  - `selectable: true`
- 选择请求：
  - `POST /api/template-candidates/select`
  - body:
    - `candidate.tendername`
    - `candidate.year`
    - `candidate.fsg` 可为空；当前选择逻辑忽略该字段
    - `candidate.shener`
- 选择成功响应：
  - `data.selected_files.clean_draft`
  - `data.selected_files.origin_tender`
  - `data.failed_slots`
  - `data.partial_success`

## 关键改动点
- 后端：
  - `backend/api/template_candidates.py`
  - `backend/util/common_util/template_candidates.py`
  - `backend/util/common_util/upload_storage.py`
- 前端：
  - `frontend/components/forms/TenderFormShared.tsx`
  - `frontend/components/forms/TemplateCandidateDialog.tsx`
  - `frontend/lib/api.ts`
  - `frontend/types/api.ts`
- 共享 UI：
  - `frontend/components/forms/shared/FormSection.tsx`

## 边界条件与已知坑点
- 若弹窗在打开前才去异步解析 `tenderno`，用户会误以为按钮没有生效；当前实现要求先开弹窗，再做参数解析与加载。
- 点击弹窗刷新时，必须重新读取当前输入框值或 URL 中的 `tenderno`，而不是只刷新已有候选列表缓存。
- 外部模板下载源返回的 `Content-Type` 可能不可靠；若直接透传 `application/octet-stream`，浏览器往往会直接下载，导致发售稿/送审稿预览体验不一致。
- 外部下载链接只允许访问配置白名单中的主机，避免把代理下载接口变成通用 SSRF 入口。
- 远端文件名可能缺失扩展名；下载代理会优先用远端响应推断扩展名，前端展示名仍保持业务名。
- 远端项目名和文件名可能带 Windows 非法字符；实际落盘前必须经过共享上传持久化层清洗。
- 模板候选行标识不能只用 `tendername + year`；外部接口可能返回同名同年的多条记录，前端必须使用更完整的组合标识，并在必要时追加行索引，避免 React 重复 key 警告与行状态错位。
- `yxj` 当前不做文案映射，直接显示接口原值；如果未来需要改成 `高/中/低` 或 `P1/P2/P3`，应先同步更新知识包、UI 测试和视觉约定。
- 当前环境下部分测试无法使用系统临时目录或产生额外子进程：
  - pytest 中涉及临时目录的用例应优先 mock 文件写入或使用仓库内受控路径
  - Jest 在当前环境需要 `--runInBand`
  - 全量 `npm run lint` 可能因环境内存限制 OOM，必要时退化为改动文件级 eslint

## 关联测试与验证路径
- 后端新增测试：
  - `backend/tests/test_template_candidates_api.py`
  - `backend/tests/test_upload_storage.py`
- 前端新增/更新测试：
  - `frontend/components/forms/TenderFormShared.test.tsx`
  - `frontend/lib/api.test.ts`
- 本次验证命令：
  - `npx jest --runInBand`
  - `npm run type-check`
  - `npx eslint components/forms/TenderFormShared.tsx components/forms/TenderFormShared.test.tsx`

## 回归风险与复用建议
- 若后续新增同类“外部候选模板”能力，优先复用 `upload_storage.py` 的持久化逻辑，不要再复制一套文件验证与保存代码。
- 若候选列表来源主机发生变化，优先更新配置项：
  - `TEMPLATE_CANDIDATE_API_URL`
  - `TEMPLATE_CANDIDATE_ALLOWED_HOSTS`
- 若未来需要对模板列表排序，必须先确认业务是否要摆脱“外部原顺序即真源”的约束，再决定是否在后端或前端重排。

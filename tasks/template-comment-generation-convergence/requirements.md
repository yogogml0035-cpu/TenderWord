# Requirements: 模板文件与批注生成链路收敛

## 来源

- 生成自当前对话中的需求计划。
- 关联 PRD：`prd.md`

## 原始对齐需求

### 摘要

- 全类型统一删除“送审稿 / 清洁稿”概念，只保留必填“模板文件”和必填“技术参数文件”。
- 生成请求统一使用前端 `file_paths.template`、后端 state `template_path`；删除 `origin_tender`、`clean_draft` 及送审稿提取计划链路。
- 批注统一由通用 `comment_prompt.py` 生成：`workflow` 走 `generate_comments`，`agent` 跳过 `generate_comments`，由 `comment_agent` 自主生成、校验、写回。
- 模板文件自带批注不主动提取、不复制、不清空，只随正文替换自然保留或移除。

### 关键变化

#### 前端表单

- `TenderFormShared` 只展示“模板文件（必填）”和“技术参数文件（必填）”。
- 未上传模板文件时阻止提交并提示“请上传模板文件”。
- 表单 draft、上传类型、提交 payload 删除 `origin_tender`、`clean_draft`，改为 `template`。

#### 前后端生成接口

- `GenerateRequest.file_paths` 收敛为 `{ template: string, tender_params: string[] }`。
- `DocumentService` 只写入 `template_path` 和 `tender_param_paths`；`prepare_template` 只从 `template_path` 复制工作副本。
- `extract_tender_params` 从 `template_path` 提取模板参考正文，从技术参数文件提取生成材料。

#### Graph 与批注

- 标准生成图删除 `get_comments`、`copy_comments`、送审稿条件分支和批注 / 删除线 / 非黑字计划 state。
- `workflow`: `generate_polished_text -> generate_comments -> update_word`。
- `agent`: `content_agent -> update_word -> comment_agent`，不进入 `generate_comments`。
- `generate_comments` 只基于 `polished_text` 和统一 `comment_prompt.py` 输出 JSON 批注候选。
- `comment_agent` 在 `generation_mode=agent` 的 generate 任务中允许无候选时自主生成批注，并复用同一 `comment_prompt.py`。
- `comment_supplement` 继续复用 `comment_agent` 与同一批注 prompt。

#### 模板候选

- 选择候选时后端只下载一次推荐模板文件。
- 响应改为单文件回填，例如 `selected_file`。
- 删除 `selected_files.clean_draft/origin_tender`、`failed_slots`、`partial_success`。
- 前端弹窗文案改为“选择后回填模板文件”，失败时整体失败。

#### 清理与知识包

- 删除旧的“依赖送审稿提取计划”的 `comment_prompt.py` 语义，保留文件名并改为新通用 prompt 真源。
- 删除 `comment_no_reference_prompt.py` 及其导出 / 测试引用。
- 清理 `comment_plan_detail`、`strikethrough_plan`、`non_black_font_plan`、`copy_comments_*` 等送审稿提取契约。
- 更新 `asset/shared_runtime_word_skill_knowledge_pack.md`、`asset/tender_type_identity_session_knowledge_pack.md`、`asset/template_candidate_pipeline_knowledge_pack.md` 和 `asset/README.md`。

## 范围

### 包含

- 前端表单上传位、draft、上传类型、提交 payload、模板候选回填和相关测试。
- 后端 `GenerateRequest.file_paths`、`DocumentService._build_initial_state()`、`prepare_template`、`extract_tender_params` 和相关测试。
- 标准生成 graph 拓扑、节点注册、进度节点展示名和各类型 graph 测试。
- `comment_prompt.py`、`generate_comments`、`comment_agent`、`comment_supplement` 三路批注契约和相关测试。
- 模板候选选择 API、响应模型、前端 API 类型和弹窗测试。
- 长期知识包和索引同步。

### 不包含

- 不保留旧会话、旧 API 字段或旧请求兼容。
- 不主动提取、复制、清空模板文件自带 Word 批注。
- 不改变 rewrite / edit 的显式入口语义，除非字段清理需要移除初次 generate 遗留命名。
- 不新增重量级依赖。

## 业务场景

- 用户创建 `xjcg`、`gngk`、`gjgk` 生成任务时，只需要上传一个模板文件和至少一个技术参数文件。
- 用户从模板候选弹窗选择推荐模板时，只回填“模板文件”一个上传位。
- `workflow` 生成时，正文生成完成后由统一批注 prompt 直接基于最终正文生成 AI 批注候选，再交给现有写回逻辑。
- `agent` 生成时，正文由 `content_agent` 生成并写回，之后由 `comment_agent` 自主生成、校验、写回批注。
- 用户对已生成文档执行补充批注时，继续复用 `comment_agent`，批注生成规则与初次生成的 agent 模式保持一致。

## 验收口径

- 前端页面和测试中不再展示“送审稿 / 清洁稿”上传概念。
- 生成 payload 只包含 `file_paths.template` 和 `file_paths.tender_params`。
- 后端初始 state 只写入 `template_path` 和 `tender_param_paths`，模板复制只读取 `template_path`。
- 标准生成图不存在 `get_comments`、`copy_comments` 分支；`workflow` 与 `agent` 的批注链路符合需求。
- `comment_prompt.py` 是唯一批注生成 prompt 真源；`comment_no_reference_prompt.py` 及其导出、测试引用被删除。
- 模板候选选择接口返回单文件结果；失败时整体失败。
- 回归搜索 `rg "送审稿|origin_tender|clean_draft|comment_plan_detail|strikethrough_plan|non_black_font_plan|copy_comments"` 只剩必要历史说明或已经更新后的文案。

## 待确认问题

- 无。当前需求已明确不保留旧字段兼容，且改动影响所有招标类型。

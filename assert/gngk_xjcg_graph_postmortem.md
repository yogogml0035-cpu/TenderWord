# GNGK 图卡在 get_comments 的复盘（对齐 XJCG 的避坑资产）

## 背景与现象

- 现象：`graphs/gngk_tender_graph.py` 的工作流看起来“停在 get_comments”，后续节点不再推进；而 `graphs/xjcg_tender_graph.py` 结构类似却能正常运行。
- 误导点：日志/进度通常显示最后执行到 `get_comments`，容易误以为是 `get_comments` 本身出错或提前结束。

## 根因（真正卡住的位置）

核心不是 “get_comments 执行完了不往下走”，而是：

- 主图在 `prepare_template` 后做了并发扇出，并且有 **并发汇合屏障**：
  - `add_edge(["get_comments", "extract_tender_params", "copy_comments"], ...)`
  - 这意味着：必须等三个分支都完成，后续的 `word_operations_subgraph` / `generate_polished_text` 才会开始。
- 因此只要另外两个分支（尤其是 Word COM 相关分支）任意一个 **卡死/挂起**，主图就会表现为“停在 get_comments”。

真正的根因是 **GNGK 的并发分支会同时抢同一个 Word 文档文件（工作副本）**，引发 Word COM 的不稳定行为（打开/关闭/退出卡住、文件被占用、RPC 断开等），从而导致某个并发分支长期不返回，主图被汇合屏障卡住。

### 关键差异：XJCG 不抢同一个 doc，GNGK 会抢

对比两套逻辑：

- **XJCG：读源文件 + 写工作副本（基本不冲突）**
  - `extract_tender_params` 读取 `clean_draft_path`（源文件，只读）
  - `copy_comments` / `replace_content` / `update_word` 操作 `prepared_doc_path`（工作副本，可写）
  - 读写分离 -> 并发时大多不会争抢同一个 doc 文件。

- **GNGK（问题版本）：读工作副本 + 写工作副本（高冲突）**
  - `gngk_extract_tender_params` 读取 `prepared_doc_path`（只读打开）
  - 同时 `copy_comments` 会对同一个 `prepared_doc_path` 以 `read_only=False` 打开并写批注
  - 同一文件被两个 Word 实例/两个 COM 会话以不同模式打开 -> 更容易卡死。

## 定位过程（可复用的排查路径）

1. 先确认“卡住”是否是并发屏障导致
   - 观察图结构是否存在 `add_edge([A,B,C], D)` 这种 join。
   - 结论：一旦 join 存在，**显示停在某节点并不等于该节点有问题**，很可能是其他分支没结束。

2. 对比 XJCG 与 GNGK 并发分支的“资源争用点”
   - 找出每个并发分支打开的文件路径字段（`origin_tender_path` / `clean_draft_path` / `prepared_doc_path`）。
   - 重点检查：是否存在两个并发节点同时打开同一个 `prepared_doc_path`（尤其一读一写）。

3. 把问题缩小为：Word COM 并发访问 + 同一文件争用
   - 这类问题往往不会抛异常，而是 COM 调用挂起（`Documents.Open` / `doc.Close` / `Quit` 等）。

## 最终改动（解决方案）

目标：**让 GNGK 完全向 XJCG 看齐：一个读源文件，一个写工作副本**，从而并发结构一致且避免争抢同一 doc。

### 1) 让 GNGK 的 `extract_tender_params` 读取源文件

- 改动：`nodes/gngk_word_nodes/gngk_extract_tender_params.py`
  - 从读取 `prepared_doc_path` 改为读取 `clean_draft_path`
  - 含义：提取锚点/正文内容时只读源文件；写入类操作仍只落在工作副本

### 2) 让 GNGK 的图并发结构与 XJCG 保持一致

- 改动：`graphs/gngk_tender_graph.py`
  - 恢复为：
    - `prepare_template` 后并发：`get_comments` / `extract_tender_params` / `copy_comments`
    - 三者完成后并发：`word_operations_subgraph` 与 `generate_polished_text`

### 3) 补齐 GNGK State 字段，确保与表单初始状态一致

- 改动：`states/gngk_tender_state.py`
  - 增加 `clean_draft_path` 字段
  - 避免后续节点读取 `clean_draft_path` 时出现缺字段问题

## 验证方式（可复用）

- 静态验证：两张图都能 `compile()` 成功（先保证拓扑和节点装配无误）
- 回归验证：跑现有测试集 `pytest` 通过

## 经验总结（给下次 AI 的避雷清单）

### A. 并发图排查必做

- 看到“停在某节点”时，先检查有没有 join 屏障（`add_edge([..], ..)`）。
- 有 join 屏障时，优先怀疑：
  - 其他分支卡住（尤其是 IO/Word COM/网络/LLM 调用分支）
  - 某分支长时间等待外部资源（文件锁、COM 卡死）

### B. Word COM 并发必做

- 并发节点里只要涉及 Word COM：
  - 尽量 **读写分离**：读源文件、写工作副本
  - 避免两个并发分支同时 `Documents.Open` 同一 doc（尤其一个只读、一个可写）
  - 路径字段要统一约定：
    - `clean_draft_path`：源文件（只读用途）
    - `prepared_doc_path`：工作副本（所有写操作都在这里）

### C. 快速对齐策略（当两张图“应该一致”时）

- 用 XJCG 作为 reference：
  - 逐个节点对比“输入字段 + 打开的文件路径”
  - 把 GNGK 中任何对 `prepared_doc_path` 的只读提取行为迁移到 `clean_draft_path`


# Rewrite 批注保留知识包

## 背景与适用范围
- 适用于 rewrite 工作流对既有生成文档做二次改写的场景。
- 目标是在删除锚点区间旧内容并插入新内容后，尽量把该区间内的旧批注重新挂回新文本。

## 业务规则与约束
- 仅处理锚点之间的批注，不处理删除线、非黑字。
- 本次“保留批注”仅指保留批注文本内容与引用文本匹配关系，不保留作者、时间、回复链。
- 提取旧批注阶段采用 strict 语义：文档不存在、锚点缺失、Word/Inspector 异常都会直接使 rewrite 任务失败。
- 回写阶段仍复用 `update_word` 现有逻辑；若修改后文本无法匹配 `reference_text`，允许记录“添加失败/未找到位置”并继续完成任务。

## 输入输出样例
- 输入：
  - `prepared_doc_path` 或 `origin_tender_path`
  - `insertion_before_text`
  - `insertion_after_text`
  - `tender_type`
- 输出：
  ```python
  {
      "polished_comments": [
          {"reference_text": "原文中的引用片段", "comment_text": "原批注内容"}
      ]
  }
  ```

## 边界条件与已知坑点
- `get_rewrite_comments` 必须先于 `delete_section`，避免同一临时文档读写并发。
- `rewrite_text` 可以继续与文件操作分支并行，因为它只做 LLM 改写，不直接修改 Word。
- `reference_text` 为空的批注无法稳定回写，当前不增加 `scope_text` 兜底匹配。

## 关联代码路径
- `backend/nodes/common_word_nodes/get_comments.py`
- `backend/nodes/common_word_nodes/get_rewrite_comments.py`
- `backend/graphs/rewrite_graph.py`
- `backend/nodes/common_word_nodes/update_word.py`

## 关联测试或验证路径
- `backend/tests/test_get_rewrite_comments.py`
- `backend/tests/test_rewrite_graph.py`
- `python -m pytest backend/tests/test_get_rewrite_comments.py backend/tests/test_rewrite_graph.py -v`

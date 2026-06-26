from __future__ import annotations

from backend.util.word_util.word_extraction_utils import extract_content_with_table_models


class _FakeRange:
    def __init__(self, xml: str) -> None:
        self.WordOpenXML = xml


def test_extract_content_with_table_models_preserves_merge_topology() -> None:
    xml = """
    <pkg:package xmlns:pkg="http://schemas.microsoft.com/office/2006/xmlPackage">
      <pkg:part>
        <pkg:xmlData>
          <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
              <w:p><w:r><w:t>人员要求</w:t></w:r></w:p>
              <w:tbl>
                <w:tr>
                  <w:tc>
                    <w:tcPr><w:gridSpan w:val="2"/><w:vMerge w:val="restart"/></w:tcPr>
                    <w:p><w:r><w:t>楼宇</w:t></w:r></w:p>
                  </w:tc>
                  <w:tc>
                    <w:p><w:r><w:t>岗位</w:t></w:r></w:p>
                  </w:tc>
                </w:tr>
                <w:tr>
                  <w:tc>
                    <w:tcPr><w:gridSpan w:val="2"/><w:vMerge/></w:tcPr>
                    <w:p><w:r><w:t></w:t></w:r></w:p>
                  </w:tc>
                  <w:tc>
                    <w:p><w:r><w:t>安保</w:t></w:r></w:p>
                  </w:tc>
                </w:tr>
                <w:tr>
                  <w:tc>
                    <w:tcPr><w:gridSpan w:val="3"/></w:tcPr>
                    <w:p><w:r><w:t>合计</w:t></w:r></w:p>
                  </w:tc>
                </w:tr>
              </w:tbl>
            </w:body>
          </w:document>
        </pkg:xmlData>
      </pkg:part>
    </pkg:package>
    """

    content, models = extract_content_with_table_models(_FakeRange(xml), table_id_prefix="TP")

    assert "[[TABLE:TP1]]" in content
    assert len(models) == 1
    model = models[0]
    assert model["table_id"] == "TP1"
    assert model["rows"] == 3
    assert model["cols"] == 3
    assert model["cells"] == [
        {"row": 1, "col": 1, "row_span": 2, "col_span": 2, "text": "楼宇"},
        {"row": 1, "col": 3, "row_span": 1, "col_span": 1, "text": "岗位"},
        {"row": 2, "col": 3, "row_span": 1, "col_span": 1, "text": "安保"},
        {"row": 3, "col": 1, "row_span": 1, "col_span": 3, "text": "合计"},
    ]
    assert "| 楼宇 | 楼宇 | 岗位 |" in content
    assert "| 楼宇 | 楼宇 | 安保 |" in content
    assert "| 合计 | 合计 | 合计 |" in content


def test_extract_content_with_table_models_renders_full_markdown_projection_for_personnel_table() -> None:
    xml = """
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:tbl>
          <w:tr>
            <w:tc><w:p><w:r><w:t>楼宇</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>楼层</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>DSA</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>岗位数人数</w:t></w:r></w:p></w:tc>
          </w:tr>
          <w:tr>
            <w:tc><w:tcPr><w:vMerge w:val="restart"/></w:tcPr><w:p><w:r><w:t>1号楼</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>2F</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>DSA1</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>2</w:t></w:r></w:p></w:tc>
          </w:tr>
          <w:tr>
            <w:tc><w:tcPr><w:vMerge/></w:tcPr><w:p><w:r><w:t></w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>3F</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>DSA2</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>3</w:t></w:r></w:p></w:tc>
          </w:tr>
        </w:tbl>
      </w:body>
    </w:document>
    """

    content, models = extract_content_with_table_models(_FakeRange(xml))

    assert "| 楼宇 | 楼层 | DSA | 岗位数人数 |" in content
    assert "| 1号楼 | 2F | DSA1 | 2 |" in content
    assert "| 1号楼 | 3F | DSA2 | 3 |" in content
    assert "[[TABLE:TP1]]" in content
    assert "| --- | --- | --- | --- |" in content
    assert len(models) == 1


def test_extract_content_with_table_models_repeats_horizontal_and_vertical_merges_in_markdown() -> None:
    xml = """
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:tbl>
          <w:tr>
            <w:tc><w:p><w:r><w:t>序号</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>楼宇</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>楼层</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>科室</w:t></w:r></w:p></w:tc>
          </w:tr>
          <w:tr>
            <w:tc><w:p><w:r><w:t>1</w:t></w:r></w:p></w:tc>
            <w:tc><w:tcPr><w:vMerge w:val="restart"/></w:tcPr><w:p><w:r><w:t>医疗综合楼</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>B2</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>放疗科</w:t></w:r></w:p></w:tc>
          </w:tr>
          <w:tr>
            <w:tc><w:p><w:r><w:t>2</w:t></w:r></w:p></w:tc>
            <w:tc><w:tcPr><w:vMerge/></w:tcPr><w:p><w:r><w:t></w:t></w:r></w:p></w:tc>
            <w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr><w:p><w:r><w:t>1F/门诊诊室</w:t></w:r></w:p></w:tc>
          </w:tr>
        </w:tbl>
      </w:body>
    </w:document>
    """

    content, models = extract_content_with_table_models(_FakeRange(xml))

    assert "| 序号 | 楼宇 | 楼层 | 科室 |" in content
    assert "| 1 | 医疗综合楼 | B2 | 放疗科 |" in content
    assert "| 2 | 医疗综合楼 | 1F/门诊诊室 | 1F/门诊诊室 |" in content
    assert "[[TABLE:TP1]]" in content
    assert len(models) == 1


def test_extract_content_with_table_models_maps_symbol_font_delta_in_paragraph() -> None:
    """`<w:sym w:font="Symbol" w:char="F044"/>` 必须在段落抽取中映射为可见 Δ。"""
    xml = """
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p>
          <w:r><w:sym w:font="Symbol" w:char="F044"/><w:t>3.1.1</w:t></w:r>
          <w:r><w:t>波长范围：400-700nm。</w:t></w:r>
        </w:p>
      </w:body>
    </w:document>
    """

    content, models = extract_content_with_table_models(_FakeRange(xml))

    assert "Δ3.1.1" in content
    assert "波长范围：400-700nm。" in content
    assert models == []


def test_extract_content_with_table_models_maps_symbol_font_delta_in_table_cell() -> None:
    """Symbol 字体的 Δ 必须在表格 cell / prompt context 中也保留。"""
    xml = """
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:tbl>
          <w:tr>
            <w:tc><w:p><w:r><w:t>序号</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>参数</w:t></w:r></w:p></w:tc>
          </w:tr>
          <w:tr>
            <w:tc><w:p><w:r><w:sym w:font="Symbol" w:char="F044"/><w:t>3.1.1</w:t></w:r></w:p></w:tc>
            <w:tc><w:p><w:r><w:t>分辨率：≥4K</w:t></w:r></w:p></w:tc>
          </w:tr>
        </w:tbl>
      </w:body>
    </w:document>
    """

    content, models = extract_content_with_table_models(_FakeRange(xml))

    assert "Δ3.1.1" in content
    assert "分辨率：≥4K" in content
    assert len(models) == 1
    # 结构化表 prompt context 也应保留 Δ。
    cell_texts = [cell["text"] for cell in models[0]["cells"]]
    assert any("Δ3.1.1" in text for text in cell_texts)


def test_extract_content_with_table_models_ignores_non_symbol_font_sym() -> None:
    """非 Symbol 字体的 sym 元素不应被错误映射。"""
    xml = """
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p>
          <w:r><w:sym w:font="Wingdings" w:char="F044"/><w:t>正文</w:t></w:r>
        </w:p>
      </w:body>
    </w:document>
    """

    content, models = extract_content_with_table_models(_FakeRange(xml))

    assert "正文" in content
    assert "Δ" not in content
    assert models == []

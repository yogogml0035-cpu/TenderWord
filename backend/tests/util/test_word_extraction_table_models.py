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


def test_extract_content_with_table_models_keeps_nonempty_projection_for_personnel_table() -> None:
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

    assert "楼宇" in content
    assert "DSA2" in content
    assert "岗位数人数" in content
    assert "[[TABLE:TP1]]" in content
    assert len(models) == 1

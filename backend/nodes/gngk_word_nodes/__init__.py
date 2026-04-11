# GNGK 目录仅保留"带前缀"的差异化节点（gngk_*）与 prompt。
# 通用节点统一放在 nodes/common_word_nodes 中实现，并在此处 re-export，
# 以保持外部导入路径 `from backend.nodes.gngk_word_nodes import ...` 不变。

from backend.nodes.common_word_nodes import (
    generate_polished_text,
    prepare_template,
    replace_content,
    extract_tender_params,
    delete_tender_param,
    update_word,
)

from backend.nodes.gngk_word_nodes.gngk_fw_zc_delete_tender_param import (
    gngk_fw_zc_delete_tender_param,
)
from backend.nodes.gngk_word_nodes.gngk_fw_zc_get_replacements import (
    gngk_fw_zc_get_replacements,
)
from backend.nodes.gngk_word_nodes.gngk_fw_zc_update_word import (
    gngk_fw_zc_update_word,
)
from backend.nodes.gngk_word_nodes.gngk_hw_zc_get_replacements import (
    gngk_hw_zc_get_replacements,
)

__all__ = [
    "prepare_template",
    "extract_tender_params",
    "delete_tender_param",
    "gngk_fw_zc_delete_tender_param",
    "gngk_fw_zc_get_replacements",
    "gngk_fw_zc_update_word",
    "gngk_hw_zc_get_replacements",
    "replace_content",
    "update_word",
    "generate_polished_text",
]

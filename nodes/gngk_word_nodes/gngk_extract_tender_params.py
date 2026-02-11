from __future__ import annotations

import os
import time
import pathlib
import sys

# 添加项目根目录到 sys.path
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from util.word_application_util import (
    create_word_application,
    close_word_application,
    open_document_with_retry,
    unprotect_document,
)
from util.word_extraction_utils import (
    extract_content_with_tables,
    extract_text_from_word_file,
)
from util.word_constants import (
    wdGoToPage,
    wdGoToAbsolute,
    wdActiveEndPageNumber,
)


def extract_tender_params(state, config):
    """
    根据前后内容定位插入位置，提取该位置的 WPS/Word 内容并存储到 tender_params 状态中。
    
    从 state 中读取：
    - insertion_before_text: 插入位置的前置文本
    - insertion_after_text: 插入位置的后置文本
    - prepared_doc_path: WPS/Word 文档路径
    
    提取的内容将存储到 state 的 tender_params 字段中。
    """
    start_time = time.time()
    print(f"[extract_tender_params] 开始执行...")
    
    clean_draft_path = state.get("clean_draft_path")
    before_text = state.get("insertion_before_text")
    after_text = state.get("insertion_after_text")
    
    if not clean_draft_path:
        raise ValueError("需要 clean_draft_path（清洁稿）来提取 WPS/Word 文档中的内容")
    
    if not before_text or not after_text:
        # 如果没有提供前后文本，返回空内容
        print(f"[extract_tender_params] 警告: 未提供 insertion_before_text 或 insertion_after_text，跳过提取")
        new_state_dict = dict(state)
        new_state_dict["tender_params"] = ""
        return new_state_dict
    
    extract_source_path = clean_draft_path
    if not os.path.isabs(extract_source_path):
        extract_source_path = os.path.abspath(extract_source_path)
    
    # 检查文件是否存在
    if not os.path.exists(extract_source_path):
        raise FileNotFoundError(f"未找到待提取文档: {extract_source_path}")
    
    # 检查文件是否可读
    if not os.access(extract_source_path, os.R_OK):
        raise PermissionError(f"无法读取待提取文档: {extract_source_path}")
    
    def _iter_paragraph_hits(doc, text: str, target_size: float):
        """遍历所有段落，返回所有匹配 text 且字号接近 target_size 的候选。"""
        hits = []
        for para in doc.Paragraphs:
            try:
                raw = para.Range.Text
                stripped = raw.strip()
                if stripped != text:
                    continue
                
                font_name = para.Range.Font.Name
                font_size = para.Range.Font.Size
                page = para.Range.Information(wdActiveEndPageNumber)
                
                # 字体可放宽：只要是宋体/SimSun即可；字号按你的逻辑
                is_font = (font_name == "宋体" or font_name == "SimSun")
                is_size = abs(float(font_size) - float(target_size)) < 0.5
                
                hits.append({
                    "page": int(page),
                    "start": int(para.Range.Start),
                    "end": int(para.Range.End),
                    "font": str(font_name),
                    "size": float(font_size),
                    "is_font": is_font,
                    "is_size": is_size,
                })
            except Exception:
                continue
        return hits
    
    def _pick_anchor(hits, prefer_last: bool = True):
        """从候选里选一个锚点：默认选页码最大的（避开目录）。"""
        if not hits:
            return None
        # 优先：字体正确 + 字号正确
        strict = [h for h in hits if h["is_font"] and h["is_size"]]
        pool = strict if strict else hits
        pool.sort(key=lambda x: (x["page"], x["start"]))
        return pool[-1] if prefer_last else pool[0]
    
    extracted_content = ""
    wps = None
    doc = None
    com_initialized = False
    
    try:
        # 使用统一的工具函数创建 Word 应用程序
        # 在并发环境下使用独立实例，避免多用户冲突
        wps, com_initialized = create_word_application(
            initial_delay=0.5,  # 创建前等待，让之前的实例有时间完全关闭
            post_init_delay=0.5,  # 给 Word 一点时间完成初始化
            use_existing=False,  # 并发环境下必须使用独立实例
            verify=True,
            node_name="extract_tender_params"
        )

        # 使用统一的工具函数打开文档（带重试机制）
        doc = open_document_with_retry(
            word_app=wps,
            file_path=extract_source_path,
            read_only=True,  # 只读模式，只需要提取内容
            node_name="extract_tender_params"
        )
        
        # 使用统一的工具函数取消文档保护
        unprotect_document(doc, node_name="extract_tender_params")
        
        target_size = 18.0 if state.get("tender_type") == "xjcg" else 22.0
        
        # === 用段落扫描查找前置文本 ===
        print(f"正在用段落扫描查找前置文本 '{before_text}' (目标字号={target_size}) ...")
        before_hits = _iter_paragraph_hits(doc, before_text, target_size)
        print(f"  前置文本命中数量: {len(before_hits)}")
        for i, h in enumerate(before_hits[:10], 1):
            print(f"    命中{i}: 页={h['page']}, {h['start']}-{h['end']}, 字体={h['font']}, 字号={h['size']}")
        
        before_hit = _pick_anchor(before_hits, prefer_last=True)  # 取页码最大的，避免目录
        
        if not before_hit:
            print(f"警告: 未找到前置文本 '{before_text}'")
            extracted_content = ""
        else:
            before_page = before_hit["page"]
            before_end_pos = before_hit["end"]
            print(f"✅ 前置锚点选中: 页={before_page}, end_pos={before_end_pos}, 字体={before_hit['font']}, 字号={before_hit['size']}")
            
            # 可选：对齐到下一页起始
            try:
                selection = wps.Selection
                selection.GoTo(wdGoToPage, wdGoToAbsolute, before_page + 1)
                next_page_start = selection.Start
                if next_page_start > before_end_pos:
                    before_end_pos = next_page_start
                    print(f"将 before_end_pos 对齐到下一页起始: {before_end_pos}")
            except Exception as adj_e:
                print(f"警告: 无法对齐 before_end_pos 到下一页起始: {adj_e}")
            
            # === 用段落扫描查找后置文本 ===
            print(f"正在用段落扫描查找后置文本 '{after_text}' (目标字号={target_size}) ...")
            after_hits = _iter_paragraph_hits(doc, after_text, target_size)
            
            # 只保留在前置锚点之后出现的后置锚点
            after_hits = [h for h in after_hits if h["start"] >= before_end_pos]
            print(f"  后置文本命中数量(过滤后): {len(after_hits)}")
            for i, h in enumerate(after_hits[:10], 1):
                print(f"    命中{i}: 页={h['page']}, {h['start']}-{h['end']}, 字体={h['font']}, 字号={h['size']}")
            
            after_hit = _pick_anchor(after_hits, prefer_last=False)  # 取最早的第四章
            
            if not after_hit:
                print(f"警告: 未找到后置文本 '{after_text}'")
                extracted_content = ""
            else:
                after_page = after_hit["page"]
                after_start_pos = after_hit["start"]
                after_end_pos = after_hit["end"]
                print(f"✅ 后置锚点选中: 页={after_page}, start={after_start_pos}, end={after_end_pos}, 字体={after_hit['font']}, 字号={after_hit['size']}")
                
                if after_page <= before_page:
                    print(f"错误: 后置文本页码 ({after_page}) 小于等于前置文本页码 ({before_page})")
                    extracted_content = ""
                else:
                    # 提取两个锚点之间的全部原始内容
                    between_rng = doc.Range(before_end_pos, after_start_pos)
                    extracted_content = extract_content_with_tables(between_rng)
                    total_chars = len(extracted_content)
                    non_whitespace_chars = len([c for c in extracted_content if not c.isspace()])
                    line_count = len(extracted_content.splitlines())
                    table_count = len(list(between_rng.Tables))
                    print(f"成功提取锚点之间内容，总长度: {total_chars} 字符，非空白字符: {non_whitespace_chars} 字符，行数: {line_count} 行，表格数量: {table_count} 个")
                    
                    # 记录页码范围供后续节点参考
                    start_page = before_page + 1
                    end_page = after_page - 1
                    print(f"[extract_tender_params] 内容提取完成，页码范围: {start_page} - {end_page}")
        
    except Exception as e:
        error_msg = f"提取内容时发生错误: {e}"
        print(f"[extract_tender_params] {error_msg}")
        # 打印详细的错误堆栈信息
        import traceback
        print(f"[extract_tender_params] 详细错误堆栈:")
        traceback.print_exc()
        # 终止图运行：抛出异常而不是吞掉错误
        raise RuntimeError(error_msg) from e
        
    finally:
        print("[extract_tender_params] 开始清理资源...")
        # 使用统一的工具函数关闭 Word 应用程序
        close_word_application(
            word_app=wps,
            doc=doc,
            com_initialized=com_initialized,
            wait_time=1.0,
            node_name="extract_tender_params"
        )
    
    # 更新状态
    new_state_dict = dict(state)
    new_state_dict["origin_tender_params"] = extracted_content
    # 保存页码范围供后续节点复用
    new_state_dict["start_page"] = locals().get("start_page")
    new_state_dict["end_page"] = locals().get("end_page")
    
    tender_param_paths = state.get("tender_param_paths")
    if tender_param_paths and not isinstance(tender_param_paths, (list, tuple)):
        tender_param_paths = [tender_param_paths]
    
    if tender_param_paths:
        print(f"[extract_tender_params] 检测到技术参数文件路径，开始提取技术参数...")
        tender_params_parts: list[str] = []
        for tender_param_file_path in tender_param_paths:
            if not tender_param_file_path:
                continue
            
            file_path_obj = pathlib.Path(str(tender_param_file_path))
            if not file_path_obj.exists():
                raise ValueError(f"tender_param_paths 中的路径不存在: {file_path_obj}")
            if not file_path_obj.is_file():
                raise ValueError(f"tender_param_paths 中的路径不是文件: {file_path_obj}")
            
            file_text = extract_text_from_word_file(str(file_path_obj))
            print(f"[extract_tender_params] 从文件提取技术参数完成: {file_path_obj.name}，长度: {len(file_text)}")
            tender_params_parts.append(file_text)
        
        tender_params = "\n\n".join([p for p in tender_params_parts if p]).strip()
        new_state_dict["tender_params"] = tender_params
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"[extract_tender_params] 执行完成，耗时: {elapsed_time:.2f} 秒 ({elapsed_time*1000:.0f} 毫秒)")
    
    return new_state_dict



if __name__ == "__main__":
    """
    测试模块：测试从指定文档中提取参数的功能（GNGK版本）
    """
    import pathlib
    import sys
    
    # 添加项目根目录到路径，以便导入模块
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    
    
    # 重新导入必要的模块（从项目根目录直接导入）
    from states import GngkTenderGraphState
    from util.word_application_util import create_word_application, close_word_application, open_document_with_retry
    from util.word_constants import wdGoToPage, wdGoToAbsolute
    
    # 测试文档路径列表
    test_doc_paths = [
        "test_word/251534-招标文件-清洁稿.doc"
    ]
    
    # 循环测试每个文件
    for doc_idx, test_doc_path_str in enumerate(test_doc_paths, 1):
        # 基于项目根目录解析路径
        test_doc_path = (ROOT / test_doc_path_str).resolve()
        
        print("\n" + "=" * 80)
        print(f"测试 {doc_idx}/{len(test_doc_paths)}: extract_tender_params 节点 (GNGK)")
        print("=" * 80)
        print(f"测试文档路径: {test_doc_path}")
        print(f"文档是否存在: {test_doc_path.exists()}")
        print()
        
        if not test_doc_path.exists():
            print(f"警告: 文档不存在: {test_doc_path}，跳过此文件")
            print()
            continue
        
        # 在处理下一个文档前，确保之前的 WPS 实例已完全关闭
        if doc_idx > 1:
            import time
            print("等待之前的 WPS 实例完全关闭...")
            time.sleep(1.0)  # 增加等待时间，确保 WPS 完全关闭
        
        # 创建测试状态（GNGK版本）
        test_state: GngkTenderGraphState = {
            "tender_type": "gngk",
            "prepared_doc_path": str(test_doc_path),
            "insertion_before_text": "第三章 招标内容及要求",
            "insertion_after_text": "第四章 投标文件有关格式",
        }
        
        try:
            # 调用 extract_tender_params 函数
            result_state = extract_tender_params(test_state, config=None)
            
            tender_params = result_state.get("origin_tender_params", "") 
            if tender_params:
                print(f"\n成功提取内容，长度: {len(tender_params)} 字符")
                
                # 保存完整内容到文件
                output_file = test_doc_path.parent / f"{test_doc_path.stem}_extracted_params_gngk.txt"
                try:
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(tender_params)
                    print(f"完整内容已保存到文件: {output_file}")
                except Exception as save_e:
                    print(f"警告: 保存文件时出错: {save_e}")
            else:
                print("\n未提取到任何内容（可能未找到前后文本或内容为空）")
            
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()
            print(f"\n继续测试下一个文件...")
            print()
            continue

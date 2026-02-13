"""
询价采购表单模块

实现询价采购文档生成的表单界面，包括：
- 招标编号输入和数据获取
- Word 文件上传
- 模型选择
- 招标数据显示
- 输入验证
- 初始状态准备
"""

from __future__ import annotations

import pathlib
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

import streamlit as st

from forms.base_form import BaseForm, render_tender_data_display, save_uploaded_file
from util.fetch_tender_data import fetch_tender_data


class XjcgTenderForm(BaseForm):
    """
    询价采购表单类
    
    继承自 BaseForm，实现询价采购文档生成的表单界面。
    
    功能：
    - 招标编号输入和自动获取（支持 URL 参数）
    - Word 模板文件上传
    - 技术参数文件上传（支持多文件）
    - 生成模型选择
    - 招标数据显示
    - 输入验证
    - 文件保存和初始状态准备
    """
    
    def render_input_fields(self) -> Dict[str, Any]:
        """
        渲染输入字段
        
        包括：
        1. 招标编号输入和获取按钮（支持 URL 参数自动填充）
        2. 招标数据显示（获取成功后）
        3. Word 模板文件上传
        4. 技术参数文件上传（支持多文件）
        5. 生成模型选择
        
        Returns:
            包含表单数据的字典，包含以下键：
            - tender_no_input: 招标编号
            - uploaded_file: 上传的模板文件
            - origin_text_files: 上传的技术参数文件列表
            - model_option: 选择的模型
        """
        st.markdown(
            "1. 输入完整的招标编号（包含招标编号前缀），点击\"获取项目信息\"获取项目信息\n"
            "2. 上传清洁稿或送审稿 Word 文档（至少上传 1 个）：两者都上传时优先以清洁稿为范本\n"
            "3. 若上传了送审稿，系统将走批注链路（get_comments/copy_comments/generate_comments）\n"
            "4. 上传包含采购需求参数的 Word 文件\n"
            "5. 点击\"开始生成\"后等待完成提示，再到对应路径查看 Word 结果或直接下载\n"
            "注意：如果是从.doc转换.docx的文件，请注意勾选保留与WPS文字早期版本的兼容性或勾选保留与Word早期版本的兼容性！否则生成内容会出错\n\n"
        )
        
        # URL 带 tenderno 时由应用层已拉取数据并写入 session，此处仅标记已处理，避免重复请求
        if not st.session_state.get("url_params_processed", False):
            st.session_state.url_params_processed = True
        
        # 招标编号输入和获取按钮
        col1, col2 = st.columns([8, 1])
        with col1:
            # 如果 URL 中有 tenderno 参数，使用它作为默认值
            default_tender_no = st.session_state.get("auto_fetched_tender_no", "")
            tender_no_input = st.text_input(
                "招标编号",
                value=default_tender_no,
                placeholder="请输入招标编号",
                key="xjcg_tender_no_input"
            )
        with col2:
            st.write("")  # 占位，用于对齐按钮
            st.write("")  # 占位，用于对齐按钮
            fetch_button = st.button(
                "获取信息",
                key="xjcg_fetch_tender_data",
                use_container_width=True,
                disabled=st.session_state.get("is_generating", False)
            )
        
        # 处理获取按钮点击
        if fetch_button:
            if not tender_no_input or not tender_no_input.strip():
                st.error("请输入招标编号")
            else:
                try:
                    with st.spinner("正在获取招标数据..."):
                        result = fetch_tender_data(tender_no_input.strip())
                        st.session_state.tender_data = result["data"]
                        st.success("数据获取成功！")
                except Exception as e:
                    st.error(f"获取数据失败：{str(e)}")
        
        # 显示当前使用的数据（只有获取到数据后才显示）
        if st.session_state.get("tender_data") is not None:
            render_tender_data_display(st.session_state.tender_data)
        
        
        # 文件上传表单
        with st.form("xjcg_tender_doc_form"):
            clean_draft_file = st.file_uploader(
                "清洁稿 Word 文档（clean_draft_path）",
                type=["doc", "docx"],
                help="请上传清洁稿 Word 文件（.doc 或 .docx）",
                key="xjcg_clean_draft_file",
            )
            origin_tender_file = st.file_uploader(
                "送审稿 Word 文档（origin_tender_path）",
                type=["doc", "docx"],
                help="若需要生成内容带批注，请上传送审稿 Word 文档（.doc 或 .docx），系统将提取批注内容作为参考",
                key="xjcg_origin_tender_file",
            )
            origin_text_files = st.file_uploader(
                "技术参数文件（tender_param_paths）",
                type=["doc", "docx"],
                help="请上传包含原始技术参数的 Word 文件（.doc 或 .docx），支持多文件",
                accept_multiple_files=True,
            )
            
            # 添加模型选择
            model_option = st.selectbox(
                "选择生成模型",
                ["深度求索(DeepSeek)", "通义千问(Qwen)", "豆包(Doubao)"],
                index=0,
                key="xjcg_llm_model_select"
            )
            
            submitted = st.form_submit_button(
                "开始生成",
                disabled=st.session_state.get("is_generating", False),
                use_container_width=True
            )
        
        # 返回表单数据
        return {
            "tender_no_input": tender_no_input,
            "clean_draft_file": clean_draft_file,
            "origin_tender_file": origin_tender_file,
            "origin_text_files": origin_text_files,
            "model_option": model_option,
            "submitted": submitted,
        }

    def validate_inputs(self, form_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证输入数据
        
        验证规则：
        1. 必须上传 Word 模板文件
        2. 必须上传技术参数文件
        3. 必须上传送审稿 Word 文档
        4. 必须先获取招标数据
        
        Args:
            form_data: 表单数据字典
        
        Returns:
            (是否有效, 错误信息) 元组
        """
        if not form_data.get("submitted"):
            return True, ""
        
        if not form_data["origin_text_files"]:
            return False, "请上传原始技术参数文件"
        
        if not form_data.get("clean_draft_file") and not form_data.get("origin_tender_file"):
            return False, "请至少上传清洁稿或送审稿 Word 文档"
        
        if st.session_state.get("tender_data") is None:
            return False, "请先点击\"获取\"按钮获取招标数据"
        
        return True, ""

    def prepare_initial_state(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        准备 graph 的初始状态
        
        处理步骤：
        1. 保存上传的模板文件到指定目录
        2. 保存上传的技术参数文件到指定目录（支持多文件）
        3. 从 session_state 获取招标数据
        4. 映射模型名称到内部标识符
        5. 构建初始状态字典
        
        Args:
            form_data: 表单数据字典
        
        Returns:
            包含 graph 初始状态的字典
        """
        clean_draft_file = form_data.get("clean_draft_file")
        origin_tender_file = form_data.get("origin_tender_file")
        origin_text_files = form_data["origin_text_files"]
        model_option = form_data["model_option"]
        tender_data = st.session_state.tender_data
        
        origin_tender_path: str = ""
        if origin_tender_file:
            origin_tender_path = save_uploaded_file(origin_tender_file)

        clean_draft_path: str = ""
        if clean_draft_file:
            clean_draft_path = save_uploaded_file(clean_draft_file)
        
        template_source_path = clean_draft_path or origin_tender_path
        if not template_source_path:
            raise ValueError("请至少上传清洁稿或送审稿 Word 文档")
        
        saved_param_paths: list[str] = []
        for origin_text_file in origin_text_files:
            saved_param_paths.append(save_uploaded_file(origin_text_file))
        
        tender_param_paths = saved_param_paths
        
        initial_state = {
            "tender_type": "xjcg",
            "origin_tender_path": origin_tender_path,
            "tender_param_paths": tender_param_paths,
            "clean_draft_path": template_source_path,
            "insertion_before_text": "第三章  采购需求",
            "insertion_after_text": "第四章  响应文件有关格式",
            "project_name": tender_data["project_name"],
            "project_number": tender_data["project_number"],
            "project_content": tender_data["project_content"],
            "bzj_rule": tender_data["bzj_rule"],
            "buyer_name": tender_data["buyer_name"],
            "project_zbr_xbr": tender_data["project_zbr_xbr"],
            "zbr_xbr_tel": tender_data["zbr_xbr_tel"],
            "zbr_pinyin": tender_data["zbr_pinyin"],
            "shell_start_date": tender_data.get("shell_start_date", ""),
            "shell_end_date": tender_data.get("shell_end_date", ""),
            "submit_date": tender_data.get("submit_date", ""),
            "platform": tender_data.get("platform", ""),
            "service_fee": tender_data.get("service_fee", ""),
        }
        
        st.session_state.generation_params = {
            **st.session_state.get("generation_params", {}),
            "model_option": model_option,
            "tender_data": tender_data,
        }
        
        return initial_state

    def render(self):
        """
        渲染完整表单
        
        覆盖基类的 render() 方法，因为此表单使用 st.form 包装，
        提交按钮在 render_input_fields() 中处理。
        """
        form_data = self.render_input_fields()
        
        if form_data.get("submitted") and not st.session_state.get("is_generating", False):
            is_valid, error_msg = self.validate_inputs(form_data)
            if not is_valid:
                st.error(error_msg)
                return
            
            initial_state = self.prepare_initial_state(form_data)
            self.start_generation(initial_state)


def render_review_draft_upload() -> Optional[str]:
    uploaded_file = st.file_uploader(
        "上传送清洁稿 Word 文档",
        type=["doc", "docx"],
        help="上传清洁稿件 Word 文档",
        key="clean_draft_file",
    )

    if uploaded_file is None:
        return None

    file_extension = uploaded_file.name.split(".")[-1].lower() if "." in uploaded_file.name else ""
    if file_extension not in ["doc", "docx"]:
        st.error("仅支持 .doc 和 .docx 格式的文件")
        return None

    upload_dir = pathlib.Path("D:/UploadFiles")
    upload_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{uploaded_file.name}"
    file_path = upload_dir / safe_filename

    try:
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"文件已上传: {safe_filename}")
        return str(file_path)
    except Exception as e:
        st.error(f"文件保存失败: {str(e)}")
        return None

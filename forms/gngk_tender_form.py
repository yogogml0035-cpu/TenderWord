"""
国内公开招标表单模块

实现国内公开招标文档生成的表单界面，包括：
- 招标编号输入和数据获取
- Word 文件上传
- 模型选择
- 招标数据显示
- 输入验证
- 初始状态准备
"""

from __future__ import annotations

import pathlib
import time
import uuid
from typing import Dict, Any, Tuple

import streamlit as st

from forms.base_form import BaseForm
from util.fetch_tender_data import fetch_tender_data


# 定义上传目录
UPLOAD_DIR = pathlib.Path("D:/UploadFiles")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class GngkTenderForm(BaseForm):
    """
    国内公开招标表单类
    
    继承自 BaseForm，实现国内公开招标文档生成的表单界面。
    
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
            "2. 上传作为参考的国内公开招标 Word 文件（清洁稿）注意：如果是从.doc转换.docx的文件，请注意勾选保留与WPS文字早期版本的兼容性或勾选保留与Word早期版本的兼容性！否则生成内容会出错\n"
            "3. 上传包含采购需求参数的 Word 文件\n"
            "4. 点击\"开始生成\"后等待完成提示，再到对应路径查看 Word 结果或直接下载\n\n"
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
                key="tender_no_input"
            )
        with col2:
            st.write("")  # 占位，用于对齐按钮
            st.write("")  # 占位，用于对齐按钮
            fetch_button = st.button(
                "获取信息",
                key="fetch_tender_data",
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
            self._render_tender_data_display()
        
        # 文件上传表单
        with st.form("tender_doc_form"):
            uploaded_file = st.file_uploader(
                "参考 Word 文件（origin_tender_path）",
                type=["doc", "docx"],
                help="请上传作为参考的 Word 文件（.doc 或 .docx）",
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
                key="llm_model_select"
            )
            
            submitted = st.form_submit_button(
                "开始生成",
                disabled=st.session_state.get("is_generating", False),
                use_container_width=True
            )
        
        # 返回表单数据
        return {
            "tender_no_input": tender_no_input,
            "uploaded_file": uploaded_file,
            "origin_text_files": origin_text_files,
            "model_option": model_option,
            "submitted": submitted
        }
    
    def _render_tender_data_display(self):
        """
        渲染招标数据显示
        
        显示从接口获取的招标数据，包括：
        - 项目名称、编号、内容
        - 保证金规则
        - 采购人信息
        - 主办人/协办人信息
        - 其他可选字段（售标时间、递交时间、平台、服务费等）
        """
        tender_data = st.session_state.tender_data
        st.markdown("**本次文件生成替换的内容：**")
        st.markdown(f"- 项目名称替换为：{tender_data['project_name']}")
        st.markdown(f"- 项目编号替换为：{tender_data['project_number']}")
        
        # 格式化显示项目内容
        project_content = tender_data['project_content'].strip()
        st.markdown("- 项目内容替换为：")
        if project_content:
            # 如果有换行符，按行显示；否则直接显示
            if '\n' in project_content:
                project_content_lines = project_content.split('\n')
                for line in project_content_lines:
                    if line.strip():
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {line.strip()}", unsafe_allow_html=True)
            else:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {project_content}", unsafe_allow_html=True)
        
        # 格式化显示保证金规则
        bzj_rule = tender_data['bzj_rule'].strip()
        st.markdown("- 保证金规则替换为：")
        if bzj_rule:
            # 如果有换行符，按行显示；否则直接显示
            if '\n' in bzj_rule:
                bzj_rule_lines = bzj_rule.split('\n')
                for line in bzj_rule_lines:
                    if line.strip():
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {line.strip()}", unsafe_allow_html=True)
            else:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {bzj_rule}", unsafe_allow_html=True)
        
        st.markdown(f"- 采购人名称替换为：{tender_data['buyer_name']}")
        st.markdown(f"- 项目主办人/协办人替换为：{tender_data['project_zbr_xbr']}")
        st.markdown(f"- 主办人/协办人电话替换为：{tender_data['zbr_xbr_tel']}")
        st.markdown(f"- 主办人拼音替换为：{tender_data['zbr_pinyin']}")
        
        # 显示可选字段
        shell_start_date = tender_data.get("shell_start_date", "")
        shell_end_date = tender_data.get("shell_end_date", "")
        submit_date = tender_data.get("submit_date", "")
        platform = tender_data.get("platform", "")
        service_fee = tender_data.get("service_fee", "")

        if shell_start_date:
            st.markdown(f"- 售标开始时间替换为：{shell_start_date}")
        if shell_end_date:
            st.markdown(f"- 售标结束时间替换为：{shell_end_date}")
        if submit_date:
            st.markdown(f"- 递交文件截止时间替换为：{submit_date}")
        if platform:
            st.markdown(f"- 发布平台替换为：{platform}")
        if service_fee:
            st.markdown(f"- 服务费规则替换为：{service_fee}")
    
    def validate_inputs(self, form_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证输入数据
        
        验证规则：
        1. 必须上传 Word 模板文件
        2. 必须上传技术参数文件
        3. 必须先获取招标数据
        
        Args:
            form_data: 表单数据字典
        
        Returns:
            (是否有效, 错误信息) 元组
        """
        # 只在表单提交时验证
        if not form_data.get("submitted"):
            return True, ""
        
        if not form_data["uploaded_file"]:
            return False, "请上传 Word 模板文件"
        
        if not form_data["origin_text_files"]:
            return False, "请上传原始技术参数文件"
        
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
        uploaded_file = form_data["uploaded_file"]
        origin_text_files = form_data["origin_text_files"]
        model_option = form_data["model_option"]
        tender_data = st.session_state.tender_data
        
        # 保存上传的模板文件到指定目录
        template_extension = pathlib.Path(uploaded_file.name).suffix
        saved_reference_path = UPLOAD_DIR / uploaded_file.name
        
        # 如果文件已存在，添加时间戳（精确到时分秒）避免覆盖
        if saved_reference_path.exists():
            timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
            name_without_ext = saved_reference_path.stem
            saved_reference_path = UPLOAD_DIR / f"{name_without_ext}_{timestamp}{template_extension}"
        
        # 保存模板文件
        with open(saved_reference_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # 保存技术参数文件
        saved_param_paths: list[str] = []
        for origin_text_file in origin_text_files:
            origin_extension = pathlib.Path(origin_text_file.name).suffix
            saved_param_path = UPLOAD_DIR / origin_text_file.name
            
            if saved_param_path.exists():
                timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
                name_without_ext = saved_param_path.stem
                unique_suffix = uuid.uuid4().hex[:8]
                saved_param_path = UPLOAD_DIR / f"{name_without_ext}_{timestamp}_{unique_suffix}{origin_extension}"
            
            with open(saved_param_path, "wb") as f:
                f.write(origin_text_file.getbuffer())
            
            saved_param_paths.append(str(saved_param_path.resolve()))
        
        origin_tender_path = str(saved_reference_path.resolve())
        tender_param_paths = saved_param_paths
        
        # 准备初始状态
        initial_state = {
            # 招标类型标识符
            "tender_type": "gngk",
            # 上传文件路径
            "origin_tender_path": origin_tender_path,
            "tender_param_paths": tender_param_paths,
            # 固定参数（与 graph.py 中保持一致）
            "insertion_before_text": "第三章 招标内容及要求",
            "insertion_after_text": "第四章 投标文件有关格式",
            "project_name": tender_data["project_name"],
            "project_number": tender_data["project_number"],
            "project_content": tender_data["project_content"],
            "bzj_rule": tender_data["bzj_rule"],
            "buyer_name": tender_data["buyer_name"],
            "project_zbr_xbr": tender_data["project_zbr_xbr"],
            "zbr_xbr_tel": tender_data["zbr_xbr_tel"],
            "zbr_pinyin": tender_data["zbr_pinyin"],
            # 新增字段
            "shell_start_date": tender_data.get("shell_start_date", ""),
            "shell_end_date": tender_data.get("shell_end_date", ""),
            "submit_date": tender_data.get("submit_date", ""),
            "platform": tender_data.get("platform", ""),
            "service_fee": tender_data.get("service_fee", ""),
        }
        
        # 保存模型选项到 generation_params（用于后续显示）
        st.session_state.generation_params = {
            **st.session_state.get("generation_params", {}),
            "model_option": model_option,
            "tender_data": tender_data  # 显式保存一份，防止意外
        }
        
        return initial_state
    
    def render(self):
        """
        渲染完整表单
        
        覆盖基类的 render() 方法，因为此表单使用 st.form 包装，
        提交按钮在 render_input_fields() 中处理。
        """
        # 1. 渲染输入字段（包含表单和提交按钮）
        form_data = self.render_input_fields()
        
        # 2. 只在表单提交时处理
        if form_data.get("submitted") and not st.session_state.get("is_generating", False):
            # 3. 验证输入
            is_valid, error_msg = self.validate_inputs(form_data)
            if not is_valid:
                st.error(error_msg)
                return
            
            # 4. 准备初始状态
            initial_state = self.prepare_initial_state(form_data)
            
            # 5. 触发生成流程
            self.start_generation(initial_state)

"""
Base form class for the project refactoring.

This module defines the BaseForm abstract class that all specific form
implementations should inherit from. It provides a standard interface for:
- Rendering input fields
- Validating user inputs
- Preparing initial state for graph execution
- Starting the generation process

The BaseForm class implements the Template Method pattern, where the render()
method defines the overall form rendering flow, and subclasses implement
specific steps through abstract methods.
"""

from abc import ABC, abstractmethod
import pathlib
import time
import uuid
from typing import Any, Dict, Tuple

import streamlit as st


UPLOAD_DIR = pathlib.Path("D:/UploadFiles")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_uploaded_file(uploaded_file) -> str:
    file_extension = pathlib.Path(uploaded_file.name).suffix
    saved_path = UPLOAD_DIR / uploaded_file.name
    if saved_path.exists():
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        name_without_ext = saved_path.stem
        unique_suffix = uuid.uuid4().hex[:8]
        saved_path = UPLOAD_DIR / f"{name_without_ext}_{timestamp}_{unique_suffix}{file_extension}"

    with open(saved_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return str(saved_path.resolve())


def render_tender_data_display(tender_data: dict):
    st.markdown("**本次文件生成替换的内容：**")
    st.markdown(f"- 项目名称替换为：{tender_data['project_name']}")
    st.markdown(f"- 项目编号替换为：{tender_data['project_number']}")

    project_content = tender_data["project_content"].strip()
    st.markdown("- 项目内容替换为：")
    if project_content:
        if "\n" in project_content:
            project_content_lines = project_content.split("\n")
            for line in project_content_lines:
                if line.strip():
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {line.strip()}", unsafe_allow_html=True)
        else:
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {project_content}", unsafe_allow_html=True)

    bzj_rule = tender_data["bzj_rule"].strip()
    st.markdown("- 保证金规则替换为：")
    if bzj_rule:
        if "\n" in bzj_rule:
            bzj_rule_lines = bzj_rule.split("\n")
            for line in bzj_rule_lines:
                if line.strip():
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {line.strip()}", unsafe_allow_html=True)
        else:
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;- {bzj_rule}", unsafe_allow_html=True)

    st.markdown(f"- 采购人名称替换为：{tender_data['buyer_name']}")
    st.markdown(f"- 项目主办人/协办人替换为：{tender_data['project_zbr_xbr']}")
    st.markdown(f"- 主办人/协办人电话替换为：{tender_data['zbr_xbr_tel']}")
    st.markdown(f"- 主办人拼音替换为：{tender_data['zbr_pinyin']}")

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


class BaseForm(ABC):
    """
    Base form class that defines the standard interface for all forms.
    
    All specific form classes should inherit from this class and implement
    the abstract methods to provide form-specific behavior.
    
    Attributes:
        config: Form configuration object containing metadata like form_id,
                tab_name, graph_name, state_name, url_params, and description.
    
    Example:
        class MyForm(BaseForm):
            def render_input_fields(self) -> Dict[str, Any]:
                # Render form inputs
                name = st.text_input("Name")
                return {"name": name}
            
            def validate_inputs(self, form_data: Dict[str, Any]) -> Tuple[bool, str]:
                # Validate inputs
                if not form_data["name"]:
                    return False, "Name is required"
                return True, ""
            
            def prepare_initial_state(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
                # Prepare graph initial state
                return {"name": form_data["name"]}
    """
    
    def __init__(self, form_config):
        """
        Initialize the form with configuration.
        
        Args:
            form_config: Form configuration object (FormConfig instance)
                        containing metadata about the form.
        """
        self.config = form_config
    
    @abstractmethod
    def render_input_fields(self) -> Dict[str, Any]:
        """
        Render input fields for the form.
        
        This method should use Streamlit widgets to render all input fields
        needed for the form and return the collected data as a dictionary.
        
        Returns:
            Dictionary containing form data with field names as keys and
            user inputs as values.
        
        Example:
            def render_input_fields(self) -> Dict[str, Any]:
                name = st.text_input("Name")
                age = st.number_input("Age", min_value=0)
                return {"name": name, "age": age}
        """
        pass
    
    @abstractmethod
    def validate_inputs(self, form_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate the form inputs.
        
        This method should check if all required fields are filled and
        if the data meets any specific validation requirements.
        
        Args:
            form_data: Dictionary containing form data returned by
                      render_input_fields().
        
        Returns:
            Tuple of (is_valid, error_message):
            - is_valid: True if validation passes, False otherwise
            - error_message: Error message to display if validation fails,
                           empty string if validation passes
        
        Example:
            def validate_inputs(self, form_data: Dict[str, Any]) -> Tuple[bool, str]:
                if not form_data["name"]:
                    return False, "Name is required"
                if form_data["age"] < 18:
                    return False, "Age must be at least 18"
                return True, ""
        """
        pass
    
    @abstractmethod
    def prepare_initial_state(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare the initial state for graph execution.
        
        This method should transform the form data into the initial state
        dictionary required by the graph. This may include:
        - Saving uploaded files
        - Fetching additional data
        - Formatting data for graph consumption
        
        Args:
            form_data: Dictionary containing validated form data.
        
        Returns:
            Dictionary containing the initial state for graph execution,
            with all required fields for the specific graph's state class.
        
        Example:
            def prepare_initial_state(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
                # Save uploaded file
                file_path = save_file(form_data["uploaded_file"])
                
                # Return initial state
                return {
                    "task_id": str(uuid.uuid4()),
                    "user_session_id": st.session_state.user_session_id,
                    "file_path": file_path,
                    "name": form_data["name"]
                }
        """
        pass
    
    def render(self):
        """
        Render the complete form with standard flow.
        
        This method implements the Template Method pattern, defining the
        overall form rendering flow:
        1. Render input fields
        2. Display submit button
        3. Validate inputs on submit
        4. Prepare initial state
        5. Start generation process
        
        Subclasses typically don't need to override this method unless
        they need custom rendering logic. Instead, they should implement
        the abstract methods to customize specific steps.
        """
        # 1. Render input fields
        form_data = self.render_input_fields()
        
        # 2. Submit button
        # The button is disabled during generation to prevent multiple submissions
        if st.button("开始生成", disabled=st.session_state.is_generating):
            # 3. Validate inputs
            is_valid, error_msg = self.validate_inputs(form_data)
            if not is_valid:
                st.error(error_msg)
                return
            
            # 4. Prepare initial state
            initial_state = self.prepare_initial_state(form_data)
            
            # 5. Trigger generation process
            self.start_generation(initial_state)
    
    def start_generation(self, initial_state: Dict[str, Any]):
        """
        Start the generation process.
        
        This method saves the generation parameters to session_state and
        triggers a rerun to start the actual generation process. This is
        the standard flow used by all forms.
        
        Subclasses can override this method if they need custom generation
        startup logic, but typically this default implementation is sufficient.
        
        Args:
            initial_state: Dictionary containing the initial state for
                          graph execution.
        
        Note:
            This method sets the following session_state variables:
            - generation_params: Contains initial_state and form_config
            - is_generating: Set to True to indicate generation is in progress
            - last_result: Cleared to remove previous results
        """
        # Save parameters to session_state
        st.session_state.generation_params = {
            "initial_state": initial_state,
            "form_config": self.config
        }
        
        # Set generation state
        st.session_state.is_generating = True
        st.session_state.last_result = None  # Clear previous results
        
        # Trigger rerun to start generation
        st.rerun()

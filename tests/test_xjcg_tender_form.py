"""
单元测试：询价采购表单文件验证和保存

测试 render_review_draft_upload 函数的文件验证和保存逻辑
需求: 1.3, 1.4, 1.5, 5.1
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from io import BytesIO
from pathlib import Path

# Import the function before any tests to avoid import issues with win32com
from forms.xjcg_tender_form import render_review_draft_upload


class TestFileValidation:
    """测试文件格式验证功能"""
    
    def test_valid_docx_file_accepted(self):
        """测试 .docx 文件被接受并保存"""
        # 创建模拟的上传文件
        mock_file = Mock()
        mock_file.name = "test_document.docx"
        mock_file.getbuffer.return_value = BytesIO(b"fake docx content")
        
        # 模拟 streamlit 组件和文件系统
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=mock_file), \
             patch('streamlit.error') as mock_error, \
             patch('streamlit.success') as mock_success, \
             patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()) as mock_file_open, \
             patch('forms.xjcg_tender_form.datetime') as mock_datetime_module:
            
            # 设置固定的时间戳
            mock_now = Mock()
            mock_now.strftime.return_value = "20240115_143022"
            mock_datetime_module.now.return_value = mock_now
            
            result = render_review_draft_upload()
            
            # 验证没有显示错误消息
            mock_error.assert_not_called()
            # 验证显示了成功消息
            mock_success.assert_called_once()
            # 验证返回了文件路径
            assert result is not None
            assert "20240115_143022_test_document.docx" in result
    
    def test_valid_doc_file_accepted(self):
        """测试 .doc 文件被接受并保存"""
        # 创建模拟的上传文件
        mock_file = Mock()
        mock_file.name = "test_document.doc"
        mock_file.getbuffer.return_value = BytesIO(b"fake doc content")
        
        # 模拟 streamlit 组件和文件系统
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=mock_file), \
             patch('streamlit.error') as mock_error, \
             patch('streamlit.success') as mock_success, \
             patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()) as mock_file_open, \
             patch('forms.xjcg_tender_form.datetime') as mock_datetime_module:
            
            # 设置固定的时间戳
            mock_now = Mock()
            mock_now.strftime.return_value = "20240115_143022"
            mock_datetime_module.now.return_value = mock_now
            
            result = render_review_draft_upload()
            
            # 验证没有显示错误消息
            mock_error.assert_not_called()
            # 验证显示了成功消息
            mock_success.assert_called_once()
            # 验证返回了文件路径
            assert result is not None
            assert "20240115_143022_test_document.doc" in result
    
    def test_invalid_pdf_file_rejected(self):
        """测试 .pdf 文件被拒绝并显示错误消息"""
        # 创建模拟的上传文件
        mock_file = Mock()
        mock_file.name = "test_document.pdf"
        mock_file.getbuffer.return_value = BytesIO(b"fake pdf content")
        
        # 模拟 streamlit 组件
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=mock_file), \
             patch('streamlit.error') as mock_error:
            
            result = render_review_draft_upload()
            
            # 验证显示了错误消息
            mock_error.assert_called_once_with("仅支持 .doc 和 .docx 格式的文件")
            # 验证返回 None
            assert result is None
    
    def test_invalid_txt_file_rejected(self):
        """测试 .txt 文件被拒绝并显示错误消息"""
        # 创建模拟的上传文件
        mock_file = Mock()
        mock_file.name = "test_document.txt"
        mock_file.getbuffer.return_value = BytesIO(b"fake txt content")
        
        # 模拟 streamlit 组件
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=mock_file), \
             patch('streamlit.error') as mock_error:
            
            result = render_review_draft_upload()
            
            # 验证显示了错误消息
            mock_error.assert_called_once_with("仅支持 .doc 和 .docx 格式的文件")
            # 验证返回 None
            assert result is None
    
    def test_file_without_extension_rejected(self):
        """测试没有扩展名的文件被拒绝"""
        # 创建模拟的上传文件
        mock_file = Mock()
        mock_file.name = "test_document"
        mock_file.getbuffer.return_value = BytesIO(b"fake content")
        
        # 模拟 streamlit 组件
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=mock_file), \
             patch('streamlit.error') as mock_error:
            
            result = render_review_draft_upload()
            
            # 验证显示了错误消息
            mock_error.assert_called_once_with("仅支持 .doc 和 .docx 格式的文件")
            # 验证返回 None
            assert result is None
    
    def test_uppercase_extension_accepted(self):
        """测试大写扩展名 .DOCX 被接受（验证大小写不敏感）"""
        # 创建模拟的上传文件
        mock_file = Mock()
        mock_file.name = "test_document.DOCX"
        mock_file.getbuffer.return_value = BytesIO(b"fake docx content")
        
        # 模拟 streamlit 组件和文件系统
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=mock_file), \
             patch('streamlit.error') as mock_error, \
             patch('streamlit.success'), \
             patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('forms.xjcg_tender_form.datetime') as mock_datetime_module:
            
            # 设置固定的时间戳
            mock_now = Mock()
            mock_now.strftime.return_value = "20240115_143022"
            mock_datetime_module.now.return_value = mock_now
            
            result = render_review_draft_upload()
            
            # 验证没有显示错误消息
            mock_error.assert_not_called()
            # 验证返回了文件路径
            assert result is not None
    
    def test_mixed_case_extension_accepted(self):
        """测试混合大小写扩展名 .DocX 被接受"""
        # 创建模拟的上传文件
        mock_file = Mock()
        mock_file.name = "test_document.DocX"
        mock_file.getbuffer.return_value = BytesIO(b"fake docx content")
        
        # 模拟 streamlit 组件和文件系统
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=mock_file), \
             patch('streamlit.error') as mock_error, \
             patch('streamlit.success'), \
             patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('forms.xjcg_tender_form.datetime') as mock_datetime_module:
            
            # 设置固定的时间戳
            mock_now = Mock()
            mock_now.strftime.return_value = "20240115_143022"
            mock_datetime_module.now.return_value = mock_now
            
            result = render_review_draft_upload()
            
            # 验证没有显示错误消息
            mock_error.assert_not_called()
            # 验证返回了文件路径
            assert result is not None
    
    def test_no_file_uploaded_returns_none(self):
        """测试未上传文件时返回 None"""
        # 模拟 streamlit 组件（未上传文件）
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=None), \
             patch('streamlit.error') as mock_error:
            
            result = render_review_draft_upload()
            
            # 验证没有显示错误消息
            mock_error.assert_not_called()
            # 验证返回 None
            assert result is None


class TestFileSave:
    """测试文件保存功能（需求 1.5, 5.1）"""
    
    def test_file_save_success(self):
        """测试文件成功保存到目标目录"""
        # 创建模拟的上传文件
        mock_file = Mock()
        mock_file.name = "test_document.docx"
        file_content = b"fake docx content"
        mock_file.getbuffer.return_value = BytesIO(file_content)
        
        # 模拟 streamlit 组件和文件系统
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=mock_file), \
             patch('streamlit.error') as mock_error, \
             patch('streamlit.success') as mock_success, \
             patch('pathlib.Path.mkdir') as mock_mkdir, \
             patch('builtins.open', mock_open()) as mock_file_open, \
             patch('forms.xjcg_tender_form.datetime') as mock_datetime_module:
            
            # 设置固定的时间戳
            mock_now = Mock()
            mock_now.strftime.return_value = "20240115_143022"
            mock_datetime_module.now.return_value = mock_now
            
            result = render_review_draft_upload()
            
            # 验证目录创建被调用
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            
            # 验证文件被打开并写入
            mock_file_open.assert_called_once()
            call_args = mock_file_open.call_args
            assert '20240115_143022_test_document.docx' in str(call_args[0][0])
            assert call_args[0][1] == 'wb'
            
            # 验证显示了成功消息
            assert mock_success.call_count == 1
            success_message = mock_success.call_args[0][0]
            assert "文件已上传" in success_message
            assert "20240115_143022_test_document.docx" in success_message
            
            # 验证返回了正确的文件路径
            assert result is not None
            assert "20240115_143022_test_document.docx" in result
    
    def test_file_save_exception_handling(self):
        """测试文件保存异常时显示错误消息"""
        # 创建模拟的上传文件
        mock_file = Mock()
        mock_file.name = "test_document.docx"
        mock_file.getbuffer.return_value = BytesIO(b"fake docx content")
        
        # 模拟文件写入失败
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=mock_file), \
             patch('streamlit.error') as mock_error, \
             patch('streamlit.success') as mock_success, \
             patch('pathlib.Path.mkdir'), \
             patch('builtins.open', side_effect=IOError("磁盘空间不足")), \
             patch('forms.xjcg_tender_form.datetime') as mock_datetime_module:
            
            # 设置固定的时间戳
            mock_now = Mock()
            mock_now.strftime.return_value = "20240115_143022"
            mock_datetime_module.now.return_value = mock_now
            
            result = render_review_draft_upload()
            
            # 验证显示了错误消息
            mock_error.assert_called_once()
            error_message = mock_error.call_args[0][0]
            assert "文件保存失败" in error_message
            assert "磁盘空间不足" in error_message
            
            # 验证没有显示成功消息
            mock_success.assert_not_called()
            
            # 验证返回 None
            assert result is None
    
    def test_unique_filename_generation(self):
        """测试生成带时间戳的唯一文件名"""
        # 创建模拟的上传文件
        mock_file = Mock()
        mock_file.name = "采购送审稿.docx"
        mock_file.getbuffer.return_value = BytesIO(b"fake docx content")
        
        # 模拟 streamlit 组件和文件系统
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=mock_file), \
             patch('streamlit.error'), \
             patch('streamlit.success'), \
             patch('pathlib.Path.mkdir'), \
             patch('builtins.open', mock_open()), \
             patch('forms.xjcg_tender_form.datetime') as mock_datetime_module:
            
            # 设置固定的时间戳
            mock_now = Mock()
            mock_now.strftime.return_value = "20240115_143022"
            mock_datetime_module.now.return_value = mock_now
            
            result = render_review_draft_upload()
            
            # 验证文件名包含时间戳和原始文件名
            assert result is not None
            assert "20240115_143022" in result
            assert "采购送审稿.docx" in result
    
    def test_directory_creation(self):
        """测试确保上传目录存在"""
        # 创建模拟的上传文件
        mock_file = Mock()
        mock_file.name = "test_document.docx"
        mock_file.getbuffer.return_value = BytesIO(b"fake docx content")
        
        # 模拟 streamlit 组件和文件系统
        with patch('streamlit.subheader'), \
             patch('streamlit.file_uploader', return_value=mock_file), \
             patch('streamlit.error'), \
             patch('streamlit.success'), \
             patch('pathlib.Path.mkdir') as mock_mkdir, \
             patch('builtins.open', mock_open()), \
             patch('forms.xjcg_tender_form.datetime') as mock_datetime_module:
            
            # 设置固定的时间戳
            mock_now = Mock()
            mock_now.strftime.return_value = "20240115_143022"
            mock_datetime_module.now.return_value = mock_now
            
            result = render_review_draft_upload()
            
            # 验证 mkdir 被调用，且使用了正确的参数
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)



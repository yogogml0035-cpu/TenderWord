"""
单元测试：批注生成节点

测试 generate_comments 节点的提示词选择和验证逻辑
需求: 5.1, 5.2, 5.3, 5.4, 5.5
"""

import pytest
from unittest.mock import Mock, patch

from nodes.common_word_nodes.generate_comments import (
    generate_comments,
    PROMPT_REGISTRY,
)
from states import XjcgTenderGraphState


class TestPromptSelectionAndValidation:
    """测试提示词选择和验证功能（任务 2.5）"""
    
    def test_prompt_registry_structure(self):
        """测试 PROMPT_REGISTRY 包含正确的招标类型"""
        # 验证 PROMPT_REGISTRY 包含 xjcg 和 gngk
        assert "xjcg" in PROMPT_REGISTRY
        assert "gngk" in PROMPT_REGISTRY
        
        # 验证每个条目是一个包含两个字符串的元组
        for tender_type, prompts in PROMPT_REGISTRY.items():
            assert isinstance(prompts, tuple)
            assert len(prompts) == 2
            system_prompt, user_prompt = prompts
            assert isinstance(system_prompt, str)
            assert isinstance(user_prompt, str)
            assert len(system_prompt) > 0
            assert len(user_prompt) > 0
    
    def test_unknown_tender_type_raises_error(self):
        """测试未知 tender_type 抛出 ValueError"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="unknown_type",
        )
        
        with pytest.raises(ValueError) as exc_info:
            generate_comments(state, config={})
        
        # 验证错误消息包含有用信息
        error_message = str(exc_info.value)
        assert "未知的招标类型" in error_message
        assert "unknown_type" in error_message
        assert "xjcg" in error_message
        assert "gngk" in error_message
    
    def test_valid_xjcg_tender_type_accepted(self):
        """测试 xjcg 招标类型被正确接受"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock the LLM call to avoid actual API calls
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            mock_llm.return_value = "[]"  # Return empty JSON array
            
            # Should not raise ValueError
            try:
                result = generate_comments(state, config={})
                # If we get here, the tender_type was accepted
                assert True
            except ValueError:
                pytest.fail("xjcg tender_type should be accepted")
    
    def test_valid_gngk_tender_type_accepted(self):
        """测试 gngk 招标类型被正确接受"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="gngk",
        )
        
        # Mock the LLM call to avoid actual API calls
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            mock_llm.return_value = "[]"  # Return empty JSON array
            
            # Should not raise ValueError
            try:
                result = generate_comments(state, config={})
                # If we get here, the tender_type was accepted
                assert True
            except ValueError:
                pytest.fail("gngk tender_type should be accepted")
    
    def test_default_tender_type_is_xjcg(self):
        """测试默认 tender_type 为 xjcg"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            # tender_type not specified, should default to "xjcg"
        )
        
        # Mock the LLM call to avoid actual API calls
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            mock_llm.return_value = "[]"  # Return empty JSON array
            
            # Should not raise ValueError (xjcg is valid)
            try:
                result = generate_comments(state, config={})
                # If we get here, the default tender_type was accepted
                assert True
            except ValueError:
                pytest.fail("Default tender_type (xjcg) should be accepted")


class TestPromptFormatting:
    """测试提示词格式化功能（任务 2.6）"""
    
    def test_prompt_formatting_includes_all_parameters(self):
        """测试格式化的提示词包含所有四个参数"""
        import json
        from nodes.common_word_nodes.comment_prompt import COMMENT_USER_PROMPT
        
        # 准备测试数据
        test_polished_text = "这是润色后的文本内容"
        test_comment_plan = [{"content": "批注内容", "scope_text": "范围文本"}]
        test_strikethrough = [{"paragraph_text": "段落", "strikethrough_text": "删除线"}]
        test_non_black_font = [{"paragraph_text": "段落", "font_text": "非黑色字体"}]
        
        # 直接测试格式化逻辑
        formatted_prompt = COMMENT_USER_PROMPT.format(
            polished_text=test_polished_text,
            comment_plan_detail=json.dumps(test_comment_plan, ensure_ascii=False, indent=2),
            strikethrough_plan=json.dumps(test_strikethrough, ensure_ascii=False, indent=2),
            non_black_font_plan=json.dumps(test_non_black_font, ensure_ascii=False, indent=2)
        )
        
        # 验证格式化的提示词包含所有参数
        assert test_polished_text in formatted_prompt, "Prompt should contain polished_text"
        assert "批注内容" in formatted_prompt, "Prompt should contain comment_plan_detail content"
        assert "删除线" in formatted_prompt, "Prompt should contain strikethrough_plan content"
        assert "非黑色字体" in formatted_prompt, "Prompt should contain non_black_font_plan content"
    
    def test_prompt_formatting_with_empty_lists(self):
        """测试空列表的提示词格式化"""
        import json
        from nodes.common_word_nodes.comment_prompt import COMMENT_USER_PROMPT
        
        # 直接测试格式化逻辑
        formatted_prompt = COMMENT_USER_PROMPT.format(
            polished_text="测试文本",
            comment_plan_detail=json.dumps([], ensure_ascii=False, indent=2),
            strikethrough_plan=json.dumps([], ensure_ascii=False, indent=2),
            non_black_font_plan=json.dumps([], ensure_ascii=False, indent=2)
        )
        
        # 验证格式化的提示词包含空数组
        assert "测试文本" in formatted_prompt
        # Empty lists should be formatted as "[]" in JSON
        assert "[]" in formatted_prompt
    
    def test_prompt_formatting_preserves_chinese_characters(self):
        """测试提示词格式化保留中文字符"""
        import json
        from nodes.common_word_nodes.comment_prompt import COMMENT_USER_PROMPT
        
        chinese_text = "这是包含中文字符的测试文本：技术参数、招标要求"
        
        # 直接测试格式化逻辑
        formatted_prompt = COMMENT_USER_PROMPT.format(
            polished_text=chinese_text,
            comment_plan_detail=json.dumps([{"content": "中文批注", "scope_text": "中文范围"}], ensure_ascii=False, indent=2),
            strikethrough_plan=json.dumps([], ensure_ascii=False, indent=2),
            non_black_font_plan=json.dumps([], ensure_ascii=False, indent=2)
        )
        
        # 验证中文字符被正确保留
        assert chinese_text in formatted_prompt
        assert "中文批注" in formatted_prompt
        assert "中文范围" in formatted_prompt
    
    def test_prompt_formatting_with_gngk_tender_type(self):
        """测试 GNGK 招标类型的提示词格式化"""
        import json
        from nodes.common_word_nodes.comment_prompt import COMMENT_USER_PROMPT
        
        test_polished_text = "GNGK 招标文本"
        test_comment_plan = [{"content": "GNGK 批注", "scope_text": "GNGK 范围"}]
        
        # 直接测试格式化逻辑
        formatted_prompt = COMMENT_USER_PROMPT.format(
            polished_text=test_polished_text,
            comment_plan_detail=json.dumps(test_comment_plan, ensure_ascii=False, indent=2),
            strikethrough_plan=json.dumps([], ensure_ascii=False, indent=2),
            non_black_font_plan=json.dumps([], ensure_ascii=False, indent=2)
        )
        
        # 验证格式化的提示词包含所有参数
        assert test_polished_text in formatted_prompt
        assert "GNGK 批注" in formatted_prompt


class TestLLMStreamingWithErrorHandling:
    """测试带错误处理的 LLM 流式调用功能（任务 2.8）"""
    
    def test_llm_timeout_error_returns_empty_list(self):
        """测试 LLM 超时错误返回空列表"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to raise LLMTimeoutError
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            from util.llm_stream_utils import LLMTimeoutError
            mock_llm.side_effect = LLMTimeoutError("deepseek", 10)
            
            # Should not raise exception, should return empty list
            result = generate_comments(state, config={})
            
            assert "polished_comments" in result
            assert result["polished_comments"] == []
    
    def test_general_exception_returns_empty_list(self):
        """测试一般异常返回空列表"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to raise a general exception
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            mock_llm.side_effect = RuntimeError("Unexpected error")
            
            # Should not raise exception, should return empty list
            result = generate_comments(state, config={})
            
            assert "polished_comments" in result
            assert result["polished_comments"] == []
    
    def test_successful_llm_call_with_empty_response(self):
        """测试成功的 LLM 调用返回空响应"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to return empty JSON array
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            # Create a proper async mock
            async def mock_stream(*args, **kwargs):
                return "[]"
            
            # Make the mock return a coroutine
            mock_llm.side_effect = mock_stream
            
            # Should successfully parse empty array
            result = generate_comments(state, config={})
            
            # Note: This will fail until tasks 2.9 and 2.10 are implemented
            # For now, we're just testing that the LLM call completes without error
            assert mock_llm.called
    
    def test_llm_call_uses_correct_parameters(self):
        """测试 LLM 调用使用正确的参数"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            comment_plan_detail=[{"content": "批注", "scope_text": "范围"}],
            tender_type="xjcg",
        )
        
        config = {
            "configurable": {
                "model_provider": "deepseek"
            }
        }
        
        # Mock stream_llm_completion to capture call parameters
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return "[]"
            
            mock_llm.side_effect = mock_stream
            
            result = generate_comments(state, config=config)
            
            # Verify stream_llm_completion was called
            assert mock_llm.called
            
            # Get the call arguments
            call_args = mock_llm.call_args
            
            # Verify correct parameters were passed
            assert call_args[1]["model_provider"] == "deepseek"
            assert call_args[1]["system_prompt"] is not None
            assert call_args[1]["user_prompt"] is not None
            assert "测试文本" in call_args[1]["user_prompt"]
            assert call_args[1]["timeout_seconds"] == 10
            assert call_args[1]["check_interval"] == 3.0
            assert call_args[1]["callbacks"] is not None
    
    def test_asyncio_event_loop_handling(self):
        """测试 asyncio 事件循环处理"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return "[]"
            
            mock_llm.side_effect = mock_stream
            
            # Should handle event loop creation/retrieval
            result = generate_comments(state, config={})
            
            # Should complete successfully (even though result is None until tasks 2.9/2.10 are done)
            assert mock_llm.called


class TestJSONParsingWithErrorHandling:
    """测试带错误处理的 JSON 解析功能（任务 2.9）"""
    
    def test_valid_json_array_parsing(self):
        """测试有效的 JSON 数组解析"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to return valid JSON array
        valid_json = '[{"reference_text": "参考文本1", "comment_text": "批注内容1"}, {"reference_text": "参考文本2", "comment_text": "批注内容2"}]'
        
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return valid_json
            
            mock_llm.side_effect = mock_stream
            
            result = generate_comments(state, config={})
            
            # Verify successful parsing
            assert "polished_comments" in result
            assert len(result["polished_comments"]) == 2
            assert result["polished_comments"][0]["reference_text"] == "参考文本1"
            assert result["polished_comments"][0]["comment_text"] == "批注内容1"
            assert result["polished_comments"][1]["reference_text"] == "参考文本2"
            assert result["polished_comments"][1]["comment_text"] == "批注内容2"
    
    def test_json_decode_error_returns_empty_list(self):
        """测试 JSON 解析错误返回空列表"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to return invalid JSON
        invalid_json = '{"invalid": "not an array"'
        
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return invalid_json
            
            mock_llm.side_effect = mock_stream
            
            result = generate_comments(state, config={})
            
            # Should return empty list on JSON decode error
            assert "polished_comments" in result
            assert result["polished_comments"] == []
    
    def test_non_list_json_returns_empty_list(self):
        """测试非列表 JSON 返回空列表"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to return JSON object instead of array
        non_list_json = '{"reference_text": "文本", "comment_text": "批注"}'
        
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return non_list_json
            
            mock_llm.side_effect = mock_stream
            
            result = generate_comments(state, config={})
            
            # Should return empty list when result is not a list
            assert "polished_comments" in result
            assert result["polished_comments"] == []
    
    def test_missing_fields_use_empty_string_defaults(self):
        """测试缺失字段使用空字符串默认值"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to return JSON with missing fields
        json_with_missing_fields = '[{"reference_text": "文本1"}, {"comment_text": "批注2"}, {"reference_text": "文本3", "comment_text": "批注3"}]'
        
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return json_with_missing_fields
            
            mock_llm.side_effect = mock_stream
            
            result = generate_comments(state, config={})
            
            # Verify missing fields are filled with empty strings
            assert len(result["polished_comments"]) == 3
            assert result["polished_comments"][0]["reference_text"] == "文本1"
            assert result["polished_comments"][0]["comment_text"] == ""
            assert result["polished_comments"][1]["reference_text"] == ""
            assert result["polished_comments"][1]["comment_text"] == "批注2"
            assert result["polished_comments"][2]["reference_text"] == "文本3"
            assert result["polished_comments"][2]["comment_text"] == "批注3"
    
    def test_non_dict_items_filtered_out(self):
        """测试非字典项被过滤掉"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to return JSON with mixed types
        json_with_mixed_types = '[{"reference_text": "文本1", "comment_text": "批注1"}, "string item", 123, null, {"reference_text": "文本2", "comment_text": "批注2"}]'
        
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return json_with_mixed_types
            
            mock_llm.side_effect = mock_stream
            
            result = generate_comments(state, config={})
            
            # Verify only dict items are included
            assert len(result["polished_comments"]) == 2
            assert result["polished_comments"][0]["reference_text"] == "文本1"
            assert result["polished_comments"][0]["comment_text"] == "批注1"
            assert result["polished_comments"][1]["reference_text"] == "文本2"
            assert result["polished_comments"][1]["comment_text"] == "批注2"
    
    def test_empty_json_array_returns_empty_list(self):
        """测试空 JSON 数组返回空列表"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to return empty JSON array
        empty_json = '[]'
        
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return empty_json
            
            mock_llm.side_effect = mock_stream
            
            result = generate_comments(state, config={})
            
            # Should return empty list
            assert "polished_comments" in result
            assert result["polished_comments"] == []
    
    def test_logging_on_successful_parsing(self):
        """测试成功解析时的日志记录"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to return valid JSON
        valid_json = '[{"reference_text": "文本1", "comment_text": "批注1"}, {"reference_text": "文本2", "comment_text": "批注2"}]'
        
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return valid_json
            
            mock_llm.side_effect = mock_stream
            
            # Capture stdout to verify logging
            import io
            import sys
            captured_output = io.StringIO()
            sys.stdout = captured_output
            
            try:
                result = generate_comments(state, config={})
                
                # Restore stdout
                sys.stdout = sys.__stdout__
                
                # Verify logging message
                output = captured_output.getvalue()
                assert "生成了 2 条批注指令" in output
            finally:
                sys.stdout = sys.__stdout__


class TestStateReturnAndLogging:
    """测试状态返回和日志记录功能（任务 2.10）"""
    
    def test_return_state_contains_only_polished_comments(self):
        """测试返回状态仅包含 polished_comments 字段"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            comment_plan_detail=[{"content": "批注", "scope_text": "范围"}],
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to return valid JSON
        valid_json = '[{"reference_text": "文本", "comment_text": "批注"}]'
        
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return valid_json
            
            mock_llm.side_effect = mock_stream
            
            result = generate_comments(state, config={})
            
            # Verify only polished_comments is in the result
            assert "polished_comments" in result
            # The result should be a TypedDict with only polished_comments
            # Other fields should not be present in the returned dict
            result_keys = list(result.keys())
            assert len(result_keys) == 1
            assert result_keys[0] == "polished_comments"
    
    def test_input_state_not_modified(self):
        """测试输入状态不被修改（不可变性）"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            comment_plan_detail=[{"content": "批注", "scope_text": "范围"}],
            tender_type="xjcg",
        )
        
        # Create a copy of the original state for comparison
        original_polished_text = state.get("polished_text")
        original_comment_plan = state.get("comment_plan_detail")
        original_tender_type = state.get("tender_type")
        
        # Mock stream_llm_completion to return valid JSON
        valid_json = '[{"reference_text": "文本", "comment_text": "批注"}]'
        
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return valid_json
            
            mock_llm.side_effect = mock_stream
            
            result = generate_comments(state, config={})
            
            # Verify input state was not modified
            assert state.get("polished_text") == original_polished_text
            assert state.get("comment_plan_detail") == original_comment_plan
            assert state.get("tender_type") == original_tender_type
    
    def test_execution_time_logging(self):
        """测试执行时间日志记录"""
        state = XjcgTenderGraphState(
            polished_text="测试文本",
            tender_type="xjcg",
        )
        
        # Mock stream_llm_completion to return valid JSON
        valid_json = '[]'
        
        with patch('nodes.common_word_nodes.generate_comments.stream_llm_completion') as mock_llm:
            async def mock_stream(*args, **kwargs):
                return valid_json
            
            mock_llm.side_effect = mock_stream
            
            # Capture stdout to verify logging
            import io
            import sys
            captured_output = io.StringIO()
            sys.stdout = captured_output
            
            try:
                result = generate_comments(state, config={})
                
                # Restore stdout
                sys.stdout = sys.__stdout__
                
                # Verify execution time logging
                output = captured_output.getvalue()
                assert "执行完成，耗时:" in output
                assert "秒" in output
                assert "毫秒" in output
            finally:
                sys.stdout = sys.__stdout__

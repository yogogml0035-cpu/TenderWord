"""
Unit tests for get_replacements_core module

Tests ExtractorSpec/ReplacementFieldSpec data structures and replacement logic
"""

import pytest
from typing import Any
from unittest.mock import Mock, patch

from backend.nodes.common_word_nodes.get_replacements_core import (
    ExtractorSpec,
    ReplacementFieldSpec,
    run_get_replacements,
)
from backend.states import TenderGraphStateBase


class TestExtractorSpec:
    """Test ExtractorSpec data structure"""

    def test_extractor_spec_basic(self):
        """Test basic ExtractorSpec creation"""

        def dummy_extractor(doc_content, header, state, log_parts):
            return "extracted_value"

        spec = ExtractorSpec(
            name="project_number",
            enabled_if=lambda state: True,
            extract_callable=dummy_extractor,
        )

        assert spec.name == "project_number"
        assert spec.enabled_if({}) is True
        assert spec.extract_callable("", "", {}, []) == "extracted_value"
        assert spec.output_field_names is None

    def test_extractor_spec_with_output_names(self):
        """Test ExtractorSpec with output_field_names"""

        def multi_extractor(doc_content, header, state, log_parts):
            return ("value1", "value2")

        spec = ExtractorSpec(
            name="contact_fields",
            enabled_if=lambda state: state.get("enabled", False),
            extract_callable=multi_extractor,
            output_field_names=["field1", "field2"],
        )

        assert spec.name == "contact_fields"
        assert spec.enabled_if({"enabled": True}) is True
        assert spec.enabled_if({"enabled": False}) is False
        assert spec.output_field_names == ["field1", "field2"]


class TestReplacementFieldSpec:
    """Test ReplacementFieldSpec data structure"""

    def test_replacement_field_basic(self):
        """Test basic ReplacementFieldSpec creation"""
        spec = ReplacementFieldSpec(field_name="project_number")

        assert spec.field_name == "project_number"
        assert spec.skip_if_equal is True
        assert spec.fallback_fields is None

    def test_replacement_field_with_fallback(self):
        """Test ReplacementFieldSpec with fallback"""
        spec = ReplacementFieldSpec(
            field_name="project_content_v1",
            skip_if_equal=False,
            fallback_fields=["project_content"],
        )

        assert spec.field_name == "project_content_v1"
        assert spec.skip_if_equal is False
        assert spec.fallback_fields == ["project_content"]


class TestReplacementLogic:
    """Test replacement generation logic"""

    def test_basic_replacement(self):
        """Test basic replacement generation"""
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isabs", return_value=True),
            patch("os.access", return_value=True),
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.create_word_application"
            ) as mock_create,
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.open_document_with_retry"
            ) as mock_open,
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.unprotect_document"
            ) as mock_unprotect,
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.close_word_application"
            ) as mock_close,
        ):
            mock_doc = Mock()
            mock_doc.Content.Text = "doc"
            mock_doc.Sections.return_value.Headers.return_value.Range.Text = "header"
            mock_create.return_value = (Mock(), True)
            mock_open.return_value = mock_doc
            mock_unprotect.return_value = True

            extractors = [
                ExtractorSpec(
                    name="project_number",
                    enabled_if=lambda state: True,
                    extract_callable=lambda d, h, s, l: "OLD-001",
                ),
            ]

            replacement_fields = [ReplacementFieldSpec(field_name="project_number")]

            state = TenderGraphStateBase(
                prepared_doc_path="/fake/path.docx",
                project_number="NEW-001",
            )

            result = run_get_replacements(
                state=state,
                config={},
                extractors=extractors,
                replacement_fields=replacement_fields,
            )

            assert result["replacements"] == [("OLD-001", "NEW-001")]
            assert result["placeholder_mapping"] == {"project_number": "OLD-001"}

    def test_skip_if_equal(self):
        """Test skip_if_equal logic"""
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isabs", return_value=True),
            patch("os.access", return_value=True),
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.create_word_application"
            ) as mock_create,
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.open_document_with_retry"
            ) as mock_open,
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.unprotect_document"
            ) as mock_unprotect,
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.close_word_application"
            ) as mock_close,
        ):
            mock_doc = Mock()
            mock_doc.Content.Text = "doc"
            mock_doc.Sections.return_value.Headers.return_value.Range.Text = "header"
            mock_create.return_value = (Mock(), True)
            mock_open.return_value = mock_doc
            mock_unprotect.return_value = True

            extractors = [
                ExtractorSpec(
                    name="field",
                    enabled_if=lambda state: True,
                    extract_callable=lambda d, h, s, l: "SAME",
                ),
            ]

            replacement_fields = [
                ReplacementFieldSpec(field_name="field", skip_if_equal=True)
            ]

            state = TenderGraphStateBase(
                prepared_doc_path="/fake/path.docx",
                field="SAME",
            )

            result = run_get_replacements(
                state=state,
                config={},
                extractors=extractors,
                replacement_fields=replacement_fields,
            )

            assert result["replacements"] == []

    def test_fallback_fields(self):
        """Test fallback_fields logic"""
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isabs", return_value=True),
            patch("os.access", return_value=True),
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.create_word_application"
            ) as mock_create,
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.open_document_with_retry"
            ) as mock_open,
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.unprotect_document"
            ) as mock_unprotect,
            patch(
                "backend.nodes.common_word_nodes.get_replacements_core.close_word_application"
            ) as mock_close,
        ):
            mock_doc = Mock()
            mock_doc.Content.Text = "doc"
            mock_doc.Sections.return_value.Headers.return_value.Range.Text = "header"
            mock_create.return_value = (Mock(), True)
            mock_open.return_value = mock_doc
            mock_unprotect.return_value = True

            extractors = [
                ExtractorSpec(
                    name="field_v1",
                    enabled_if=lambda state: True,
                    extract_callable=lambda d, h, s, l: "OLD",
                ),
            ]

            replacement_fields = [
                ReplacementFieldSpec(
                    field_name="field_v1",
                    fallback_fields=["field_fallback"],
                ),
            ]

            state = TenderGraphStateBase(
                prepared_doc_path="/fake/path.docx",
                field_v1="",
                field_fallback="FALLBACK-VALUE",
            )

            result = run_get_replacements(
                state=state,
                config={},
                extractors=extractors,
                replacement_fields=replacement_fields,
            )

            assert result["replacements"] == [("OLD", "FALLBACK-VALUE")]

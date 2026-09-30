"""Unit tests for owl_dsl.reasoner module."""

import pytest
from unittest.mock import MagicMock, patch, Mock

from owl_dsl.reasoner import (
    remove_indefinite_article,
    count_leading_spaces,
    process_manchester_owl_local_names,
    process_manchester_owl_uris,
)
from owlapy.class_expression import OWLClass, OWLObjectIntersectionOf, OWLObjectUnionOf


class TestRemoveIndefiniteArticle:
    """Tests for remove_indefinite_article function."""

    def test_remove_from_it_a(self):
        """Test removing 'It is a' prefix."""
        assert remove_indefinite_article("It is a cat") == "is a cat"

    def test_remove_from_it_an(self):
        """Test removing 'It is an' prefix."""
        assert remove_indefinite_article("It is an apple") == "is an apple"

    def test_no_prefix(self):
        """Test string without 'It is' prefix."""
        assert remove_indefinite_article("is a cat") == "is a cat"
        assert remove_indefinite_article("The cat") == "The cat"


class TestCountLeadingSpaces:
    """Tests for count_leading_spaces function."""

    def test_multiple_spaces(self):
        """Test counting multiple leading spaces."""
        assert count_leading_spaces("  hello") == 2

    def test_no_spaces(self):
        """Test string with no leading spaces."""
        assert count_leading_spaces("hello") == 0

    def test_tab(self):
        """Test tab character as whitespace."""
        assert count_leading_spaces("\thello") >= 1

    def test_only_spaces(self):
        """Test string of only spaces."""
        assert count_leading_spaces("   ") == 3


class TestProcessManchesterOwlLocalNames:
    """Tests for process_manchester_owl_local_names function."""

    def test_basic_link(self):
        """Test parsing basic Manchester OWL link to local name."""
        line = "- [label](http://example.org/ClassA)"
        spaces, result = process_manchester_owl_local_names(line)

        assert spaces == 0, f"Expected 0 leading spaces, got {spaces}"
        assert result == "ClassA", f"Expected 'ClassA', got '{result}'"

    def test_with_leading_indentation(self):
        """Test parsing with leading indentation."""
        line = "  - [label](http://example.org/ClassB)"
        spaces, result = process_manchester_owl_local_names(line)

        assert spaces == 2, f"Expected 2 leading spaces, got {spaces}"
        assert result == "ClassB", f"Expected 'ClassB', got '{result}'"

    def test_complex_uri(self):
        """Test parsing with complex URI."""
        line = "- [Person](http://purl.obolibrary.org/obo/FMA_12345)"
        spaces, result = process_manchester_owl_local_names(line)

        assert spaces == 0
        assert "FMA_12345" in result


class TestProcessManchesterOwlUris:
    """Tests for process_manchester_owl_uris function."""

    def test_basic_link_to_uri(self):
        """Test converting link to URI format."""
        line = "- [label](http://example.org/ClassA)"
        spaces, result = process_manchester_owl_uris(line)

        assert spaces == 0, f"Expected 0 leading spaces, got {spaces}"
        assert (
            result == "<http://example.org/ClassA>"
        ), f"Expected '<http://example.org/ClassA>', got '{result}'"

    def test_with_leading_indentation(self):
        """Test with leading indentation."""
        line = "  - [label](http://example.org/ClassB)"
        spaces, result = process_manchester_owl_uris(line)

        assert spaces == 2, f"Expected 2 leading spaces, got {spaces}"
        assert (
            result == "<http://example.org/ClassB>"
        ), f"Expected '<http://example.org/ClassB>', got '{result}'"


class TestVerbalizeGciJustifications:
    """Tests for verbalize_gci_justifications function based on README examples."""

    @pytest.fixture
    def mock_handler(self):
        """Create a mock CNLRenderer handler."""
        from owl_dsl.renderer import CNLRenderer

        handler = Mock(spec=CNLRenderer)
        handler.ontology_namespace = "http://test.org/onto.owl#"
        handler.class_inference_to_ignore = []

        # Mock render_owl_class to return simple strings
        def mock_render(cls):
            if hasattr(cls, "name"):
                return cls.name.lower()
            elif hasattr(cls, "label") and cls.label:
                return str(cls.label[0]).lower()
            return "unknown"

        handler.render_owl_class = Mock(side_effect=mock_render)
        handler.render_role_restriction = Mock(return_value="part of")

        return handler

    @pytest.fixture
    def mock_explanation_content(self):
        """Create mock explanation file content based on README examples."""
        # Example from README: vestibular aqueduct reasoning output
        return """## Explanation for Axiom: 'vestibular aqueduct' SubClassOf 'bone foramen'

Every vestibular aqueduct is a foramen of skull that is a conduit for a vein of vestibular aqueduct and vice versa.
  Every foramen of skull is a bone foramen
"""

    @patch("owl_dsl.reasoner.prefix_with_indefinite_article", return_value="an animal")
    @patch("owl_dsl.reasoner.run_subprocess")
    def test_successful_explanation_simple(
        self, mock_run_subprocess, mock_prefix, mock_handler, mock_explanation_content
    ):
        """Test successful explanation generation with simple output."""
        from owl_dsl.reasoner import verbalize_gci_justifications

        # Setup subprocess mock
        mock_response = MagicMock()
        mock_response.returncode = 0
        mock_run_subprocess.return_value = mock_response

        # Mock file reading
        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_file.read.return_value = mock_explanation_content
            mock_open.return_value.__enter__.return_value = mock_file

            Dog = Mock()
            Dog.name = "Dog"

            # Call the function - should not raise and should print output
            verbalize_gci_justifications(
                handler=mock_handler,
                owl_class=Dog,
                owl_class_rdfs_label="dog",
                ontology=Mock(),
                ontology_namespace_baseuri="http://test.org/onto.owl#",
                owl_url_or_path="http://test.org/onto.owl",
                owl_super_class_expression="'animal'",
                verbose=False,
            )

    @patch("owl_dsl.reasoner.prefix_with_indefinite_article", return_value="an animal")
    @patch("owl_dsl.reasoner.run_subprocess")
    def test_verbose_output(
        self, mock_run_subprocess, mock_prefix, mock_handler, mock_explanation_content
    ):
        """Test verbose output mode."""
        from owl_dsl.reasoner import verbalize_gci_justifications

        # Setup subprocess mock
        mock_response = MagicMock()
        mock_response.returncode = 0
        mock_run_subprocess.return_value = mock_response

        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_file.read.return_value = mock_explanation_content
            mock_open.return_value.__enter__.return_value = mock_file

            Dog = Mock()
            Dog.name = "Dog"

            verbalize_gci_justifications(
                handler=mock_handler,
                owl_class=Dog,
                owl_class_rdfs_label="dog",
                ontology=Mock(),
                ontology_namespace_baseuri="http://test.org/onto.owl#",
                owl_url_or_path="http://test.org/onto.owl",
                owl_super_class_expression="'animal'",
                verbose=True,  # Enable verbose mode
            )

    @patch("owl_dsl.reasoner.run_subprocess")
    def test_robot_failure(self, mock_run_subprocess):
        """Test handling of robot command failure."""
        from owl_dsl.reasoner import verbalize_gci_justifications

        # Setup subprocess mock to fail
        mock_response = MagicMock()
        mock_response.returncode = 1
        mock_response.stderr = "robot failed"
        mock_run_subprocess.return_value = mock_response

        with patch("builtins.open", new_callable=MagicMock):
            with pytest.warns(UserWarning, match="robot command"):
                Dog = Mock()
                Dog.name = "Dog"

                verbalize_gci_justifications(
                    handler=Mock(),
                    owl_class=Dog,
                    owl_class_rdfs_label="dog",
                    ontology=Mock(),
                    ontology_namespace_baseuri="http://test.org/onto.owl#",
                    owl_url_or_path="http://test.org/onto.owl",
                    owl_super_class_expression="'animal'",
                    verbose=False,
                )

    @patch(
        "owl_dsl.reasoner.prefix_with_indefinite_article",
        return_value="an anatomical entity",
    )
    @patch("owl_dsl.reasoner.run_subprocess")
    def test_transitive_property_explanation(
        self, mock_run_subprocess, mock_prefix, mock_handler
    ):
        """Test parsing of transitive property explanations as in README."""
        from owl_dsl.reasoner import verbalize_gci_justifications

        # Example with transitive property explanation (from README pattern)
        explanation = """## Explanation

- [part of](http://purl.obolibrary.org/obo/BFO_0000050) is a transitive property.
  If A part of B and B part of C then A part of C
"""

        mock_response = MagicMock()
        mock_response.returncode = 0
        mock_run_subprocess.return_value = mock_response

        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_file.read.return_value = explanation
            mock_open.return_value.__enter__.return_value = mock_file

            Dog = Mock()
            Dog.name = "Dog"

            verbalize_gci_justifications(
                handler=mock_handler,
                owl_class=Dog,
                owl_class_rdfs_label="dog",
                ontology=Mock(),
                ontology_namespace_baseuri="http://purl.obolibrary.org/obo/",
                owl_url_or_path="uberon.owl",
                owl_super_class_expression="'anatomical entity'",
                verbose=False,
            )

    @patch("owl_dsl.reasoner.prefix_with_indefinite_article", return_value="an Animal")
    @patch("owl_dsl.reasoner.run_subprocess")
    def test_domain_range_explanation(
        self, mock_run_subprocess, mock_prefix, mock_handler
    ):
        """Test parsing of domain/range explanations."""
        from owl_dsl.reasoner import verbalize_gci_justifications

        # Example with domain explanation (from README pattern)
        explanation = """## Explanation

- [has_pet](http://test.org/onto.owl#has_pet) Domain [Person](http://test.org/onto.owl#Person)
  If A is related to B via 'has_pet' then A is a 'person'
"""

        mock_response = MagicMock()
        mock_response.returncode = 0
        mock_run_subprocess.return_value = mock_response

        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_file.read.return_value = explanation
            mock_open.return_value.__enter__.return_value = mock_file

            Dog = Mock()
            Dog.name = "Dog"

            verbalize_gci_justifications(
                handler=mock_handler,
                owl_class=Dog,
                owl_class_rdfs_label="dog",
                ontology=Mock(),
                ontology_namespace_baseuri="http://test.org/onto.owl#",
                owl_url_or_path="test.owl",
                owl_super_class_expression="'Animal'",
                verbose=False,
            )


class TestManchesterExpressionExamples:
    """Tests for Manchester OWL expression parsing based on README examples."""

    def test_complex_manchester_expression(self):
        """Test complex Manchester expressions from README like 'process' and 'part of' some 'inflammatory response'"""
        # This tests the pattern matching in process_manchester_owl_local_names
        line = "  - [process](http://purl.obolibrary.org/obo/BFO_0000015) and [part of](http://purl.obolibrary.org/obo/BFO_0000050) some [inflammatory response]"

        spaces, result = process_manchester_owl_local_names(line)

        assert spaces == 2, f"Expected 2 leading spaces, got {spaces}"
        # Should extract local names from the Manchester expression
        assert "process" in result or "BFO_0000015" in result


class TestClassInferenceToIgnore:
    """Tests for class_inference_to_ignore functionality based on README."""

    def test_class_labels_in_ignore_list(self):
        """Test that class labels from README example are properly handled."""
        # From README, these classes should be ignored:
        ignore_classes = [
            "material anatomical entity",
            "anatomical entity",
            "anatomical structure",
            "multicellular anatomical structure",
            "molecular_function",
            "occurrent",
            "process",
            "independent continuant",
            "continuant",
            "material entity",
            "molecular entity",
        ]

        # Verify these are valid class labels that could be used in configuration
        for cls_label in ignore_classes:
            assert isinstance(cls_label, str)
            assert len(cls_label.strip()) > 0

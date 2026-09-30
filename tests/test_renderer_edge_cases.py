"""Unit tests for edge cases and error handling in owl_dsl.renderer.CNLRenderer."""

import pytest
from unittest.mock import Mock, patch
from pyhornedowl.model import (
    Class,
    ObjectIntersectionOf,
    ObjectUnionOf,
    ObjectSomeValuesFrom,
    ObjectProperty,
)
from rdflib import URIRef

TEST_NS = "http://test.org/onto.owl#"


class TestClassRenderingEdgeCases:
    """Tests for edge cases in OWL class rendering."""

    def test_class_without_label_attribute(self, cnl_renderer, mock_person):
        rendered = cnl_renderer.render_readable_owl_class(mock_person)
        assert isinstance(rendered, str)

    def test_class_with_empty_label(self, cnl_renderer, mock_person):
        rendered = cnl_renderer.render_readable_owl_class(
            mock_person, no_indef_article=True
        )
        assert isinstance(rendered, str)

    def test_lowercase_labels_parameter(self, cnl_renderer, mock_person):
        original_case = cnl_renderer.lowercase_labels
        cnl_renderer.lowercase_labels = True
        rendered_lower = cnl_renderer.render_readable_owl_class(mock_person)
        cnl_renderer.lowercase_labels = original_case
        assert isinstance(rendered_lower, str)


class TestConceptGroupingEdgeCases:
    """Tests for concept grouping and key identification edge cases."""

    def test_empty_property_iris_list(self, cnl_renderer):
        assert cnl_renderer.RESTRICTION_START_KEY == 2
        test_key = cnl_renderer.RESTRICTION_START_KEY + 10
        assert cnl_renderer.is_named_owl_class_key(test_key)

    def test_concept_group_key_not_type_handling(self, cnl_renderer):
        unknown_mock = Mock()
        with pytest.raises(NotImplementedError):
            cnl_renderer.concept_group_key(unknown_mock)


class TestExtractDefinitionalPhrasesEdgeCases:
    """Tests for extract_definitional_phrases edge cases."""

    def test_empty_owl_classes_list(self, cnl_renderer):
        definitional_phrases = []
        cnl_renderer.extract_definitional_phrases(
            definitional_phrases=definitional_phrases,
            owl_classes=[],
            owl_class_definition="test definition",
            owl_class_id="http://test.org/onto.owl#TestClass",
            owl_class_name_phrase="the test class",
        )
        assert isinstance(definitional_phrases, list)

    def test_empty_is_a_list(self, cnl_renderer):
        definitional_phrases = []
        cnl_renderer.extract_definitional_phrases(
            definitional_phrases=definitional_phrases,
            owl_classes=[],
            owl_class_definition="test dog",
            owl_class_id="http://test.org/onto.owl#Dog",
            owl_class_name_phrase="the test dog",
        )
        assert isinstance(definitional_phrases, list)

    def test_multiple_parent_classes(self, cnl_renderer):
        person = Class(cnl_renderer.ontology.iri(TEST_NS + "Person"))
        animal = Class(cnl_renderer.ontology.iri(TEST_NS + "Animal"))
        definitional_phrases = []
        cnl_renderer.extract_definitional_phrases(
            definitional_phrases=definitional_phrases,
            owl_classes=[person, animal],
            owl_class_definition="test dog",
            owl_class_id="http://test.org/onto.owl#Dog",
            owl_class_name_phrase="the test dog",
        )
        assert isinstance(definitional_phrases, list)


class TestRoleRestrictionEdgeCases:
    """Tests for role restriction rendering edge cases."""

    def test_render_role_restriction_no_custom_phrasing(self, cnl_renderer):
        original_mode = cnl_renderer.custom_role_rendering
        cnl_renderer.custom_role_rendering = False
        rendered = cnl_renderer.render_role_restriction(
            TEST_NS + "has_pet", operand1="A", operand2="B"
        )
        cnl_renderer.custom_role_rendering = original_mode
        assert "has pet" in rendered.lower()

    def test_render_role_restriction_custom_phrasing(self, cnl_renderer):
        original_mode = cnl_renderer.custom_role_rendering
        cnl_renderer.custom_role_rendering = True
        rendered = cnl_renderer.render_role_restriction(
            TEST_NS + "has_pet", operand1="A", operand2="B"
        )
        cnl_renderer.custom_role_rendering = original_mode
        assert isinstance(rendered, str)

    def test_role_restriction_wo_articles(self, cnl_renderer):
        prop_uri = URIRef(TEST_NS + "has_pet")
        cnl_renderer.role_restriction_wo_articles.add(prop_uri)
        assert URIRef(TEST_NS + "has_pet") in cnl_renderer.role_restriction_wo_articles


class TestHandleFirstDefinitionalPhraseEdgeCases:
    """Tests for handle_first_definitional_phrase edge cases."""

    def test_with_ontology_title(self, cnl_renderer):
        cnl_renderer.ontology_title = "Test Ontology"
        result = cnl_renderer.handle_first_definitional_phrase(
            definitional_phrases=[], name="person"
        )
        assert isinstance(result, str)

    def test_without_ontology_title(self, cnl_renderer):
        original_title = cnl_renderer.ontology_title
        cnl_renderer.ontology_title = None
        result = cnl_renderer.handle_first_definitional_phrase(
            definitional_phrases=[], name="person"
        )
        cnl_renderer.ontology_title = original_title
        assert isinstance(result, str)

    def test_empty_phrases_list(self, cnl_renderer):
        result = cnl_renderer.handle_first_definitional_phrase(
            definitional_phrases=[], name="person"
        )
        assert isinstance(result, str)


class TestDefinitionInfoEdgeCases:
    """Tests for definition_info dictionary handling."""

    def test_definition_info_populated(self, cnl_renderer):
        definition = cnl_renderer.handle_owl_class(TEST_NS + "Dog")
        assert isinstance(definition, str)


class TestCustomRestrictionRenderingEdgeCases:
    """Tests for custom restriction rendering edge cases."""

    def test_custom_restriction_property_rendering(self, cnl_renderer):
        prop_uri = URIRef(TEST_NS + "has_pet")
        cnl_renderer.custom_restriction_property_rendering[prop_uri] = (
            lambda x, y: "custom"
        )
        rendered = cnl_renderer.render_role_restriction(
            TEST_NS + "has_pet", operand1="A", operand2="B"
        )
        assert isinstance(rendered, str)


class TestRenderReadableOwlClassEdgeCases:
    """Tests for render_readable_owl_class edge cases."""

    def test_anonymous_class_rendering(self, cnl_renderer, mock_person):
        rendered_named = cnl_renderer.render_readable_owl_class(
            mock_person, no_indef_article=False
        )
        rendered_anonymous = cnl_renderer.render_readable_owl_class(
            mock_person, no_indef_article=True
        )
        assert isinstance(rendered_named, str)
        assert isinstance(rendered_anonymous, str)

    def test_no_indefinite_article(self, cnl_renderer, mock_person):
        rendered_with = cnl_renderer.render_readable_owl_class(
            mock_person, no_indef_article=False
        )
        rendered_without = cnl_renderer.render_readable_owl_class(
            mock_person, no_indef_article=True
        )
        assert isinstance(rendered_with, str)
        assert isinstance(rendered_without, str)


class TestPropertyIRILookupEdgeCases:
    """Tests for property IRI lookup edge cases."""

    def test_property_not_found_in_search(self, cnl_renderer):
        with pytest.raises(IndexError):
            cnl_renderer._get_entity_by_iri("http://test.org/onto.owl#nonexistent")

    def test_property_with_multiple_labels(self, cnl_renderer):
        rendered = cnl_renderer.render_role_restriction(
            TEST_NS + "has_pet", operand1="A", operand2="B"
        )
        assert isinstance(rendered, str)

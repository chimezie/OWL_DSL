"""Unit tests for owl_dsl.renderer module."""

import pytest
from pyhornedowl.model import (
    Class,
    ObjectIntersectionOf,
    ObjectUnionOf,
    ObjectSomeValuesFrom,
    ObjectExactCardinality,
    ObjectMinCardinality,
    ObjectProperty,
)
from pyhornedowl.model import IRI

TEST_NS = "http://test.org/onto.owl#"
OWL_THING = "http://www.w3.org/2002/07/owl#Thing"
OWL_NOTHING = "http://www.w3.org/2002/07/owl#Nothing"


def test_render_simple_class(cnl_renderer, mock_person):
    rendered = cnl_renderer.render_owl_class(mock_person)
    assert rendered == "person", f"Expected 'person', got '{rendered}'"


def test_render_capitalized_class(cnl_renderer, mock_person):
    rendered = cnl_renderer.render_readable_owl_class(
        mock_person, capitalize_first_letter=True
    )
    assert rendered == "person", f"Expected 'person' (lowercase), got '{rendered}'"


def test_render_special_classes(cnl_renderer):
    thing = Class(cnl_renderer.ontology.iri(OWL_THING))
    rendered_thing = cnl_renderer.render_owl_class(thing)
    assert (
        rendered_thing == "Everything"
    ), f"Expected 'Everything', got '{rendered_thing}'"

    nothing = Class(cnl_renderer.ontology.iri(OWL_NOTHING))
    rendered_nothing = cnl_renderer.render_owl_class(nothing)
    assert (
        rendered_nothing == "Nothing"
    ), f"Expected 'Nothing', got '{rendered_nothing}'"


def test_render_intersection(cnl_renderer, mock_person, mock_animal):
    intersection = ObjectIntersectionOf([mock_person, mock_animal])
    rendered = cnl_renderer.render_owl_class(intersection)
    assert "person" in rendered.lower(), f"'person' not found in '{rendered}'"
    assert "animal" in rendered.lower(), f"'animal' not found in '{rendered}'"


def test_render_union(cnl_renderer, mock_dog, mock_cat):
    union = ObjectUnionOf([mock_dog, mock_cat])
    rendered = cnl_renderer.render_owl_class(union)
    assert "dog" in rendered.lower(), f"'dog' not found in '{rendered}'"
    assert "cat" in rendered.lower(), f"'cat' not found in '{rendered}'"


def test_render_restriction_some(cnl_renderer, mock_has_pet, mock_dog):
    restriction = ObjectSomeValuesFrom(ope=mock_has_pet, bce=mock_dog)
    rendered = cnl_renderer.render_owl_class(restriction)
    assert "has pet" in rendered.lower(), f"'has pet' not found in '{rendered}'"


def test_render_restriction_exactly(cnl_renderer, mock_has_pet, mock_dog):
    restriction = ObjectExactCardinality(n=2, ope=mock_has_pet, bce=mock_dog)
    rendered = cnl_renderer.render_owl_class(restriction)
    assert "exactly" in rendered.lower(), f"'exactly' not found in '{rendered}'"
    assert "2" in rendered, f"'2' not found in '{rendered}'"


def test_render_restriction_min(cnl_renderer, mock_has_pet, mock_dog):
    restriction = ObjectMinCardinality(n=1, ope=mock_has_pet, bce=mock_dog)
    rendered = cnl_renderer.render_owl_class(restriction)
    assert "at least" in rendered.lower(), f"'at least' not found in '{rendered}'"


def test_handle_owl_class_definition(cnl_renderer):
    definition = cnl_renderer.handle_owl_class(TEST_NS + "Dog")
    assert isinstance(definition, str), f"Expected string, got {type(definition)}"


def test_handle_owl_class_equivalent(cnl_renderer):
    definition = cnl_renderer.handle_owl_class(TEST_NS + "Dog")
    assert isinstance(definition, str), f"Expected string, got {type(definition)}"


def test_extract_definitional_phrases(cnl_renderer):
    definitional_phrases = []
    person = Class(cnl_renderer.ontology.iri(TEST_NS + "Person"))
    cnl_renderer.extract_definitional_phrases(
        definitional_phrases=definitional_phrases,
        owl_classes=[person],
        owl_class_definition="test dog definition",
        owl_class_id="http://test.org/onto.owl#Dog",
        owl_class_name_phrase="the test dog",
    )
    assert isinstance(
        definitional_phrases, list
    ), f"Expected list, got {type(definitional_phrases)}"


def test_concept_group_key(cnl_renderer, mock_person):
    assert cnl_renderer.is_named_owl_class_key(
        cnl_renderer.concept_group_key(mock_person)
    ), "Expected named owl class key"


def test_render_role_restriction(cnl_renderer):
    rendered = cnl_renderer.render_role_restriction(
        TEST_NS + "has_pet", operand1="A", operand2="B"
    )
    assert "has pet" in rendered.lower(), f"'has pet' not found in '{rendered}'"


def test_render_readable_owl_class_no_label(cnl_renderer, mock_person):
    rendered = cnl_renderer.render_readable_owl_class(mock_person)
    assert isinstance(rendered, str)


def test_handle_first_definitional_phrase(cnl_renderer):
    result = cnl_renderer.handle_first_definitional_phrase([], "person")
    assert isinstance(result, str), f"Expected string, got {type(result)}"


def test_is_logical_construct_key(cnl_renderer, mock_person, mock_animal):
    intersection = ObjectIntersectionOf([mock_person, mock_animal])
    key = cnl_renderer.concept_group_key(intersection)
    assert cnl_renderer.is_logical_construct_key(
        key
    ), f"Expected logical construct key for {type(intersection)}"


def test_is_restriction_key(cnl_renderer):
    if len(cnl_renderer.property_iris) > 0:
        test_key = cnl_renderer.RESTRICTION_START_KEY
        assert cnl_renderer.is_restriction_key(
            test_key
        ), f"Expected {test_key} to be a restriction key"

        non_restriction_key = (
            cnl_renderer.RESTRICTION_START_KEY + len(cnl_renderer.property_iris) + 10
        )
        assert not cnl_renderer.is_restriction_key(
            non_restriction_key
        ), f"Expected {non_restriction_key} to NOT be a restriction key"
    else:
        test_key = cnl_renderer.RESTRICTION_START_KEY + 5
        assert not cnl_renderer.is_restriction_key(
            test_key
        ), f"Expected {test_key} to NOT be a restriction key when property_iris is empty"


def test_pretty_print_list(cnl_renderer):
    from owl_dsl import pretty_print_list

    result = pretty_print_list(["A", "B"], and_char=", and ")
    assert result == "A and B", f"Expected 'A and B', got '{result}'"

    result = pretty_print_list(["A", "B", "C"], and_char=", and ")
    assert ", and C" in result, f"Expected comma-and before last item: '{result}'"


def test_prefix_with_indefinite_article(cnl_renderer):
    from owl_dsl import prefix_with_indefinite_article

    result = prefix_with_indefinite_article("dog")
    assert "a dog" == result, f"Expected 'a dog', got '{result}'"

    result = prefix_with_indefinite_article(None)
    assert "something" in result, f"Expected 'something' for None: '{result}'"

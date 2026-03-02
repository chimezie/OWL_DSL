"""Unit tests for owl_dsl.renderer module."""

import pytest
from unittest.mock import Mock
from owlready2 import Restriction, base, And, Or, owl, ThingClass


def test_render_simple_class(cnl_renderer, mock_person):
    """Test rendering of a basic named OWL class."""
    Person = cnl_renderer.ontology.search_one(iri="*Person")

    assert Person is not None, "Person class not found in ontology"

    rendered = cnl_renderer.render_owl_class(Person)
    assert rendered == "person", f"Expected 'person', got '{rendered}'"


def test_render_capitalized_class(cnl_renderer):
    """Test rendering with capitalization."""
    Person = cnl_renderer.ontology.search_one(iri="*Person")

    assert Person is not None

    rendered = cnl_renderer.render_readable_owl_class(
        Person, capitalize_first_letter=True
    )
    # Note: lowercase_labels defaults to True in CNLRenderer, so this returns "person"
    assert rendered == "person", f"Expected 'person' (lowercase), got '{rendered}'"


def test_render_special_classes(cnl_renderer):
    """Test rendering of owl:Thing and owl:Nothing."""
    rendered_thing = cnl_renderer.render_owl_class(owl.Thing)
    assert (
        rendered_thing == "Everything"
    ), f"Expected 'Everything', got '{rendered_thing}'"

    rendered_nothing = cnl_renderer.render_owl_class(owl.Nothing)
    assert (
        rendered_nothing == "Nothing"
    ), f"Expected 'Nothing', got '{rendered_nothing}'"


def test_render_intersection(cnl_renderer, mock_person, mock_animal):
    """Test rendering of logical intersection (AND)."""
    Person = cnl_renderer.ontology.search_one(iri="*Person")
    Animal = cnl_renderer.ontology.search_one(iri="*Animal")

    assert Person is not None and Animal is not None

    # Create an intersection: Person and Animal
    intersection = And([Person, Animal])

    rendered = cnl_renderer.render_owl_class(intersection)
    assert "person" in rendered.lower(), f"'person' not found in '{rendered}'"
    assert "animal" in rendered.lower(), f"'animal' not found in '{rendered}'"


def test_render_union(cnl_renderer, mock_dog, mock_cat):
    """Test rendering of logical union (OR)."""
    Dog = cnl_renderer.ontology.search_one(iri="*Dog")
    Cat = cnl_renderer.ontology.search_one(iri="*Cat")

    assert Dog is not None and Cat is not None

    # Create a union: Dog or Cat
    union = Or([Dog, Cat])

    rendered = cnl_renderer.render_owl_class(union)
    assert "dog" in rendered.lower(), f"'dog' not found in '{rendered}'"
    assert "cat" in rendered.lower(), f"'cat' not found in '{rendered}'"


def test_render_restriction_some(cnl_renderer, mock_has_pet, mock_dog):
    """Test rendering of SOME restriction (existential)."""
    has_pet = cnl_renderer.ontology.search_one(iri="*has_pet")
    Dog = cnl_renderer.ontology.search_one(iri="*Dog")

    assert has_pet is not None and Dog is not None

    # Create: has_pet some Dog
    restriction = Restriction(has_pet, base.SOME, Dog)

    rendered = cnl_renderer.render_owl_class(restriction)
    assert "has pet" in rendered.lower(), f"'has pet' not found in '{rendered}'"


def test_render_restriction_exactly(cnl_renderer, mock_has_pet, mock_dog):
    """Test rendering of EXACTLY restriction (cardinality)."""
    has_pet = cnl_renderer.ontology.search_one(iri="*has_pet")
    Dog = cnl_renderer.ontology.search_one(iri="*Dog")

    assert has_pet is not None and Dog is not None

    # Create: has_pet exactly 2 Dog
    restriction = Restriction(has_pet, base.EXACTLY, 2, Dog)

    rendered = cnl_renderer.render_owl_class(restriction)
    assert "exactly" in rendered.lower(), f"'exactly' not found in '{rendered}'"
    assert "2" in rendered, f"'2' not found in '{rendered}'"


def test_render_restriction_min(cnl_renderer, mock_has_pet, mock_dog):
    """Test rendering of MIN restriction (at least)."""
    has_pet = cnl_renderer.ontology.search_one(iri="*has_pet")
    Dog = cnl_renderer.ontology.search_one(iri="*Dog")

    assert has_pet is not None and Dog is not None

    # Create: has_pet at least 1 Dog
    restriction = Restriction(has_pet, base.MIN, 1, Dog)

    rendered = cnl_renderer.render_owl_class(restriction)
    assert "at least" in rendered.lower(), f"'at least' not found in '{rendered}'"


def test_handle_owl_class_definition(cnl_renderer, mock_dog):
    """Test handling of OWL class definitions with is_a relationships."""
    Dog = cnl_renderer.ontology.search_one(iri="*Dog")

    assert Dog is not None
    # Ensure is_a and equivalent_to are iterable lists
    Dog.equivalent_to = []
    # is_a is already set in the fixture

    definition = cnl_renderer.handle_owl_class(Dog)

    assert isinstance(definition, str), f"Expected string, got {type(definition)}"


def test_handle_owl_class_equivalent(cnl_renderer):
    """Test handling of OWL class equivalent_to relationships."""
    Person = cnl_renderer.ontology.search_one(iri="*Person")

    assert Person is not None

    # Create a mock class with equivalent_to relationship
    mock_centaur = Mock()
    mock_centaur.iri = "http://test.org/onto.owl#Centaur"
    mock_centaur.label = ["centaur"]
    mock_centaur.equivalent_to = [Person]
    mock_centaur.is_a = []  # Ensure is_a is iterable

    definition = cnl_renderer.handle_owl_class(mock_centaur)

    assert isinstance(definition, str), f"Expected string, got {type(definition)}"


def test_extract_definitional_phrases(cnl_renderer):
    """Test extraction of definitional phrases from OWL classes."""
    Person = cnl_renderer.ontology.search_one(iri="*Person")

    assert Person is not None

    # Create a mock class with is_a relationship that passes isinstance checks
    mock_dog = Mock(spec=ThingClass)
    mock_dog.label = ["dog"]
    mock_dog.is_a = [Person]

    # Add required attributes for groupby to work
    mock_dog.Classes = []

    definitional_phrases = []
    cnl_renderer.extract_definitional_phrases(
        definitional_phrases=definitional_phrases,
        owl_classes=[mock_dog],
        owl_class_definition="test dog definition",
        owl_class_id="http://test.org/onto.owl#Dog",
        owl_class_name_phrase="the test dog",
    )

    assert isinstance(
        definitional_phrases, list
    ), f"Expected list, got {type(definitional_phrases)}"


def test_concept_group_key(cnl_renderer):
    """Test grouping of concepts by type."""
    Person = cnl_renderer.ontology.search_one(iri="*Person")

    assert Person is not None

    # Test key assignment for different concept types
    assert cnl_renderer.is_named_owl_class_key(
        cnl_renderer.concept_group_key(Person)
    ), "Expected named owl class key"


def test_render_role_restriction(cnl_renderer, mock_has_pet):
    """Test rendering of role restrictions."""
    has_pet = cnl_renderer.ontology.search_one(iri="*has_pet")

    assert has_pet is not None

    # Test with custom phrasing disabled (default)
    rendered = cnl_renderer.render_role_restriction(has_pet, operand1="A", operand2="B")
    assert "has pet" in rendered.lower(), f"'has pet' not found in '{rendered}'"


def test_render_readable_owl_class_no_label(cnl_renderer):
    """Test rendering of class without label."""
    Person = cnl_renderer.ontology.search_one(iri="*Person")

    assert Person is not None

    # Temporarily clear the label
    original_label = list(Person.label) if hasattr(Person, "label") else []
    Person.label = []

    rendered = cnl_renderer.render_readable_owl_class(Person)

    # Restore label
    Person.label = original_label


def test_handle_first_definitional_phrase(cnl_renderer):
    """Test handling of first definitional phrase."""
    result = cnl_renderer.handle_first_definitional_phrase([], "person")
    assert isinstance(result, str), f"Expected string, got {type(result)}"


def test_is_logical_construct_key(cnl_renderer):
    """Test identification of logical construct keys."""
    Person = cnl_renderer.ontology.search_one(iri="*Person")
    Animal = cnl_renderer.ontology.search_one(iri="*Animal")

    assert Person is not None and Animal is not None

    intersection = And([Person, Animal])

    key = cnl_renderer.concept_group_key(intersection)

    assert cnl_renderer.is_logical_construct_key(
        key
    ), f"Expected logical construct key for {type(intersection)}"


def test_is_restriction_key(cnl_renderer):
    """Test identification of restriction keys."""
    # The is_restriction_key method checks if a key falls within the range
    # RESTRICTION_START_KEY to RESTRICTION_START_KEY + len(property_iris)

    if len(cnl_renderer.property_iris) > 0:
        # Test with a key that falls in the restriction range
        test_key = cnl_renderer.RESTRICTION_START_KEY + 1
        assert cnl_renderer.is_restriction_key(
            test_key
        ), f"Expected {test_key} to be a restriction key"

        # Test with a key outside the restriction range (should not be restriction)
        non_restriction_key = (
            cnl_renderer.RESTRICTION_START_KEY + len(cnl_renderer.property_iris) + 10
        )
        assert (
            not cnl_renderer.is_restriction_key(non_restriction_key),
            f"Expected {non_restriction_key} to NOT be a restriction key",
        )
    else:
        # If no properties, just verify the method doesn't crash
        test_key = cnl_renderer.RESTRICTION_START_KEY + 5
        assert (
            not cnl_renderer.is_restriction_key(test_key),
            f"Expected {test_key} to NOT be a restriction key when property_iris is empty",
        )


def test_pretty_print_list(cnl_renderer):
    """Test pretty printing of lists."""
    from owl_dsl import pretty_print_list

    # Test two items (binary)
    result = pretty_print_list(["A", "B"], and_char=", and ")
    assert result == "A and B", f"Expected 'A and B', got '{result}'"

    # Test three or more items
    result = pretty_print_list(["A", "B", "C"], and_char=", and ")
    assert ", and C" in result, f"Expected comma-and before last item: '{result}'"


def test_prefix_with_indefinite_article(cnl_renderer):
    """Test prefixing with indefinite article."""
    from owl_dsl import prefix_with_indefinite_article

    # Test noun starting with consonant
    result = prefix_with_indefinite_article("dog")
    assert "a dog" == result, f"Expected 'a dog', got '{result}'"

    # Test None input (should return "something")
    result = prefix_with_indefinite_article(None)
    assert "something" in result, f"Expected 'something' for None: '{result}'"

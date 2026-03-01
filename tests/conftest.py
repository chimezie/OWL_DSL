"""Pytest fixtures and conftest configuration."""

import pytest
from unittest.mock import Mock, MagicMock
from owlready2 import ThingClass, ObjectProperty, Restriction, base, And, Or, owl


@pytest.fixture
def mock_person():
    """Create a mock Person class."""
    person = Mock(spec=ThingClass)
    person.iri = "http://test.org/onto.owl#Person"
    person.name = "Person"
    person.label = ["person"]
    return person


@pytest.fixture
def mock_animal():
    """Create a mock Animal class."""
    animal = Mock(spec=ThingClass)
    animal.iri = "http://test.org/onto.owl#Animal"
    animal.name = "Animal"
    animal.label = ["animal"]
    return animal


@pytest.fixture
def mock_dog(mock_animal):
    """Create a mock Dog class."""
    dog = Mock(spec=ThingClass)
    dog.iri = "http://test.org/onto.owl#Dog"
    dog.name = "Dog"
    dog.label = ["dog"]
    dog.is_a = [mock_animal]  # Dog is a subclass of Animal
    return dog


@pytest.fixture
def mock_cat(mock_animal):
    """Create a mock Cat class."""
    cat = Mock(spec=ThingClass)
    cat.iri = "http://test.org/onto.owl#Cat"
    cat.name = "Cat"
    cat.label = ["cat"]
    cat.is_a = [mock_animal]  # Cat is a subclass of Animal
    return cat


@pytest.fixture
def mock_has_pet():
    """Create a mock has_pet property."""
    prop = Mock(spec=ObjectProperty)
    prop.iri = "http://test.org/onto.owl#has_pet"
    prop.name = "has_pet"
    prop.label = ["has pet"]
    return prop


@pytest.fixture
def simple_ontology(mock_person, mock_animal, mock_dog, mock_cat, mock_has_pet):
    """Create a mock ontology with all test entities."""
    onto = Mock()
    onto.base_iri = "http://test.org/onto.owl#"

    # Mock search_one to return the correct entity based on IRI pattern
    def search_one(iri=None, label=None):
        if iri:
            if "*Person" in iri or iri == "http://test.org/onto.owl#Person":
                return mock_person
            elif "*Animal" in iri or iri == "http://test.org/onto.owl#Animal":
                return mock_animal
            elif "*Dog" in iri or iri == "http://test.org/onto.owl#Dog":
                return mock_dog
            elif "*Cat" in iri or iri == "http://test.org/onto.owl#Cat":
                return mock_cat
            elif "*has_pet" in iri or iri == "http://test.org/onto.owl#has_pet":
                return mock_has_pet
        return None

    onto.search_one = search_one
    onto.properties.return_value = []  # No properties for simple tests
    onto.classes.return_value = [mock_person, mock_animal, mock_dog, mock_cat]

    return onto


@pytest.fixture
def cnl_renderer(simple_ontology):
    """Create a CNLRenderer instance with the test ontology."""
    from owl_dsl.renderer import CNLRenderer

    return CNLRenderer(
        ontology=simple_ontology,
        ontology_namespace="http://test.org/onto.owl#",
        verbose=False,
    )

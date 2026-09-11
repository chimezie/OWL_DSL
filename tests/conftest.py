"""Pytest fixtures and conftest configuration using py-horned-owl."""

import pytest
import pyhornedowl
from pyhornedowl.model import (
    Class,
    ObjectProperty,
    SubClassOf,
    DeclareClass,
    DeclareObjectProperty,
    NamedIndividual,
    IRI,
)

TEST_NS = "http://test.org/onto.owl#"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"


def _iri(suffix: str) -> IRI:
    return IRI.parse(TEST_NS + suffix)


def _add_label(onto, iri: str, label: str):
    onto.set_label(IRI.parse(iri), label)


def build_test_ontology() -> pyhornedowl.PyIndexedOntology:
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", TEST_NS)

    person_iri = TEST_NS + "Person"
    animal_iri = TEST_NS + "Animal"
    dog_iri = TEST_NS + "Dog"
    cat_iri = TEST_NS + "Cat"
    has_pet_iri = TEST_NS + "has_pet"

    onto.add_component(DeclareClass(Class(_iri("Person"))))
    onto.add_component(DeclareClass(Class(_iri("Animal"))))
    onto.add_component(DeclareClass(Class(_iri("Dog"))))
    onto.add_component(DeclareClass(Class(_iri("Cat"))))
    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("has_pet"))))

    _add_label(onto, person_iri, "person")
    _add_label(onto, animal_iri, "animal")
    _add_label(onto, dog_iri, "dog")
    _add_label(onto, cat_iri, "cat")
    _add_label(onto, has_pet_iri, "has pet")

    onto.add_component(SubClassOf(Class(_iri("Dog")), Class(_iri("Animal"))))
    onto.add_component(SubClassOf(Class(_iri("Cat")), Class(_iri("Animal"))))

    return onto


@pytest.fixture
def simple_ontology():
    return build_test_ontology()


@pytest.fixture
def cnl_renderer(simple_ontology):
    from owl_dsl.renderer import CNLRenderer

    renderer = CNLRenderer(
        ontology=simple_ontology,
        ontology_namespace=TEST_NS,
        verbose=False,
    )
    renderer.lowercase_labels = True
    return renderer


@pytest.fixture
def mock_person(simple_ontology):
    return Class(simple_ontology.iri(TEST_NS + "Person"))


@pytest.fixture
def mock_animal(simple_ontology):
    return Class(simple_ontology.iri(TEST_NS + "Animal"))


@pytest.fixture
def mock_dog(simple_ontology):
    return Class(simple_ontology.iri(TEST_NS + "Dog"))


@pytest.fixture
def mock_cat(simple_ontology):
    return Class(simple_ontology.iri(TEST_NS + "Cat"))


@pytest.fixture
def mock_has_pet(simple_ontology):
    return ObjectProperty(simple_ontology.iri(TEST_NS + "has_pet"))

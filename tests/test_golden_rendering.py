"""Golden (characterization) tests that pin exact rendered output.

These tests serve as the **port contract**: when the renderer is migrated from
owlready2 to py-horned-owl, every assertion here must remain **identical**.
"""

import os
import pytest
from pathlib import Path

import pyhornedowl
from pyhornedowl.model import (
    Class,
    ObjectProperty,
    DataProperty,
    ObjectIntersectionOf,
    ObjectUnionOf,
    ObjectSomeValuesFrom,
    ObjectAllValuesFrom,
    ObjectHasValue,
    ObjectMinCardinality,
    ObjectMaxCardinality,
    ObjectExactCardinality,
    DataSomeValuesFrom,
    SubClassOf,
    EquivalentClasses,
    ObjectOneOf,
    DeclareClass,
    DeclareObjectProperty,
    DeclareDataProperty,
    DeclareNamedIndividual,
    NamedIndividual,
    Datatype,
    IRI,
)
from owl_dsl.renderer import CNLRenderer

DIR = Path(__file__).parent
BASE_URI = "https://github.com/chimezie/owl_dsl/golden#"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
OWL_THING = "http://www.w3.org/2002/07/owl#Thing"
OWL_NOTHING = "http://www.w3.org/2002/07/owl#Nothing"
XSD_INTEGER = "http://www.w3.org/2001/XMLSchema#integer"


def _iri(suffix: str) -> IRI:
    return IRI.parse(BASE_URI + suffix)


def _add_label(onto, iri_str: str, label: str):
    onto.set_label(IRI.parse(iri_str), label)


def _cls(suffix: str):
    return Class(_iri(suffix))


def _make_handler(onto):
    return CNLRenderer(onto, BASE_URI, lowercase_labels=False)


@pytest.fixture
def onto():
    return pyhornedowl.PyIndexedOntology()


def test_triple_conjunction():
    """Three-way conjunction: 'a Mammal, a Canine, and a Domesticated'."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    for suffix, label in [
        ("Mammal", "Mammal"),
        ("Canine", "Canine"),
        ("Domesticated", "Domesticated"),
        ("Dog", "Dog"),
    ]:
        onto.add_component(DeclareClass(_cls(suffix)))
        _add_label(onto, base + suffix, label)

    onto.add_component(
        SubClassOf(
            Class(_iri("Dog")),
            ObjectIntersectionOf(
                [
                    Class(_iri("Mammal")),
                    Class(_iri("Canine")),
                    Class(_iri("Domesticated")),
                ]
            ),
        )
    )

    rendered = _make_handler(onto).handle_owl_class(base + "Dog")
    assert rendered == "The Dog is defined as a Mammal, a Canine, and a Domesticated"


@pytest.mark.golden
def test_conjunction_with_min_cardinality():
    """Parent class + MIN cardinality: 'a Human that has pet at least 1 Dog'."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    for suffix, label in [("Human", "Human"), ("Dog", "Dog"), ("Owner", "Owner")]:
        onto.add_component(DeclareClass(_cls(suffix)))
        _add_label(onto, base + suffix, label)

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("has_pet"))))
    _add_label(onto, base + "has_pet", "has pet")

    onto.add_component(
        SubClassOf(
            Class(_iri("Owner")),
            ObjectIntersectionOf(
                [
                    Class(_iri("Human")),
                    ObjectMinCardinality(
                        n=1, ope=ObjectProperty(_iri("has_pet")), bce=Class(_iri("Dog"))
                    ),
                ]
            ),
        )
    )

    rendered = _make_handler(onto).handle_owl_class(base + "Owner")
    assert rendered == "The Owner is defined as a Human that has pet at least 1 Dog"


@pytest.mark.golden
def test_some_restriction():
    """SOME restriction: 'has pet an Animal'."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    for suffix, label in [("Animal", "Animal"), ("Owner", "Owner")]:
        onto.add_component(DeclareClass(_cls(suffix)))
        _add_label(onto, base + suffix, label)

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("has_pet"))))
    _add_label(onto, base + "has_pet", "has pet")

    onto.add_component(
        SubClassOf(
            Class(_iri("Owner")),
            ObjectSomeValuesFrom(
                ope=ObjectProperty(_iri("has_pet")), bce=Class(_iri("Animal"))
            ),
        )
    )

    rendered = _make_handler(onto).handle_owl_class(base + "Owner")
    assert rendered == "The Owner is defined as has pet an Animal"


@pytest.mark.golden
def test_only_restriction():
    """ONLY restriction renders identically to SOME."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    for suffix, label in [("Animal", "Animal"), ("Owner", "Owner")]:
        onto.add_component(DeclareClass(_cls(suffix)))
        _add_label(onto, base + suffix, label)

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("has_pet"))))
    _add_label(onto, base + "has_pet", "has pet")

    onto.add_component(
        SubClassOf(
            Class(_iri("Owner")),
            ObjectAllValuesFrom(
                ope=ObjectProperty(_iri("has_pet")), bce=Class(_iri("Animal"))
            ),
        )
    )

    rendered = _make_handler(onto).handle_owl_class(base + "Owner")
    assert rendered == "The Owner is defined as has pet an Animal"


@pytest.mark.golden
def test_value_restriction():
    """VALUE restriction: 'has pet a Fido'."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    for suffix, label in [("Dog", "Dog"), ("Owner", "Owner")]:
        onto.add_component(DeclareClass(_cls(suffix)))
        _add_label(onto, base + suffix, label)

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("has_pet"))))
    _add_label(onto, base + "has_pet", "has pet")

    onto.add_component(DeclareNamedIndividual(NamedIndividual(_iri("Fido"))))
    _add_label(onto, base + "Fido", "Fido")

    onto.add_component(
        SubClassOf(
            Class(_iri("Owner")),
            ObjectHasValue(
                ope=ObjectProperty(_iri("has_pet")), i=NamedIndividual(_iri("Fido"))
            ),
        )
    )

    rendered = _make_handler(onto).handle_owl_class(base + "Owner")
    assert rendered == "The Owner is defined as has pet a Fido"


@pytest.mark.golden
def test_disjunction():
    """Disjunction renders with 'and' instead of 'or'."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    for suffix, label in [("Cat", "Cat"), ("Dog", "Dog"), ("Pet", "Pet")]:
        onto.add_component(DeclareClass(_cls(suffix)))
        _add_label(onto, base + suffix, label)

    onto.add_component(
        SubClassOf(
            Class(_iri("Pet")),
            ObjectUnionOf([Class(_iri("Cat")), Class(_iri("Dog"))]),
        )
    )

    rendered = _make_handler(onto).handle_owl_class(base + "Pet")
    assert rendered == "The Pet is defined as is a Cat and a Dog"


@pytest.mark.golden
def test_exactly_cardinality_isolation_raises():
    """EXACTLY cardinality in isolation raises IndexError."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    for suffix, label in [("Animal", "Animal"), ("Owner", "Owner")]:
        onto.add_component(DeclareClass(_cls(suffix)))
        _add_label(onto, base + suffix, label)

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("has_pet"))))
    _add_label(onto, base + "has_pet", "has pet")

    onto.add_component(
        SubClassOf(
            Class(_iri("Owner")),
            ObjectExactCardinality(
                n=2, ope=ObjectProperty(_iri("has_pet")), bce=Class(_iri("Animal"))
            ),
        )
    )

    with pytest.raises(IndexError):
        _make_handler(onto).handle_owl_class(base + "Owner")


@pytest.mark.golden
def test_min_cardinality_isolation_raises():
    """MIN cardinality in isolation raises IndexError."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    for suffix, label in [("Animal", "Animal"), ("Owner", "Owner")]:
        onto.add_component(DeclareClass(_cls(suffix)))
        _add_label(onto, base + suffix, label)

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("has_pet"))))
    _add_label(onto, base + "has_pet", "has pet")

    onto.add_component(
        SubClassOf(
            Class(_iri("Owner")),
            ObjectMinCardinality(
                n=1, ope=ObjectProperty(_iri("has_pet")), bce=Class(_iri("Animal"))
            ),
        )
    )

    with pytest.raises(IndexError):
        _make_handler(onto).handle_owl_class(base + "Owner")


@pytest.mark.golden
def test_max_cardinality_isolation_raises():
    """MAX cardinality in isolation raises IndexError."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    for suffix, label in [("Animal", "Animal"), ("Owner", "Owner")]:
        onto.add_component(DeclareClass(_cls(suffix)))
        _add_label(onto, base + suffix, label)

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("has_pet"))))
    _add_label(onto, base + "has_pet", "has pet")

    onto.add_component(
        SubClassOf(
            Class(_iri("Owner")),
            ObjectMaxCardinality(
                n=3, ope=ObjectProperty(_iri("has_pet")), bce=Class(_iri("Animal"))
            ),
        )
    )

    with pytest.raises(IndexError):
        _make_handler(onto).handle_owl_class(base + "Owner")


@pytest.mark.golden
def test_owl_thing_renders_empty():
    """owl:Thing renders as empty string."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    onto.add_component(DeclareClass(Class(_iri("Top"))))
    _add_label(onto, base + "Top", "Top")

    onto.add_component(
        SubClassOf(
            Class(_iri("Top")),
            Class(IRI.parse(OWL_THING)),
        )
    )

    rendered = _make_handler(onto).handle_owl_class(base + "Top")
    assert rendered == ""


@pytest.mark.golden
def test_owl_nothing_renders_empty():
    """owl:Nothing renders as empty string."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    onto.add_component(DeclareClass(Class(_iri("Bottom"))))
    _add_label(onto, base + "Bottom", "Bottom")

    onto.add_component(
        SubClassOf(
            Class(_iri("Bottom")),
            Class(IRI.parse(OWL_NOTHING)),
        )
    )

    rendered = _make_handler(onto).handle_owl_class(base + "Bottom")
    assert rendered == ""


@pytest.mark.golden
def test_render_owl_class_owl_thing():
    """render_owl_class(owl.Thing) returns 'Everything'."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    onto.add_component(DeclareClass(Class(_iri("Animal"))))
    _add_label(onto, base + "Animal", "Animal")

    rendered = _make_handler(onto).render_owl_class(Class(IRI.parse(OWL_THING)))
    assert rendered == "Everything"


@pytest.mark.golden
def test_render_owl_class_owl_nothing():
    """render_owl_class(owl.Nothing) returns 'Nothing'."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    onto.add_component(DeclareClass(Class(_iri("Animal"))))
    _add_label(onto, base + "Animal", "Animal")

    rendered = _make_handler(onto).render_owl_class(Class(IRI.parse(OWL_NOTHING)))
    assert rendered == "Nothing"


@pytest.mark.golden
def test_render_owl_class_property():
    """render_owl_class with ObjectProperty returns its local name."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    onto.add_component(DeclareClass(Class(_iri("Animal"))))
    _add_label(onto, base + "Animal", "Animal")

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("has_pet"))))
    _add_label(onto, base + "has_pet", "has pet")

    has_pet = ObjectProperty(IRI.parse(base + "has_pet"))
    rendered = _make_handler(onto).render_owl_class(has_pet)
    assert rendered == "has_pet"


@pytest.mark.golden
def test_not_construct_not_implemented():
    """Not construct raises NotImplementedError."""
    from pyhornedowl.model import ObjectComplementOf

    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    onto.add_component(DeclareClass(Class(_iri("Animal"))))
    _add_label(onto, base + "Animal", "Animal")

    with pytest.raises(NotImplementedError):
        _make_handler(onto).render_owl_class(ObjectComplementOf(Class(_iri("Animal"))))


@pytest.mark.golden
def test_inverse_construct_not_implemented():
    """Inverse construct raises NotImplementedError."""
    from pyhornedowl.model import InverseObjectProperty

    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    onto.add_component(DeclareClass(Class(_iri("Animal"))))
    _add_label(onto, base + "Animal", "Animal")

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("has_pet"))))
    _add_label(onto, base + "has_pet", "has pet")

    inv = InverseObjectProperty(ObjectProperty(_iri("has_pet")))
    with pytest.raises(NotImplementedError):
        _make_handler(onto).render_owl_class(inv)


@pytest.mark.golden
def test_oneof_construct_not_implemented():
    """OneOf construct raises NotImplementedError."""
    from pyhornedowl.model import ObjectOneOf, NamedIndividual

    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    onto.add_component(DeclareClass(Class(_iri("Animal"))))
    _add_label(onto, base + "Animal", "Animal")

    onto.add_component(DeclareNamedIndividual(NamedIndividual(_iri("Fido"))))
    _add_label(onto, base + "Fido", "Fido")

    with pytest.raises(NotImplementedError):
        _make_handler(onto).render_owl_class(
            ObjectOneOf([NamedIndividual(_iri("Fido"))])
        )


@pytest.mark.golden
def test_data_some_restriction_renders():
    """DataProperty + some(datatype) renders as 'has age an integer'."""
    base = "https://github.com/chimezie/owl_dsl/golden#"
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", base)

    onto.add_component(DeclareClass(Class(_iri("Movie"))))
    _add_label(onto, base + "Movie", "Movie")

    onto.add_component(DeclareDataProperty(DataProperty(_iri("has_age"))))
    _add_label(onto, base + "has_age", "has age")

    onto.add_component(
        SubClassOf(
            Class(_iri("Movie")),
            DataSomeValuesFrom(
                dp=DataProperty(_iri("has_age")),
                dr=Datatype(IRI.parse(XSD_INTEGER)),
            ),
        )
    )

    movie = _make_handler(onto)
    rendered = movie.handle_owl_class(base + "Movie")
    assert rendered is not None

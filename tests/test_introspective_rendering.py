import os
import pytest
from pathlib import Path

import pyhornedowl
from pyhornedowl.model import (
    Class,
    ObjectProperty,
    NamedIndividual,
    ObjectIntersectionOf,
    ObjectUnionOf,
    ObjectSomeValuesFrom,
    ObjectAllValuesFrom,
    ObjectHasValue,
    ObjectMinCardinality,
    SubClassOf,
    EquivalentClasses,
    DeclareClass,
    DeclareObjectProperty,
    DeclareNamedIndividual,
    IRI,
)
from rdflib import Graph, Namespace, Literal, URIRef
from owl_dsl.renderer import CNLRenderer
from owl_dsl.annotations import configure_cnl_from_annotations

DIR = Path(__file__).parent
BASE_URI = "https://github.com/chimezie/owl_dsl/Terms#"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
OWL_DSL_NS = "http://purl.org/ontology-dsl#"
OWL_DSL = Namespace(OWL_DSL_NS)

EXPECTED_TEXT2 = "The Fantastical Pig is defined as a Pig that speaks a Language or has a Pair of Wings. It is a Pig"
EXPECTED_TEXT3 = "The Pig is defined as an Animal that bears only a Pig"
EXPECTED_TEXT4 = (
    "The Child of Emeka is defined as a Person that has Emeka as their father"
)
EXPECTED_TEXT5 = "The Person is defined as a Human that has a father relationship with at least one Person"


def _iri(suffix: str) -> IRI:
    return IRI.parse(BASE_URI + suffix)


def _build_annotation_graph(prop_templates: dict[str, str]) -> Graph:
    g = Graph()
    for prop_iri_str, template in prop_templates.items():
        g.add((URIRef(prop_iri_str), OWL_DSL.OWL_DSL_000001, Literal(template)))
    return g


def test_conjunct_disjunct_rendering():
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", BASE_URI)

    for suffix, label in [
        ("Animal", "Animal"),
        ("Pig", "Pig"),
        ("Language", "Language"),
        ("PairOfWings", "Pair of Wings"),
        ("FantasticalPig", "Fantastical Pig"),
    ]:
        onto.add_component(DeclareClass(Class(_iri(suffix))))
        onto.set_label(_iri(suffix), label)

    for suffix in ["bears", "speaks", "has"]:
        onto.add_component(DeclareObjectProperty(ObjectProperty(_iri(suffix))))
        onto.set_label(_iri(suffix), suffix)

    onto.add_component(
        SubClassOf(
            Class(_iri("Pig")),
            ObjectIntersectionOf(
                [
                    Class(_iri("Animal")),
                    ObjectAllValuesFrom(
                        ObjectProperty(_iri("bears")), Class(_iri("Pig"))
                    ),
                ]
            ),
        )
    )

    onto.add_component(
        SubClassOf(
            Class(_iri("FantasticalPig")),
            Class(_iri("Pig")),
        )
    )

    onto.add_component(
        EquivalentClasses(
            [
                Class(_iri("FantasticalPig")),
                ObjectIntersectionOf(
                    [
                        Class(_iri("Pig")),
                        ObjectUnionOf(
                            [
                                ObjectSomeValuesFrom(
                                    ObjectProperty(_iri("speaks")),
                                    Class(_iri("Language")),
                                ),
                                ObjectSomeValuesFrom(
                                    ObjectProperty(_iri("has")),
                                    Class(_iri("PairOfWings")),
                                ),
                            ]
                        ),
                    ]
                ),
            ]
        )
    )

    graph = _build_annotation_graph(
        {
            BASE_URI + "speaks": "speaks {}",
            BASE_URI + "has": "has {}",
        }
    )

    handler = CNLRenderer(onto, BASE_URI, verbose=False, lowercase_labels=False)
    configure_cnl_from_annotations(handler, graph)
    assert handler.handle_owl_class(BASE_URI + "FantasticalPig") == EXPECTED_TEXT2
    assert handler.handle_owl_class(BASE_URI + "Pig") == EXPECTED_TEXT3


def test_advanced_role_restriction_rendering():
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", BASE_URI)

    for suffix, label in [("Person", "Person"), ("EmekasChild", "Child of Emeka")]:
        onto.add_component(DeclareClass(Class(_iri(suffix))))
        onto.set_label(_iri(suffix), label)

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("father"))))
    onto.set_label(_iri("father"), "father")

    onto.add_component(DeclareNamedIndividual(NamedIndividual(_iri("Emeka"))))
    onto.set_label(_iri("Emeka"), "Emeka")

    onto.add_component(
        SubClassOf(
            Class(_iri("EmekasChild")),
            ObjectIntersectionOf(
                [
                    Class(_iri("Person")),
                    ObjectHasValue(
                        ObjectProperty(_iri("father")), NamedIndividual(_iri("Emeka"))
                    ),
                ]
            ),
        )
    )

    graph = _build_annotation_graph(
        {
            BASE_URI + "father": "has {} as their father",
        }
    )

    handler = CNLRenderer(onto, BASE_URI, verbose=False, lowercase_labels=False)
    configure_cnl_from_annotations(handler, graph)
    assert handler.handle_owl_class(BASE_URI + "EmekasChild") == EXPECTED_TEXT4


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Rendering a named parent (Human) conjoined with a cardinality role "
        "restriction that carries a custom OWL_DSL_000001 template is not yet "
        "implemented. The conjunction path (render_owl_class) does not apply "
        "custom role templates, while the custom-template path "
        "(extract_definitional_phrases) emits a separate '. It ...' clause "
        "instead of joining with 'that'. See renderer.extract_definitional_phrases."
    ),
)
def test_min_cardinality_restriction():
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", BASE_URI)

    for suffix, label in [("Human", "Human"), ("Person", "Person")]:
        onto.add_component(DeclareClass(Class(_iri(suffix))))
        onto.set_label(_iri(suffix), label)

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("father"))))
    onto.set_label(_iri("father"), "father")

    onto.add_component(
        SubClassOf(
            Class(_iri("Person")),
            ObjectIntersectionOf(
                [
                    Class(_iri("Human")),
                    ObjectMinCardinality(
                        n=1,
                        ope=ObjectProperty(_iri("father")),
                        bce=Class(_iri("Person")),
                    ),
                ]
            ),
        )
    )

    graph = _build_annotation_graph(
        {
            BASE_URI + "father": "has a father relationship with at least one {}",
        }
    )

    handler = CNLRenderer(onto, BASE_URI, verbose=False, lowercase_labels=False)
    configure_cnl_from_annotations(handler, graph)
    rendered = handler.handle_owl_class(BASE_URI + "Person")
    assert rendered == EXPECTED_TEXT5


def test_min_cardinality_no_double_article():
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", BASE_URI)

    onto.add_component(DeclareClass(Class(_iri("Person"))))
    onto.set_label(_iri("Person"), "Person")

    onto.add_component(DeclareObjectProperty(ObjectProperty(_iri("father"))))
    onto.set_label(_iri("father"), "father")

    onto.add_component(
        SubClassOf(
            Class(_iri("Person")),
            ObjectMinCardinality(
                n=1, ope=ObjectProperty(_iri("father")), bce=Class(_iri("Person"))
            ),
        )
    )

    graph = _build_annotation_graph(
        {
            BASE_URI + "father": "has a father relationship with at least one {}",
        }
    )

    handler = CNLRenderer(onto, BASE_URI, verbose=False, lowercase_labels=False)
    configure_cnl_from_annotations(handler, graph)
    rendered = handler.handle_owl_class(BASE_URI + "Person")
    assert "at least one Person" in rendered
    assert "at least one a Person" not in rendered

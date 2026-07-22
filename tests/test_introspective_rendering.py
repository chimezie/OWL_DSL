import os
import pytest
from pathlib import Path
from owlready2 import default_world, Thing, ObjectProperty, AnnotationProperty
from rdflib import Graph, Namespace
from owl_dsl.renderer import CNLRenderer
from owl_dsl.annotations import configure_cnl_from_annotations

DIR = Path(__file__).parent
BASE_URI = "https://github.com/chimezie/owl_dsl/Terms#"
NS = Namespace(BASE_URI)
OWL_DSL_NS = "https://github.com/chimezie/OWL_DSL/tree/main/ontology_configurations/"
OWL_DSL = Namespace(OWL_DSL_NS)

EXPECTED_TEXT1 = (
    "The Hypertension Diagnosis from H/P is defined as a History and Physical Evaluation that contains a "
    "Pulmonary hypertension primary medical diagnosis or "
    "Systemic vascular hypertension primary medical diagnosis"
)

EXPECTED_TEXT2 = "The Fantastical Pig is defined as a Pig that speaks a Language or has a Pair of Wings. It is a Pig"
EXPECTED_TEXT3 = "The Pig is defined as an Animal that bears only a Pig"
EXPECTED_TEXT4 = (
    "The Child of Emeka is defined as a Person that has Emeka as their father"
)
EXPECTED_TEXT5 = "The Person is defined as a Human that has a father relationship with at least one Person"

SQLITE_FILE = str(DIR / "test_introspective_rendering.sqlite")


def setup_module():
    os.environ["OWL_DSL_COLLECT_DEFINITION_INFO"] = "0"


def teardown_module():
    if os.path.exists(SQLITE_FILE):
        os.remove(SQLITE_FILE)


def test_patient_record_ontology():
    graph = Graph().parse(DIR / "ptrec.owl")
    ontology = default_world.get_ontology(BASE_URI)
    ontology.set_base_iri(BASE_URI, rename_entities=False)
    owlready2_graph = default_world.as_rdflib_graph()
    with ontology:
        owlready2_graph += graph
    default_world.save()
    owl_class = ontology.search_one(iri=NS.H_and_P_with_htn_dx)
    handler = CNLRenderer(ontology, BASE_URI, verbose=True, lowercase_labels=False)
    configure_cnl_from_annotations(handler, graph)
    rendered = handler.handle_owl_class(owl_class)
    del default_world.ontologies[ontology.base_iri]
    assert rendered == EXPECTED_TEXT1


def test_conjunct_disjunct_rendering():
    ontology = default_world.get_ontology(BASE_URI)
    owl_dsl_ns = ontology.get_namespace(OWL_DSL_NS)
    with ontology:
        with owl_dsl_ns:

            class OWL_DSL_000001(AnnotationProperty):
                pass

        class Animal(Thing):
            label = ["Animal"]

        class Pig(Animal):
            label = ["Pig"]

        class Language(Thing):
            label = ["Language"]

        class PairOfWings(Thing):
            label = ["Pair of Wings"]

        class bears(ObjectProperty):
            label = ["bears"]

        class speaks(ObjectProperty):
            label = ["speaks"]
            OWL_DSL_000001 = ["speaks {}"]

        class has(ObjectProperty):
            label = ["has"]
            OWL_DSL_000001 = ["has {}"]

        Pig.is_a = [Animal & bears.only(Pig)]

        class FantasticalPig(Pig):
            label = ["Fantastical Pig"]

        FantasticalPig.equivalent_to = [
            Pig & (speaks.some(Language) | has.some(PairOfWings))
        ]
    default_world.save()
    handler = CNLRenderer(ontology, BASE_URI, verbose=False, lowercase_labels=False)
    configure_cnl_from_annotations(handler, ontology.world.as_rdflib_graph())
    assert (
        handler.handle_owl_class(ontology.search_one(iri=NS.FantasticalPig))
        == EXPECTED_TEXT2
    )
    assert handler.handle_owl_class(ontology.search_one(iri=NS.Pig)) == EXPECTED_TEXT3
    del default_world.ontologies[ontology.base_iri]


def test_advanced_role_restriction_rendering():
    ontology = default_world.get_ontology(BASE_URI)
    owl_dsl_ns = ontology.get_namespace(OWL_DSL_NS)
    with ontology:
        with owl_dsl_ns:

            class OWL_DSL_000001(AnnotationProperty):
                pass

        class Person(Thing):
            label = ["Person"]

        class EmekasChild(Person):
            label = ["Child of Emeka"]

        class father(ObjectProperty):
            label = ["father"]
            OWL_DSL_000001 = ["has {} as their father"]

        emeka = Person("Emeka", label=["Emeka"])
        EmekasChild.is_a = [Person & father.value(emeka)]
    default_world.save()
    handler = CNLRenderer(ontology, BASE_URI, verbose=False, lowercase_labels=False)
    configure_cnl_from_annotations(handler, ontology.world.as_rdflib_graph())
    assert (
        handler.handle_owl_class(ontology.search_one(iri=NS.EmekasChild))
        == EXPECTED_TEXT4
    )
    del default_world.ontologies[ontology.base_iri]


def test_min_cardinality_restriction():
    ontology = default_world.get_ontology(BASE_URI)
    owl_dsl_ns = ontology.get_namespace(OWL_DSL_NS)
    with ontology:
        with owl_dsl_ns:

            class OWL_DSL_000001(AnnotationProperty):
                pass

        class Human(Thing):
            label = ["Human"]

        class Person(Human):
            label = ["Person"]

        class father(ObjectProperty):
            label = ["father"]
            OWL_DSL_000001 = ["has a father relationship with at least one {}"]

        Person.is_a = [father.min(1, Person)]
    default_world.save()
    handler = CNLRenderer(ontology, BASE_URI, verbose=False, lowercase_labels=False)
    configure_cnl_from_annotations(handler, ontology.world.as_rdflib_graph())
    rendered = handler.handle_owl_class(ontology.search_one(iri=NS.Person))
    del default_world.ontologies[ontology.base_iri]
    assert rendered == EXPECTED_TEXT5

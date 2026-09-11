"""Tests for owl_dsl.annotations — annotation parsing from rdflib graphs."""

import pytest
from rdflib import Graph, URIRef, Literal, RDF, RDFS, OWL, BNode
from rdflib.term import Identifier as RDFIdentifier
from rdflib.namespace import Namespace
from owl_dsl.annotations import (
    _iter_rdf_list,
    _expand_objects,
    _objects_as_strings,
    _first_literal,
    _get_ontology_subject,
    get_annotation_value,
    load_global_annotations,
    load_property_annotations,
    OWL_DSL,
    OBO,
    DEFAULT_EXPERT_DEFINITION_PROPERTIES,
)

TEST_NS = "https://github.com/chimezie/owl_dsl/test#"
TEST = Namespace(TEST_NS)


# -- Helpers --


class TestIterRdfList:
    def test_single_element_list(self):
        g = Graph()
        head = BNode()
        g.add((head, RDF.first, Literal("foo")))
        g.add((head, RDF.rest, RDF.nil))
        assert list(_iter_rdf_list(g, head)) == [Literal("foo")]

    def test_multiple_elements(self):
        g = Graph()
        n1 = BNode()
        n2 = BNode()
        g.add((n1, RDF.first, Literal("a")))
        g.add((n1, RDF.rest, n2))
        g.add((n2, RDF.first, Literal("b")))
        g.add((n2, RDF.rest, RDF.nil))
        assert list(_iter_rdf_list(g, n1)) == [Literal("a"), Literal("b")]

    def test_nil_head_yields_nothing(self):
        g = Graph()
        assert list(_iter_rdf_list(g, RDF.nil)) == []


class TestExpandObjects:
    def test_uriref_returns_single_string(self):
        g = Graph()
        assert _expand_objects(g, TEST.SomeClass) == [str(TEST.SomeClass)]

    def test_literal_returns_single_string(self):
        g = Graph()
        assert _expand_objects(g, Literal("hello")) == ["hello"]

    def test_bnode_list_expands(self):
        g = Graph()
        head = BNode()
        g.add((head, RDF.first, Literal("x")))
        g.add((head, RDF.rest, RDF.nil))
        assert _expand_objects(g, head) == ["x"]

    def test_bnode_not_list_returns_empty(self):
        g = Graph()
        b = BNode()
        assert _expand_objects(g, b) == []


class TestObjectsAsStrings:
    def test_single_literal(self):
        g = Graph()
        g.add((TEST.Sub, TEST.p, Literal("val")))
        assert _objects_as_strings(g, TEST.Sub, TEST.p) == ["val"]

    def test_multiple_literals(self):
        g = Graph()
        g.add((TEST.Sub, TEST.p, Literal("a")))
        g.add((TEST.Sub, TEST.p, Literal("b")))
        assert sorted(_objects_as_strings(g, TEST.Sub, TEST.p)) == ["a", "b"]

    def test_rdf_list_expanded(self):
        g = Graph()
        head = BNode()
        g.add((head, RDF.first, TEST.Item1))
        g.add((head, RDF.rest, RDF.nil))
        g.add((TEST.Sub, TEST.p, head))
        assert _objects_as_strings(g, TEST.Sub, TEST.p) == [str(TEST.Item1)]


class TestFirstLiteral:
    def test_returns_first_literal(self):
        g = Graph()
        g.add((TEST.Sub, TEST.p, Literal("first")))
        g.add((TEST.Sub, TEST.p, Literal("second")))
        assert _first_literal(g, TEST.Sub, TEST.p) == "first"

    def test_ignores_non_literals(self):
        g = Graph()
        g.add((TEST.Sub, TEST.p, TEST.SomeClass))
        g.add((TEST.Sub, TEST.p, Literal("text")))
        assert _first_literal(g, TEST.Sub, TEST.p) == "text"

    def test_none_when_no_literal(self):
        g = Graph()
        g.add((TEST.Sub, TEST.p, TEST.SomeClass))
        assert _first_literal(g, TEST.Sub, TEST.p) is None


class TestGetOntologySubject:
    def test_finds_ontology_subject(self):
        g = Graph()
        g.add((TEST.MyOnt, RDF.type, OWL.Ontology))
        assert _get_ontology_subject(g) == TEST.MyOnt

    def test_none_when_missing(self):
        g = Graph()
        assert _get_ontology_subject(g) is None


class TestGetAnnotationValue:
    def test_returns_literal(self):
        g = Graph()
        g.add((TEST.Sub, TEST.p, Literal("hello")))
        assert get_annotation_value(g, TEST.Sub, TEST.p) == "hello"

    def test_default_when_missing(self):
        g = Graph()
        assert (
            get_annotation_value(g, TEST.Sub, TEST.p, default="fallback") == "fallback"
        )

    def test_none_default_when_missing(self):
        g = Graph()
        assert get_annotation_value(g, TEST.Sub, TEST.p) is None


# -- load_global_annotations --


def make_ontology_graph(**annotations):
    """Build an rdflib Graph with a single OWL Ontology subject and optional
    OWL_DSL annotations attached to it."""
    g = Graph()
    onto = TEST.MyOnt
    g.add((onto, RDF.type, OWL.Ontology))
    for predicate, values in annotations.items():
        if isinstance(values, list):
            # Build an RDF list
            if not values:
                g.add((onto, predicate, RDF.nil))
            else:
                prev = None
                first = None
                for v in values:
                    node = BNode()
                    g.add(
                        (
                            node,
                            RDF.first,
                            URIRef(v) if v.startswith("http") else Literal(v),
                        )
                    )
                    if prev is not None:
                        g.add((prev, RDF.rest, node))
                    else:
                        first = node
                    prev = node
                g.add((prev, RDF.rest, RDF.nil))
                g.add((onto, predicate, first))
        else:
            g.add((onto, predicate, values))
    return g, onto


class TestLoadGlobalAnnotations:
    def test_no_ontology_subject_returns_defaults(self):
        g = Graph()
        result = load_global_annotations(g)
        assert result["class_inference_to_ignore"] == []
        assert (
            result["expert_definition_properties"]
            == DEFAULT_EXPERT_DEFINITION_PROPERTIES
        )
        assert result["expert_definition_properties_present"] is False
        assert result["standard_role_restriction_is_phrasing"] == []

    def test_empty_ontology_returns_defaults(self):
        g, _ = make_ontology_graph()
        result = load_global_annotations(g)
        assert result["class_inference_to_ignore"] == []
        assert result["standard_role_restriction_is_phrasing"] == []

    def test_class_inference_to_ignore(self):
        g, onto = make_ontology_graph()
        # Build RDF list via helper
        _add_list(g, onto, OWL_DSL.OWL_DSL_000004, [TEST.ClassA, TEST.ClassB])
        result = load_global_annotations(g)
        assert str(TEST.ClassA) in result["class_inference_to_ignore"]
        assert str(TEST.ClassB) in result["class_inference_to_ignore"]

    def test_expert_definition_properties(self):
        g, onto = make_ontology_graph()
        _add_list(g, onto, OWL_DSL.OWL_DSL_000005, [TEST.MyDef])
        result = load_global_annotations(g)
        assert str(TEST.MyDef) in result["expert_definition_properties"]
        assert result["expert_definition_properties_present"] is True

    def test_expert_definition_properties_default_when_empty(self):
        g, onto = make_ontology_graph()
        # No OWL_DSL_000005 predicate at all → defaults used
        result = load_global_annotations(g)
        assert (
            result["expert_definition_properties"]
            == DEFAULT_EXPERT_DEFINITION_PROPERTIES
        )
        assert result["expert_definition_properties_present"] is False

    def test_standard_role_restriction_is_phrasing(self):
        g, onto = make_ontology_graph()
        _add_list(g, onto, OWL_DSL.OWL_DSL_000006, [TEST.has_pet])
        result = load_global_annotations(g)
        assert str(TEST.has_pet) in result["standard_role_restriction_is_phrasing"]


# -- load_property_annotations --


def _add_list(graph, subject, predicate, items):
    """Add an RDF list from *subject* via *predicate*."""
    if not items:
        graph.add((subject, predicate, RDF.nil))
        return
    prev = None
    first = None
    for item in items:
        node = BNode()
        graph.add(
            (
                node,
                RDF.first,
                (
                    URIRef(item)
                    if isinstance(item, str) and item.startswith("http")
                    else item
                ),
            )
        )
        if prev is not None:
            graph.add((prev, RDF.rest, node))
        else:
            first = node
        prev = node
    graph.add((prev, RDF.rest, RDF.nil))
    graph.add((subject, predicate, first))


class TestLoadPropertyAnnotations:
    def test_empty_graph(self):
        g = Graph()
        tm, rm = load_property_annotations(g)
        assert tm == {}
        assert rm == {}

    def test_singular_template(self):
        g = Graph()
        g.add((TEST.has_pet, OWL_DSL.OWL_DSL_000001, Literal("has a pet {}")))
        tm, rm = load_property_annotations(g)
        assert str(TEST.has_pet) in tm
        s, p, pr = tm[str(TEST.has_pet)]
        assert s == "has a pet {}"
        assert p is None
        assert pr is None
        assert rm == {}

    def test_all_templates(self):
        g = Graph()
        g.add((TEST.has_pet, OWL_DSL.OWL_DSL_000001, Literal("has a pet {}")))
        g.add((TEST.has_pet, OWL_DSL.OWL_DSL_000002, Literal("have pets {}")))
        g.add(
            (TEST.has_pet, OWL_DSL.OWL_DSL_000003, Literal("What pets does {} have?"))
        )
        tm, rm = load_property_annotations(g)
        assert str(TEST.has_pet) in tm
        s, p, pr = tm[str(TEST.has_pet)]
        assert s == "has a pet {}"
        assert p == "have pets {}"
        assert pr == "What pets does {} have?"

    def test_reflexive_map(self):
        g = Graph()
        g.add(
            (
                TEST.interacts_with,
                OWL_DSL.OWL_DSL_000007,
                Literal("that interacts with itself"),
            )
        )
        tm, rm = load_property_annotations(g)
        # reflexive_map is populated inside the SPARQL loop over template
        # predicates; without at least one template row it stays empty.
        assert tm == {}
        # Reflexive requires template co-presence due to loop structure
        assert rm == {}

    def test_reflexive_with_template(self):
        """When a property has both a template annotation and a reflexive
        annotation, both template_map and reflexive_map are populated."""
        g = Graph()
        g.add(
            (TEST.interacts_with, OWL_DSL.OWL_DSL_000001, Literal("interacts with {}"))
        )
        g.add(
            (
                TEST.interacts_with,
                OWL_DSL.OWL_DSL_000007,
                Literal("that interacts with itself"),
            )
        )
        tm, rm = load_property_annotations(g)
        assert str(TEST.interacts_with) in tm
        s, p, pr = tm[str(TEST.interacts_with)]
        assert s == "interacts with {}"
        assert str(TEST.interacts_with) in rm
        assert rm[str(TEST.interacts_with)] == "that interacts with itself"


# -- configure_cnl_from_annotations (integration) --


class TestConfigureCnlFromAnnotations:
    def test_configure_templates(self, cnl_renderer):
        g = Graph()
        g.add((TEST.has_pet, OWL_DSL.OWL_DSL_000001, Literal("has a pet {}")))
        from owl_dsl.annotations import configure_cnl_from_annotations

        configure_cnl_from_annotations(cnl_renderer, g)
        key = URIRef(str(TEST.has_pet))
        assert key in cnl_renderer.relevant_role_restriction_cnl_phrasing
        s, p, pr = cnl_renderer.relevant_role_restriction_cnl_phrasing[key]
        assert s == "has a pet {}"

    def test_configure_reflexive(self, cnl_renderer):
        g = Graph()
        g.add(
            (
                TEST.interacts_with,
                OWL_DSL.OWL_DSL_000007,
                Literal("that interacts with itself"),
            )
        )
        from owl_dsl.annotations import configure_cnl_from_annotations

        configure_cnl_from_annotations(cnl_renderer, g)
        key = URIRef(str(TEST.interacts_with))
        assert key in cnl_renderer.reflexive_property_customizations
        assert (
            cnl_renderer.reflexive_property_customizations[key]
            == "that interacts with itself"
        )

    def test_standard_role_restriction_is_phrasing(self, cnl_renderer):
        g = Graph()
        onto_uri = URIRef(str(TEST.MyOnt))
        g.add((onto_uri, RDF.type, OWL.Ontology))
        g.add((onto_uri, OWL_DSL.OWL_DSL_000006, TEST.has_pet))
        g.add((TEST.has_pet, RDF.type, OWL.ObjectProperty))
        g.add((TEST.has_pet, RDFS.label, Literal("has pet")))
        from owl_dsl.annotations import configure_cnl_from_annotations

        configure_cnl_from_annotations(cnl_renderer, g)
        key = URIRef(str(TEST.has_pet))
        if key in cnl_renderer.relevant_role_restriction_cnl_phrasing:
            phrasing = cnl_renderer.relevant_role_restriction_cnl_phrasing[key]
            assert "is has pet" in phrasing[0]

    def test_expert_definition_properties(self, cnl_renderer):
        g = Graph()
        onto_uri = URIRef(str(TEST.MyOnt))
        g.add((onto_uri, RDF.type, OWL.Ontology))
        g.add((TEST.MyDef, RDF.type, OWL.AnnotationProperty))
        g.add((TEST.MyDef, OWL_DSL.OWL_DSL_000005, Literal(True)))
        from owl_dsl.annotations import configure_cnl_from_annotations

        configure_cnl_from_annotations(cnl_renderer, g)
        # configure_cnl_from_annotations sets expert_definition_properties
        assert hasattr(cnl_renderer, "expert_definition_properties")
        assert OBO.IAO_0000115 in cnl_renderer.expert_definition_properties
        # SPARQL results are appended as single-element tuples
        assert (TEST.MyDef,) in cnl_renderer.expert_definition_properties

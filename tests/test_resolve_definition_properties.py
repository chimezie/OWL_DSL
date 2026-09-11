"""Tests for the unified ontology-first configuration resolution.

``owl_dsl.annotations.resolve_definition_properties`` is the single shared
entry point used by ``owl_dsl.review`` (render_class, find_properties,
lint_ontology), ``owl_dsl.reason`` (explain_logical_inferences, justify_gci)
and ``owl_dsl.render_rules``. Ontology-embedded ``OWL_DSL_*`` annotations take
precedence for expert definition properties; the YAML ``--configuration-file``
is applied first and kept as fallback.
"""

import pytest
from click.testing import CliRunner
from rdflib import BNode, Graph, Literal, Namespace, RDF, OWL, URIRef
from unittest.mock import MagicMock, patch

from owl_dsl.annotations import (
    DEFAULT_EXPERT_DEFINITION_PROPERTIES,
    OWL_DSL,
    resolve_definition_properties,
)

TEST_NS = "https://github.com/chimezie/owl_dsl/test#"
TEST = Namespace(TEST_NS)
FILE_DEF = "http://example.org/file_definition"
ONTO_DEF = "http://example.org/onto_definition"


def _add_list(graph, subject, predicate, items):
    """Add an RDF list from *subject* via *predicate*."""
    if not items:
        graph.add((subject, predicate, RDF.nil))
        return
    prev = None
    first = None
    for item in items:
        node = BNode()
        graph.add((node, RDF.first, URIRef(item)))
        if prev is not None:
            graph.add((prev, RDF.rest, node))
        else:
            first = node
        prev = node
    graph.add((prev, RDF.rest, RDF.nil))
    graph.add((subject, predicate, first))


def _plain_graph():
    """Graph with an ontology header but no OWL_DSL annotations."""
    graph = Graph()
    graph.add((TEST.MyOnt, RDF.type, OWL.Ontology))
    return graph


def _annotated_graph(with_templates=False):
    """Graph declaring ONTO_DEF as an expert definition property."""
    graph = _plain_graph()
    _add_list(graph, TEST.MyOnt, OWL_DSL.OWL_DSL_000005, [ONTO_DEF])
    if with_templates:
        graph.add((TEST.has_pet, OWL_DSL.OWL_DSL_000001, Literal("has a pet {}")))
        graph.add((TEST.has_pet, OWL_DSL.OWL_DSL_000002, Literal("have pets {}")))
        graph.add(
            (
                TEST.has_pet,
                OWL_DSL.OWL_DSL_000003,
                Literal("What pets does {} have?"),
            )
        )
    return graph


def _write_owl_file(tmp_path, graph, name="test.owl"):
    """Serialize *graph* to a temp OWL file parseable by load_annotations_graph."""
    path = tmp_path / name
    path.write_text(graph.serialize(format="xml"))
    return str(path)


@pytest.fixture
def yaml_config(tmp_path):
    """YAML config declaring FILE_DEF as the expert definition property."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "class_inference_to_ignore: []\n"
        "tooling:\n"
        f"  expert_definition_properties: ['{FILE_DEF}']\n"
        "standard_role_restriction_is_phrasing: []\n"
        "reflexive_roles: []\n"
        "role_restriction_phrasing: {}\n"
    )
    return str(config_file)


class TestResolveDefinitionProperties:
    def test_file_only(self, cnl_renderer, tmp_path, yaml_config):
        owl_path = _write_owl_file(tmp_path, _plain_graph())
        props, graph = resolve_definition_properties(
            cnl_renderer, None, owl_path, yaml_config
        )
        assert props == [FILE_DEF]
        assert graph is not None

    def test_ontology_only(self, cnl_renderer, tmp_path):
        owl_path = _write_owl_file(tmp_path, _annotated_graph())
        props, graph = resolve_definition_properties(cnl_renderer, None, owl_path, None)
        assert ONTO_DEF in props
        assert FILE_DEF not in props

    def test_annotations_win_when_both_present(
        self, cnl_renderer, tmp_path, yaml_config
    ):
        owl_path = _write_owl_file(tmp_path, _annotated_graph())
        props, _ = resolve_definition_properties(
            cnl_renderer, None, owl_path, yaml_config
        )
        assert ONTO_DEF in props
        assert FILE_DEF not in props

    def test_file_kept_when_no_annotation_definitions(
        self, cnl_renderer, tmp_path, yaml_config
    ):
        owl_path = _write_owl_file(tmp_path, _plain_graph())
        props, _ = resolve_definition_properties(
            cnl_renderer, None, owl_path, yaml_config
        )
        assert props == [FILE_DEF]

    def test_annotation_templates_merge_with_file(
        self, cnl_renderer, tmp_path, yaml_config
    ):
        """Property templates from annotations apply even when the file wins."""
        owl_path = _write_owl_file(tmp_path, _annotated_graph(with_templates=True))
        props, _ = resolve_definition_properties(
            cnl_renderer, None, owl_path, yaml_config
        )
        assert ONTO_DEF in props
        key = URIRef(str(TEST.has_pet))
        assert key in cnl_renderer.relevant_role_restriction_cnl_phrasing
        singular, _, _ = cnl_renderer.relevant_role_restriction_cnl_phrasing[key]
        assert singular == "has a pet {}"

    def test_neither_source_gives_defaults(self, cnl_renderer, tmp_path):
        owl_path = _write_owl_file(tmp_path, _plain_graph())
        props, _ = resolve_definition_properties(cnl_renderer, None, owl_path, None)
        assert props == DEFAULT_EXPERT_DEFINITION_PROPERTIES


class TestBackwardsCompatibility:
    def test_cli_setup_configuration_still_importable(self, tmp_path):
        from owl_dsl.cli import setup_configuration

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "class_inference_to_ignore: []\n"
            "tooling:\n"
            f"  expert_definition_properties: ['{FILE_DEF}']\n"
            "standard_role_restriction_is_phrasing: []\n"
            "reflexive_roles: []\n"
            "role_restriction_phrasing: {}\n"
        )
        handler = MagicMock()
        assert setup_configuration(handler, str(config_file)) == [FILE_DEF]

    def test_reasoner_configuration_file_is_optional(self):
        from owl_dsl.reasoner import main

        opt = next(p for p in main.params if p.name == "configuration_file")
        assert opt.required is False


class TestFindPropertiesWithoutConfigurationFile:
    """find_properties must no longer require --configuration-file."""

    @patch("owl_dsl.cli.pyhornedowl.open_ontology")
    @patch("owl_dsl.cli.CNLRenderer")
    def test_find_properties_ontology_only(
        self, mock_renderer_cls, mock_open_onto, tmp_path
    ):
        from owl_dsl.cli import main

        owl_path = _write_owl_file(tmp_path, _plain_graph())

        mock_onto = MagicMock()
        mock_open_onto.return_value = mock_onto
        annotation_graph = Graph()
        annotation_graph.parse(owl_path)
        mock_onto.world.as_rdflib_graph.return_value = annotation_graph

        prop_iri = "http://test.org/onto.owl#has_pet"
        mock_onto.get_object_properties.return_value = {prop_iri}
        mock_onto.get_data_properties.return_value = set()
        mock_onto.get_annotation_properties.return_value = set()
        mock_onto.get_annotations.side_effect = lambda iri, prop: (
            ["has pet"] if prop == "http://www.w3.org/2000/01/rdf-schema#label" else []
        )

        mock_renderer = MagicMock()
        mock_renderer_cls.return_value = mock_renderer
        mock_renderer.class_inference_to_ignore = []
        mock_renderer.relevant_role_restriction_cnl_phrasing = {}
        mock_renderer.reflexive_property_customizations = {}
        mock_renderer.ontology = MagicMock()
        mock_renderer.ontology.search.return_value = []

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--action",
                "find_properties",
                "--ontology-uri",
                "http://test.org/onto.owl",
                "--ontology-namespace-baseuri",
                "http://test.org/onto.owl#",
                owl_path,
            ],
        )
        assert result.exit_code == 0, result.output
        assert prop_iri in result.output

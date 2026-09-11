import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock, patch
from owl_dsl.cli import match_object_sparql_expression, main, run_subprocess


def test_match_object_sparql_expression():
    # Single resource, not just filter
    res = match_object_sparql_expression("var", ["http://example.org/A"])
    assert res == "<http://example.org/A>"

    # Multiple resources, not just filter
    res = match_object_sparql_expression(
        "var", ["http://example.org/A", "http://example.org/B"]
    )
    assert (
        "?var FILTER(?var = <http://example.org/A> || ?var = <http://example.org/B>)"
        in res
    )

    # Multiple resources, just filter
    res = match_object_sparql_expression(
        "var", ["http://example.org/A", "http://example.org/B"], just_filter=True
    )
    assert (
        "FILTER(?var = <http://example.org/A> || ?var = <http://example.org/B>)" in res
    )

    # Empty resources
    res = match_object_sparql_expression("var", [])
    assert res == ""


@patch("owl_dsl.cli.pyhornedowl.open_ontology")
def test_cli_find_classes(mock_open_onto):
    runner = CliRunner()

    mock_onto = MagicMock()
    mock_onto.get_classes.return_value = {"http://example.org/Person"}
    mock_onto.get_annotations.return_value = ["Person"]
    mock_onto.get_object_properties.return_value = set()
    mock_onto.get_data_properties.return_value = set()
    mock_onto.get_annotation_properties.return_value = set()
    mock_open_onto.return_value = mock_onto

    result = runner.invoke(
        main,
        [
            "--action",
            "find_classes",
            "--class-search",
            "Person",
            "--ontology-uri",
            "http://test.org/onto.owl",
            "--ontology-namespace-baseuri",
            "http://test.org/onto.owl#",
            "--sqlite-file",
            "/tmp/test.sqlite",
        ],
    )

    assert result.exit_code == 0
    assert "http://example.org/Person 'Person'" in result.output


@patch("owl_dsl.cli.pyhornedowl.open_ontology")
@patch("owl_dsl.cli.CNLRenderer")
@patch("owl_dsl.cli.resolve_definition_properties")
def test_cli_render_class(mock_resolve, mock_renderer_cls, mock_open_onto):
    runner = CliRunner()

    mock_onto = MagicMock()
    mock_open_onto.return_value = mock_onto

    mock_renderer = MagicMock()
    mock_renderer_cls.return_value = mock_renderer
    mock_renderer._entity_label.return_value = "Person"

    IAO_0000115 = "http://purl.obolibrary.org/obo/IAO_0000115"
    mock_resolve.return_value = ([IAO_0000115], None)

    def mock_get_annotations(iri, prop):
        if prop == IAO_0000115:
            return ["Definition of Person"]
        if prop == "http://www.w3.org/2000/01/rdf-schema#label":
            return ["Person"]
        return []

    mock_onto.get_annotations.side_effect = mock_get_annotations

    mock_renderer.handle_owl_class.return_value = "Person is a mammal."

    result = runner.invoke(
        main,
        [
            "--action",
            "render_class",
            "--class-reference",
            "Person",
            "--ontology-uri",
            "http://test.org/onto.owl",
            "--ontology-namespace-baseuri",
            "http://test.org/onto.owl#",
            "--sqlite-file",
            "/tmp/test.sqlite",
            "--configuration-file",
            "config.yaml",
            "--by-id",
        ],
    )

    if result.exit_code != 0:
        print(result.output)
        print(result.exception)

    assert result.exit_code == 0
    assert "# http://test.org/onto.owl#Person (Person) #" in result.output
    assert "Definition of Person" in result.output
    assert "Person is a mammal." in result.output


@patch("subprocess.run")
def test_run_subprocess(mock_run):
    mock_resp = MagicMock()
    mock_resp.stdout.decode.return_value = "output"
    mock_run.return_value = mock_resp

    run_subprocess(["ls", "-l"], verbose=True)

    mock_run.assert_called_with(["ls", "-l"], capture_output=True)

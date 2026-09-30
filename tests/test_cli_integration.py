"""Integration tests for owl_dsl.cli using real OWL ontologies.
Each CLI invocation uses its own SQLite file to avoid database locking."""

import os
import pytest
from click.testing import CliRunner
from owl_dsl.cli import main

ONTO_URI = "https://github.com/chimezie/owl_dsl/Terms#"
BASE_URI = "https://github.com/chimezie/owl_dsl/Terms#"


def test_cli_load_owl(tmp_path):
    """load_owl action with a real OWL file."""
    sqlite = str(tmp_path / "load.sqlite")
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--action",
            "load_owl",
            "--ontology-uri",
            ONTO_URI,
            "--ontology-namespace-baseuri",
            BASE_URI,
            "--sqlite-file",
            sqlite,
        ],
    )
    assert result.exit_code == 0


def test_cli_destroy_sqlite(tmp_path):
    """destroy_sqlite action with a pre-created file."""
    sqlite = str(tmp_path / "destroy.sqlite")
    # Create an empty file first
    open(sqlite, "w").close()
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--action",
            "destroy_sqlite",
            "--sqlite-file",
            sqlite,
            "--ontology-uri",
            ONTO_URI,
            "--ontology-namespace-baseuri",
            BASE_URI,
        ],
    )
    assert result.exit_code == 0
    assert not os.path.exists(sqlite)

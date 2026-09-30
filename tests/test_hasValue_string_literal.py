"""Test: hasValue with string literal should not crash."""

import os
import pytest

import pyhornedowl
from pyhornedowl.model import (
    Class,
    DataProperty,
    DataHasValue,
    SubClassOf,
    DeclareClass,
    DeclareDataProperty,
    IRI,
    SimpleLiteral,
)
from owl_dsl.renderer import CNLRenderer

BASE_URI = "https://github.com/chimezie/owl_dsl/Terms#"


def setup_module():
    os.environ["OWL_DSL_COLLECT_DEFINITION_INFO"] = "0"


def test_hasValue_string_literal():
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", BASE_URI)

    onto.add_component(DeclareClass(Class(IRI.parse(BASE_URI + "Movie"))))
    onto.set_label(IRI.parse(BASE_URI + "Movie"), "Movie")

    onto.add_component(
        DeclareDataProperty(DataProperty(IRI.parse(BASE_URI + "movie_type")))
    )
    onto.set_label(IRI.parse(BASE_URI + "movie_type"), "movie type")

    dhv = DataHasValue(
        DataProperty(IRI.parse(BASE_URI + "movie_type")), SimpleLiteral("movie")
    )
    rendered = CNLRenderer(
        onto, BASE_URI, verbose=False, lowercase_labels=False
    ).render_owl_class(dhv)
    assert rendered is not None
    assert '"movie"' in rendered
    assert "movie type" in rendered

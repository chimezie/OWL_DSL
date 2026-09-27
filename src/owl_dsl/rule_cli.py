#!/usr/bin/env python
"""CLI entry point for ``owl_dsl.render_rules``.

Extracts Horn rules from an OWL ontology using FuXi's Description Logic
Programming (DLP) system and renders each rule as a Controlled Natural
Language (CNL) sentence via :class:`~owl_dsl.rule_renderer.RuleRenderer`.

Derived predicates (IDB rule heads) are identified automatically from the
extracted rule set.  :func:`fuxi.LP.IdentifyHybridPredicates` is then used
to detect predicates that also appear as extensional (EDB) facts in the
ontology graph; these are reported in verbose mode.

Property phrase templates are loaded from ``OWL_DSL_000001`` annotations
on object properties in the ontology graph.  Properties that lack an
annotation fall back to a default ``"has {} as their <label>"`` template
derived from the property's ``rdfs:label``.

An optional YAML configuration file (same format as ``owl_dsl.review``)
can supplement annotation-derived templates. Ontology-embedded
``OWL_DSL_*`` annotations take precedence for expert definition properties;
the YAML file is used as fallback.
"""

import click
from rdflib import RDF, URIRef
from owlready2 import World, default_world

from fuxi.Horn.PositiveConditions import Uniterm
from fuxi.LP import identify_hybrid_predicates
from fuxi.Rete.RuleStore import setup_rule_store

from owl_dsl.annotations import resolve_definition_properties
from owl_dsl.rule_renderer import RuleRenderer


def _is_subclass_rule(rule) -> bool:
    """Return True if *rule* is a pure rdf:type → rdf:type (subclass) rule."""
    return (
        isinstance(rule.formula.body, Uniterm)
        and rule.formula.body.op == RDF.type
        and isinstance(rule.formula.head, Uniterm)
        and rule.formula.head.op == RDF.type
    )


@click.command()
@click.option(
    "--ontology-uri",
    type=str,
    default=None,
    help="URI of the ontology. Inferred from the OWL file when a local path is given.",
)
@click.option(
    "--ontology-namespace-baseuri",
    type=str,
    default=None,
    help="Base URI of the ontology namespace passed to RuleRenderer. "
    "Defaults to --ontology-uri when omitted.",
)
@click.option(
    "--sqlite-file",
    type=str,
    default=None,
    help="SQLite backend file for an already-loaded owlready2 world.",
)
@click.option(
    "--configuration-file",
    type=str,
    default=None,
    help="YAML configuration file for CNL rendering (same format as owl_dsl.review). "
    "Supplements ontology-embedded OWL_DSL_* annotations, which take precedence.",
)
@click.option(
    "--skip-subclass-rules/--no-skip-subclass-rules",
    default=True,
    help="Skip pure rdf:type → rdf:type rules (already covered by OWL class rendering).",
)
@click.option("--verbose/--no-verbose", default=False)
@click.argument("owl_url_or_path", required=False)
def main(
    ontology_uri,
    ontology_namespace_baseuri,
    sqlite_file,
    configuration_file,
    skip_subclass_rules,
    verbose,
    owl_url_or_path,
):
    """Render Horn rules extracted from an OWL ontology as CNL sentences.

    Loads the ontology from OWL_URL_OR_PATH (a file path or URL) or from a
    previously-populated SQLite backend (--sqlite-file), extracts Horn rules
    via FuXi's DLP system, and prints each rule as a natural-language sentence.

    Derived predicates are identified automatically from the rule heads;
    hybrid predicates (those that appear both as derived and as direct facts)
    are reported when --verbose is set.

    \b
    Example (from file):
        owl_dsl.render_rules \\
            --ontology-uri http://example.org/ \\
            --ontology-namespace-baseuri http://example.org/ \\
            path/to/my.owl

    \b
    Example (from SQLite world):
        owl_dsl.render_rules \\
            --ontology-uri http://example.org/ \\
            --ontology-namespace-baseuri http://example.org/ \\
            --sqlite-file my_world.sqlite
    """
    # --- Load ontology ---
    if sqlite_file:
        if not ontology_uri:
            raise click.UsageError(
                "--ontology-uri is required when using --sqlite-file."
            )
        default_world.set_backend(filename=sqlite_file)
        ontology = default_world.ontologies.get(ontology_uri)
        if ontology is None:
            raise click.ClickException(
                f"Ontology '{ontology_uri}' not found in '{sqlite_file}'. "
                "Load it first with: owl_dsl.review --action load_owl ..."
            )
        ont_graph = default_world.as_rdflib_graph()
    elif owl_url_or_path:
        world = World()
        ontology = world.get_ontology(owl_url_or_path)
        ontology.load()
        ont_graph = world.as_rdflib_graph()
        if not ontology_uri:
            ontology_uri = ontology.base_iri
        if not ontology_namespace_baseuri:
            ontology_namespace_baseuri = ontology_uri
    else:
        raise click.UsageError(
            "Provide either --sqlite-file or a positional OWL_URL_OR_PATH argument."
        )

    if verbose:
        print(f"Ontology loaded: {ontology_uri}")

    # --- Extract all Horn rules via FuXi DLP ---
    rule_store, rule_graph, network = setup_rule_store(make_network=True)
    program = list(
        network.setup_description_logic_programming(
            ont_graph,
            add_pd_semantics=False,
            construct_network=False,
            derived_preds=None,
        )
    )

    if verbose:
        print(f"Extracted {len(program)} rules from DLP")

    # --- Auto-identify derived predicates from rule heads ---
    derived_preds = {
        URIRef(rule.formula.head.op)
        for rule in program
        if isinstance(rule.formula.head, Uniterm) and rule.formula.head.op != RDF.type
    }

    # Detect hybrid predicates: derived predicates that also appear as EDB facts
    hybrid_preds = identify_hybrid_predicates(ont_graph, derived_preds)
    if verbose and hybrid_preds:
        print(f"Hybrid predicates (IDB ∩ EDB): {hybrid_preds}")

    # --- Configure renderer (ontology annotations win, YAML file as fallback) ---
    renderer = RuleRenderer(ontology, ontology_namespace_baseuri, verbose=verbose)
    resolve_definition_properties(
        renderer, ontology, owl_url_or_path, configuration_file, verbose
    )

    # --- Render rules ---
    rendered = 0
    for rule in program:
        if skip_subclass_rules and _is_subclass_rule(rule):
            continue
        try:
            print("--------------")
            print(rule)
            print(renderer.render_rule(rule))
            rendered += 1
        except Exception as exc:
            if verbose:
                import traceback

                traceback.print_exc()
                print(f"Warning: could not render rule {rule}: {exc}")

    if verbose:
        print(f"Rendered {rendered} rules")


if __name__ == "__main__":
    main()

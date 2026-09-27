#!/usr/bin/env python
"""CLI entry points for the OWL-DSL toolset.

This module provides a Command Line Interface for interacting with OWL ontologies.
It enables users to load ontologies into a persistent SQLite backend, find classes
and properties via SPARQL, and render complex OWL class definitions into
Controlled Natural Language (CNL) for domain expert review.
"""

import difflib
from io import StringIO

import click
import os
import re
from subprocess import CompletedProcess
from click import Choice
from typing import List, Iterable
import tracemalloc

import pyhornedowl
from pyhornedowl.model import (
    Class,
    ObjectIntersectionOf,
    ObjectUnionOf,
    ObjectSomeValuesFrom,
    ObjectAllValuesFrom,
    ObjectHasValue,
    ObjectHasSelf,
    ObjectMinCardinality,
    ObjectMaxCardinality,
    ObjectExactCardinality,
    DataSomeValuesFrom,
    DataAllValuesFrom,
    DataHasValue,
    DataMinCardinality,
    DataMaxCardinality,
    DataExactCardinality,
    ObjectComplementOf,
    InverseObjectProperty,
    ObjectProperty,
    DataProperty,
    AnnotationProperty,
    ObjectOneOf,
    DatatypeRestriction,
    NamedIndividual,
    AnonymousIndividual,
    Datatype,
    SubClassOf,
    EquivalentClasses,
    AnnotationAssertion,
)
from rdflib import URIRef, Literal, Namespace, Graph

from fuxi.Syntax.InfixOWL import (
    GraphContext,
    Property as InfixProperty,
    Class as InfixClass,
    all_properties,
    all_classes,
)
from owl_dsl.annotations import (
    resolve_definition_properties,
    setup_configuration_from_yaml,
)
from owl_dsl.renderer import CNLRenderer, RDFS_LABEL, SKOS_PREFLABEL, _get_local_name

DC_TITLE_URI = "http://purl.org/dc/elements/1.1/title"
DC_DESCRIPTION_URI = "http://purl.org/dc/elements/1.1/description"


def run_subprocess(command: List[str], verbose=False) -> CompletedProcess:
    """
    Execute a system command as a subprocess.

    Args:
        command: The command and its arguments as a list of strings.
        verbose: If True, print the command and its stdout to the console.

    Returns:
        The CompletedProcess instance containing the result of the execution.
    """
    import subprocess

    if verbose:
        print("Running command: ", " ".join(command))
    resp = subprocess.run(command, capture_output=verbose)
    if verbose:
        print(resp.stdout.decode("utf-8"))
    return resp


def match_object_sparql_expression(
    variable_name: str, resources: List[str], just_filter: bool = False
):
    """
    Construct a SPARQL expression to match a set of resources.

    This utility generates either a simple URI reference (for single resources)
    or a FILTER expression using OR logic (for multiple resources) to refine
    SPARQL queries dynamically.

    Args:
        variable_name: The SPARQL variable name (e.g., 'prop').
        resources: A list of resource IRIs to match against.
        just_filter: If True, returns only the FILTER clause. If False,
            includes the variable declaration.

    Returns:
        A string containing the formatted SPARQL expression.
    """
    if len(resources) == 1 and not just_filter:
        return f"<{resources[0]}>"
    elif len(resources):
        filter_expr = " || ".join([f"?{variable_name} = <{p}>" for p in resources])
        return (
            f"FILTER({filter_expr})"
            if just_filter
            else f"?{variable_name} FILTER({filter_expr})"
        )
    else:
        return ""


def render_to_man_owl(graph):
    """
    Convert an rdflib Graph into Manchester OWL syntax.

    Iterates through all properties and classes in the provided graph and
    formats them into a human-readable Manchester OWL string for debugging
    or verification purposes.

    Args:
        graph: The rdflib Graph instance to render.

    Returns:
        A string representation of the graph in Manchester OWL syntax.
    """
    io = StringIO()
    for p in all_properties(graph):
        print(p.identifier, next(p.label, None), file=io)
        print(repr(p), file=io)
    for c in all_classes(graph):
        print(c.__repr__(True), file=io)
    return io.getvalue()


@click.command()
@click.option(
    "--action",
    "-a",
    type=Choice(
        [
            "render_class",
            "find_properties",
            "load_owl",
            "destroy_sqlite",
            "find_classes",
            "list_ontologies",
            "lint_ontology",
        ]
    ),
    required=True,
    help="Action to perform",
    default="render_class",
)
@click.option(
    "--by-id",
    is_flag=True,
    default=False,
    help="Find ontology class by ID (otherwise by rdfs:label)",
)
@click.option("--class-reference", help="The ID (or label) of the Uberon class")
@click.option(
    "--class-search", help="The string to use for searching for a class to use"
)
@click.option("--regex-search/--no-regex-search", default=False)
@click.option("--verbose/--no-verbose", default=False)
@click.option(
    "--exact-class-labels/--no-exact-class-labels",
    default=False,
    help="Render OWL class labels as is (don't convert to lower case by default)",
)
@click.option(
    "--configuration-file",
    type=str,
    help="Path to configuration YAML file for NL rendering of ontology terms. "
    "When omitted, ontology-embedded OWL_DSL_* annotations are used.",
)
@click.option(
    "--sqlite-file",
    type=str,
    help="Location of SQLite file used for persistence (only needed for destroy_sqlite action)",
    required=False,
)
@click.option(
    "--prefix",
    type=str,
    help="Filter properties by URI prefix (only for 'find_properties' action)",
    default="",
)
@click.option(
    "--prop-reference-label",
    type=str,
    help="Filter properties by rdfs:label using REGEX (only for 'find_properties' action)",
    default="",
)
@click.option(
    "--show-property-definition-usage",
    is_flag=True,
    default=False,
    help="Show class definition examples for listed properties (only for 'find_properties' action)",
)
@click.option(
    "--limit",
    type=int,
    default=1,
    help="Limit number of results (only for 'find_properties' action with --show-property-definition-usage)",
)
@click.option(
    "--collect-definition-info/--no-collect-definition-info",
    default=True,
    help="Collect definition info during rendering (default: on)",
)
@click.option(
    "--full-definition/--no-full-definition",
    default=True,
    help="Include logical CNL in the class summary (default: on)",
)
@click.option(
    "--no-textual-definition",
    is_flag=True,
    default=False,
    help="Suppress the textual definition, show only logical CNL",
)
@click.option("--ontology-uri", type=str, required=True, help="The URI of the ontology")
@click.option(
    "--ontology-namespace-baseuri",
    type=str,
    required=True,
    help="The base URI of the ontology namespace",
)
@click.argument("owl_url_or_path", required=False)
def main(
    action,
    by_id,
    class_reference,
    class_search,
    regex_search,
    verbose,
    exact_class_labels,
    configuration_file,
    sqlite_file,
    prefix,
    prop_reference_label,
    show_property_definition_usage,
    limit,
    collect_definition_info,
    full_definition,
    no_textual_definition,
    ontology_uri,
    ontology_namespace_baseuri,
    owl_url_or_path,
):
    if action == "find_classes":
        onto = pyhornedowl.open_ontology(owl_url_or_path)
        print("Loaded ontology")
        for class_iri in sorted(onto.get_classes()):
            labels = onto.get_annotations(class_iri, RDFS_LABEL)
            for label in labels:
                if regex_search:
                    if re.search(class_search, label):
                        print(f"{class_iri} '{label}'")
                else:
                    if class_search.lower() in label.lower():
                        print(f"{class_iri} '{label}'")

    elif action == "render_class":
        onto = pyhornedowl.open_ontology(owl_url_or_path)
        print("Loaded ontology")
        handler = CNLRenderer(
            onto,
            ontology_namespace_baseuri,
            verbose=verbose,
            lowercase_labels=not exact_class_labels,
            collect_definition_info=collect_definition_info,
        )
        definition_properties, _ = resolve_definition_properties(
            handler, onto, owl_url_or_path, configuration_file, verbose
        )
        if by_id:
            class_iri = ontology_namespace_baseuri + class_reference
        else:
            class_iri = None
            for iri in onto.get_classes():
                labels = onto.get_annotations(iri, RDFS_LABEL)
                if labels and labels[0] == class_reference:
                    class_iri = iri
                    break
        if class_iri:
            definition = None
            for def_prop in definition_properties:
                defs = onto.get_annotations(class_iri, def_prop)
                if defs:
                    definition = defs[0]
                    break
            if no_textual_definition:
                definition = None
            summarize_owl_class(
                definition, handler, class_iri, full_definition=full_definition
            )

    elif action == "find_properties":
        onto = pyhornedowl.open_ontology(owl_url_or_path)
        print("Loaded ontology")
        handler = CNLRenderer(
            onto,
            ontology_namespace_baseuri,
            verbose=verbose,
            lowercase_labels=not exact_class_labels,
        )
        definition_properties, _ = resolve_definition_properties(
            handler, onto, owl_url_or_path, configuration_file, verbose
        )

        all_prop_iris: set[str] = set()
        all_prop_iris.update(onto.get_object_properties())
        all_prop_iris.update(onto.get_data_properties())
        all_prop_iris.update(onto.get_annotation_properties())

        if prop_reference_label:
            regex_pattern = re.compile(prop_reference_label)
            filtered_properties = [
                p
                for p in sorted(all_prop_iris)
                if any(
                    regex_pattern.search(l) for l in onto.get_annotations(p, RDFS_LABEL)
                )
            ]
        else:
            filtered_properties = [
                p for p in sorted(all_prop_iris) if not prefix or p.startswith(prefix)
            ]

        for prop_iri in filtered_properties:
            labels = onto.get_annotations(prop_iri, RDFS_LABEL)
            prop_label = labels[0] if labels else None
            definitions = []
            for def_prop in definition_properties:
                defs = onto.get_annotations(prop_iri, def_prop)
                if defs:
                    definitions.extend(defs)
            definition_str = definitions[0] if definitions else None
            print(
                "- ",
                prop_iri,
                f"'{prop_label}'" if prop_label else "(no label)",
                f'"{definition_str}"' if definition_str else "(no definition)",
            )
            if show_property_definition_usage:
                seen: set[str] = set()
                for ac in onto.get_axioms():
                    match ac.component:
                        case SubClassOf(sub, sup):
                            sup_str = str(sup)
                            if prop_iri in sup_str:
                                class_iri = (
                                    str(sub.first)
                                    if hasattr(sub, "first")
                                    else str(sub)
                                )
                                if class_iri not in seen:
                                    seen.add(class_iri)
                                    owl_class_label = handler._entity_label(class_iri)
                                    if owl_class_label:
                                        try:
                                            owl_class_definition = (
                                                handler.handle_owl_class(class_iri)
                                            )
                                        except Exception as e:
                                            print(f"Error: {e}")
                                            owl_class_definition = None
                                        print(f"\n{class_iri} '{owl_class_label}':")
                                        print(
                                            f"{owl_class_definition if owl_class_definition else ''}"
                                        )
            print("------" * 5)
    elif action == "load_owl":
        if not owl_url_or_path:
            print("No ontology URL or path provided. Exiting.")
            return
        print(f"Loading ontology from {owl_url_or_path}.")
        onto = pyhornedowl.open_ontology(owl_url_or_path)
        onto.prefix_mapping.add_prefix("", ontology_uri)
        print(f"Loaded {owl_url_or_path} as {ontology_uri}")
    elif action == "destroy_sqlite":
        if not sqlite_file:
            print("Error: --sqlite-file is required for destroy_sqlite action")
            return
        os.remove(sqlite_file)
        print(f"Deleted {sqlite_file}")
    elif action == "list_ontologies":
        onto = pyhornedowl.open_ontology(owl_url_or_path)
        num_classes = len(onto.get_classes())
        num_obj_props = len(onto.get_object_properties())
        num_data_props = len(onto.get_data_properties())
        prefixes = {}
        for p, ns in onto.prefix_mapping.get_prefixes().items():
            prefixes[p] = ns
        print(f"Ontology: {owl_url_or_path}")
        print(f"  Classes: {num_classes}")
        print(f"  Object properties: {num_obj_props}")
        print(f"  Data properties: {num_data_props}")
        for p, ns in sorted(prefixes.items()):
            print(f"  Prefix '{p}': {ns}")
    elif action == "lint_ontology":
        OWL_DSL = Namespace("http://purl.org/ontology-dsl#")
        onto = pyhornedowl.open_ontology(owl_url_or_path)
        handler = CNLRenderer(
            onto,
            ontology_namespace_baseuri,
            verbose=verbose,
            lowercase_labels=not exact_class_labels,
        )
        definition_properties, annotation_graph = resolve_definition_properties(
            handler, onto, owl_url_or_path, configuration_file, verbose
        )

        graph = annotation_graph if annotation_graph is not None else Graph()

        annotation_info = {}
        all_class_iris = set(onto.get_classes())
        all_obj_prop_iris = set(onto.get_object_properties())
        all_data_prop_iris = set(onto.get_data_properties())
        all_prop_iris = (
            all_obj_prop_iris
            | all_data_prop_iris
            | set(onto.get_annotation_properties())
        )

        def to_space_separated(text):
            text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
            text = text.replace("_", " ").replace("-", " ")
            return " ".join(text.split())

        def render_term(iri, label):
            is_property = iri in all_prop_iris
            is_class = iri in all_class_iris
            if not (is_property or is_class):
                return None
            cnl_annotations = {
                OWL_DSL.OWL_DSL_000001,
                OWL_DSL.OWL_DSL_000002,
                OWL_DSL.OWL_DSL_000003,
            }.intersection(graph.predicates(iri, unique=True))
            annotations = (
                "Has CNL annotations" if cnl_annotations else "(no CNL annotations)"
            )
            if label is None and (
                (is_property and not cnl_annotations) or not is_property
            ):
                if iri.startswith(handler.ontology_namespace):
                    local_name = iri.split(handler.ontology_namespace)[-1]
                    template = ""
                    if is_property:
                        template = input(
                            f"Enter infix, singular phrase template for :{local_name} : "
                        ).strip()
                        annotation_info.setdefault("templates", {}).setdefault(
                            "property" if is_property else "class", {}
                        )[iri] = template
                        template = f"template: `{template}`"
                    if label is None:
                        l_name = re.split(r"#|/|\\", local_name)[-1]
                        extra = to_space_separated(l_name).lower()
                        extra_hint = f"('{extra}')"
                        label = input(
                            f"Enter a label for :{local_name} {extra_hint}: "
                        ).strip()
                        label = extra if not label else label
                        annotation_info.setdefault("labels", {}).setdefault(
                            "property" if is_property else "class", {}
                        )[iri] = label
                    return (
                        f"_:{local_name}\nlabel: {label}\n{annotations if is_property else ''}",
                        template,
                    )
                else:
                    template = ""
                    if label is None:
                        l_name = re.split(r"#|/|\\", iri)[-1]
                        extra = to_space_separated(l_name).lower()
                        extra_hint = f"('{extra}')"
                        label = input(
                            f"Enter a label for <{iri}> {extra_hint}: "
                        ).strip()
                        label = extra if not label else label
                        annotation_info.setdefault("labels", {}).setdefault(
                            "property" if is_property else "class", {}
                        )[iri] = label
                    return (
                        f"<{iri}>\nlabel: {label}\n{annotations if is_property else ''}",
                        template,
                    )

        print("# Classes")
        for class_iri in sorted(all_class_iris):
            labels = onto.get_annotations(class_iri, RDFS_LABEL)
            label = labels[0] if labels else None
            response = render_term(class_iri, label)
            if response:
                print("\n".join(response), "\n")
        print("# Properties")
        for prop_iri in sorted(all_prop_iris):
            labels = onto.get_annotations(prop_iri, RDFS_LABEL)
            label = labels[0] if labels else None
            response = render_term(prop_iri, label)
            if response:
                print("\n".join(response), "\n")

        owl_graph = Graph()
        if annotation_graph is not None:
            owl_graph += annotation_graph

        singular_annotation = OWL_DSL.OWL_DSL_000001

        before_graph_content = owl_graph.serialize(format="xml")

        with GraphContext(owl_graph, {"owl_dsl": OWL_DSL}):
            template_dict = annotation_info.get("templates", {})
            for iri, template in template_dict.get("property", {}).items():
                prop = InfixProperty(URIRef(iri))
                prop.set_annotation(singular_annotation, Literal(template))
                for label in annotation_info.get("labels", {}).get(iri, []):
                    prop.label = label
            for iri, template in template_dict.get("class", {}).items():
                owl_class = InfixClass(URIRef(iri))
                owl_class.set_annotation(singular_annotation, Literal(template))
                for label in annotation_info.get("labels", {}).get(iri, []):
                    owl_class.label = label
            label_dict = annotation_info.get("labels", {})
            for iri, label in label_dict.get("property", {}).items():
                InfixProperty(URIRef(iri), label=label)
            for iri, label in label_dict.get("class", {}).items():
                InfixClass(URIRef(iri), label=label)

        after_graph_content = owl_graph.serialize(format="xml")

        graph_content_diff = difflib.unified_diff(
            before_graph_content.splitlines(keepends=True),
            after_graph_content.splitlines(keepends=True),
            fromfile="ontology.mc",
            tofile="annotated_ontology.mc",
            lineterm="",
        )
        print("##### Annotation graph diff: #####")
        print("".join(graph_content_diff))
        print("##################################")


def summarize_owl_class(
    definition: str | None,
    handler: CNLRenderer,
    class_iri: str,
    full_definition: bool = True,
):
    """
    Print a comprehensive summary of an OWL class.

    Args:
        definition: The existing textual definition from the ontology.
        handler: The CNLRenderer instance used for logical rendering.
        class_iri: The full IRI string of the class to summarize.
        full_definition: Whether to include the logical CNL rendering.
    """
    label = handler._entity_label(class_iri) or _get_local_name(class_iri)
    print(f"# {class_iri} ({label}) # ")
    lines: list[str] = []
    if definition:
        lines.append(definition)
    if full_definition:
        logical = handler.handle_owl_class(class_iri).strip()
        if logical:
            _, _, rest = logical.partition(" is defined as ")
            if not rest:
                rest = logical
            rest = rest.strip()
            if rest:
                rest = rest[0].upper() + rest[1:] if rest[0].islower() else rest
                lines.append(rest)
    print("\n".join(lines))


def setup_configuration(
    handler: CNLRenderer, configuration_file: str, verbose: bool = False
) -> list[str]:
    """Initialize a CNLRenderer using settings from a YAML configuration file.

    Backwards-compatible wrapper around
    :func:`owl_dsl.annotations.setup_configuration_from_yaml`. Prefer
    :func:`owl_dsl.annotations.resolve_definition_properties` for new code,
    which additionally honours ontology-embedded ``OWL_DSL_*`` annotations.

    Args:
        handler: The CNLRenderer instance to configure.
        configuration_file: Path to the YAML configuration file.
        verbose: If True, prints warnings for missing labels.

    Returns:
        A list of IRIs representing the definition properties.
    """
    return setup_configuration_from_yaml(handler, configuration_file, verbose)


if __name__ == "__main__":
    main()

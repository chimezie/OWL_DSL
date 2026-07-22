#!/usr/bin/env python
import difflib
from io import StringIO

import click
import os
import re
import yaml
from subprocess import CompletedProcess
from click import Choice
from yaml import CLoader as Loader
from typing import List, Iterable
import tracemalloc

from rdflib import URIRef, Literal, Namespace, Graph

from owlready2 import (
    ThingClass,
    default_world,
    get_ontology,
    ObjectPropertyClass,
    DataPropertyClass,
)

from fuxi.Syntax.InfixOWL import (
    GraphContext,
    Property,
    Class,
    all_properties,
    all_classes,
)
from owl_dsl import base_uri, get_owl_class_label
from owl_dsl.annotations import (
    apply_annotations_to_handler,
    load_annotations_graph,
    configure_cnl_from_annotations,
)
from owl_dsl.renderer import CNLRenderer

DC_TITLE_URI = "http://purl.org/dc/elements/1.1/title"
DC_DESCRIPTION_URI = "http://purl.org/dc/elements/1.1/description"

CLASS_BY_CONTAINS_LABEL_SPARQL = """
#Fetch owl classes by string matching against their labels
SELECT DISTINCT ?owl_class ?label {{
    ?owl_class a owl:Class; rdfs:label ?label.
    FILTER(contains(lcase(?label), lcase("{pattern}"))) 
}}"""

CLASS_BY_REGEX_LABEL_SPARQL = """
#Fetch owl classes by REGEX matching against their labels
SELECT DISTINCT ?owl_class ?label {{
    ?owl_class a owl:Class; rdfs:label ?label.
    FILTER(regex(?label, "{pattern}")) 
}}"""

CLASSES_SPARQL = """
#Fetch owl classes and their labels
SELECT DISTINCT ?owl_class ?label {{
    ?owl_class a owl:Class .
    OPTIONAL {{ ?owl_class rdfs:label ?label }}
}} """

PROPERTIES_SPARQL = """
#Fetch owl classes and their labels
SELECT DISTINCT ?owl_property ?label {{
    ?owl_property a ?property_type .
    FILTER(?property_type = <http://www.w3.org/2002/07/owl#SymmetricProperty>           ||
           ?property_type = <http://www.w3.org/2002/07/owl#FunctionalProperty>          ||
           ?property_type = <http://www.w3.org/2002/07/owl#InverseFunctionalProperty>   ||
           ?property_type = <http://www.w3.org/2002/07/owl#TransitiveProperty>          ||
           ?property_type = <http://www.w3.org/2002/07/owl#DatatypeProperty>            ||
           ?property_type = <http://www.w3.org/2002/07/owl#ObjectProperty>              ||
           ?property_type = <http://www.w3.org/2002/07/owl#AnnotationProperty>)
    OPTIONAL {{ ?owl_property rdfs:label ?label }} 
}}"""

DEFINITION_FOR_PROPERTY_SPARQL = """
#Fetch any ontology-indicated (human-readable) definitions for the property
SELECT DISTINCT ?prop ?definition {{
    [] owl:onProperty ?prop {prop_filter}  
    OPTIONAL {{ ?prop ?defprop ?definition {def_prop_expression} }} 
}}"""

IRI_AND_LABEL_FOR_EXAMPLE_SPARQL = """
#Fetch any classes whose definition in the ontology include a GCI involving a restriction on the property
SELECT DISTINCT ?subj ?label {{ 
    ?subj rdfs:label ?label; 
          rdfs:subClassOf [ owl:onProperty ?prop ]
    {filtered_prop}
}} ORDER BY RAND() LIMIT {limit} 
"""

CLASS_AND_THEIR_DEFINITION_SPARQL = """
# An OWL class with an rdfs:label and any definitions (?defprop) it may have as specified in the ontology.
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
SELECT ?owl_class ?definition {{ 
    {owl_class_expression} 
    OPTIONAL {{ ?owl_class ?defprop ?definition {def_prop_expression} }} }}"""


def run_subprocess(command: List[str], verbose=False) -> CompletedProcess:
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
    Generate SPARQL expression for matching object based on variable name and resources.

    :param variable_name: Name of the variable to match.
    :param resources: List of resources to match against.
    :param just_filter: If True, return only the FILTER expression (including singletons), otherwise return the full
    SPARQL expression.
    :return: SPARQL expression for matching object.
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
    help="Path to configuration YAML file for NL rendering of ontology terms",
)
@click.option(
    "--sqlite-file",
    type=str,
    help="Location of SQLite file used for persistence",
    required=True,
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
    ontology_uri,
    ontology_namespace_baseuri,
    owl_url_or_path,
):
    tracemalloc_enabled = os.environ.get("OWL_DSL_TRACEMALLOC", "0") == "1"
    if tracemalloc_enabled:
        tracemalloc.start()
        start_snapshot = tracemalloc.take_snapshot()
    try:
        default_world.set_backend(filename=sqlite_file)
        if action == "find_classes":
            print("Loaded ontology")
            for owl_class, label in default_world.sparql_query(
                (
                    CLASS_BY_REGEX_LABEL_SPARQL
                    if regex_search
                    else CLASS_BY_CONTAINS_LABEL_SPARQL
                ).format(pattern=class_search)
            ):
                print(f"{owl_class.iri} '{label}'")

        elif action == "render_class":
            if not configuration_file:
                onto = default_world.get_ontology(ontology_uri)
                print("Loaded ontology")
                handler = CNLRenderer(
                    onto,
                    ontology_namespace_baseuri,
                    verbose=verbose,
                    lowercase_labels=not exact_class_labels,
                )
                # from pprint import pprint; pprint(default_world.ontologies)
                configure_cnl_from_annotations(handler, default_world.as_rdflib_graph())
                definition_properties = handler.expert_definition_properties
                # raise ValueError(
                #     "Configuration file is required for render_class action"
                # )
            else:
                onto = default_world.get_ontology(ontology_uri)
                print("Loaded ontology")
                handler = CNLRenderer(
                    onto,
                    ontology_namespace_baseuri,
                    verbose=verbose,
                    lowercase_labels=not exact_class_labels,
                )
                definition_properties = setup_configuration(
                    handler, configuration_file, verbose
                )
            if by_id:
                class_iri = ontology_namespace_baseuri + class_reference
                sparql_expression = (
                    f"?owl_class rdfs:label ?label "
                    f"FILTER(?owl_class = <{class_iri}>)"
                )
            else:
                sparql_expression = f"?owl_class rdfs:label '{class_reference}'"
            prop_conjunction = (
                " || ".join([f"?defprop = <{p}>" for p in definition_properties])
                if len(definition_properties) > 1
                else (
                    f"?defprop = <{definition_properties[0]}>"
                    if definition_properties
                    else ""
                )
            )
            def_prop_expression = (
                f"FILTER({prop_conjunction})" if prop_conjunction else ""
            )
            query = CLASS_AND_THEIR_DEFINITION_SPARQL.format(
                owl_class_expression=sparql_expression,
                def_prop_expression=def_prop_expression,
            )
            for owl_class, definition in default_world.sparql_query(query):
                summarize_owl_class(definition, handler, owl_class)

        elif action == "find_properties":
            if not configuration_file:
                raise ValueError(
                    "Configuration file is required for find_properties action"
                )
            onto = default_world.get_ontology(ontology_uri)
            print("Loaded ontology")
            handler = CNLRenderer(
                onto,
                ontology_namespace_baseuri,
                verbose=verbose,
                lowercase_labels=not exact_class_labels,
            )
            definition_properties = setup_configuration(
                handler, configuration_file, verbose
            )
            annotation_graph = load_annotations_graph(onto, owl_url_or_path)
            if annotation_graph is not None:
                (
                    annotation_definition_properties,
                    annotation_definitions_present,
                ) = apply_annotations_to_handler(handler, annotation_graph)
                if annotation_definitions_present or not definition_properties:
                    definition_properties = annotation_definition_properties

            if prop_reference_label:
                # Filter properties by label using regex
                regex_pattern = re.compile(prop_reference_label)
                filtered_properties = []
                for p in sorted(onto.properties()):
                    prop_base_uri, suffix = base_uri(p.iri)
                    prop_labels = [
                        l
                        for l in onto.get_namespace(prop_base_uri)[suffix].label
                        if isinstance(l, str)
                    ]
                    if any(regex_pattern.search(label) for label in prop_labels):
                        filtered_properties.append(p.iri)
            else:
                filtered_properties = [
                    p.iri
                    for p in sorted(onto.properties())
                    if not prefix or p.iri.startswith(prefix)
                ]

            def_prop_expression = match_object_sparql_expression(
                "defprop", definition_properties, just_filter=True
            )
            filter_only_prop_expr = match_object_sparql_expression(
                "prop", filtered_properties, just_filter=True
            )
            query = DEFINITION_FOR_PROPERTY_SPARQL.format(
                prop_filter=filter_only_prop_expr,
                def_prop_expression=def_prop_expression,
            )
            for prop, definition in default_world.sparql_query(query):
                prop_base_uri, suffix = base_uri(prop.iri)
                prop_label = [
                    l
                    for l in onto.get_namespace(prop_base_uri)[suffix].label
                    if isinstance(l, str)
                ]
                prop_label = prop_label[0] if prop_label else None
                print(
                    "- ",
                    prop.iri,
                    f"'{prop_label}'" if prop_label else "(no label)",
                    f'"{definition}"' if definition else "(no definition)",
                )
                domain = [
                    get_owl_class_label(d)
                    for d in prop.domain
                    if isinstance(d, ThingClass) and get_owl_class_label(d)
                ]
                range = [
                    get_owl_class_label(r)
                    for r in prop.range
                    if isinstance(r, ThingClass) and get_owl_class_label(r)
                ]
                if domain:
                    print(f"\t- Domain: {', '.join(domain)}")
                if range:
                    print(f"\t- Range: {', '.join(range)}")
                if show_property_definition_usage:
                    query = IRI_AND_LABEL_FOR_EXAMPLE_SPARQL.format(
                        filtered_prop=match_object_sparql_expression(
                            "prop", [prop.iri], just_filter=True
                        ),
                        limit=limit,
                    )
                    for (
                        reference_owl_class,
                        owl_class_label,
                    ) in default_world.sparql_query(query):
                        owl_class_base_uri, suffix = base_uri(reference_owl_class.iri)
                        owl_class_label = [
                            l
                            for l in onto.get_namespace(owl_class_base_uri)[
                                suffix
                            ].label
                            if isinstance(l, str)
                        ]
                        owl_class_label = (
                            owl_class_label[0] if owl_class_label else None
                        )
                        try:
                            owl_class_definition = (
                                handler.handle_owl_class(reference_owl_class)
                                if owl_class_label
                                else ""
                            )
                        except Exception as e:
                            print(f"Error: {e}")
                            owl_class_definition = None
                        print(f"\n{reference_owl_class.iri} '{owl_class_label}':")
                        print(f"{owl_class_definition if owl_class_definition else ''}")
                print("------" * 5)
        elif action == "load_owl":
            if not owl_url_or_path:
                print("No ontology URL or path provided. Exiting.")
                return
            print(f"Loading ontology from {owl_url_or_path}, a IRI or local path.")
            ontology = get_ontology(owl_url_or_path)
            ontology.load()
            ontology.set_base_iri(ontology_uri, rename_entities=False)
            default_world.save()
            print(f"Saved {owl_url_or_path} to {ontology_uri}")
        elif action == "destroy_sqlite":
            os.remove(sqlite_file)
            print(f"Deleted {sqlite_file}")
        elif action == "list_ontologies":
            for uri, ontology in default_world.ontologies.items():
                print(
                    f"{uri}: ({ontology.name} with {len(list(ontology.get_triples())):,} triples)"
                )
        elif action == "lint_ontology":
            OWL_DSL = Namespace(
                "https://github.com/chimezie/OWL_DSL/tree/main/ontology_configurations/"
            )
            onto = default_world.get_ontology(ontology_uri)
            handler = CNLRenderer(
                onto,
                ontology_namespace_baseuri,
                verbose=verbose,
                lowercase_labels=not exact_class_labels,
            )
            annotation_graph = load_annotations_graph(onto, owl_url_or_path)
            definition_properties = []
            if annotation_graph is not None:
                (
                    annotation_definition_properties,
                    annotation_definitions_present,
                ) = apply_annotations_to_handler(handler, annotation_graph)
                if annotation_definitions_present:
                    definition_properties = annotation_definition_properties
            else:
                definition_properties = setup_configuration(
                    handler, configuration_file, verbose
                )

            graph = default_world.as_rdflib_graph()

            annotation_info = {}

            import re

            def to_space_separated(text):
                # 1. Insert space before uppercase letters (for camelCase)
                text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
                # 2. Replace underscores and dashes with spaces
                text = text.replace("_", " ").replace("-", " ")
                # 3. Remove extra internal spaces and trim
                return " ".join(text.split())

            def render_term(term, label):
                # label = label if label is not None else "(no label)"
                if isinstance(
                    term, (DataPropertyClass, ObjectPropertyClass, ThingClass)
                ):
                    is_property = isinstance(
                        term, (DataPropertyClass, ObjectPropertyClass)
                    )
                    cnl_annotations = {
                        OWL_DSL.OWL_DSL_000001,
                        OWL_DSL.OWL_DSL_000002,
                        OWL_DSL.OWL_DSL_000003,
                    }.intersection(graph.predicates(term.iri, unique=True))
                    annotations = (
                        "Has CNL annotations"
                        if cnl_annotations
                        else "(no CNL annotations)"
                    )
                    if label is None and (
                        (is_property and not cnl_annotations) or not is_property
                    ):
                        if term.iri.startswith(handler.ontology_namespace):
                            local_name = term.iri.split(handler.ontology_namespace)[-1]
                            template = ""
                            if is_property:
                                template = input(
                                    f"Enter infix, singular phrase template for :{local_name} : "
                                ).strip()
                                annotation_info.setdefault("templates", {}).setdefault(
                                    "property" if is_property else "class", {}
                                )[term.iri] = template
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
                                )[term.iri] = label
                            return (
                                f"_:{local_name}\nlabel: {label}\n{annotations if is_property else ''}",
                                template,
                            )
                        else:
                            template = ""
                            # if is_property:
                            #     template = input(f"Enter an infix, singular phrase template for <{term.iri}> : ").strip()
                            #     annotation_info.setdefault('templates', {}).setdefault(
                            #         'property' if is_property else 'class', {})[term.iri] = template
                            #     template = f"template: `{template}`"
                            if label is None:
                                l_name = re.split(r"#|/|\\", term.iri)[-1]
                                extra = to_space_separated(l_name).lower()
                                extra_hint = f"('{extra}')"
                                label = input(
                                    f"Enter a label for <{term.iri}> {extra_hint}: "
                                ).strip()
                                label = extra if not label else label
                                annotation_info.setdefault("labels", {}).setdefault(
                                    "property" if is_property else "class", {}
                                )[term.iri] = label
                            return (
                                f"<{term.iri}>\nlabel: {label}\n{annotations if is_property else ''}",
                                template,
                            )

            print("# Classes")
            for owl_class, label in default_world.sparql_query(CLASSES_SPARQL):
                response = render_term(owl_class, label)
                if response:
                    print("\n".join(response), "\n")
            print("# Properties")
            for owl_property, label in default_world.sparql_query(PROPERTIES_SPARQL):
                response = render_term(owl_property, label)
                if response:
                    print("\n".join(response), "\n")

            owl_graph = Graph()
            owl_graph += annotation_graph

            singular_annotation = OWL_DSL.OWL_DSL_000001

            # before_graph_content = render_to_man_owl(owl_graph)
            before_graph_content = owl_graph.serialize(format="xml")

            from pprint import pprint

            with GraphContext(owl_graph, {"owl_dsl": OWL_DSL}):
                template_dict = annotation_info["templates"]
                for iri, template in template_dict.get("property", {}).items():
                    prop = Property(URIRef(iri))
                    prop.set_annotation(singular_annotation, Literal(template))
                    for label in annotation_info.get("labels", {}).get(iri, []):
                        prop.label = label
                for iri, template in template_dict.get("class", {}).items():
                    owl_class = Class(URIRef(iri))
                    owl_class.set_annotation(singular_annotation, Literal(template))
                    for label in annotation_info.get("labels", {}).get(iri, []):
                        owl_class.label = label
                label_dict = annotation_info["labels"]
                for iri, label in label_dict.get("property", {}).items():
                    Property(URIRef(iri), label=label)
                for iri, label in label_dict.get("class", {}).items():
                    Class(URIRef(iri), label=label)

            # after_graph_content = render_to_man_owl(owl_graph)
            after_graph_content = owl_graph.serialize(format="xml")

            import difflib

            lines1 = before_graph_content.splitlines(keepends=True)
            lines2 = after_graph_content.splitlines(keepends=True)

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
    finally:
        if tracemalloc_enabled:
            end_snapshot = tracemalloc.take_snapshot()
            stats = end_snapshot.compare_to(start_snapshot, "lineno")
            print("Top 20 allocators:")
            for stat in stats[:20]:
                print(stat)
            current, peak = tracemalloc.get_traced_memory()
            print(f"Current memory: {current / (1024 * 1024):.2f} MB")
            print(f"Peak memory: {peak / (1024 * 1024):.2f} MB")


def summarize_owl_class(
    definition: str | None,
    handler: CNLRenderer,
    owl_class: ThingClass,
    full_definition: bool = True,
):
    print(f"# {owl_class.iri} ({owl_class.label[0]}) # ")
    if definition:
        print(f"## Textual definition ##")
        print(definition, "\n")
    if full_definition:
        print(f"## Logical definition ##")
        print(handler.handle_owl_class(owl_class))


def setup_configuration(
    handler: CNLRenderer, configuration_file: str, verbose: bool = False
) -> list[str]:
    with open(configuration_file, "r") as file:
        config = yaml.load(file, Loader=Loader)
        reflexive_roles = config["reflexive_roles"] if config["reflexive_roles"] else []
        handler.class_inference_to_ignore = config.get("class_inference_to_ignore", [])
        for role in reflexive_roles:
            for property_uri, phrase in role.items():
                handler.reflexive_property_customizations[URIRef(property_uri)] = (
                    phrase[0]
                )

        definition_properties = (
            config["tooling"]["expert_definition_properties"]
            if config["tooling"]
            else []
        )
        for prop in config["standard_role_restriction_is_phrasing"]:
            prop_obj = handler.ontology.search(iri=prop)
            if prop_obj and prop_obj[0].label:
                props = [label for label in prop_obj[0].label if isinstance(label, str)]
                prop_label = props[0] if props else "(no label)"
                handler.relevant_role_restriction_cnl_phrasing[URIRef(prop)] = (
                    f"is {prop_label} " + "{}",
                ) * 2 + ("What is {}" + f" {prop_label}?",)
            elif verbose:
                print(f"Warning: Could not find label for property {prop}")
        for prop_uri, info in config["role_restriction_phrasing"].items():
            handler.relevant_role_restriction_cnl_phrasing[URIRef(prop_uri)] = tuple(
                info
            )
        for prop_uri in config.get("role_restriction_wo_articles", []):
            handler.role_restriction_wo_articles.add(URIRef(prop_uri))
    return definition_properties


if __name__ == "__main__":
    main()

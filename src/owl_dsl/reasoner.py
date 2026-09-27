"""Ontology reasoning and logical entailment explanation.

This module provides tools for explaining logical inferences within an OWL ontology.
It leverages the ELK reasoner (via ROBOT explain) to generate justifications for
General Concept Inclusions (GCIs), which are then verbalized into human-readable
natural language. It bridges the gap between owlready2's class representations
and owlapy's reasoning capabilities.
"""

import os
import warnings
from typing import Tuple

import click
import re

import pyhornedowl
from pyhornedowl.model import (
    Class,
    ObjectIntersectionOf,
    ObjectUnionOf,
    ObjectSomeValuesFrom,
    ObjectAllValuesFrom,
    ObjectProperty,
)
from rdflib import OWL

from owl_dsl.cli import (
    run_subprocess,
    summarize_owl_class,
)
from owl_dsl.annotations import resolve_definition_properties
from owl_dsl.renderer import CNLRenderer
from owl_dsl import base_uri, prefix_with_indefinite_article
from owlready2 import (
    ThingClass,
    And,
    Restriction,
    base,
    default_world,
    get_ontology,
    EntityClass,
    Or,
)

from owlapy.class_expression import (
    OWLObjectIntersectionOf,
    OWLObjectSomeValuesFrom,
    OWLObjectAllValuesFrom,
    OWLObjectUnionOf,
)
from owlapy import manchester_to_owl_expression
from owlapy.owl_reasoner import SyncReasoner
from owlapy.owl_property import OWLObjectProperty
from owlapy.owl_ontology import Ontology, OWLClass
from owlapy.owl_data_ranges import OWLPropertyRange
from owlapy.iri import IRI

CLASS_AND_THEIR_DEFINITION_SPARQL = """
# An OWL class with an rdfs:label and any definitions (?defprop) it may have as specified in the ontology.
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
SELECT ?owl_class ?definition {{ 
    {owl_class_expression} 
    OPTIONAL {{ ?owl_class ?defprop ?definition {def_prop_expression} }} }}"""

EXPLANATION_FILE = os.environ.get("OWL_DSL_EXPLANATION_FILE", "/tmp/explanation.md")
EXPLANATION_PATTERN = re.compile(
    r"^##.+\n\n(?P<info>.+(?=# Axiom Impact)).+$", re.MULTILINE | re.DOTALL
)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

ENTAILED_GCI_SPARQL = """
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
SELECT DISTINCT ?owl_class ?ancestor {{ [] oboInOwl:is_inferred  'true';
                                           owl:annotatedProperty rdfs:subClassOf ;
                                           owl:annotatedSource   ?owl_class;
                                           owl:annotatedTarget   ?ancestor }}"""

ENTAILED_GCI_BY_IRI_SPARQL = """
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
SELECT DISTINCT ?ancestor {{ [] oboInOwl:is_inferred    'true';
                                owl:annotatedProperty   rdfs:subClassOf ;
                                owl:annotatedSource     <{owl_class}>;
                                owl:annotatedTarget     ?ancestor }}"""

ENTAILED_GCI_BY_LABEL_SPARQL = """
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
SELECT DISTINCT ?ancestor {{ [] oboInOwl:is_inferred    'true';
                                owl:annotatedProperty   rdfs:subClassOf ;
                                owl:annotatedSource     [ rdfs:label '{label}'];
                                owl:annotatedTarget     ?ancestor }}  
"""

STATED_GCI_SUBCLASSES_SPARQL = """SELECT DISTINCT ?subclass {{ 
    {{ ?subclass rdfs:subClassOf <{owl_class}> }}
                    UNION 
    {{ ?subclass owl:intersectionOf [ rdf:first <{owl_class}> ] }}
                    UNION 
    {{ ?subclass rdfs:subClassOf [ owl:intersectionOf [ rdf:first <{owl_class}> ]] }}
}}"""


def remove_indefinite_article(s: str) -> str:
    """
    Remove the leading 'It ' prefix from a string if it exists.

    Used primarily during the verbalization of GCI justifications to ensure
    the resulting sentence flows naturally when concatenated with other phrases.
    """
    if s.startswith("It "):
        return s[3:]
    return s


def get_owlready2_class(onto: Ontology, iri: str) -> EntityClass:
    """
    Retrieve an owlready2 class entity using its IRI.

    Args:
        onto: The owlready2 Ontology object to search.
        iri: The IRI string of the target class.

    Returns:
        The first matching EntityClass found in the ontology.
    """
    return onto.search(iri=iri)[0]


def count_leading_spaces(s: str) -> int:
    """
    Calculate the number of leading whitespace characters in a string.

    Used to preserve the indentation hierarchy of ROBOT explain output
    during natural language verbalization.
    """
    return len(s) - len(s.lstrip())


def process_manchester_owl_local_names(
    line: str, skip_indices: int = 2
) -> Tuple[int, str]:
    """
    Parse a ROBOT justification line and resolve Manchester OWL links to local names.

    This function extracts the indentation level and replaces full URIs in
    Manchester OWL links with their short local names (the part after the last slash).

    Args:
        line: The raw justification line from the reasoner.
        skip_indices: Number of characters to strip from the start of the processed string.

    Returns:
        A tuple containing the indentation depth and the cleaned string with local names.
    """
    num_leading_spaces = count_leading_spaces(line)

    def repl(match: re.Match) -> str:
        return str(base_uri(match.group(2))[-1])

    processed_string = LINK_RE.sub(repl, line)
    if processed_string is None:
        raise SyntaxError(f"Could not parse line: {line}")
    return num_leading_spaces, processed_string.strip()[skip_indices:]


def process_manchester_owl_uris(line: str, skip_indices: int = 2) -> Tuple[int, str]:
    """
    Parse a ROBOT justification line and resolve Manchester OWL links to full URIs.

    Similar to `process_manchester_owl_local_names`, but preserves the full
    URI within angle brackets instead of shortening to the local name.

    Args:
        line: The raw justification line from the reasoner.
        skip_indices: Number of characters to strip from the start of the processed string.

    Returns:
        A tuple containing the indentation depth and the string with URIs in angle brackets.
    """
    num_leading_spaces = count_leading_spaces(line)

    def repl(match: re.Match) -> str:
        return f"<{match.group(2)}>"

    processed_string = LINK_RE.sub(repl, line)
    if processed_string is None:
        raise SyntaxError(f"Could not parse line: {line}")
    return num_leading_spaces, processed_string.strip()[skip_indices:]


def owlapy_to_pyhornedowl(
    owlapy_expr: OWLPropertyRange,
    onto: "pyhornedowl.PyIndexedOntology",
):
    """Translate an owlapy logical expression into a py-horned-owl representation.

    This is the replacement for ``owlapy_to_owlready2`` — it converts owlapy
    expressions to py-horned-owl model objects that the CNLRenderer can consume.

    Args:
        owlapy_expr: The owlapy expression to convert.
        onto: The PyIndexedOntology used for IRI resolution.

    Returns:
        The equivalent py-horned-owl expression.

    Raises:
        ValueError: If a class or property IRI cannot be found.
        NotImplementedError: If the owlapy expression type is not supported.
    """
    if isinstance(owlapy_expr, OWLObjectIntersectionOf):
        return ObjectIntersectionOf(
            [owlapy_to_pyhornedowl(item, onto) for item in owlapy_expr._operands]
        )
    elif isinstance(owlapy_expr, (OWLObjectProperty, OWLClass)):
        iri_str = owlapy_expr.iri.str
        if isinstance(owlapy_expr, OWLObjectProperty):
            return ObjectProperty(onto.iri(iri_str))
        return Class(onto.iri(iri_str))
    elif isinstance(owlapy_expr, OWLObjectSomeValuesFrom):
        return ObjectSomeValuesFrom(
            ope=owlapy_to_pyhornedowl(owlapy_expr.get_property(), onto),
            bce=owlapy_to_pyhornedowl(owlapy_expr.get_filler(), onto),
        )
    elif isinstance(owlapy_expr, OWLObjectUnionOf):
        return ObjectUnionOf(
            [owlapy_to_pyhornedowl(item, onto) for item in owlapy_expr._operands]
        )
    elif isinstance(owlapy_expr, OWLObjectAllValuesFrom):
        return ObjectAllValuesFrom(
            ope=owlapy_to_pyhornedowl(owlapy_expr.get_property(), onto),
            bce=owlapy_to_pyhornedowl(owlapy_expr.get_filler(), onto),
        )
    else:
        raise NotImplementedError(
            f"Unsupported OWL expression type: {type(owlapy_expr)}"
        )


def get_owlready2_ontology(
    ontology_uri: str,
    owl_url_or_path: str,
    sqlite_file: str,
    verbose: bool = False,
    exact_class_labels: bool = False,
) -> tuple[CNLRenderer, Ontology]:
    """
    Retrieves or loads an ontology using the Owlready2 library. If the ontology is not
    already loaded within the default Owlready2 world, it will attempt to load it from
    the specified path or URL. A ``CNLRenderer`` handler is created using a
    py-horned-owl ``PyIndexedOntology`` loaded from the same file.

    :param ontology_uri: The base IRI of the ontology.
    :param owl_url_or_path: The file path or URL to load the ontology from.
    :returns: A tuple containing the ``CNLRenderer`` and the owlready2 ``Ontology``.
    """
    if ontology_uri not in default_world.ontologies:
        found = False
        for stored_uri in default_world.ontologies:
            if stored_uri.startswith(ontology_uri) or ontology_uri.startswith(
                stored_uri
            ):
                ontology = default_world.ontologies[stored_uri]
                found = True
                break
        if not found:
            if owl_url_or_path is None:
                raise ValueError(
                    f"Ontology '{ontology_uri}' not found in SQLite and no owl_url_or_path provided"
                )
            print(
                f"Forcibly loading ontology from {owl_url_or_path} into {ontology_uri} (using {sqlite_file})"
            )
            ontology = get_ontology(owl_url_or_path)
            ontology.load()
            default_world.ontologies[ontology_uri] = ontology
            ontology.set_base_iri(ontology_uri, rename_entities=False)
            default_world.save()
    else:
        ontology = default_world.ontologies[ontology_uri]
    pho_onto = pyhornedowl.open_ontology(owl_url_or_path)
    pho_onto.prefix_mapping.add_prefix("", ontology_uri)
    handler = CNLRenderer(
        pho_onto, ontology_uri, verbose=verbose, lowercase_labels=not exact_class_labels
    )
    return handler, ontology


def verbalize_gci_justifications(
    handler: CNLRenderer,
    owl_class: ThingClass,
    owl_class_rdfs_label: str,
    ontology: Ontology,
    ontology_namespace_baseuri: str,
    owl_url_or_path: str,
    owl_super_class_expression,
    verbose: bool,
    display_label: str | None = None,
):
    """
    Verbalizes justifications for a General Concept Inclusion (GCI) axiom in an ontology.

    This function generates a justification for a specified General Concept Inclusion (GCI)
    axiom and presents it in a concise natural-language format

    :param handler: Instance of `CNLRenderer` used to convert class expressions and
        properties from an ontology into controlled natural language.
    :param owl_class: Instance of `ThingClass` representing the OWL class for which justifications
        are generated.
    :param owl_class_rdfs_label: The class's `rdfs:label`. Used in the Manchester axiom passed to
        `robot explain`, which resolves classes against the OWL file's rdfs:label values.
    :param ontology: Ontology object providing the structure and axioms from which justifications
        are derived.
    :param ontology_namespace_baseuri: String defining the base URI of the ontology namespace, utilized
        for parsing and resolving classes or properties.
    :param owl_url_or_path: String representing the URL or local file path to the OWL ontology file.
    :param owl_super_class_expression: OWL class expression representing the superclass used in the
        GCI axiom.
    :param verbose: Boolean flag indicating if detailed additional information, such as matching explanations
        and verbose commands, should be printed.
    :param display_label: Optional human-friendly label (typically `skos:prefLabel`) used in the
        "How is every '...'" console output. Falls back to `owl_class_rdfs_label` when omitted.

    :return: None. Outputs verbalized justifications or related ontology reasoning to the console.
    """
    axiom_to_prove = f"'{owl_class_rdfs_label}' SubClassOf {owl_super_class_expression}"
    extra_info = f" ({axiom_to_prove})" if verbose else ""
    prefixed_owl_superclass = prefix_with_indefinite_article(owl_super_class_expression)
    printed_label = display_label if display_label else owl_class_rdfs_label
    print(
        f"How is "
        f"every '{printed_label}' ({owl_class.name}) {prefixed_owl_superclass}{extra_info}?\n"
    )
    commands = [
        "robot",
        "explain",
        "--input",
        owl_url_or_path,
        "--reasoner",
        "ELK",
        "--axiom",
        axiom_to_prove,
        "--explanation",
        EXPLANATION_FILE,
    ]
    response = run_subprocess(commands, verbose=verbose)
    if response.returncode == 0:
        with open(EXPLANATION_FILE, "r") as f:
            explanation = f.read()
            match = EXPLANATION_PATTERN.match(explanation)
            if match:
                info = match.group("info")
                for item in info.split("\n"):
                    if item.strip():
                        if verbose:
                            print(item)
                        depth = count_leading_spaces(item)
                        whitespace_prefix = " " * depth
                        if item.strip().startswith("-  Transitive: "):
                            _ = item.strip().split("Transitive:")[-1]
                            prop_label = LINK_RE.match(_.strip()).groups()[0]
                            print(
                                f"{whitespace_prefix}'{prop_label}' is a transitive property."
                            )
                        elif " Domain " in item.strip():
                            info = [*item.strip().split(" Domain ")]
                            prop, _domain_owl_class = info
                            prop, _domain_owl_class = map(
                                str.strip, [prop[2:], _domain_owl_class]
                            )
                            info = [
                                process_manchester_owl_uris(prop, skip_indices=0)[-1][
                                    1:-1
                                ],
                                process_manchester_owl_uris(
                                    _domain_owl_class, skip_indices=0
                                )[-1][1:-1],
                            ]
                            prop, _domain_owl_class = map(
                                lambda i: ontology.search_one(iri=i), info
                            )
                            prop_label = prop.label[0]
                            domain_owl_class_label = _domain_owl_class.label[0]
                            print(
                                f"{whitespace_prefix}If A is related to B via '{prop_label}' "
                                f"then A is a '{domain_owl_class_label}'"
                            )
                        elif " DisjointUnionOf " in item.strip():
                            print(item.strip())
                            raise NotImplementedError(
                                "DisjointUnionOf not yet supported"
                            )
                        elif " Range " in item.strip():
                            info = [*item.strip().split(" Range ")]
                            prop, _range_owl_class = info
                            prop, _range_owl_class = map(
                                str.strip, [prop[2:], _range_owl_class]
                            )
                            info = [
                                process_manchester_owl_uris(prop, skip_indices=0)[-1][
                                    1:-1
                                ],
                                process_manchester_owl_uris(
                                    _range_owl_class, skip_indices=0
                                )[-1][1:-1],
                            ]
                            prop, _range_owl_class = map(
                                lambda i: ontology.search_one(iri=i), info
                            )
                            prop_iri = str(prop.iri)
                            prop_phrase = handler.render_role_restriction(prop_iri)
                            range_owl_class_label = _range_owl_class.label[0]
                            print(
                                f"{whitespace_prefix}If {prop_phrase}, then B is a '{range_owl_class_label}'"
                            )
                        elif " SubPropertyOf: " in item.strip():
                            info = [*item.strip().split(" SubPropertyOf: ")]
                            sub_prop, super_prop = info
                            sub_prop, super_prop = map(
                                str.strip, [sub_prop[2:], super_prop]
                            )
                            sub_prop, super_prop = map(
                                lambda i: process_manchester_owl_uris(
                                    i, skip_indices=0
                                )[-1],
                                [sub_prop, super_prop],
                            )
                            sub_prop, super_prop = map(
                                lambda i: ontology.search_one(iri=i[1:-1]),
                                [sub_prop, super_prop],
                            )

                            sub_prop_iri = str(sub_prop.iri)
                            super_prop_iri = str(super_prop.iri)
                            sub_prop_phrase = handler.render_role_restriction(
                                sub_prop_iri
                            )
                            super_prop_phrase = handler.render_role_restriction(
                                super_prop_iri
                            )
                            sub_prop_label = sub_prop.label[0]
                            super_prop_label = super_prop.label[0]
                            print(
                                f"{whitespace_prefix}If {sub_prop_phrase}, then {super_prop_phrase} also ("
                                f"'{sub_prop_label}' is a subproperty of '{super_prop_label}')"
                            )
                        else:
                            classA = None
                            operand = None
                            ClassB = None
                            depth, manchester_expression = process_manchester_owl_uris(
                                item
                            )
                            if " EquivalentTo " in manchester_expression:
                                parts = manchester_expression.split(" EquivalentTo ", 1)
                                classA, operand, ClassB = (
                                    parts[0].strip(),
                                    "EquivalentTo",
                                    parts[1].strip(),
                                )
                            elif " SubClassOf " in manchester_expression:
                                parts = manchester_expression.split(" SubClassOf ", 1)
                                classA, operand, ClassB = (
                                    parts[0].strip(),
                                    "SubClassOf",
                                    parts[1].strip(),
                                )
                            classA = ontology.search(iri=classA[1:-1])[0]
                            parsed_expression = manchester_to_owl_expression(
                                ClassB, ontology_namespace_baseuri
                            )
                            pho_expression = owlapy_to_pyhornedowl(
                                parsed_expression, handler.ontology
                            )
                            defs = [None]
                            handler.extract_definitional_phrases(
                                defs, [pho_expression], "", "", ""
                            )
                            defs = [
                                (
                                    definition[5:]
                                    if definition.startswith("None ")
                                    else remove_indefinite_article(definition)
                                )
                                for definition in defs[1:]
                            ]
                            classA_pho = Class(handler.ontology.iri(str(classA.iri)))
                            def_prefix = " " if defs[0].startswith("is ") else " is "
                            if operand == "EquivalentTo":
                                cnl_phrase = (
                                    f"Every {handler.render_owl_class(classA_pho)}{def_prefix}"
                                    f"{defs[0]} and vice versa."
                                )
                            else:
                                cnl_phrase = f"Every {handler.render_owl_class(classA_pho)}{def_prefix}{defs[0]}"
                            print(f"{whitespace_prefix}{cnl_phrase}")
            else:
                print(explanation)
            print("------" * 10)
    else:
        warnings.warn(
            f"robot command {' '.join(commands)} was not successfully completed: {response.stderr}"
        )


@click.command()
@click.option(
    "--action",
    "-a",
    type=click.Choice(["explain_logical_inferences", "justify_gci"]),
    required=True,
    help="Action to perform",
    default="explain_logical_inferences",
)
@click.option("--ontology-uri", type=str, required=True, help="The URI of the ontology")
@click.option(
    "--ontology-namespace-baseuri",
    type=str,
    required=True,
    help="The base URI of the ontology namespace",
)
@click.option(
    "--sqlite-file",
    type=str,
    help="Location of SQLite file used for persistence",
    required=True,
)
@click.option(
    "--configuration-file",
    type=str,
    help="Path to configuration YAML file for NL rendering of ontology terms. "
    "When omitted, ontology-embedded OWL_DSL_* annotations are used.",
    required=False,
    default=None,
)
@click.option("--class-reference", help="The IRI (or label) of the Uberon class")
@click.option(
    "--manchester-owl-expression",
    help="Manchester OWL expression for GCI (used with justify_gci",
)
@click.option(
    "--by-id",
    is_flag=True,
    default=False,
    help="Find ontology class by ID (otherwise by rdfs:label)",
)
@click.option("--verbose/--no-verbose", default=False)
@click.option(
    "--exact-class-labels/--no-exact-class-labels",
    default=False,
    help="Render OWL class labels as is (don't convert to lower case by default)",
)
@click.argument("owl_url_or_path", required=False)
def main(
    action,
    ontology_uri,
    ontology_namespace_baseuri,
    sqlite_file,
    configuration_file,
    class_reference,
    manchester_owl_expression,
    by_id,
    verbose,
    exact_class_labels,
    owl_url_or_path,
):
    if action == "explain_logical_inferences":
        default_world.set_backend(filename=sqlite_file)
        handler, ontology = get_owlready2_ontology(
            ontology_uri, owl_url_or_path, sqlite_file, verbose, exact_class_labels
        )
        reasoner = SyncReasoner(ontology=owl_url_or_path, reasoner="ELK")
        definition_properties, _ = resolve_definition_properties(
            handler, ontology, owl_url_or_path, configuration_file, verbose
        )
        if by_id:
            class_iri = ontology_namespace_baseuri + class_reference
            class_expression = (
                f"?owl_class rdfs:label ?label " f"FILTER(?owl_class = <{class_iri}>)"
            )
        else:
            class_expression = f"?owl_class rdfs:label '{class_reference}'"
        prop_conjunction = (
            " || ".join([f"?defprop = <{p}>" for p in definition_properties])
            if len(definition_properties) > 1
            else (
                f"?defprop = <{definition_properties[0]}>"
                if definition_properties
                else ""
            )
        )
        def_prop_expression = f"FILTER({prop_conjunction})" if prop_conjunction else ""
        query = CLASS_AND_THEIR_DEFINITION_SPARQL.format(
            owl_class_expression=class_expression,
            def_prop_expression=def_prop_expression,
        )
        for owl_class, definition in default_world.sparql_query(query):
            owl_class_rdfs_label = owl_class.label[0]
            owl_class_label = (
                owl_class.prefLabel[0]
                if getattr(owl_class, "prefLabel", None) and owl_class.prefLabel
                else owl_class_rdfs_label
            )
            class_iri_str = str(owl_class.iri)
            summarize_owl_class(definition, handler, class_iri_str)
            print("------" * 10)
            stated_ancestry_iris = [
                item.iri if isinstance(item, ThingClass) else item
                for item in owl_class.is_a + owl_class.equivalent_to
            ]

            stated_subclass_iris = [
                item.iri
                for (item,) in default_world.sparql_query(
                    STATED_GCI_SUBCLASSES_SPARQL.format(owl_class=owl_class.iri)
                )
                if isinstance(item, ThingClass)
            ]

            owl2apy_iri = IRI.create(
                class_iri_str, is_file_path="/" not in class_iri_str
            )
            owl2apy_class = OWLClass(owl2apy_iri)
            for super_owl_class in reasoner.super_classes(owl2apy_class):
                try:
                    super_owl_class_iri = str(super_owl_class.iri.str)
                    if super_owl_class_iri in stated_ancestry_iris + [str(OWL.Thing)]:
                        continue
                    super_owl_class = get_owlready2_class(ontology, super_owl_class_iri)
                    super_class_rdfs_label = super_owl_class.label[0]
                    super_class_display_label = (
                        super_owl_class.prefLabel[0]
                        if getattr(super_owl_class, "prefLabel", None)
                        and super_owl_class.prefLabel
                        else super_class_rdfs_label
                    )
                    quoted_super_owl_class_label = f"'{super_class_rdfs_label}'"
                    if (
                        str(super_class_display_label)
                        not in handler.class_inference_to_ignore
                    ):
                        try:
                            verbalize_gci_justifications(
                                handler,
                                owl_class,
                                owl_class_rdfs_label,
                                ontology,
                                ontology_namespace_baseuri,
                                owl_url_or_path,
                                quoted_super_owl_class_label,
                                verbose,
                                display_label=owl_class_label,
                            )
                        except NotImplementedError as e:
                            warnings.warn(
                                f"Skipping GCI justification for {super_owl_class.iri}: {e}"
                            )
                except IndexError as e:
                    warnings.warn(
                        f"Skipping GCI justification for {super_owl_class} due to missing label: {e}"
                    )
            for owl_sub_class in reasoner.sub_classes(owl2apy_class):
                if owl_sub_class.iri.str not in stated_subclass_iris:
                    try:
                        owl_super_class_label = f"'{owl_class_rdfs_label}'"
                        owlr2_sub_class = get_owlready2_class(
                            ontology, owl_sub_class.iri.str
                        )
                        owl_sub_class_rdfs_label = owlr2_sub_class.label[0]
                        owl_sub_class_label = (
                            owlr2_sub_class.prefLabel[0]
                            if getattr(owlr2_sub_class, "prefLabel", None)
                            and owlr2_sub_class.prefLabel
                            else owl_sub_class_rdfs_label
                        )
                        verbalize_gci_justifications(
                            handler,
                            owlr2_sub_class,
                            owl_sub_class_rdfs_label,
                            ontology,
                            ontology_namespace_baseuri,
                            owl_url_or_path,
                            owl_super_class_label,
                            verbose,
                            display_label=owl_sub_class_label,
                        )
                    except (NotImplementedError, IndexError) as e:
                        warnings.warn(
                            f"Skipping GCI justification for {owl_sub_class.iri}: {e}"
                        )

    elif action == "justify_gci":
        handler, ontology = get_owlready2_ontology(
            ontology_uri, owl_url_or_path, sqlite_file
        )
        definition_properties, _ = resolve_definition_properties(
            handler, ontology, owl_url_or_path, configuration_file, verbose
        )
        if by_id:
            class_iri = ontology_namespace_baseuri + class_reference
            class_expression = (
                f"?owl_class rdfs:label ?label " f"FILTER(?owl_class = <{class_iri}>)"
            )
        else:
            class_expression = f"?owl_class rdfs:label '{class_reference}'"
        prop_conjunction = (
            " || ".join([f"?defprop = <{p}>" for p in definition_properties])
            if len(definition_properties) > 1
            else (
                f"?defprop = <{definition_properties[0]}>"
                if definition_properties
                else ""
            )
        )
        def_prop_expression = f"FILTER({prop_conjunction})" if prop_conjunction else ""
        query = CLASS_AND_THEIR_DEFINITION_SPARQL.format(
            owl_class_expression=class_expression,
            def_prop_expression=def_prop_expression,
        )
        if verbose:
            print(query)
        for owl_class, definition in default_world.sparql_query(query):
            owl_class_rdfs_label = owl_class.label[0]
            owl_class_label = (
                owl_class.prefLabel[0]
                if getattr(owl_class, "prefLabel", None) and owl_class.prefLabel
                else owl_class_rdfs_label
            )
            summarize_owl_class(definition, handler, str(owl_class.iri))
            print("------" * 10)
            verbalize_gci_justifications(
                handler,
                owl_class,
                owl_class_rdfs_label,
                ontology,
                ontology_namespace_baseuri,
                owl_url_or_path,
                manchester_owl_expression,
                verbose,
                display_label=owl_class_label,
            )


if __name__ == "__main__":
    main()

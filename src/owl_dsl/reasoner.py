import os
import warnings
from typing import Tuple

import click
import re

from rdflib import OWL

from owl_dsl.cli import run_subprocess, setup_configuration, CLASS_AND_THEIR_DEFINITION_SPARQL, summarize_owl_class
from owl_dsl.renderer import CNLRenderer
from owl_dsl import base_uri, prefix_with_indefinite_article
from owlready2 import ThingClass, And, Restriction, base, default_world, get_ontology, EntityClass, Or

from owlapy.class_expression import OWLObjectIntersectionOf, OWLObjectSomeValuesFrom, OWLObjectAllValuesFrom, \
    OWLObjectUnionOf
from owlapy import manchester_to_owl_expression
from owlapy.owl_reasoner import SyncReasoner
from owlapy.owl_property import OWLObjectProperty
from owlapy.owl_ontology import Ontology, OWLClass
from owlapy.owl_data_ranges import OWLPropertyRange

EXPLANATION_FILE = os.environ.get('OWL_DSL_EXPLANATION_FILE', '/tmp/explanation.md')
EXPLANATION_PATTERN = re.compile(r'^##.+\n\n(?P<info>.+(?=# Axiom Impact)).+$', re.MULTILINE | re.DOTALL)
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

STATED_GCI_SUBCLASSES_SPARQL = \
"""SELECT DISTINCT ?subclass {{ 
    {{ ?subclass rdfs:subClassOf <{owl_class}> }}
                    UNION 
    {{ ?subclass owl:intersectionOf [ rdf:first <{owl_class}> ] }}
                    UNION 
    {{ ?subclass rdfs:subClassOf [ owl:intersectionOf [ rdf:first <{owl_class}> ]] }}
}}"""

def remove_indefinite_article(s: str) -> str:
    if s.startswith("It "):
        return s[3:]
    return s

def get_owlready2_class(onto: Ontology, iri:str) -> EntityClass:
    return onto.search(iri=iri)[0]

def count_leading_spaces(s: str) -> int:
    return len(s) - len(s.lstrip())

def process_manchester_owl_local_names(line: str, skip_indices:int = 2) -> Tuple[int, str]:
    """
    Processes a justification line from robot, returning the number of leading spaces and the result of
    replacing manchester OWL links with the suffix after the last '/' (skipping a prefix, the length of which is
    specified and defaults to 2 for '- ')

    :param line:
    :param skip_indices:
    :return:
    """
    num_leading_spaces = count_leading_spaces(line)
    def repl(match: re.Match) -> str:
        return str(base_uri(match.group(2))[-1])
    processed_string = LINK_RE.sub(repl, line)
    if processed_string is None:
        raise SyntaxError(f"Could not parse line: {line}")
    return num_leading_spaces, processed_string.strip()[skip_indices:]

def process_manchester_owl_uris(line: str, skip_indices:int = 2) -> Tuple[int, str]:
    """
    Processes a justification line from robot, returning the number of leading spaces and the result of
    replacing manchester OWL links with <URIs> (skipping a prefix, the length of which is specified and
    defaults to 2 for '- ')

    :param line: The input string containing Manchester OWL references.
    :type line: str
    :param skip_indices: The number of leading characters to strip from the processed string. Defaults to 2.
    :type skip_indices: int
    :return: A tuple containing the number of leading spaces and the processed string with specified
        characters stripped.
    :rtype: Tuple[int, str]
    :raises SyntaxError: If the input line cannot be parsed and processed.
    """
    num_leading_spaces = count_leading_spaces(line)
    def repl(match: re.Match) -> str:
        return f"<{match.group(2)}>"

    processed_string = LINK_RE.sub(repl, line)
    if processed_string is None:
        raise SyntaxError(f"Could not parse line: {line}")
    return num_leading_spaces, processed_string.strip()[skip_indices:]

def owlapy_to_owlready2(owlapy_expr: OWLPropertyRange, ontology: Ontology):
    """
    Converts an owlapy expression (`owlapy_expr`) into its owlready2 equivalent within the
    given ontology.

    :param owlapy_expr: The OWL property range expression to be resolved. It must be
        an instance of supported `OWLPropertyRange` types such as `OWLObjectIntersectionOf`,
        `OWLObjectProperty`, `OWLClass`, or `OWLObjectSomeValuesFrom`.
    :param ontology: The ontology in which mappings and searches will be performed.
        This is used to lookup matching classes or properties based on IRI.
    :return: The unfurled expression resolved into its corresponding owlready2 class,
        property, or restriction representation.
    :rtype: Union[And, Restriction, Any]

    :raises ValueError: Raised when a class or property in the ontology cannot be
        found using the IRI provided in `owlapy_expr`.
    :raises NotImplementedError: Raised for unsupported types of `owlapy_expr` that
        are not defined in the function logic.
    """
    if isinstance(owlapy_expr, OWLObjectIntersectionOf):
        return And([owlapy_to_owlready2(item, ontology) for item in owlapy_expr._operands])
    elif isinstance(owlapy_expr, (OWLObjectProperty, OWLClass)):
        class_or_property=ontology.search(iri=owlapy_expr.iri.str)
        if not class_or_property:
            raise ValueError(f"Could not find owlready2 class or property ({type(owlapy_expr)}) with IRI {owlapy_expr.iri.str}")
        return class_or_property[0]
    elif isinstance(owlapy_expr, OWLObjectSomeValuesFrom):
        return Restriction(owlapy_to_owlready2(owlapy_expr.get_property(), ontology),
                           base.SOME,
                           value=owlapy_to_owlready2(owlapy_expr.get_filler(), ontology))
    elif isinstance(owlapy_expr, OWLObjectUnionOf):
        return Or([owlapy_to_owlready2(item, ontology) for item in owlapy_expr._operands])
    else:
        raise NotImplementedError(f"Unsupported OWL expression type: {type(owlapy_expr)}")

def get_owlready2_ontology(ontology_uri: str,
                           owl_url_or_path:str,
                           sqlite_file: str,
                           verbose: bool = False,
                           exact_class_labels: bool = False) -> tuple[CNLRenderer, Ontology]:
    """
    Retrieves or loads an ontology using the Owlready2 library. If the ontology is not
    already loaded within the default Owlready2 world, it will attempt to load it from
    the specified path or URL. A `CNLRenderer` handler is created for rendering the
    ontology content.

    :param ontology_uri: The base IRI of the ontology.
    :type ontology_uri: str
    :param owl_url_or_path: The file path or URL to load the ontology from,
                            if it is not already loaded.
    :type owl_url_or_path: str
    :return: A tuple containing the `CNLRenderer` for the ontology and the
             ontology object itself.
    :rtype: tuple[CNLRenderer, Ontology]
    """
    if ontology_uri not in default_world.ontologies:
        print(f"Forcibly loading ontology from {owl_url_or_path} into {ontology_uri} (using {sqlite_file})")
        ontology = get_ontology(owl_url_or_path)
        ontology.load()
        default_world.ontologies[ontology_uri] = ontology
        ontology.set_base_iri(ontology_uri, rename_entities=False)
        default_world.save()
        print(default_world.ontologies)
    else:
        ontology = default_world.ontologies[ontology_uri]
    handler = CNLRenderer(ontology, ontology_uri, verbose=verbose, lowercase_labels=not exact_class_labels)
    return handler, ontology

def verbalize_gci_justifications(handler: CNLRenderer,
                                 owl_class: ThingClass,
                                 owl_class_label: str,
                                 ontology: Ontology,
                                 ontology_namespace_baseuri: str,
                                 owl_url_or_path: str,
                                 owl_super_class_expression,
                                 verbose: bool):
    """
    Verbalizes justifications for a General Concept Inclusion (GCI) axiom in an ontology.

    This function generates a justification for a specified General Concept Inclusion (GCI)
    axiom and presents it in a concise natural-language format

    :param handler: Instance of `CNLRenderer` used to convert class expressions and
        properties from an ontology into controlled natural language.
    :param owl_class: Instance of `ThingClass` representing the OWL class for which justifications
        are generated.
    :param owl_class_label: Human-readable label or name for the OWL class.
    :param ontology: Ontology object providing the structure and axioms from which justifications
        are derived.
    :param ontology_namespace_baseuri: String defining the base URI of the ontology namespace, utilized
        for parsing and resolving classes or properties.
    :param owl_url_or_path: String representing the URL or local file path to the OWL ontology file.
    :param owl_super_class_expression: OWL class expression representing the superclass used in the
        GCI axiom.
    :param verbose: Boolean flag indicating if detailed additional information, such as matching explanations
        and verbose commands, should be printed.

    :return: None. Outputs verbalized justifications or related ontology reasoning to the console.
    """
    axiom_to_prove = f"'{owl_class_label}' SubClassOf {owl_super_class_expression}"
    extra_info = f" ({axiom_to_prove})" if verbose else ""
    prefixed_owl_superclass = prefix_with_indefinite_article(owl_super_class_expression)
    print(f"How is "
          f"every '{owl_class_label}' ({owl_class.name}) {prefixed_owl_superclass}{extra_info}?\n")
    commands = [
        'robot',
        'explain',
        '--input', owl_url_or_path,
        '--reasoner', 'ELK',
        '--axiom', axiom_to_prove,
        '--explanation', EXPLANATION_FILE]
    response = run_subprocess(commands, verbose=verbose)
    if response.returncode == 0:
        with open(EXPLANATION_FILE, 'r') as f:
            explanation = f.read()
            match = EXPLANATION_PATTERN.match(explanation)
            if match:
                info = match.group('info')
                for item in info.split('\n'):
                    if item.strip():
                        if verbose:
                            print(item)
                        depth = count_leading_spaces(item)
                        whitespace_prefix = ' ' * depth
                        if item.strip().startswith('-  Transitive: '):
                            _ = item.strip().split('Transitive:')[-1]
                            prop_label = LINK_RE.match(_.strip()).groups()[0]
                            print(f"{whitespace_prefix}'{prop_label}' is a transitive property.")
                        elif ' Domain ' in item.strip():
                            info = [*item.strip().split(' Domain ')]
                            prop, _domain_owl_class = info
                            prop, _domain_owl_class = map(str.strip, [prop[2:], _domain_owl_class])
                            info = [process_manchester_owl_uris(prop, skip_indices=0)[-1][1:-1],
                                    process_manchester_owl_uris(_domain_owl_class, skip_indices=0)[-1][1:-1]]
                            prop, _domain_owl_class = map(lambda i:ontology.search_one(iri=i), info)
                            prop_label = prop.label[0]
                            domain_owl_class_label = _domain_owl_class.label[0]
                            print(f"{whitespace_prefix}If A is related to B via '{prop_label}' "
                                  f"then A is a '{domain_owl_class_label}'")
                        elif ' DisjointUnionOf ' in item.strip():
                            raise NotImplementedError("DisjointUnionOf not yet supported")
                        elif ' Range ' in item.strip():
                            info = [*item.strip().split(' Range ')]
                            prop, _range_owl_class = info
                            prop, _range_owl_class = map(str.strip, [prop[2:], _range_owl_class])
                            info = [process_manchester_owl_uris(prop, skip_indices=0)[-1][1:-1],
                                    process_manchester_owl_uris(_range_owl_class, skip_indices=0)[-1][1:-1]]
                            prop, _range_owl_class = map(lambda i:ontology.search_one(iri=i), info)
                            prop_phrase = handler.render_role_restriction(prop)
                            range_owl_class_label = _range_owl_class.label[0]
                            print(f"{whitespace_prefix}If {prop_phrase}, then B is a '{range_owl_class_label}'")
                        elif ' SubPropertyOf: ' in item.strip():
                            info = [*item.strip().split(' SubPropertyOf: ')]
                            sub_prop, super_prop = info
                            sub_prop, super_prop = map(str.strip, [sub_prop[2:], super_prop])
                            sub_prop, super_prop = map(lambda i: process_manchester_owl_uris(i, skip_indices=0)[-1],
                                                       [sub_prop, super_prop])
                            sub_prop, super_prop = map(lambda i: ontology.search_one(iri=i[1:-1]),
                                                       [sub_prop, super_prop])

                            sub_prop_phrase = handler.render_role_restriction(sub_prop)
                            super_prop_phrase = handler.render_role_restriction(super_prop)
                            sub_prop_label = sub_prop.label[0]
                            super_prop_label = super_prop.label[0]
                            print(f"{whitespace_prefix}If {sub_prop_phrase}, then {super_prop_phrase} also ("
                                  f"'{sub_prop_label}' is a subproperty of '{super_prop_label}')")
                        else:
                            classA = None
                            operand = None
                            ClassB = None
                            depth, manchester_expression = process_manchester_owl_uris(item)
                            if ' EquivalentTo ' in manchester_expression:
                                parts = manchester_expression.split(' EquivalentTo ', 1)
                                classA, operand, ClassB = parts[0].strip(), 'EquivalentTo', parts[1].strip()
                            elif ' SubClassOf ' in manchester_expression:
                                parts = manchester_expression.split(' SubClassOf ', 1)
                                classA, operand, ClassB = parts[0].strip(), 'SubClassOf', parts[1].strip()
                            classA = ontology.search(iri=classA[1:-1])[0]
                            parsed_expression = manchester_to_owl_expression(ClassB,
                                                                             ontology_namespace_baseuri)
                            owlready2_expression = owlapy_to_owlready2(parsed_expression, ontology)
                            defs = [None]
                            handler.extract_definitional_phrases(defs,
                                                                 [owlready2_expression],
                                                                 "",
                                                                 "",
                                                                 "")
                            defs = [definition[5:] if definition.startswith('None ')
                                    else remove_indefinite_article(definition) for definition in defs[1:]]
                            def_prefix = ' ' if defs[0].startswith('is ') else ' is '
                            if operand == 'EquivalentTo':
                                cnl_phrase = (f"Every {handler.render_owl_class(classA)}{def_prefix}"
                                              f"{defs[0]} and vice versa.")
                            else:
                                cnl_phrase = f"Every {handler.render_owl_class(classA)}{def_prefix}{defs[0]}"
                            print(f"{whitespace_prefix}{cnl_phrase}")
            else:
                print(explanation)
            print('------' * 10)
    else:
        warnings.warn(f"robot command {' '.join(commands)} was not successfully completed: {response.stderr}")


@click.command()
@click.option('--action', '-a', type=click.Choice(
    ['explain_logical_inferences', 'justify_gci']), required=True,
              help='Action to perform',
              default='explain_logical_inferences')
@click.option('--ontology-uri', type=str, required=True,
              help="The URI of the ontology")
@click.option('--ontology-namespace-baseuri', type=str, required=True,
              help="The base URI of the ontology namespace")
@click.option('--sqlite-file', type=str,
              help="Location of SQLite file used for persistence", required=True)
@click.option('--configuration-file', type=str,
              help="Path to configuration YAML file for NL rendering of ontology terms",
              required=True)
@click.option('--class-reference', help='The IRI (or label) of the Uberon class')
@click.option('--manchester-owl-expression', help='Manchester OWL expression for GCI (used with justify_gci')
@click.option('--by-id', is_flag = True, default = False,
              help='Find ontology class by ID (otherwise by rdfs:label)')
@click.option('--verbose/--no-verbose', default=False)
@click.option('--exact-class-labels/--no-exact-class-labels', default = False,
              help = "Render OWL class labels as is (don't convert to lower case by default)")
@click.argument('owl_url_or_path', required=False)
def main(action,
         ontology_uri,
         ontology_namespace_baseuri,
         sqlite_file,
         configuration_file,
         class_reference,
         manchester_owl_expression,
         by_id,
         verbose,
         exact_class_labels,
         owl_url_or_path):
    if action == 'explain_logical_inferences':
        default_world.set_backend(filename=sqlite_file)
        handler, ontology = get_owlready2_ontology(ontology_uri,
                                                   owl_url_or_path,
                                                   sqlite_file,
                                                   verbose,
                                                   exact_class_labels)
        reasoner = SyncReasoner(ontology=owl_url_or_path, reasoner="ELK")
        definition_properties = setup_configuration(handler, configuration_file)
        class_expression = (f"?owl_class rdfs:label ?label "
                            f"FILTER(?owl_class = <{getattr(handler.ontology_lookup, class_reference).iri}>)"
                            if by_id
                            else f"?owl_class rdfs:label '{class_reference}'")
        prop_conjunction = (' || '.join([f"?defprop = <{p}>" for p in definition_properties]
                                       ) if len(definition_properties) > 1
                            else f"?defprop = <{definition_properties[0]}>" if definition_properties else "")
        def_prop_expression = f"FILTER({prop_conjunction})"
        query = CLASS_AND_THEIR_DEFINITION_SPARQL.format(owl_class_expression=class_expression,
                                                         def_prop_expression=def_prop_expression)
        for owl_class, definition in default_world.sparql_query(query):
            owl_class_label = owl_class.label[0]
            summarize_owl_class(definition, handler, owl_class)
            print("------" * 10)
            stated_ancestry_iris = [item.iri if isinstance(item, ThingClass) else item
                                    for item in owl_class.is_a + owl_class.equivalent_to]

            stated_subclass_iris = [item.iri for (item,) in default_world.sparql_query(
                STATED_GCI_SUBCLASSES_SPARQL.format(owl_class=owl_class.iri)) if isinstance(item, ThingClass)
            ]

            owl2apy_class = OWLClass(owl_class.iri)
            for super_owl_class in reasoner.super_classes(owl2apy_class):
                try:
                    super_owl_class_iri = str(super_owl_class.iri.str)
                    if super_owl_class_iri in stated_ancestry_iris + [str(OWL.Thing)]:
                        continue
                    super_owl_class = get_owlready2_class(ontology, super_owl_class_iri)
                    super_class_label = super_owl_class.label[0]
                    quoted_super_owl_class_label = f"'{super_class_label}'"
                    if str(super_class_label) not in handler.class_inference_to_ignore:
                        verbalize_gci_justifications(handler, owl_class, owl_class_label, ontology, ontology_namespace_baseuri,
                                                     owl_url_or_path, quoted_super_owl_class_label, verbose)
                except IndexError as e:
                    warnings.warn(f"Skipping GCI justification for {super_owl_class} due to missing label: {e}")
            for owl_sub_class in reasoner.sub_classes(owl2apy_class):
                if owl_sub_class.iri.str not in stated_subclass_iris:
                    try:
                        owl_super_class_label = f"'{owl_class_label}'"
                        owlr2_sub_class = get_owlready2_class(ontology, owl_sub_class.iri.str)
                        verbalize_gci_justifications(handler, owlr2_sub_class,
                                                     owlr2_sub_class.label[0],
                                                     ontology, ontology_namespace_baseuri,
                                                     owl_url_or_path, owl_super_class_label, verbose)
                    except IndexError as e:
                        warnings.warn(f"Skipping GCI justification for {owl_sub_class.iri} due to missing label: {e}")

    elif action == 'justify_gci':
        handler, ontology = get_owlready2_ontology(ontology_uri, owl_url_or_path, sqlite_file)
        definition_properties = setup_configuration(handler, configuration_file)
        class_expression = (f"?owl_class rdfs:label ?label "
                            f"FILTER(?owl_class = <{getattr(handler.ontology_lookup, class_reference).iri}>)"
                            if by_id
                            else f"?owl_class rdfs:label '{class_reference}'")
        prop_conjunction = (' || '.join([f"?defprop = <{p}>" for p in definition_properties]
                                       ) if len(definition_properties) > 1
                            else f"?defprop = <{definition_properties[0]}>" if definition_properties else "")
        def_prop_expression = f"FILTER({prop_conjunction})"
        query = CLASS_AND_THEIR_DEFINITION_SPARQL.format(owl_class_expression=class_expression,
                                                         def_prop_expression=def_prop_expression)
        if verbose:
            print(query)
        for owl_class, definition in default_world.sparql_query(query):
            owl_class_label = owl_class.label[0]
            summarize_owl_class(definition, handler, owl_class)
            print("------" * 10)
            verbalize_gci_justifications(handler, owl_class, owl_class_label, ontology, ontology_namespace_baseuri,
                                         owl_url_or_path, manchester_owl_expression, verbose)

if __name__ == '__main__':
    main()

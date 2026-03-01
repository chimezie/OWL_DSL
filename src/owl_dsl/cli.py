#!/usr/bin/env python
import click
import os
import re
import yaml
from subprocess import CompletedProcess
from click import Choice
from yaml import CLoader as Loader
from typing import List

from rdflib import URIRef

from owlready2 import ThingClass, default_world, get_ontology
from owl_dsl import base_uri, get_owl_class_label
from owl_dsl.renderer import CNLRenderer

DC_TITLE_URI = "http://purl.org/dc/elements/1.1/title"
DC_DESCRIPTION_URI = "http://purl.org/dc/elements/1.1/description"

CLASS_BY_CONTAINS_LABEL_SPARQL =\
"""
#Fetch owl classes by string matching against their labels
SELECT DISTINCT ?owl_class ?label {{
    ?owl_class a owl:Class; rdfs:label ?label.
    FILTER(contains(lcase(?label), lcase("{pattern}"))) 
}}"""

CLASS_BY_REGEX_LABEL_SPARQL =\
"""
#Fetch owl classes by REGEX matching against their labels
SELECT DISTINCT ?owl_class ?label {{
    ?owl_class a owl:Class; rdfs:label ?label.
    FILTER(regex(?label, "{pattern}")) 
}}"""

DEFINITION_FOR_PROPERTY_SPARQL =\
"""
#Fetch any ontology-indicated (human-readable) definitions for the property
SELECT DISTINCT ?prop ?definition {{
    [] owl:onProperty ?prop {prop_filter}  
    OPTIONAL {{ ?prop ?defprop ?definition {def_prop_expression} }} 
}}"""

IRI_AND_LABEL_FOR_EXAMPLE_SPARQL = \
"""
#Fetch any classes whose definition in the ontology include a GCI involving a restriction on the property
SELECT DISTINCT ?subj ?label {{ 
    ?subj rdfs:label ?label; 
          rdfs:subClassOf [ owl:onProperty ?prop ]
    {filtered_prop}
}} ORDER BY RAND() LIMIT {limit} 
"""

CLASS_AND_THEIR_DEFINITION_SPARQL = \
"""
# An OWL class with an rdfs:label and any definitions (?defprop) it may have as specified in the ontology.
PREFIX obo: <http://purl.obolibrary.org/obo/>
PREFIX oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
SELECT ?owl_class ?definition {{ 
    {owl_class_expression} 
    OPTIONAL {{ ?owl_class ?defprop ?definition {def_prop_expression} }} }}"""

def run_subprocess(command: List[str], verbose = False) -> CompletedProcess:
    import subprocess
    if verbose:
        print("Running command: ", ' '.join(command))
    resp = subprocess.run(command, capture_output = verbose)
    if verbose:
        print(resp.stdout.decode("utf-8"))
    return resp

def match_object_sparql_expression(variable_name: str, resources: List[str],
                                   just_filter: bool = False):
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
        filter_expr = ' || '.join([f"?{variable_name} = <{p}>" for p in resources])
        return f"FILTER({filter_expr})" if just_filter else f"?{variable_name} FILTER({filter_expr})"
    else:
        return ""

@click.command()
@click.option('--action', '-a', type = Choice(
    ['render_class', 'find_properties', 'load_owl', 'destroy_sqlite', 'find_classes']),
              required = True,
              help = 'Action to perform',
              default = 'render_class')
@click.option('--by-id', is_flag = True, default = False,
              help='Find ontology class by ID (otherwise by rdfs:label)')
@click.option('--class-reference', help='The ID (or label) of the Uberon class')
@click.option('--class-search', help='The string to use for searching for a class to use')
@click.option('--regex-search/--no-regex-search', default=False)
@click.option('--verbose/--no-verbose', default = False)
@click.option('--exact-class-labels/--no-exact-class-labels', default = False,
              help = "Render OWL class labels as is (don't convert to lower case by default)")
@click.option('--configuration-file', type =  str,
              help="Path to configuration YAML file for NL rendering of ontology terms",
              required=True)
@click.option('--sqlite-file', type = str,
              help="Location of SQLite file used for persistence", required=True)
@click.option('--prefix', type = str,
              help="Filter properties by URI prefix (only for 'find_properties' action)",
              default='')
@click.option('--prop-reference-label', type = str,
              help="Filter properties by rdfs:label using REGEX (only for 'find_properties' action)",
              default='')
@click.option('--show-property-definition-usage', is_flag = True, default = False,
              help="Show class definition examples for listed properties (only for 'find_properties' action)")
@click.option('--limit', type = int, default = 1,
              help="Limit number of results (only for 'find_properties' action with --show-property-definition-usage)")
@click.option('--ontology-uri', type = str, required = True,
              help="The URI of the ontology")
@click.option('--ontology-namespace-baseuri', type = str, required = True,
              help="The base URI of the ontology namespace")
@click.argument('owl_url_or_path', required = False)
def main(action,
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
         owl_url_or_path):
    default_world.set_backend(filename=sqlite_file)
    if action == 'find_classes':
        print("Loaded ontology")
        for owl_class, label in default_world.sparql_query(
                (CLASS_BY_REGEX_LABEL_SPARQL if regex_search
                else CLASS_BY_CONTAINS_LABEL_SPARQL).format(pattern=class_search)):
            print(f"{owl_class.iri} '{label}'")

    elif action == 'render_class':
        onto = default_world.ontologies[ontology_uri]
        print("Loaded ontology")
        handler = CNLRenderer(onto,
                              ontology_namespace_baseuri,
                              verbose=verbose,
                              lowercase_labels=not exact_class_labels)
        definition_properties = setup_configuration(handler, configuration_file)
        sparql_expression = (f"?owl_class rdfs:label ?label "
                            f"FILTER(?owl_class = <{getattr(handler.ontology_lookup, class_reference).iri}>)"
                            if by_id
                            else f"?owl_class rdfs:label '{class_reference}'")
        prop_conjunction = (' || '.join([f"?defprop = <{p}>" for p in definition_properties]
                                       ) if len(definition_properties) > 1
                            else f"?defprop = <{definition_properties[0]}>" if definition_properties else "")
        def_prop_expression = f"FILTER({prop_conjunction})"
        query = CLASS_AND_THEIR_DEFINITION_SPARQL.format(owl_class_expression=sparql_expression,
                                                         def_prop_expression=def_prop_expression)
        for owl_class, definition in default_world.sparql_query(query):
            summarize_owl_class(definition, handler, owl_class)

    elif action == 'find_properties':
        onto = default_world.ontologies[ontology_uri]
        print("Loaded ontology")
        handler = CNLRenderer(onto,
                              ontology_namespace_baseuri,
                              verbose=verbose,
                              lowercase_labels=not exact_class_labels)
        definition_properties = setup_configuration(handler, configuration_file)

        if prop_reference_label:
            # Filter properties by label using regex
            regex_pattern = re.compile(prop_reference_label)
            filtered_properties = []
            for p in sorted(onto.properties()):
                prop_base_uri, suffix = base_uri(p.iri)
                prop_labels = [l for l in onto.get_namespace(prop_base_uri)[suffix].label
                               if isinstance(l, str)]
                if any(regex_pattern.search(label) for label in prop_labels):
                    filtered_properties.append(p.iri)
        else:
            filtered_properties = [p.iri for p in sorted(onto.properties()) if not prefix or p.iri.startswith(prefix)]

        def_prop_expression = match_object_sparql_expression("defprop",
                                                             definition_properties,
                                                             just_filter=True)
        filter_only_prop_expr = match_object_sparql_expression("prop",
                                                               filtered_properties,
                                                               just_filter=True)
        query = DEFINITION_FOR_PROPERTY_SPARQL.format(prop_filter=filter_only_prop_expr,
                                                      def_prop_expression=def_prop_expression)
        for prop, definition  in default_world.sparql_query(query):
            prop_base_uri, suffix = base_uri(prop.iri)
            prop_label = [l for l in onto.get_namespace(prop_base_uri)[suffix].label
                          if isinstance(l, str)]
            prop_label = prop_label[0] if prop_label else None
            print("- ", prop.iri, f"'{prop_label}'" if prop_label else "(no label)",
                  f'"{definition}"' if definition else "(no definition)")
            domain = [get_owl_class_label(d) for d in prop.domain
                      if isinstance(d, ThingClass) and get_owl_class_label(d)]
            range = [get_owl_class_label(r) for r in prop.range
                     if isinstance(r, ThingClass) and get_owl_class_label(r)]
            if domain:
                print(f"\t- Domain: {', '.join(domain)}")
            if range:
                print(f"\t- Range: {', '.join(range)}")
            if show_property_definition_usage:
                query = IRI_AND_LABEL_FOR_EXAMPLE_SPARQL.format(
                    filtered_prop=match_object_sparql_expression("prop",
                                                                 [prop.iri],just_filter=True),
                    limit=limit)
                for reference_owl_class, owl_class_label in default_world.sparql_query(query):
                    owl_class_base_uri, suffix = base_uri(reference_owl_class.iri)
                    owl_class_label = [l for l in onto.get_namespace(owl_class_base_uri)[suffix].label
                                  if isinstance(l, str)]
                    owl_class_label = owl_class_label[0] if owl_class_label else None
                    try:
                        owl_class_definition = handler.handle_owl_class(reference_owl_class) if owl_class_label else ''
                    except Exception as e:
                        print(f"Error: {e}")
                        owl_class_definition = None
                    print(f"\n{reference_owl_class.iri} '{owl_class_label}':")
                    print(f"{owl_class_definition if owl_class_definition else ''}")
            print('------'*5)
    elif action == 'load_owl':
        if not owl_url_or_path:
            print("No ontology URL or path provided. Exiting.")
            return
        print(f"Loading Uberon ontology from {owl_url_or_path}, a IRI or local path.")
        get_ontology(owl_url_or_path).load()
        default_world.base_iri = ontology_uri
        default_world.save()
        print(default_world.ontologies)
        print(f"Saved {owl_url_or_path} to {ontology_uri}", default_world.ontologies)
    elif action == 'destroy_sqlite':
        os.remove(sqlite_file)
        print(f"Deleted {sqlite_file}")

def summarize_owl_class(definition: str | None,
                        handler: CNLRenderer,
                        owl_class: ThingClass,
                        full_definition: bool = True):
    print(f"# {owl_class.iri} ({owl_class.label[0]}) # ")
    if definition:
        print(f"## Textual definition ##")
        print(definition, "\n")
    if full_definition:
        print(f"## Logical definition ##")
        print(handler.handle_owl_class(owl_class))

def setup_configuration(handler: CNLRenderer, configuration_file: str) -> list[str]:
    with open(configuration_file, 'r') as file:
        config = yaml.load(file, Loader=Loader)
        reflexive_roles = config['reflexive_roles'] if config['reflexive_roles'] else []
        handler.class_inference_to_ignore = config.get('class_inference_to_ignore', [])
        for role in reflexive_roles:
            for property_uri, phrase in role.items():
                handler.reflexive_property_customizations[URIRef(property_uri)] = phrase[0]

        definition_properties = config['tooling']['expert_definition_properties'] if config['tooling'] else []
        for prop in config['standard_role_restriction_is_phrasing']:
            prop_obj = handler.ontology.search(iri=prop)
            if prop_obj and prop_obj[0].label:
                props = [label for label in prop_obj[0].label if isinstance(label, str)]
                prop_label = props[0] if props else '(no label)'
                handler.relevant_role_restriction_cnl_phrasing[URIRef(prop)] = (
                                                                           f'is {prop_label} ' + '{}',
                                                                       ) * 2 + ('What is {}' + f' {prop_label}?',)
            else:
                print(f"Warning: Could not find label for property {prop}")
        for prop_uri, info in config['role_restriction_phrasing'].items():
            handler.relevant_role_restriction_cnl_phrasing[URIRef(prop_uri)] = tuple(info)
    return definition_properties


if __name__ == '__main__':
    main()

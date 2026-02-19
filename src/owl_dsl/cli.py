#!/usr/bin/env python
import re
import traceback
import warnings

import yaml
from click import Choice
from yaml import CLoader as Loader
import click
from itertools import groupby
from rdflib import Namespace, URIRef
from owlready2 import (get_namespace, ThingClass, LogicalClassConstruct, Or, And, owl, Construct, EntityClass,
                       PropertyClass, Not, Inverse, Restriction, base, OneOf, ConstrainedDatatype, PropertyChain,
                       rdfs_datatype, DataPropertyClass, default_world,
                       get_ontology, ClassConstruct, HAS_SELF, IndividualValueList)

from owl_dsl import base_uri, pretty_print_list, prefix_with_indefinite_article

from typing import Union, List, Any

class OutputHandler:
    """
    Handles output generation for ontology classes and properties.

    Attributes:
        ontology (Ontology): The ontology to process.
        definition_info (dict): Information about definitional phrases for classes.
        property_iris (list): List of property IRIs in the ontology.
        verbose (bool): Whether to print verbose output.
        ontology_namespace (str): Namespace of the ontology.
    """
    LOGICAL_COMPLEMENT_KEY = 0
    LOGICAL_CONSTRUCT_KEY = 1
    RESTRICTION_START_KEY = 2

    def __init__(self, ontology, ontology_namespace, verbose:bool = False):
        self.ontology = ontology
        self.definition_info = {}
        self.property_iris = [p.iri for p in sorted(self.ontology.properties())]
        self.verbose = verbose
        self.ontology_namespace = Namespace(ontology_namespace)
        self.ontology_lookup = get_namespace(self.ontology_namespace)
        self.reflexive_property_customizations = {}
        self.relevant_role_restriction_cnl_phrasing = {}
        self.custom_restriction_property_rendering = {}
        self.role_restriction_wo_articles = {}

    def is_logical_construct_key(self, key: int) -> bool:
        return key == self.LOGICAL_CONSTRUCT_KEY

    def is_restriction_key(self, key: int) -> bool:
        return self.RESTRICTION_START_KEY <= key < self.RESTRICTION_START_KEY + len(self.property_iris)

    def is_named_class_key(self, key: int) -> bool:
        return key >= self.RESTRICTION_START_KEY + len(self.property_iris)

    def concept_group_key(self, concept: Union[Construct, EntityClass]) -> int:
        if isinstance(concept, LogicalClassConstruct):
            return self.LOGICAL_CONSTRUCT_KEY
        elif isinstance(concept, Restriction):
            # Distinguish restrictions by their owl:onProperty value
            return self.RESTRICTION_START_KEY + self.property_iris.index(concept.property.iri)
        elif isinstance(concept, ThingClass):
            return self.RESTRICTION_START_KEY + len(self.property_iris)
        elif isinstance(concept, Not):
                return self.LOGICAL_COMPLEMENT_KEY
        else:
            raise NotImplementedError(concept)

    def render_class_name(self, klass: ThingClass, capitalize_first_letter=False, no_indef_article=True) -> str:
        if isinstance(klass, LogicalClassConstruct):
            class_names = [self.render_concept(c) for c in klass.Classes]
            if len(class_names) == 0:
                return self.render_concept(klass)
            elif len(class_names) == 1:
                return class_names[0]
            elif len(class_names) == 2:
                return f"{class_names[0]} that {class_names[1]}"
            else:
                # First and second joined with ' that ', rest joined with ' and '
                result = f"{class_names[0]} that {class_names[1]}"
                return result + f" and {pretty_print_list(class_names[2:], and_char=', and ')}"
        else:
            if klass.label:
                klass_label = klass.label[0]
                if no_indef_article:
                    name = f"{klass_label}"
                else:
                    prefixed_name = prefix_with_indefinite_article(klass_label).capitalize()
                    name = prefixed_name
            else:
                name = "" if no_indef_article else f"the {str(klass.label[0])}"
            if name.strip():
                name = name if capitalize_first_letter else name[0].lower() + name[1:]
            else:
                name = None
            return name

    def render_concept(self, concept: Union[Construct, EntityClass], anonymous: bool = False) -> str:
        if concept is None:
            raise NotImplementedError
        if isinstance(concept, ThingClass):
            if concept is owl.Thing:
                return "Everything"
            if concept is owl.Nothing:
                return "Nothing"
            return self.render_class_name(concept)
        if isinstance(concept, PropertyClass):
            return concept.name  # TODO: narrative labels for CNL
        if isinstance(concept, LogicalClassConstruct):
            s = []
            for x in concept.Classes:
                if isinstance(x, LogicalClassConstruct):
                    s.append("(" + self.render_concept(x) + ")")
                else:
                    s.append(self.render_concept(x))
            if isinstance(concept, Or):
                return pretty_print_list(s, and_char=", or ")
            if isinstance(concept, And):
                return pretty_print_list(s, and_char=", and ")
        if isinstance(concept, Not):
            raise NotImplementedError
        if isinstance(concept, Inverse):
            raise NotImplementedError
            # return "%s%s" % (render_concept(concept.property), _DL_SYNTAX.INVERSE)
        if isinstance(concept, Restriction):
            # SOME:
            # VALUE:
            prop_iri = concept.property.iri
            custom_phrases = self.relevant_role_restriction_cnl_phrasing.get(URIRef(prop_iri))
            if concept.type == base.SOME:
                restriction_value = self.render_class_name(concept.value)
                value_name = prefix_with_indefinite_article(restriction_value)
                # article = value_name.split(' ')[0]
                if custom_phrases:
                    return custom_phrases[0].format(value_name)
                elif len(concept.property.label):
                    # print(f"#### {prop_iri} {concept.property.name} ###")
                    prop_label = str(concept.property.label[0])
                    prefix = "" if anonymous else "is "
                    rt = f"{prefix}{prop_label} {value_name}"
                    return rt
                else:
                    return "something"
            if concept.type == base.ONLY:
                raise NotImplementedError
            if concept.type == base.VALUE:
                return "%s .{%s}" % (self.render_concept(concept.property),
                                     concept.value.name
                                     if isinstance(concept.value, owl.Thing) else concept.value)
            if concept.type == base.HAS_SELF:
                raise NotImplementedError
            if concept.type == base.EXACTLY:
                prop_label = str(concept.property.label[0])
                prefix = "" if anonymous else "is "
                return f"{prefix}{prop_label} exactly {concept.cardinality} {self.render_class_name(concept.value)}"

            if concept.type == base.MIN:
                prop_label = str(concept.property.label[0])
                prefix = "" if anonymous else "is "
                return f"{prefix}{prop_label} at least {concept.cardinality} {self.render_class_name(concept.value)}"
            if concept.type == base.MAX:
                raise NotImplementedError
        if isinstance(concept, OneOf):
            raise NotImplementedError
        if isinstance(concept, ConstrainedDatatype):
            raise NotImplementedError
        if isinstance(concept, PropertyChain):
            raise NotImplementedError
        if rdfs_datatype in [some_class.storid for some_class in concept.is_a]:  # rdfs:Datatype
            return concept.name
        raise NotImplementedError

    def extract_conjunction_phrases(self,
                                    owl_class: ClassConstruct,
                                    definitional_phrases: List[str],
                                    name: str):
        named_class_block = []
        unnamed_class_block = []
        for is_named_class, _group in groupby(owl_class.Classes,
                                              lambda i: self.is_named_class_key(self.concept_group_key(i))):
            if is_named_class:
                for c in _group:
                    named_class_block.append(
                        prefix_with_indefinite_article(self.render_concept(c)))
            else:
                for c in _group:
                    unnamed_class_block.append(self.render_concept(c, anonymous=True))
        if named_class_block and unnamed_class_block:
            prefix = pretty_print_list(named_class_block, and_char=", and ")
            suffix = pretty_print_list(unnamed_class_block, and_char=", and ")
            name_or_pronoun = handle_first_definitional_phrase(definitional_phrases, name)
            definitional_phrases.append(f"{name_or_pronoun} {prefix} that {suffix}")
        elif named_class_block:
            name_or_pronoun = handle_first_definitional_phrase(definitional_phrases, name)
            block_phrase = pretty_print_list(named_class_block, and_char=", and ")
            definitional_phrases.append(f"{name_or_pronoun} {block_phrase}")
        else:
            name_or_pronoun = handle_first_definitional_phrase(definitional_phrases, name)
            phrase = pretty_print_list(unnamed_class_block, and_char=", and ")
            definitional_phrases.append(f"{name_or_pronoun} {phrase}")

    def extract_definitional_phrases(self, definitional_phrases: List, class_iterable, name, handler, klass_id, base_name):
        klass_def_info = handler.definition_info.setdefault(klass_id, {})
        for key, group in groupby(sorted(class_iterable, key=handler.concept_group_key,
                                         reverse=True), key=handler.concept_group_key):
            if handler.is_logical_construct_key(key):
                # Logical construct (It is a/an (A OR B OR C) or It is a/an (A AND B AND C))
                for _class in group:
                    if isinstance(_class, Or):
                        name_or_pronoun = handle_first_definitional_phrase(definitional_phrases, name)
                        disjunction = pretty_print_list([*map(lambda i: prefix_with_indefinite_article(
                            self.render_concept(i)), _class.Classes)],
                                                        and_char=", or ")
                        definitional_phrases.append(f"{name_or_pronoun} is {disjunction}")
                    else:  # Conjunctions
                        self.extract_conjunction_phrases(_class, definitional_phrases, name)
            elif handler.is_restriction_key(key):
                # Restriction block
                for prop_iri, _group in groupby(group, lambda i: i.property.iri):
                    if prop_iri in map(str, PROPERTIES_TO_SKIP):
                        continue
                    cnl_phrase = self.relevant_role_restriction_cnl_phrasing.get(URIRef(prop_iri))
                    custom_render_fn = self.custom_restriction_property_rendering.get(URIRef(prop_iri))
                    if custom_render_fn:
                        custom_render_fn, prompt = custom_render_fn
                        name_or_pronoun = handle_first_definitional_phrase(definitional_phrases, name)
                        for c in _group:
                            try:
                                phrase = custom_render_fn(c.value)
                            except NotImplementedError as e:
                                # print(f"#### Skipping {prop_iri} ({e}) ###")
                                continue
                            else:
                                definitional_phrase = f"{name_or_pronoun} {phrase}"
                                klass_def_info[prompt.format(base_name)] = definitional_phrase
                                definitional_phrases.append(definitional_phrase)
                    elif cnl_phrase:
                        singular_phrase, plural_phrase, prompt = cnl_phrase
                        values = []
                        for c in _group:
                            concept_name = self.render_concept(c.value)
                            values.append(prefix_with_indefinite_article(concept_name)
                                          if URIRef(prop_iri) not in self.role_restriction_wo_articles else concept_name)
                        name_or_pronoun = handle_first_definitional_phrase(definitional_phrases, name)
                        values_list = pretty_print_list(values, and_char=", and ")
                        if callable(singular_phrase):
                            singular_phrase = singular_phrase(values_list)
                            plural_phrase = plural_phrase(values_list)
                        phrase = (plural_phrase if len(values) > 1 else singular_phrase).format(values_list)
                        definitional_phrase = f"{name_or_pronoun} {phrase}"
                        klass_def_info[prompt.format(base_name)] = definitional_phrase
                        definitional_phrases.append(definitional_phrase)
                    else:
                        prop = self.ontology_lookup[prop_iri.split(self.ontology_namespace)[-1]]
                        if not isinstance(prop, DataPropertyClass) and prop.label:
                            # print(f"#### {prop.iri} ###")
                            name_or_pronoun = handle_first_definitional_phrase(definitional_phrases, name)
                            prop_label = str(prop.label[0])
                            values = []
                            for c in _group:
                                if isinstance(c.value, ThingClass) and c.type == HAS_SELF:
                                    if URIRef(prop.iri) in REFLEXIVE_PROPERTY_CUSTOMIZATION:
                                        values.append(REFLEXIVE_PROPERTY_CUSTOMIZATION[URIRef(prop.iri)])
                                    else:
                                        values.append(f"{prop_label} itself")
                                else:
                                    values.append(prefix_with_indefinite_article(
                                        self.render_class_name(c.value)))
                            values_phrase = pretty_print_list(values, and_char=", and ")
                            phrase = f"{prop_label} {values_phrase}"
                            definitional_phrase = f"{name_or_pronoun} {phrase}"
                            klass_def_info[f'What is {base_name} {prop_label}?'] = definitional_phrase
                            definitional_phrases.append(definitional_phrase)
                        else:
                            warnings.warn(f"Unsupported property type: {prop}")
            elif handler.is_named_class_key(key):
                # ThingClass
                for c in group:
                    name_or_pronoun = handle_first_definitional_phrase(definitional_phrases, name)
                    parent_name = self.render_class_name(c, no_indef_article=True)
                    if parent_name is None:
                        continue
                    parent_name = prefix_with_indefinite_article(parent_name)
                    name_or_pronoun = f"{name_or_pronoun} is" if name_or_pronoun == "It" else name_or_pronoun
                    definitional_phrases.append(f"{name_or_pronoun} {parent_name}")

    def handle_class(self, klass: ThingClass) -> str:
        klass_id = klass.iri.split(self.ontology_namespace)[-1]
        klass_name_phrase = f"the {str(klass.label[0])}"
        name = self.render_class_name(klass, capitalize_first_letter=True).strip()
        definitional_phrases = []
        if klass.equivalent_to:
            self.extract_definitional_phrases(definitional_phrases, klass.equivalent_to, name, self, klass_id,
                                              klass_name_phrase)
        if klass.is_a:
            self.extract_definitional_phrases(definitional_phrases, klass.is_a, name, self, klass_id, klass_name_phrase)
        definition = f". ".join(map(str.strip, definitional_phrases))
        return definition

PROPERTIES_TO_SKIP = []
REFLEXIVE_PROPERTY_CUSTOMIZATION = {}

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
SELECT ?klass ?definition {{ 
    {class_expression} 
    OPTIONAL {{ ?klass ?defprop ?definition {def_prop_expression} }} }}"""

def handle_first_definitional_phrase(definitional_phrases, name):
    for ontology_title in default_world.sparql_query(f"SELECT ?ontology_title "
                                                     f"{{ ?ontology a owl:Ontology; dc:title ?ontology_title }}"):
        return "It" if definitional_phrases else f"The {name} is defined in {ontology_title[0]} as"

def run_subprocess(command, verbose = False):
    import subprocess
    if verbose:
        print("Running command: ", ' '.join(command))
    resp = subprocess.run(command, capture_output=verbose)
    if verbose:
        print(resp.stdout.decode("utf-8"))

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
@click.option('--action', '-a', type=Choice(
    ['render_class', 'list_properties', 'load_owl', 'render_all_classes']), required=True,
              help='Action to perform',
              default='render_class')
@click.option('--by-id', is_flag=True, default=False,
              help='Find Uberon class by ID (otherwise by rdfs:label)')
@click.option('--class-reference', help='The ID (or label) of the Uberon class')

@click.option("--semantic-verbosity", default=False, help="Just summarize training data")
@click.option('--verbose/--no-verbose', default=False)
@click.option('--configuration-file', type=str,
              help="Path to configuration YAML file",
              default='ontology_configurations/Uberon.CNL.yaml')
@click.option('--sqlite-file', type=str,
              help="Location of SQLite file (defaults to '/tmp/fma.sqlite3')",
              default='/tmp/uberon.sqlite3')
@click.option('--prefix', type=str,
              help="Filter properties by URI prefix (only for 'list_properties' action)",
              default='')
@click.option('--prop-reference-label', type=str,
              help="Filter properties by label using REGEX (only for 'list_properties' action)",
              default='')
@click.option('--show-property-definition-usage', is_flag=True, default=False,
              help="Show property definition usage references (only for 'list_properties' action)")
@click.option('--limit', type=int, default=1,
              help="Limit number of results (only for 'list_properties' action with --show-property-definition-usage)")
@click.option('--ontology-uri', type=str, required=True,
              help="The URI of the ontology")
@click.option('--ontology-namespace-baseuri', type=str, required=True,
              help="The base URI of the ontology namespace")
@click.argument('owl_file', required=False)
def main(action,
         by_id,
         class_reference,
         semantic_verbosity,
         verbose,
         configuration_file,
         sqlite_file,
         prefix,
         prop_reference_label,
         show_property_definition_usage,
         limit,
         ontology_uri,
         ontology_namespace_baseuri,
         owl_file):
    default_world.set_backend(filename=sqlite_file)
    if action == 'render_class':
        onto = default_world.ontologies[ontology_uri]
        print("Loaded ontology")
        handler = OutputHandler(onto, ontology_namespace_baseuri, verbose=semantic_verbosity)
        definition_properties = setup_configuration(handler, configuration_file)
        class_expression = (f"?klass rdfs:label ?label "
                            f"FILTER(?klass = <{getattr(handler.ontology_lookup, class_reference).iri}>)"
                            if by_id
                            else f"?klass rdfs:label '{class_reference}'")
        prop_conjunction = (' || '.join([f"?defprop = <{p}>" for p in definition_properties]
                                       ) if len(definition_properties) > 1
                            else f"?defprop = <{definition_properties[0]}>" if definition_properties else "")
        def_prop_expression = f"FILTER({prop_conjunction})"
        query = CLASS_AND_THEIR_DEFINITION_SPARQL.format(class_expression=class_expression,
                                                         def_prop_expression=def_prop_expression)
        for klass, definition in default_world.sparql_query(query):
            if definition:
                print(f"Definition: {definition} # ")
        print(f"# {klass.iri} # ")
        print(handler.handle_class(klass))


    elif action == 'render_all_classes':
        onto = default_world.ontologies[ontology_uri]
        print("Loaded ontology")
        for klass in default_world.sparql_query("SELECT DISTINCT ?klass {{ ?klass a owl:Class; rdfs:label ?label }}"):
            klass = klass[0]
            print(f"# {klass.iri} # ")
            try:
                print(OutputHandler(onto, ontology_namespace_baseuri).handle_class(klass))
            except NotImplementedError as e:
                traceback.print_exc()

    elif action == 'list_properties':
        onto = default_world.ontologies[ontology_uri]
        print("Loaded ontology")
        handler = OutputHandler(onto, ontology_namespace_baseuri, verbose=semantic_verbosity)
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
            domain = [get_class_label(d) for d in prop.domain if is_first_class(d)]
            range = [get_class_label(r) for r in prop.range if is_first_class(r)]
            if domain:
                print(f"\t- Domain: {', '.join(domain)}")
            if range:
                print(f"\t- Range: {', '.join(range)}")
            if show_property_definition_usage:
                query = IRI_AND_LABEL_FOR_EXAMPLE_SPARQL.format(
                    filtered_prop=match_object_sparql_expression("prop",
                                                                 [prop.iri],just_filter=True),
                    limit=limit)
                for reference_class, class_label in default_world.sparql_query(query):
                    klass_base_uri, suffix = base_uri(reference_class.iri)
                    klass_label = [l for l in onto.get_namespace(klass_base_uri)[suffix].label
                                  if isinstance(l, str)]
                    klass_label = klass_label[0] if klass_label else None
                    try:
                        klass_definition = handler.handle_class(reference_class) if klass_label else ''
                    except Exception as e:
                        print(f"Error: {e}")
                        klass_definition = None
                    print(f"\n{reference_class.iri} '{klass_label}':")
                    print(f"{klass_definition if klass_definition else ''}")
            print('------'*5)
    elif action == 'load_owl' and owl_file:
        print(f"Loading Uberon ontology from {owl_file}")
        get_ontology(owl_file).load()
        default_world.save()
        print(f"Saved {owl_file}")

def is_first_class(ancestor) -> bool:
    return not isinstance(ancestor, Restriction) and isinstance(ancestor, ThingClass)


def get_class_label(klass: ThingClass) -> str | None:
    labels: IndividualValueList = klass.label
    return next((item for item in labels if isinstance(item, str)), None)


def setup_configuration(handler: OutputHandler, configuration_file: str) -> list[Any] | Any:
    with open(configuration_file, 'r') as file:
        config = yaml.load(file, Loader=Loader)
        reflexive_roles = config['reflexive_roles'] if config['reflexive_roles'] else []
        for role in reflexive_roles:
            for property_uri, phrase in role.items():
                handler.reflexive_property_customizations[URIRef(property_uri)] = phrase[0]

        definition_properties = config['tooling']['expert_definition_properties'] if config['tooling'] else []
        for prop in config['standard_role_restriction_is_phrasing']:
            prop_base_uri, suffix = base_uri(prop)
            prop_label = [label for label in handler.ontology.get_namespace(prop_base_uri)[suffix].label
                          if isinstance(label, str)][0]
            handler.relevant_role_restriction_cnl_phrasing[URIRef(prop)] = (
                                                                       f'is {prop_label} ' + '{}',
                                                                   ) * 2 + ('What is {}' + f' {prop_label}?',)
        for prop_uri, info in config['role_restriction_phrasing'].items():
            handler.relevant_role_restriction_cnl_phrasing[URIRef(prop_uri)] = tuple(info)
    return definition_properties


if __name__ == '__main__':
    main()

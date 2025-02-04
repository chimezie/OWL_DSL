#!/usr/bin/env python
import re
import yaml
from yaml import CLoader as Loader
import json
import click
from itertools import groupby
from pathlib import Path
from rdflib import Namespace, URIRef
from zipfile import ZipFile, ZIP_BZIP2

from owlready2 import (get_namespace, ThingClass, LogicalClassConstruct, Or, And, owl, Construct, EntityClass,
                       PropertyClass, Not, Inverse, Restriction, base, OneOf, ConstrainedDatatype, PropertyChain,
                       rdfs_datatype, DataPropertyClass, default_world, dl_render, sync_reasoner, reasoning, get_ontology)

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except (OSError, ImportError):
    nlp = None

from typing import Dict, Union

SNOMED_ANATOMY_NAME_PATTERN = re.compile(
    r'^(?P<prefix>(Structure of|Entire)\s)?(?P<name>.+)(?P<organ_tag>\s\([^\)]+\)\s)?\(body structure\)$')

FMA = Namespace('http://purl.org/sig/ont/fma/')
FMA_ONT_NS = get_namespace('http://purl.org/sig/ont/fma/')

def pretty_print_list(my_list, sep=", ", and_char=", & "):
    return and_char.join([sep.join(my_list[:-1]), my_list[-1]]) if len(my_list) > 2 else '{} and {}'.format(
        my_list[0], my_list[1]
    ) if len(my_list) == 2 else my_list[0]

def prefix_with_indefinite_article(term, unquoted=True):
    _term = (term if unquoted else f"'{term}'")
    if nlp is not None:
        for token in nlp(term):
            if token.tag_ == 'VBG':
                return _term
    return f"{'an' if term[0].lower() in 'aeiou' else 'a'} " + _term

class OutputHandler:
    LOGICAL_CONSTRUCT_KEY = 1
    RESTRICTION_START_KEY = 2

    def __init__(self, ontology, prompt_field, completion_field, output_path, verbose=False):
        self.prompt_field = prompt_field
        self.completion_field = completion_field
        self.ontology = ontology
        self.fma_definition_info = {}
        self.fma_fine_grained_definition_info = {}
        self.output_path = Path(output_path)
        self.property_iris = [p.iri for p in sorted(self.ontology.properties())]
        self.verbose = verbose

    def is_logical_construct_key(self, key: int):
        return key == self.LOGICAL_CONSTRUCT_KEY

    def is_restriction_key(self, key: int):
        return self.RESTRICTION_START_KEY <= key < self.RESTRICTION_START_KEY + len(self.property_iris)

    def is_named_class_key(self, key: int):
        return self.RESTRICTION_START_KEY + len(self.property_iris)

    def concept_group_key(self, concept: Union[Construct, EntityClass]) -> int:
        if isinstance(concept, LogicalClassConstruct):
            return self.LOGICAL_CONSTRUCT_KEY
        elif isinstance(concept, Restriction):
            # Distinguish restrictions by their owl:onProperty value
            return self.RESTRICTION_START_KEY + self.property_iris.index(concept.property.iri)
        elif isinstance(concept, ThingClass):
            return self.RESTRICTION_START_KEY + len(self.property_iris)
        else:
            raise NotImplemented

    def handle_class(self, klass: ThingClass, store_definitions=True) -> str:
        klass_id = klass.iri.split(FMA)[-1]
        klass_name_phrase = f"the {str(klass.label[0])}"
        name = render_class_name(klass, capitalize_first_letter=True).strip()
        definitional_phrases = []
        if klass.equivalent_to:
            extract_definitional_phrases(definitional_phrases, klass.equivalent_to, name, self, klass_id,
                                         klass_name_phrase)
        if klass.is_a:
            extract_definitional_phrases(definitional_phrases, klass.is_a, name, self, klass_id, klass_name_phrase)
        definition = f". ".join(map(str.strip, definitional_phrases))
        if store_definitions:
            self.fma_definition_info.setdefault(klass_id, {})[f'What is {klass_name_phrase.strip()}?'] = definition
        else:
            if klass_id in self.fma_definition_info:
                del self.fma_definition_info[klass_id]
            if klass_id in self.fma_fine_grained_definition_info:
                del self.fma_fine_grained_definition_info[klass_id]
        return definition

    def process(self):
        output_files = []
        filename = "train.jsonl"
        json_file = (self.output_path / filename)
        entries = []

        num_standard_entries = 0
        num_fine_grained = 0

        for fma_id in [k.iri.split(FMA)[-1] for k in self.ontology.classes()
                       if k.label]:
            klass = getattr(FMA_ONT_NS, fma_id)
            try:
                self.handle_class(klass)
            except NotImplementedError as e:
                print(f"Unable to  handle klass {fma_id}", e)
                raise e

            entries.extend([{self.prompt_field: prompt, self.completion_field: completion}
                            for prompt, completion
                            in self.fma_definition_info[fma_id].items()])
            entries.extend([{self.prompt_field: prompt, self.completion_field: completion}
                            for prompt, completion
                            in self.fma_fine_grained_definition_info[fma_id].items()])
            num_standard_entries += len(self.fma_definition_info[fma_id])
            num_fine_grained += len(self.fma_fine_grained_definition_info[fma_id])

        print(f"Extracted {num_standard_entries:,} full definition training records")
        print(f"Added {num_fine_grained:,} fine-grained definition training records")

        with json_file.open('w') as f:
            for entry in entries:
                json.dump(entry, f)
                f.write('\n')
        print("Wrote", json_file, f"({len(entries):,} entries)")
        output_files.append(filename)
        for written_file in output_files:
            file_no_extension = written_file.split('.')[0]
            bzip_file = self.output_path / f"fma_drift_train-{file_no_extension}.bz2"
            source_file = self.output_path / written_file
            with source_file.open('r'):
                with ZipFile(str(bzip_file), 'w', compression=ZIP_BZIP2) as myzip:
                    myzip.write(str(source_file))
            print("Compressed into", bzip_file)

    def print(self, concept, include_dl_expression=False):
        print(dl_render.dl_render_class_str(concept, {}))
        if include_dl_expression:
            print(dl_render.dl_render_class_str(concept))
        print(self.handle_class(concept, store_definitions=False))
        if self.verbose:
            handled = set()
            for klass, other_klass in default_world.sparql_query(
                    f"SELECT ?s ?other_klass {{ ?s ?p <{concept.iri}> . ?other_klass ?p2 ?s }}"):
                if isinstance(klass, Construct):
                    if other_klass and isinstance(other_klass, EntityClass):
                        print("\t", f"{other_klass.label[0]} ({dl_render.dl_render_concept_str(klass)})")
                        print("\t\t", self.handle_class(other_klass, store_definitions=False), "\n")

                elif isinstance(klass, EntityClass) and klass.iri not in handled:
                    print("\t (specialization)", dl_render.dl_render_concept_str(klass))
                    print("\t\t", self.handle_class(klass, store_definitions=False), "\n")
                    handled.add(klass.iri)


def render_developmental_fusion(concept: Union[Construct, EntityClass]) -> str:
    if isinstance(concept, Restriction):
        other = prefix_with_indefinite_article(render_class_name(concept.value))
        return f"developmentally fuses with {other}"
    else:
        expr = dl_render.dl_render_concept_str(concept)
        raise NotImplementedError(expr)


def render_attributed_development(concept: Union[Construct, EntityClass]) -> str:
    assert isinstance(concept, And)
    process = None
    other_structure = None
    for item in concept.Classes:
        assert isinstance(item, Restriction)
        if item.property == FMA_ONT_NS.development_type:
            process = item.value
        elif item.property == FMA_ONT_NS.related_developmental_entity:
            other_structure = item.value
        else:
            expr = dl_render.dl_render_concept_str(item)
            print(f"Problematic class expression: {expr}")
    related_concept = prefix_with_indefinite_article(render_class_name(other_structure))
    process = prefix_with_indefinite_article(render_class_name(process))
    return f"develops in {process.lower()} into {related_concept}".strip()


def render_orientation_restriction(concept: Union[Construct, EntityClass]) -> str:
    related_object = None
    laterality = None
    coordinate = None
    if isinstance(concept, Restriction):
        if URIRef(concept.property.iri) == FMA.anatomical_coordinate:
            return f"is {concept.value.lower()}"
        else:
            raise NotImplementedError(concept.property.iri)
    elif isinstance(concept, And):
        for item in concept.Classes:
            assert isinstance(item, Restriction)
            if item.property == FMA_ONT_NS.related_object:
                related_object = item.value
            elif item.property == FMA_ONT_NS.laterality:
                laterality = item.value
            else:
                assert item.property == FMA_ONT_NS.anatomical_coordinate
                coordinate = item.value
        related_concept = prefix_with_indefinite_article(render_class_name(related_object))
        if laterality:
            phrase = f"and {coordinate.lower()} to " if coordinate else ""
            return f"is to the {laterality.lower()} of {phrase}{related_concept}".strip()
        else:
            return f"is {coordinate.lower()} to {related_concept}".strip()
    else:
        raise NotImplementedError(repr(concept))

#Special case role that need even more customization in how they are rendered
CUSTOM_RESTRICTION_PROPERTY_RENDERING = {
    FMA.orientation: (render_orientation_restriction,
                      'What is the orientation of {}?'),
    FMA.attributed_development: (render_attributed_development,
                                 'How does {} develop?'),
    FMA.developmental_fusion: (render_developmental_fusion,
                               'What does {} fuse with developmentally?')
}

ROLE_RESTRICTION_WO_ARTICLES = [FMA.has_direct_cell_shape, getattr(FMA, 'inherent_3-D_shape'),
                                FMA.anatomical_entity_observed]

RELEVANT_ROLE_RESTRICTION_CNL_PHRASING = {
    FMA.member_of: (lambda i: 'is an element of {}' if 'a set of' in i else 'is an element of {}',
                    ) * 2 + ('What anatomical set is {} an element of?',),
    getattr(FMA, 'inherent_3-D_shape'): ('has a {} shape',) * 2 + ('What is the shape of {}?',),
}

with (Path(__file__).resolve().parent / "FMA.CNL.yaml").open("r") as file:
    config = yaml.load(file, Loader=Loader)
    for prop_short_name, info in config['role_restriction_phrasing'].items():
        RELEVANT_ROLE_RESTRICTION_CNL_PHRASING[FMA[prop_short_name]] = tuple(info)

    PROPERTIES_TO_SKIP = [FMA[prop_short_name] for prop_short_name in config['skip']]

    for prop in config['standard_role_restriction_is_phrasing']:
        prop_lname = prop.split(FMA)[-1]
        prop_lname = ' '.join(prop_lname.split('_'))
        RELEVANT_ROLE_RESTRICTION_CNL_PHRASING[prop] = (f'is {prop_lname} ' + '{}',
                                                        ) * 2 + ('What is {}' + f' {prop_lname}?',)

def render_class_name(klass: ThingClass, capitalize_first_letter=False, no_indef_article=True) -> str:
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


def render_concept(concept: Union[Construct, EntityClass], anonymous: bool = False) -> str:
    if concept is None:
        raise NotImplemented
    if isinstance(concept, ThingClass):
        if concept is owl.Thing:
            return "Everything"
        if concept is owl.Nothing:
            return "Nothing"
        return render_class_name(concept)
    if isinstance(concept, PropertyClass):
        return concept.name  # TODO: narrative labels for CNL
    if isinstance(concept, LogicalClassConstruct):
        s = []
        for x in concept.Classes:
            if isinstance(x, LogicalClassConstruct):
                s.append("(" + render_concept(x) + ")")
            else:
                s.append(render_concept(x))
        if isinstance(concept, Or):
            return pretty_print_list(s, and_char=", or ")
        if isinstance(concept, And):
            return pretty_print_list(s, and_char=", and ")
    if isinstance(concept, Not):
        raise NotImplemented
    if isinstance(concept, Inverse):
        raise NotImplemented
        # return "%s%s" % (render_concept(concept.property), _DL_SYNTAX.INVERSE)
    if isinstance(concept, Restriction):
        # SOME:
        # VALUE:
        prop_iri = concept.property.iri
        custom_phrases = RELEVANT_ROLE_RESTRICTION_CNL_PHRASING.get(URIRef(prop_iri))
        if concept.type == base.SOME:
            restriction_value = render_class_name(concept.value)
            value_name = prefix_with_indefinite_article(restriction_value)
            # article = value_name.split(' ')[0]
            if custom_phrases:
                return custom_phrases[0].format(value_name)
            else:
                # print(f"#### {prop_iri} {concept.property.name} ###")
                prop_label = str(concept.property.label[0])
                prefix = "" if anonymous else "is "
                rt = f"{prefix}{prop_label} {value_name}"
                return rt
        if concept.type == base.ONLY:
            raise NotImplemented
        if concept.type == base.VALUE:
            return "%s %s .{%s}" % (dl_render._DL_SYNTAX.EXISTS,
                                    render_concept(concept.property),
                                    concept.value.name
                                    if isinstance(concept.value, owl.Thing) else concept.value)
        if concept.type == base.HAS_SELF:
            raise NotImplemented
        if concept.type == base.EXACTLY:
            raise NotImplemented
        if concept.type == base.MIN:
            raise NotImplemented
        if concept.type == base.MAX:
            raise NotImplemented
    if isinstance(concept, OneOf):
        raise NotImplemented
    if isinstance(concept, ConstrainedDatatype):
        raise NotImplemented
    if isinstance(concept, PropertyChain):
        raise NotImplemented
    if rdfs_datatype in [_.storid for _ in concept.is_a]:  # rdfs:Datatype
        return concept.name
    raise NotImplemented


def extract_definitional_phrases(definitional_phrases, class_iterable, name, handler, klass_id, base_name):
    klass_def_info = handler.fma_fine_grained_definition_info.setdefault(klass_id, {})
    for key, group in groupby(sorted(class_iterable, key=handler.concept_group_key,
                                     reverse=True), key=handler.concept_group_key):
        if handler.is_logical_construct_key(key):
            # Logical construct (It is a/an (A OR B OR C) or It is a/an (A AND B AND C))
            for _ in group:
                if isinstance(_, Or):
                    name_or_pronoun = handle_first_definitional_phrase(definitional_phrases, name)
                    disjunction = pretty_print_list(map(lambda i: render_concept(i, {}),
                                                        _.Classes),
                                                    and_char=", or ")
                    definitional_phrases.append(f"{name_or_pronoun} is a/an {disjunction}")
                else:  # Conjunctions
                    extract_conjunction_phrases(_, definitional_phrases, name, handler)
        elif handler.is_restriction_key(key):
            # Restriction block
            for prop_iri, _group in groupby(group, lambda i: i.property.iri):
                if prop_iri in map(str, PROPERTIES_TO_SKIP):
                    continue
                cnl_phrase = RELEVANT_ROLE_RESTRICTION_CNL_PHRASING.get(URIRef(prop_iri))
                custom_render_fn = CUSTOM_RESTRICTION_PROPERTY_RENDERING.get(URIRef(prop_iri))
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
                        concept_name = render_concept(c.value)
                        values.append(prefix_with_indefinite_article(concept_name)
                                      if URIRef(prop_iri) not in ROLE_RESTRICTION_WO_ARTICLES else concept_name)
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
                    prop = FMA_ONT_NS[prop_iri.split(FMA)[-1]]
                    if not isinstance(prop, DataPropertyClass) and prop.label:
                        # print(f"#### {prop.iri} ###")
                        name_or_pronoun = handle_first_definitional_phrase(definitional_phrases, name)
                        prop_label = str(prop.label[0])
                        values = []
                        for c in _group:
                            values.append(prefix_with_indefinite_article(
                                render_class_name(c.value)))
                        values_phrase = pretty_print_list(values, and_char=", and ")
                        phrase = f"{prop_label} {values_phrase}"
                        definitional_phrase = f"{name_or_pronoun} {phrase}"
                        klass_def_info[f'What is {base_name} {prop_label}?'] = definitional_phrase
                        definitional_phrases.append(definitional_phrase)
                    # else:
                    #     print(f"#### Skipping {prop.iri} ###")
        elif handler.is_named_class_key(key):
            # ThingClass
            for c in group:
                name_or_pronoun = handle_first_definitional_phrase(definitional_phrases, name)
                parent_name = render_class_name(c, no_indef_article=True)
                if parent_name is None:
                    continue
                parent_name = prefix_with_indefinite_article(parent_name)
                definitional_phrases.append(f"{name_or_pronoun} {parent_name}" if '(FMA)' in name_or_pronoun
                                            else f"{name_or_pronoun} is {parent_name}".strip())


def extract_conjunction_phrases(_, definitional_phrases, name, handler):
    named_class_block = []
    unnamed_class_block = []
    for is_named_class, _group in groupby(_.Classes,
                                          lambda i: handler.is_named_class_key(handler.concept_group_key(i))):
        if is_named_class:
            for c in _group:
                named_class_block.append(
                    prefix_with_indefinite_article(render_concept(c, {})))
        else:
            for c in _group:
                unnamed_class_block.append(render_concept(c, {}, anonymous=True))
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


def handle_first_definitional_phrase(definitional_phrases, name):
    return "It" if definitional_phrases else f"The {name} is defined in the Foundational Model Anatomy (FMA) as"

def fma_owl_names(owl_class):
    return set(map(str, owl_class.label)).union(set(map(str, owl_class.synonym)))


def export_mapping(classify, reasoner_memory, semantic_verbosity, prompt_field, completion_field, output_path,
                   sqlite_file, verbose):
    onto = default_world.ontologies["http://purl.org/sig/ont/fma.owl#"]
    print("Loaded ontology")
    if classify:
        reasoning.JAVA_MEMORY = reasoner_memory
        with onto:
            sync_reasoner()
        print("Classified ontology")
    handler = OutputHandler(onto, prompt_field, completion_field, output_path, verbose=semantic_verbosity)
    handler.process()

@click.command()
@click.option('--classify/--no-classify', default=False)
@click.option('--reasoner-memory', type=int,
              help='How much Java Heap space to allocate for reasoner (Hermit)', default=2000)
@click.option("--semantic-verbosity", default=False, help="Just summarize training data")
@click.option('--verbose/--no-verbose', default=False)
@click.option('--prompt-field', type=str,  help="The field name for the prompt (defaults to 'prompt')",
              default='prompt')
@click.option('--completion-field', type=str,
              help="The field name for the prompt (defaults to 'completion')",
              default='completion')
@click.option('--output-path', type=str,
              help="The location where to write the output (defaults to '/tmp')",
              default='/tmp')
@click.option('--sqlite-file', type=str,
              help="Location of SQLite file (defaults to '/tmp/fma.sqlite3')",
              default='/tmp/fma.sqlite3')
@click.argument('owl_file', required=False)
def main(classify, reasoner_memory, semantic_verbosity, verbose, prompt_field, completion_field, output_path,
         sqlite_file, owl_file):
    default_world.set_backend(filename=sqlite_file)
    if owl_file:
        # owl_path = "file:///home/chimezie/PDGM-files/FMA.owl"
        print(f"Loading FMA ontology from {owl_file}")
        get_ontology(owl_file).load()
        default_world.save()
        print(f"Saved {owl_file} to {sqlite_file}")
    else:
        export_mapping(classify, reasoner_memory, semantic_verbosity, prompt_field, completion_field, output_path,
                       sqlite_file, verbose)

if __name__ == '__main__':
    main()

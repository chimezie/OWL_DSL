import warnings
from itertools import groupby
from typing import Union, List, Iterable

from owlready2 import Ontology, get_namespace, default_world, Construct, EntityClass, LogicalClassConstruct, \
    Restriction, ThingClass, Not, owl, PropertyClass, Or, And, Inverse, base, OneOf, ConstrainedDatatype, PropertyChain, \
    rdfs_datatype, ClassConstruct, DataPropertyClass, HAS_SELF, ObjectPropertyClass
from rdflib import Namespace, URIRef

from owl_dsl import pretty_print_list, prefix_with_indefinite_article

PROPERTIES_TO_SKIP = []

class CNLRenderer:
    """
    Handles NL generation of readable representations of ontology classes and properties.

    Attributes:
        ontology (Ontology): The ontology to process.
        definition_info (dict): A dictionary in which to store definitional phrases for LLM training data.
        property_iris (list): List of property IRIs in the ontology.
        verbose (bool): Whether to print verbose output.
        ontology_namespace (Namespace): rdflib.Namespace of the ontology.
        reflexive_property_customizations (dict): Dictionary mapping reflexive property IRIs to custom rendering.
        relevant_role_restriction_cnl_phrasing (dict): Dictionary mapping property IRIs to CNL phrases.
        custom_restriction_property_rendering (dict): Mapping property IRIs to custom NL rendering functions.
        role_restriction_wo_articles (set): Property IRIs for whom should not be prefixed with indefinate articles
        custom_role_rendering (bool): Whether to use custom role rendering for CNL phrases (uses DL form instead).
        ontology_title (str): Title of the ontology.
    """
    #Used to help group common constructs together for rendering purposes
    LOGICAL_COMPLEMENT_KEY = 0
    LOGICAL_CONSTRUCT_KEY = 1
    RESTRICTION_START_KEY = 2

    def __init__(self,
                 ontology: Ontology,
                 ontology_namespace: str,
                 verbose:bool = False,
                 custom_role_rendering:bool = True,
                 lowercase_labels: bool = True):
        self.ontology = ontology
        self.definition_info = {}
        self.property_iris = [p.iri for p in sorted(self.ontology.properties())]
        self.verbose = verbose
        self.ontology_namespace = Namespace(ontology_namespace)
        self.ontology_lookup = get_namespace(self.ontology_namespace)
        self.reflexive_property_customizations = {}
        self.relevant_role_restriction_cnl_phrasing = {}
        self.custom_restriction_property_rendering = {}
        self.reflexive_property_customization = {}
        self.role_restriction_wo_articles = set()
        self.custom_role_rendering = custom_role_rendering
        self.class_inference_to_ignore = []
        self.ontology_title = None
        self.lowercase_labels = lowercase_labels
        for (title,) in default_world.sparql_query(f"SELECT ?ontology_title "
                                                         f"{{ ?ontology a owl:Ontology; dc:title ?ontology_title }}"):
            self.ontology_title = title

    def is_logical_construct_key(self, key: int) -> bool:
        """
        Determines if the provided key is for a logical construct
        """
        return key == self.LOGICAL_CONSTRUCT_KEY

    def is_restriction_key(self, key: int) -> bool:
        """
        Determines if the provided key is for a restriction
        """
        return self.RESTRICTION_START_KEY <= key < self.RESTRICTION_START_KEY + len(self.property_iris)

    def is_named_owl_class_key(self, key: int) -> bool:
        """
        Determines if the provided key is for a named OWL class
        """
        return key >= self.RESTRICTION_START_KEY + len(self.property_iris)

    def concept_group_key(self, concept: Union[Construct, EntityClass]) -> int:
        """
        Determines the group key for a concept based on its type
        """
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

    def handle_first_definitional_phrase(self, definitional_phrases: List[str], name: str) -> str:
        """
        Returns rendering of a name based on if it is the first definitional phrase and the ontology title, if present

        :param definitional_phrases: A list of strings representing the definitional phrases
            used to define the entity.
        :param name: The name of the entity being defined.
        :return: A string representing the reformulated sentence based on the provided
            definitional phrases and the presence or absence of an ontology title.
        """
        if self.ontology_title:
            return "It" if definitional_phrases else f"The {name} is defined in {self.ontology_title} as"
        else:
            return "It" if definitional_phrases else f"The {name} is defined as"

    def render_readable_owl_class(self,
                                  owl_class: ThingClass,
                                  capitalize_first_letter = False,
                                  no_indef_article = True) -> str:
        """
        Renders an OWL class based on specified configuration options. The function handles both simple
        OWL classes as well as logical class constructs. The main principle of how it is rendering is English
        grammar rules as well best practices from the study of Controlled Natural Languages (CNL) for OWL

        :param owl_class: The OWL class, which can be a basic `ThingClass` or a `LogicalClassConstruct` defining a set
            of combined logical classes.
        :type owl_class: ThingClass | LogicalClassConstruct
        :param capitalize_first_letter: If True, capitalizes the first letter of the generated name. Defaults to False.
        :type capitalize_first_letter: bool
        :param no_indef_article: If True, suppresses the use of an indefinite article prefix when generating the class name.
            Defaults to True.
        :type no_indef_article: bool
        :return: A formatted string representation of the OWL class name, adjusted according to the specified options.
        :rtype: str
        """
        if isinstance(owl_class, LogicalClassConstruct):
            owl_class_names = [self.render_owl_class(c) for c in owl_class.Classes]
            if len(owl_class_names) == 0:
                return self.render_owl_class(owl_class)
            elif len(owl_class_names) == 1:
                return owl_class_names[0]
            elif len(owl_class_names) == 2:
                return f"{owl_class_names[0]} that {owl_class_names[1]}"
            else:
                # First and second joined with ' that ', rest joined with ' and '
                result = f"{owl_class_names[0]} that {owl_class_names[1]}"
                return result + f" and {pretty_print_list(owl_class_names[2:], and_char = ', and ')}"
        else:
            if owl_class.label:
                owl_class_label = owl_class.label[0]
                if no_indef_article:
                    name = f"{owl_class_label}"
                else:
                    prefixed_name = prefix_with_indefinite_article(owl_class_label).capitalize()
                    name = prefixed_name
            else:
                name = "" if no_indef_article else f"the {str(owl_class.label[0])}"
            if name.strip():
                name = name if capitalize_first_letter else (name[0].lower() if self.lowercase_labels
                                                             else name[0]) + name[1:]
            else:
                name = None
            return name
    def render_owl_class(self, owl_class: Union[Construct, EntityClass], anonymous: bool = False) -> str:
        """
        Renders an OWL class into a string representation based on its type and structure, using owlready2 to
        handle the structure of a variety of OWL constructs.  Derived from owlready2's dl_render_concept_str

        :param owl_class: The OWL class construct to be rendered. Supported types include `ThingClass`,
            `PropertyClass`, `LogicalClassConstruct`, and `Restriction`. The value provides the structure
            and semantics of the OWL class.
        :type owl_class: Union[Construct, EntityClass]
        :param anonymous: Determines whether the rendered OWL class should be treated as anonymous.
            When set to `True`, the rendering assumes anonymity (e.g., hiding prefixes like 'is').
        :type anonymous: bool, optional
        :return: A string representation of the provided OWL class construct, formatted either in a
            human-readable or structured format depending on its type.
        :rtype: str
        """
        if owl_class is None:
            raise NotImplementedError
        if isinstance(owl_class, ThingClass):
            if owl_class is owl.Thing:
                return "Everything"
            if owl_class is owl.Nothing:
                return "Nothing"
            return self.render_readable_owl_class(owl_class)
        if isinstance(owl_class, PropertyClass):
            return owl_class.name
        if isinstance(owl_class, LogicalClassConstruct):
            s = []
            for x in owl_class.Classes:
                if isinstance(x, LogicalClassConstruct):
                    s.append("(" + self.render_owl_class(x) + ")")
                else:
                    s.append(self.render_owl_class(x))
            if isinstance(owl_class, Or):
                return pretty_print_list(s, and_char = ", or ")
            if isinstance(owl_class, And):
                return pretty_print_list(s, and_char = ", and ")
        if isinstance(owl_class, Not):
            raise NotImplementedError
        if isinstance(owl_class, Inverse):
            raise NotImplementedError
            # return "%s%s" % (render_concept(concept.property), _DL_SYNTAX.INVERSE)
        if isinstance(owl_class, Restriction):
            # SOME:
            # VALUE:
            prop_iri = owl_class.property.iri
            custom_phrases = self.relevant_role_restriction_cnl_phrasing.get(URIRef(prop_iri))
            if owl_class.type == base.SOME:
                restriction_value = self.render_readable_owl_class(owl_class.value)
                value_name = prefix_with_indefinite_article(restriction_value)
                if custom_phrases and self.custom_role_rendering:
                    return custom_phrases[0].format(value_name)
                elif len(owl_class.property.label):
                    prop_label = str(owl_class.property.label[0])
                    prefix = "" if anonymous else "is "
                    rt = f"{prefix}{prop_label} {value_name}"
                    return rt
                else:
                    return "something"
            if owl_class.type == base.ONLY:
                raise NotImplementedError
            if owl_class.type == base.VALUE:
                return "%s .{%s}" % (self.render_owl_class(owl_class.property),
                                     owl_class.value.name
                                     if isinstance(owl_class.value, owl.Thing) else owl_class.value)
            if owl_class.type == base.HAS_SELF:
                raise NotImplementedError
            if owl_class.type == base.EXACTLY:
                prop_label = str(owl_class.property.label[0])
                prefix = "" if anonymous else "is "
                return (f"{prefix}{prop_label} exactly {owl_class.cardinality} "
                        f"{self.render_readable_owl_class(owl_class.value)}")

            if owl_class.type == base.MIN:
                prop_label = str(owl_class.property.label[0])
                prefix = "" if anonymous else "is "
                return (f"{prefix}{prop_label} at least {owl_class.cardinality} "
                        f"{self.render_readable_owl_class(owl_class.value)}")
            if owl_class.type == base.MAX:
                raise NotImplementedError
        if isinstance(owl_class, OneOf):
            raise NotImplementedError
        if isinstance(owl_class, ConstrainedDatatype):
            raise NotImplementedError
        if isinstance(owl_class, PropertyChain):
            raise NotImplementedError
        if rdfs_datatype in [some_owl_class.storid for some_owl_class in owl_class.is_a]:  # rdfs:Datatype
            return owl_class.name
        raise NotImplementedError

    def extract_conjunction_phrases(self,
                                    owl_class: ClassConstruct,
                                    definitional_phrases: List[str],
                                    name: str):
        """
        Extracts and organizes conjunction phrases based on an OWL class structure. The method processes
        instances of the provided OWL class to categorize and aggregate named and unnamed class blocks,
        constructing definitional phrases that are appended to the provided list. The output phrases are
        formulated to describe relationships in the OWL class in natural language.

        :param owl_class: An instance of ClassConstruct representing the OWL class structure from which
            conjunction phrases will be extracted.
        :param definitional_phrases: A list of strings to which the resulting definitional phrases will
            be appended.
        :param name: A string representing the name of the concept, used as a base in building phrases.
        :return: None
        """
        named_owl_class_block = []
        unnamed_owl_class_block = []
        for is_named_owl_class, _group in groupby(owl_class.Classes,
                                              lambda i: self.is_named_owl_class_key(self.concept_group_key(i))):
            if is_named_owl_class:
                for owl_class in _group:
                    named_owl_class_block.append(
                        prefix_with_indefinite_article(self.render_owl_class(owl_class)))
            else:
                for owl_class in _group:
                    unnamed_owl_class_block.append(self.render_owl_class(owl_class, anonymous = True))
        if named_owl_class_block and unnamed_owl_class_block:
            prefix = pretty_print_list(named_owl_class_block, and_char = ", and ")
            suffix = pretty_print_list(unnamed_owl_class_block, and_char = ", and ")
            name_or_pronoun = self.handle_first_definitional_phrase(definitional_phrases, name)
            definitional_phrases.append(f"{name_or_pronoun} {prefix} that {suffix}")
        elif named_owl_class_block:
            name_or_pronoun = self.handle_first_definitional_phrase(definitional_phrases, name)
            block_phrase = pretty_print_list(named_owl_class_block, and_char = ", and ")
            definitional_phrases.append(f"{name_or_pronoun} {block_phrase}")
        else:
            name_or_pronoun = self.handle_first_definitional_phrase(definitional_phrases, name)
            phrase = pretty_print_list(unnamed_owl_class_block, and_char = ", and ")
            definitional_phrases.append(f"{name_or_pronoun} {phrase}")

    def extract_definitional_phrases(self,
                                     definitional_phrases: List,
                                     owl_classes: Iterable[ClassConstruct],
                                     owl_class_definition: str,
                                     owl_class_id: str,
                                     owl_class_name_phrase):
        """
        Extract definitional phrases from a given set of OWL classes, and construct descriptive
        English sentences that express the relationships and logical constructs among the
        classes. The method organizes OWL classes into logical constructs (disjunctions and
        conjunctions) or restriction relationships (properties and their respective values),
        and generates natural language descriptions accordingly. It supports custom rendering
        of certain properties or restrictions.

        :param definitional_phrases: A list to store the generated definitional phrases.
        :param owl_classes: An iterable of OWL classes or constructs to extract
            definitional phrases from.
        :param owl_class_definition: A textual definition or description of the OWL class
            being processed.
        :param owl_class_id: The unique identifier (IRI) of the OWL class being processed.
        :param owl_class_name_phrase: A human-readable name or phrase that identifies the
            OWL class being processed.
        :return: None.
        """
        owl_class_def_info = self.definition_info.setdefault(owl_class_id, {})
        for key, group in groupby(sorted(owl_classes, key=self.concept_group_key,
                                         reverse=True), key=self.concept_group_key):
            if self.is_logical_construct_key(key):
                # Logical construct (It is a/an (A OR B OR C) or It is a/an (A AND B AND C))
                for owl_class in group:
                    if isinstance(owl_class, Or):
                        name_or_pronoun = self.handle_first_definitional_phrase(definitional_phrases,
                                                                                owl_class_definition)
                        disjunction = pretty_print_list([*map(lambda i: prefix_with_indefinite_article(
                            self.render_owl_class(i)), owl_class.Classes)],
                                                        and_char = ", or ")
                        definitional_phrases.append(f"{name_or_pronoun} is {disjunction}")
                    else:  # Conjunctions
                        self.extract_conjunction_phrases(owl_class, definitional_phrases, owl_class_definition)
            elif self.is_restriction_key(key):
                # Restriction block
                for prop_iri, _group in groupby(group, lambda i: i.property.iri):
                    if prop_iri in map(str, PROPERTIES_TO_SKIP):
                        continue
                    cnl_phrase = self.relevant_role_restriction_cnl_phrasing.get(URIRef(prop_iri))
                    custom_render_fn = self.custom_restriction_property_rendering.get(URIRef(prop_iri))
                    if custom_render_fn:
                        custom_render_fn, prompt = custom_render_fn
                        name_or_pronoun = self.handle_first_definitional_phrase(definitional_phrases, owl_class_definition)
                        for owl_class in _group:
                            try:
                                phrase = custom_render_fn(owl_class.value)
                            except NotImplementedError as e:
                                # print(f"#### Skipping {prop_iri} ({e}) ###")
                                continue
                            else:
                                definitional_phrase = f"{name_or_pronoun} {phrase}"
                                owl_class_def_info[prompt.format(owl_class_name_phrase)] = definitional_phrase
                                definitional_phrases.append(definitional_phrase)
                    elif cnl_phrase:
                        singular_phrase, plural_phrase, prompt = cnl_phrase
                        values = []
                        for owl_class in _group:
                            concept_name = self.render_owl_class(owl_class.value)
                            values.append(prefix_with_indefinite_article(concept_name)
                                          if URIRef(prop_iri) not in self.role_restriction_wo_articles else concept_name)
                        name_or_pronoun = self.handle_first_definitional_phrase(definitional_phrases, owl_class_definition)
                        values_list = pretty_print_list(values, and_char = ", and ")
                        if callable(singular_phrase):
                            singular_phrase = singular_phrase(values_list)
                            plural_phrase = plural_phrase(values_list)
                        phrase = (plural_phrase if len(values) > 1 else singular_phrase).format(values_list)
                        definitional_phrase = f"{name_or_pronoun} {phrase}"
                        owl_class_def_info[prompt.format(owl_class_name_phrase)] = definitional_phrase
                        definitional_phrases.append(definitional_phrase)
                    else:
                        prop = self.ontology.search(iri=prop_iri)[0]
                        if not isinstance(prop, DataPropertyClass) and prop.label:
                            # print(f"#### {prop.iri} ###")
                            name_or_pronoun = self.handle_first_definitional_phrase(definitional_phrases, owl_class_definition)
                            prop_label = str(prop.label[0])
                            values = []
                            for owl_class in _group:
                                if isinstance(owl_class.value, ThingClass) and owl_class.type == HAS_SELF:
                                    if URIRef(prop.iri) in self.reflexive_property_customization:
                                        values.append(self.reflexive_property_customization[URIRef(prop.iri)])
                                    else:
                                        values.append(f"{prop_label} itself")
                                else:
                                    values.append(prefix_with_indefinite_article(
                                        self.render_readable_owl_class(owl_class.value)))
                            values_phrase = pretty_print_list(values, and_char = ", and ")
                            phrase = f"{prop_label} {values_phrase}"
                            definitional_phrase = f"{name_or_pronoun} {phrase}"
                            owl_class_def_info[f'What is {owl_class_name_phrase} {prop_label}?'] = definitional_phrase
                            definitional_phrases.append(definitional_phrase)
                        else:
                            warnings.warn(f"Unsupported property type: {prop}")
            elif self.is_named_owl_class_key(key):
                # ThingClass
                for owl_class in group:
                    name_or_pronoun = self.handle_first_definitional_phrase(definitional_phrases, owl_class_definition)
                    parent_name = self.render_readable_owl_class(owl_class, no_indef_article = True)
                    if parent_name is None:
                        continue
                    parent_name = prefix_with_indefinite_article(parent_name)
                    name_or_pronoun = f"{name_or_pronoun} is" if name_or_pronoun == "It" else name_or_pronoun
                    definitional_phrases.append(f"{name_or_pronoun} {parent_name}")

    def handle_owl_class(self, owl_class: ThingClass) -> str:
        """
        Generate a human-readable definition for an OWL class

        :param owl_class: The OWL class to be processed, represented as a ``ThingClass``
            object. Contains attributes such as `iri`, `label`, `equivalent_to`, and `is_a`.
        :return: A string representing a human-readable definition of the provided OWL
            class based on its ontology relationships and definitional phrases.
        :rtype: str
        """
        owl_class_id = owl_class.iri.split(self.ontology_namespace)[-1]
        owl_class_name_phrase = f"the {str(owl_class.label[0])}"
        owl_class_definition = self.render_readable_owl_class(owl_class, capitalize_first_letter = True).strip()
        definitional_phrases = []
        if owl_class.equivalent_to:
            self.extract_definitional_phrases(definitional_phrases,
                                              owl_class.equivalent_to,
                                              owl_class_definition,
                                              owl_class_id,
                                              owl_class_name_phrase)
        if owl_class.is_a:
            self.extract_definitional_phrases(definitional_phrases,
                                              owl_class.is_a,
                                              owl_class_definition,
                                              owl_class_id,
                                              owl_class_name_phrase)
        definition = f". ".join(map(str.strip, definitional_phrases))
        return definition

    def render_role_restriction(self,
                                object_property_owl_class: ObjectPropertyClass,
                                operand1: str = "A",
                                operand2: str = "B") -> str:
        custom_phrases = self.relevant_role_restriction_cnl_phrasing.get(URIRef(object_property_owl_class.iri))
        if custom_phrases and self.custom_role_rendering:
            property_phrase = f"{operand1} {custom_phrases[0].format(operand2)}"
        else:
            property_phrase = f"{operand1} '{str(object_property_owl_class.label[0])}' {operand2}"
        return property_phrase


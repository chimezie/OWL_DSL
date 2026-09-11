"""CNL (Controlled Natural Language) rendering for OWL ontologies.

This module provides the `CNLRenderer` class, which transforms complex OWL 2
ontology class expressions into human-readable English sentences using
py-horned-owl (a Rust-backed, axiom-centric OWL model).
"""

import warnings
import os
from itertools import groupby
from typing import Union, List, Iterable, Any, Tuple, Optional

from pyhornedowl import PyIndexedOntology
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
    SimpleLiteral,
    LanguageLiteral,
    DatatypeLiteral,
    SubClassOf,
    EquivalentClasses,
    AnnotationAssertion,
    Annotation,
    AnnotationProperty as AnnProp,
    DeclareClass,
    DeclareObjectProperty,
    DeclareDataProperty,
    SymmetricObjectProperty,
    TransitiveObjectProperty,
    ReflexiveObjectProperty,
    FunctionalObjectProperty,
    InverseFunctionalObjectProperty,
    IrreflexiveObjectProperty,
    AsymmetricObjectProperty,
    OntologyAnnotation,
    DataIntersectionOf,
    DataUnionOf,
    DataComplementOf,
    DataOneOf,
)
from rdflib import Namespace, URIRef

from owl_dsl import pretty_print_list, prefix_with_indefinite_article

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
SKOS_PREFLABEL = "http://www.w3.org/2004/02/skos/core#prefLabel"
OWL_THING = "http://www.w3.org/2002/07/owl#Thing"
OWL_NOTHING = "http://www.w3.org/2002/07/owl#Nothing"
DC_TITLE = "http://purl.org/dc/elements/1.1/title"

XSD_TYPES = frozenset(
    {
        "http://www.w3.org/2001/XMLSchema#string",
        "http://www.w3.org/2001/XMLSchema#integer",
        "http://www.w3.org/2001/XMLSchema#decimal",
        "http://www.w3.org/2001/XMLSchema#float",
        "http://www.w3.org/2001/XMLSchema#double",
        "http://www.w3.org/2001/XMLSchema#boolean",
        "http://www.w3.org/2001/XMLSchema#dateTime",
        "http://www.w3.org/2001/XMLSchema#anyURI",
        "http://www.w3.org/2000/01/rdf-schema#Literal",
        "http://www.w3.org/2002/07/owl#real",
        "http://www.w3.org/2002/07/owl#rational",
    }
)

_OBJECT_RESTRICTION_TYPES = (
    ObjectSomeValuesFrom,
    ObjectAllValuesFrom,
    ObjectHasValue,
    ObjectHasSelf,
    ObjectMinCardinality,
    ObjectMaxCardinality,
    ObjectExactCardinality,
)

_DATA_RESTRICTION_TYPES = (
    DataSomeValuesFrom,
    DataAllValuesFrom,
    DataHasValue,
    DataMinCardinality,
    DataMaxCardinality,
    DataExactCardinality,
)

_RESTRICTION_TYPES = _OBJECT_RESTRICTION_TYPES + _DATA_RESTRICTION_TYPES

_PROPERTIES_TO_SKIP = []

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _is_restriction(expr) -> bool:
    """Return True if *expr* is any OWL restriction type (object or data)."""
    return isinstance(expr, _RESTRICTION_TYPES)


def _is_object_restriction(expr) -> bool:
    return isinstance(expr, _OBJECT_RESTRICTION_TYPES)


def _is_data_restriction(expr) -> bool:
    return isinstance(expr, _DATA_RESTRICTION_TYPES)


def _get_property_expr(expr):
    """Return the property expression from *expr*.

    ObjectHasSelf stores the property at ``.first``; object restrictions
    at ``.ope``; data restrictions at ``.dp``.
    """
    if isinstance(expr, ObjectHasSelf):
        return expr.first
    if _is_object_restriction(expr):
        return expr.ope
    if _is_data_restriction(expr):
        return expr.dp
    return None


def _get_property_iri(expr) -> str | None:
    """Return the property IRI string from *expr*.

    Handles the InverseObjectProperty double-unwrap automatically.
    """
    pe = _get_property_expr(expr)
    if pe is None:
        return None
    if isinstance(pe, InverseObjectProperty):
        return str(pe.first.first)
    return str(pe.first)


def _get_filler(expr):
    """Return the filler (value) from *expr*.

    For ``ObjectHasValue`` returns the ``.i`` (Individual);
    for ``DataHasValue`` returns the ``.l`` (Literal);
    for data-range restrictions returns ``.dr`` (DataRange);
    for object restrictions with a filler returns ``.bce``.

    ``ObjectHasSelf`` has no filler -- returns None.
    """
    if isinstance(expr, ObjectHasValue):
        return expr.i
    if isinstance(expr, DataHasValue):
        return expr.l
    if isinstance(
        expr,
        (
            DataSomeValuesFrom,
            DataAllValuesFrom,
            DataMinCardinality,
            DataMaxCardinality,
            DataExactCardinality,
        ),
    ):
        return expr.dr
    if isinstance(expr, ObjectHasSelf):
        return None
    if hasattr(expr, "bce"):
        return expr.bce
    return None


def _get_cardinality(expr) -> int | None:
    """Return the cardinality integer from cardinality restrictions, else None."""
    if isinstance(
        expr,
        (
            ObjectMinCardinality,
            ObjectMaxCardinality,
            ObjectExactCardinality,
            DataMinCardinality,
            DataMaxCardinality,
            DataExactCardinality,
        ),
    ):
        return expr.n
    return None


def _get_local_name(iri_str: str) -> str:
    """Return the local name (the part after ``#`` or ``/``) from an IRI string."""
    if "#" in iri_str:
        return iri_str.rsplit("#", 1)[-1]
    if "/" in iri_str:
        return iri_str.rsplit("/", 1)[-1]
    return iri_str


def _literal_to_py(lit):
    """Convert a py-horned-owl Literal to its Python value (string)."""
    if isinstance(lit, (SimpleLiteral, LanguageLiteral, DatatypeLiteral)):
        return lit.literal
    return str(lit)


# ---------------------------------------------------------------------------
# CNLRenderer
# ---------------------------------------------------------------------------


class CNLRenderer:
    """
    Transforms OWL ontology classes and properties into Controlled Natural Language (CNL).

    The CNLRenderer analyzes the structure of OWL classes (including their
    logical definitions and restrictions) and generates natural English
    descriptions. It supports custom phrasing for specific properties to
    ensure the output is domain-appropriate.

    Attributes:
        ontology (PyIndexedOntology | None): The py-horned-owl ontology
            being rendered.
        definition_info (dict): Storage for definitional phrases, useful
            for generating LLM training data.
        property_iris (list): A list of all property IRIs discovered in
            the ontology.
        verbose (bool): If True, enables detailed logging of the rendering
            process.
        ontology_namespace (Namespace): The rdflib Namespace for the
            ontology.
        reflexive_property_customizations (dict): Custom strings for
            reflexive properties (e.g., "itself").
        relevant_role_restriction_cnl_phrasing (dict): Custom templates
            for rendering specific role restrictions.
        custom_restriction_property_rendering (dict): Functions for
            bespoke rendering of specific properties.
        role_restriction_wo_articles (set): Properties that should not be
            prefixed with "a" or "an".
        custom_role_rendering (bool): Whether to use the custom CNL
            phrases or fall back to DL-style rendering.
        ontology_title (str | None): The title of the ontology, used to
            provide context in generated sentences.
    """

    LOGICAL_COMPLEMENT_KEY = 0
    LOGICAL_CONSTRUCT_KEY = 1
    RESTRICTION_START_KEY = 2

    def __init__(
        self,
        ontology: PyIndexedOntology | None,
        ontology_namespace: str,
        verbose: bool = False,
        custom_role_rendering: bool = True,
        lowercase_labels: bool = True,
        collect_definition_info: bool | None = None,
    ):
        self.ontology = ontology
        self.definition_info = {}
        if self.ontology is not None:
            self.property_iris = self._get_all_property_iris()
            self.property_iri_index = {
                prop_iri: index for index, prop_iri in enumerate(self.property_iris)
            }
        else:
            self.property_iris = []
            self.property_iri_index = {}
        self.verbose = verbose
        self.ontology_namespace = Namespace(ontology_namespace)
        self.reflexive_property_customizations = {}
        self.relevant_role_restriction_cnl_phrasing = {}
        self.custom_restriction_property_rendering = {}
        self.reflexive_property_customization = {}
        self.role_restriction_wo_articles = set()
        self.custom_role_rendering = custom_role_rendering
        self.class_inference_to_ignore = []
        self.ontology_title = None
        self.lowercase_labels = lowercase_labels
        if collect_definition_info is None:
            collect_definition_info = (
                os.environ.get("OWL_DSL_COLLECT_DEFINITION_INFO", "1") != "0"
            )
        self.collect_definition_info = collect_definition_info
        self._entity_by_iri = {}
        if self.ontology is not None:
            self._load_ontology_title()

    def _load_ontology_title(self):
        """Scan ontology components for ``dc:title``."""
        for c in self.ontology.get_components():
            match c.component:
                case OntologyAnnotation(ann):
                    if str(ann.ap.first) == DC_TITLE:
                        if isinstance(ann.av, (SimpleLiteral, LanguageLiteral)):
                            self.ontology_title = ann.av.literal
                            return

    def _get_all_property_iris(self) -> List[str]:
        """Retrieve all property IRIs defined within the ontology.

        Returns the sorted union of declared object, data, and annotation
        property IRIs, plus properties declared via characteristic axioms
        (SymmetricProperty, TransitiveProperty, etc.).
        """
        result: set[str] = set()
        result.update(self.ontology.get_object_properties())
        result.update(self.ontology.get_data_properties())
        result.update(self.ontology.get_annotation_properties())
        for ac in self.ontology.get_axioms():
            match ac.component:
                case SymmetricObjectProperty(p):
                    result.add(str(p.first))
                case TransitiveObjectProperty(p):
                    result.add(str(p.first))
                case ReflexiveObjectProperty(p):
                    result.add(str(p.first))
                case FunctionalObjectProperty(p):
                    result.add(str(p.first))
                case InverseFunctionalObjectProperty(p):
                    result.add(str(p.first))
                case IrreflexiveObjectProperty(p):
                    result.add(str(p.first))
                case AsymmetricObjectProperty(p):
                    result.add(str(p.first))
        return sorted(result)

    def is_logical_construct_key(self, key: int) -> bool:
        """Check if the given key represents a logical construct (AND, OR, NOT)."""
        return key == self.LOGICAL_CONSTRUCT_KEY

    def is_restriction_key(self, key: int) -> bool:
        """Check if the given key represents an OWL property restriction."""
        return (
            self.RESTRICTION_START_KEY
            <= key
            < self.RESTRICTION_START_KEY + len(self.property_iris)
        )

    def is_named_owl_class_key(self, key: int) -> bool:
        """Check if the given key represents a named OWL class."""
        return key >= self.RESTRICTION_START_KEY + len(self.property_iris)

    def concept_group_key(self, concept) -> int:
        """Assign a group key to a concept to facilitate sorted grouping.

        Args:
            concept: A py-horned-owl expression (Class, ObjectIntersectionOf,
                restriction, etc.).

        Returns:
            An integer key used for grouping and sorting.

        Raises:
            ValueError: If the property IRI of a restriction is not indexed.
            NotImplementedError: If the concept type is not supported.
        """
        if isinstance(concept, (ObjectIntersectionOf, ObjectUnionOf)):
            return self.LOGICAL_CONSTRUCT_KEY
        if _is_restriction(concept):
            prop_iri = _get_property_iri(concept)
            if prop_iri is None:
                raise ValueError("Could not extract property IRI from restriction")
            prop_index = self.property_iri_index.get(prop_iri)
            if prop_index is None:
                raise ValueError(f"Property IRI not found: {prop_iri}")
            return self.RESTRICTION_START_KEY + prop_index
        if isinstance(concept, Class):
            return self.RESTRICTION_START_KEY + len(self.property_iris)
        if isinstance(concept, ObjectComplementOf):
            return self.LOGICAL_COMPLEMENT_KEY
        raise NotImplementedError(type(concept).__name__)

    def handle_first_definitional_phrase(
        self, definitional_phrases: List[str], name: str
    ) -> str:
        """Determine the appropriate opening phrase for the first part of a definition."""
        if self.ontology_title:
            return (
                "It"
                if definitional_phrases
                else f"The {name} is defined in {self.ontology_title} as"
            )
        else:
            return "It" if definitional_phrases else f"The {name} is defined as"

    def _entity_label(self, entity_iri: str) -> str | None:
        """Return the best label for an entity IRI (prefLabel > label > None)."""
        labels = self.ontology.get_annotations(entity_iri, SKOS_PREFLABEL)
        if labels:
            return labels[0]
        labels = self.ontology.get_annotations(entity_iri, RDFS_LABEL)
        if labels:
            return labels[0]
        return None

    def _format_label(
        self,
        label: str,
        capitalize_first_letter: bool = False,
        no_indef_article: bool = True,
    ) -> str:
        """Apply formatting rules to a label string."""
        if not label:
            return "" if no_indef_article else "the unknown"
        if no_indef_article:
            name = label
        else:
            name = prefix_with_indefinite_article(label).capitalize()
        if name.strip():
            name = (
                name
                if capitalize_first_letter
                else (name[0].lower() if self.lowercase_labels else name[0]) + name[1:]
            )
        else:
            name = None
        return name

    def render_readable_owl_class(
        self,
        owl_class,
        capitalize_first_letter=False,
        no_indef_article=True,
    ) -> str:
        """Render a specific OWL class as a readable name or short phrase.

        Unlike `handle_owl_class`, which generates a full definition, this
        method focuses on the "naming" aspect of the class.
        """
        if isinstance(owl_class, (ObjectIntersectionOf, ObjectUnionOf)):
            items = list(owl_class.first)
            names = [self.render_owl_class(c) for c in items]
            if len(names) == 0:
                return ""
            if len(names) == 1:
                return names[0]
            if len(names) == 2:
                if isinstance(owl_class, ObjectUnionOf):
                    return f"{names[0]} or {names[1]}"
                return f"{names[0]} that {names[1]}"
            result = f"{names[0]} that {names[1]}"
            return result + f" and {pretty_print_list(names[2:], and_char=', and ')}"

        if isinstance(owl_class, (str, int, float, bool)):
            if isinstance(owl_class, str):
                return f'"{owl_class}"'
            return str(owl_class)

        if _is_restriction(owl_class):
            prop_iri = _get_property_iri(owl_class)
            prop_custom_phrases = None
            if prop_iri:
                prop_custom_phrases = self.relevant_role_restriction_cnl_phrasing.get(
                    URIRef(prop_iri)
                )
            return self.render_restrictions(
                anonymous=True,
                custom_phrases=prop_custom_phrases,
                owl_class=owl_class,
                label_based_template="{prefix}{prop_label} {value_name}",
                indefinate_article=False,
            )

        if isinstance(owl_class, Class):
            iri = str(owl_class.first)
            label = self._entity_label(iri)
            return self._format_label(label, capitalize_first_letter, no_indef_article)

        if isinstance(owl_class, (SimpleLiteral, LanguageLiteral, DatatypeLiteral)):
            return self.render_readable_owl_class(
                _literal_to_py(owl_class),
                capitalize_first_letter=capitalize_first_letter,
                no_indef_article=no_indef_article,
            )

        if isinstance(owl_class, NamedIndividual):
            iri = str(owl_class.first)
            label = self._entity_label(iri)
            if label:
                return self._format_label(
                    label, capitalize_first_letter, no_indef_article
                )
            return "something"

        if isinstance(owl_class, AnonymousIndividual):
            return "something"

        if isinstance(owl_class, Datatype):
            return _get_local_name(str(owl_class.first))

        return ""

    def render_owl_class(self, owl_class, anonymous: bool = False) -> str:
        """Recursively render an OWL construct into a string representation.

        Handles the structural decomposition of OWL constructs, converting
        them into intermediate natural language fragments.
        """
        if owl_class is None:
            raise NotImplementedError

        if isinstance(owl_class, Class):
            iri = str(owl_class.first)
            if iri == OWL_THING:
                return "Everything"
            if iri == OWL_NOTHING:
                return "Nothing"
            return self.render_readable_owl_class(owl_class)

        if isinstance(owl_class, ObjectProperty):
            return _get_local_name(str(owl_class.first))
        if isinstance(owl_class, (DataProperty, AnnotationProperty)):
            return _get_local_name(str(owl_class.first))

        if isinstance(owl_class, (ObjectUnionOf, ObjectIntersectionOf)):
            s = []
            for x in owl_class.first:
                if isinstance(x, (ObjectUnionOf, ObjectIntersectionOf)):
                    s.append("(" + self.render_owl_class(x) + ")")
                else:
                    s.append(self.render_owl_class(x))
            if isinstance(owl_class, ObjectUnionOf):
                return pretty_print_list(s, and_char=", or ", binary_op="or")
            return pretty_print_list(s, and_char=", and ")

        if isinstance(owl_class, ObjectComplementOf):
            raise NotImplementedError

        if isinstance(owl_class, InverseObjectProperty):
            raise NotImplementedError

        if _is_restriction(owl_class):
            prop_iri = _get_property_iri(owl_class)
            custom_phrases = None
            if prop_iri:
                custom_phrases = self.relevant_role_restriction_cnl_phrasing.get(
                    URIRef(prop_iri)
                )
            if isinstance(owl_class, (ObjectSomeValuesFrom, DataSomeValuesFrom)):
                return self.render_restrictions(anonymous, custom_phrases, owl_class)
            if isinstance(owl_class, (ObjectAllValuesFrom, DataAllValuesFrom)):
                return self.render_restrictions(
                    anonymous,
                    custom_phrases,
                    owl_class,
                    label_based_template="{prefix}{prop_label} only {value_name}",
                )
            if isinstance(owl_class, (ObjectHasValue, DataHasValue)):
                return self.render_restrictions(
                    anonymous,
                    custom_phrases,
                    owl_class,
                    label_based_template="{prefix}{prop_label} {value_name}",
                    indefinate_article=False,
                )
            if isinstance(owl_class, ObjectHasSelf):
                raise NotImplementedError
            if isinstance(owl_class, (ObjectExactCardinality, DataExactCardinality)):
                return self.render_cardinality_restrictions(anonymous, owl_class)
            if isinstance(owl_class, (ObjectMinCardinality, DataMinCardinality)):
                return self.render_cardinality_restrictions(
                    anonymous, owl_class, phrase=" at least "
                )
            if isinstance(owl_class, (ObjectMaxCardinality, DataMaxCardinality)):
                return self.render_cardinality_restrictions(
                    anonymous, owl_class, phrase=" no more than "
                )

        if isinstance(owl_class, ObjectOneOf):
            raise NotImplementedError
        if isinstance(owl_class, DatatypeRestriction):
            raise NotImplementedError

        # Datatype detection: check if the IRI is a known XSD type
        if isinstance(owl_class, Datatype):
            return _get_local_name(str(owl_class.first))

        if isinstance(owl_class, (str, int, float, bool)):
            if isinstance(owl_class, str):
                return f'"{owl_class}"'
            return str(owl_class)

        if isinstance(owl_class, type):
            return {int: "integer", str: "string", float: "float", bool: "boolean"}.get(
                owl_class, owl_class.__name__
            )

        if isinstance(owl_class, NamedIndividual):
            iri = str(owl_class.first)
            label = self._entity_label(iri)
            return label if label else "something"

        if isinstance(owl_class, AnonymousIndividual):
            return "something"

        if isinstance(owl_class, (SimpleLiteral, LanguageLiteral, DatatypeLiteral)):
            return self.render_owl_class(_literal_to_py(owl_class))

        raise NotImplementedError(type(owl_class).__name__)

    def render_cardinality_restrictions(
        self, anonymous: bool, owl_class, phrase: str = " exactly "
    ) -> str:
        """Render a cardinality restriction as a human-readable phrase.

        Produces text like "is related to at least 2 Persons" based on the
        property label, cardinality value, and restriction type.
        """
        prop_iri = _get_property_iri(owl_class)
        if prop_iri:
            labels = self.ontology.get_annotations(prop_iri, RDFS_LABEL)
            if labels:
                prop_label = labels[0]
            else:
                prop_label = _get_local_name(prop_iri)
        else:
            prop_label = "unknown property"
        cardinality = _get_cardinality(owl_class) or 0
        filler = _get_filler(owl_class)
        prefix = "" if anonymous else "is "
        return (
            f"{prefix}{prop_label}{phrase}{cardinality} "
            f"{self.render_readable_owl_class(filler)}"
        )

    def render_restrictions(
        self,
        anonymous: bool,
        custom_phrases: Optional[Tuple[str, str, str]],
        owl_class,
        label_based_template: str = "{prefix}{prop_label} {value_name}",
        indefinate_article: bool = True,
    ) -> str:
        """Render an OWL restriction (someValuesFrom, allValuesFrom, hasValue) as CNL."""
        restriction_value = self.render_readable_owl_class(_get_filler(owl_class))
        value_name = (
            prefix_with_indefinite_article(restriction_value)
            if indefinate_article
            else restriction_value
        )
        if custom_phrases and self.custom_role_rendering:
            return custom_phrases[0].format(value_name)
        prop_iri = _get_property_iri(owl_class)
        if prop_iri:
            labels = self.ontology.get_annotations(prop_iri, RDFS_LABEL)
            if labels:
                prop_label = labels[0]
                prefix = "" if anonymous else "is "
                return label_based_template.format(
                    prefix=prefix, prop_label=prop_label, value_name=value_name
                )
        return "something"

    def _get_entity_by_iri(self, iri: str) -> str:
        """Return the IRI string itself (there are no live entity objects).

        Checks the IRI is known in the ontology, caches it, and returns the
        string. Raises ``IndexError`` if unknown.
        """
        cached = self._entity_by_iri.get(iri)
        if cached is not None:
            return cached
        known = set()
        known.update(self.ontology.get_classes())
        known.update(self.ontology.get_object_properties())
        known.update(self.ontology.get_data_properties())
        known.update(self.ontology.get_annotation_properties())
        if iri not in known:
            raise IndexError(f"No entity found for IRI: {iri}")
        self._entity_by_iri[iri] = iri
        return iri

    def extract_conjunction_phrases(
        self, owl_class, definitional_phrases: List[str], name: str
    ):
        """Decompose an OWL conjunction (AND) into natural language phrases."""
        named_owl_class_block = []
        unnamed_owl_class_block = []
        for is_named_owl_class, _group in groupby(
            owl_class.first,
            lambda i: self.is_named_owl_class_key(self.concept_group_key(i)),
        ):
            if is_named_owl_class:
                for cls in _group:
                    named_owl_class_block.append(
                        prefix_with_indefinite_article(self.render_owl_class(cls))
                    )
            else:
                for cls in _group:
                    unnamed_owl_class_block.append(
                        self.render_owl_class(cls, anonymous=True)
                    )
        if named_owl_class_block and unnamed_owl_class_block:
            prefix = pretty_print_list(named_owl_class_block, and_char=", and ")
            suffix = pretty_print_list(unnamed_owl_class_block, and_char=", and ")
            name_or_pronoun = self.handle_first_definitional_phrase(
                definitional_phrases, name
            )
            definitional_phrases.append(f"{name_or_pronoun} {prefix} that {suffix}")
        elif named_owl_class_block:
            name_or_pronoun = self.handle_first_definitional_phrase(
                definitional_phrases, name
            )
            block_phrase = pretty_print_list(named_owl_class_block, and_char=", and ")
            definitional_phrases.append(f"{name_or_pronoun} {block_phrase}")
        else:
            name_or_pronoun = self.handle_first_definitional_phrase(
                definitional_phrases, name
            )
            phrase = pretty_print_list(unnamed_owl_class_block, and_char=", and ")
            definitional_phrases.append(f"{name_or_pronoun} {phrase}")

    def extract_definitional_phrases(
        self,
        definitional_phrases: List,
        owl_classes: Iterable,
        owl_class_definition: str,
        owl_class_id: str,
        owl_class_name_phrase,
    ):
        """Iterate through OWL constructs to extract individual definitional phrases.

        This is the core logic for breaking down an OWL equivalent class or
        super-class into a series of English sentences.
        """
        owl_class_def_info = (
            self.definition_info.setdefault(owl_class_id, {})
            if self.collect_definition_info
            else None
        )
        for key, group in groupby(
            sorted(owl_classes, key=self.concept_group_key, reverse=True),
            key=self.concept_group_key,
        ):
            if self.is_logical_construct_key(key):
                for owl_class in group:
                    if isinstance(owl_class, ObjectUnionOf):
                        name_or_pronoun = self.handle_first_definitional_phrase(
                            definitional_phrases, owl_class_definition
                        )
                        disjunction = pretty_print_list(
                            [
                                *map(
                                    lambda i: prefix_with_indefinite_article(
                                        self.render_owl_class(i)
                                    ),
                                    owl_class.first,
                                )
                            ],
                            and_char=", or ",
                        )
                        definitional_phrases.append(
                            f"{name_or_pronoun} is {disjunction}"
                        )
                    else:
                        self.extract_conjunction_phrases(
                            owl_class, definitional_phrases, owl_class_definition
                        )
            elif self.is_restriction_key(key):
                for prop_iri, _group in groupby(group, lambda i: _get_property_iri(i)):
                    if prop_iri in map(str, _PROPERTIES_TO_SKIP):
                        continue
                    cnl_phrase = self.relevant_role_restriction_cnl_phrasing.get(
                        URIRef(prop_iri) if prop_iri else None
                    )
                    custom_render_fn = self.custom_restriction_property_rendering.get(
                        URIRef(prop_iri) if prop_iri else None
                    )
                    if custom_render_fn:
                        custom_render_fn, prompt = custom_render_fn
                        name_or_pronoun = self.handle_first_definitional_phrase(
                            definitional_phrases, owl_class_definition
                        )
                        for restriction in _group:
                            try:
                                phrase = custom_render_fn(_get_filler(restriction))
                            except NotImplementedError:
                                continue
                            else:
                                definitional_phrase = f"{name_or_pronoun} {phrase}"
                                if owl_class_def_info is not None:
                                    owl_class_def_info[
                                        prompt.format(owl_class_name_phrase)
                                    ] = definitional_phrase
                                definitional_phrases.append(definitional_phrase)
                    elif cnl_phrase:
                        singular_phrase, plural_phrase, prompt = cnl_phrase
                        values = []
                        for restriction in _group:
                            concept_name = self.render_owl_class(
                                _get_filler(restriction)
                            )
                            is_cardinality = isinstance(
                                restriction,
                                (
                                    ObjectMinCardinality,
                                    DataMinCardinality,
                                    ObjectMaxCardinality,
                                    DataMaxCardinality,
                                    ObjectExactCardinality,
                                    DataExactCardinality,
                                ),
                            )
                            values.append(
                                prefix_with_indefinite_article(concept_name)
                                if (
                                    prop_iri is None
                                    or URIRef(prop_iri)
                                    not in self.role_restriction_wo_articles
                                )
                                and not is_cardinality
                                else concept_name
                            )
                        name_or_pronoun = self.handle_first_definitional_phrase(
                            definitional_phrases, owl_class_definition
                        )
                        values_list = pretty_print_list(values, and_char=", and ")
                        if callable(singular_phrase):
                            singular_phrase = singular_phrase(values_list)
                            plural_phrase = plural_phrase(values_list)
                        phrase = (
                            plural_phrase if len(values) > 1 else singular_phrase
                        ).format(values_list)
                        definitional_phrase = f"{name_or_pronoun} {phrase}"
                        if owl_class_def_info and prompt is not None:
                            owl_class_def_info[prompt.format(owl_class_name_phrase)] = (
                                definitional_phrase
                            )
                        definitional_phrases.append(definitional_phrase)
                    else:
                        if prop_iri is None:
                            continue
                        try:
                            self._get_entity_by_iri(prop_iri)
                        except IndexError:
                            continue
                        is_data_prop = prop_iri in self.ontology.get_data_properties()
                        prop_labels = self.ontology.get_annotations(
                            prop_iri, RDFS_LABEL
                        )
                        if not is_data_prop and prop_labels:
                            name_or_pronoun = self.handle_first_definitional_phrase(
                                definitional_phrases, owl_class_definition
                            )
                            prop_label = prop_labels[0]
                            values = []
                            for restriction in _group:
                                if isinstance(restriction, ObjectHasSelf):
                                    if (
                                        URIRef(prop_iri)
                                        in self.reflexive_property_customization
                                    ):
                                        values.append(
                                            self.reflexive_property_customization[
                                                URIRef(prop_iri)
                                            ]
                                        )
                                    else:
                                        values.append(f"{prop_label} itself")
                                elif isinstance(
                                    restriction,
                                    (
                                        ObjectMinCardinality,
                                        DataMinCardinality,
                                        ObjectMaxCardinality,
                                        DataMaxCardinality,
                                        ObjectExactCardinality,
                                        DataExactCardinality,
                                    ),
                                ):
                                    pass
                                else:
                                    values.append(
                                        prefix_with_indefinite_article(
                                            self.render_readable_owl_class(
                                                _get_filler(restriction)
                                            )
                                        )
                                    )
                            values_phrase = pretty_print_list(values, and_char=", and ")
                            phrase = f"{prop_label} {values_phrase}"
                            definitional_phrase = f"{name_or_pronoun} {phrase}"
                            if owl_class_def_info is not None:
                                owl_class_def_info[
                                    f"What is {owl_class_name_phrase} {prop_label}?"
                                ] = definitional_phrase
                            definitional_phrases.append(definitional_phrase)
                        else:
                            warnings.warn(f"Unsupported property type: {prop_iri}")
            elif self.is_named_owl_class_key(key):
                for owl_class in group:
                    name_or_pronoun = self.handle_first_definitional_phrase(
                        definitional_phrases, owl_class_definition
                    )
                    parent_name = self.render_readable_owl_class(
                        owl_class, no_indef_article=True
                    )
                    if parent_name is None:
                        continue
                    parent_name = prefix_with_indefinite_article(parent_name)
                    name_or_pronoun = (
                        f"{name_or_pronoun} is"
                        if name_or_pronoun == "It"
                        else name_or_pronoun
                    )
                    definitional_phrases.append(f"{name_or_pronoun} {parent_name}")

    def handle_owl_class(self, owl_class_iri: str) -> str:
        """Generate a comprehensive human-readable definition for a class by IRI.

        This is the primary entry point for rendering a class. It queries the
        ontology for ``EquivalentClasses`` and ``SubClassOf`` axioms involving
        the given IRI, extracts definitional phrases, and joins them into a
        narrative description.

        Args:
            owl_class_iri: The full IRI string of the class to render.

        Returns:
            A natural language string describing the class.
        """
        owl_class_id = owl_class_iri.split(str(self.ontology_namespace))[-1]
        best_label = self._entity_label(owl_class_iri)
        owl_class_name_phrase = (
            f"the {best_label}" if best_label else f"the {owl_class_id}"
        )
        owl_class_definition = self.render_readable_owl_class(
            Class(self.ontology.iri(owl_class_iri)),
            capitalize_first_letter=True,
        ).strip()
        definitional_phrases: List[str] = []

        equivalent_to: List = []
        is_a: List = []
        seen_is_a: set = set()

        skip_iris = {OWL_THING, OWL_NOTHING}
        for ac in self.ontology.get_axioms_for_iri(owl_class_iri):
            match ac.component:
                case EquivalentClasses(members):
                    if any(str(m) == owl_class_iri for m in members):
                        for m in members:
                            if str(m) != owl_class_iri and str(m) not in skip_iris:
                                key = str(m)
                                if key not in seen_is_a:
                                    equivalent_to.append(m)
                                    seen_is_a.add(key)
                case SubClassOf(sub, sup):
                    if str(sub) == owl_class_iri and str(sup) not in skip_iris:
                        key = str(sup)
                        if key not in seen_is_a:
                            is_a.append(sup)
                            seen_is_a.add(key)

        if equivalent_to:
            self.extract_definitional_phrases(
                definitional_phrases,
                equivalent_to,
                owl_class_definition,
                owl_class_id,
                owl_class_name_phrase,
            )
        if is_a:
            self.extract_definitional_phrases(
                definitional_phrases,
                is_a,
                owl_class_definition,
                owl_class_id,
                owl_class_name_phrase,
            )

        return ". ".join(map(str.strip, definitional_phrases))

    def render_role_restriction(
        self,
        property_iri: str,
        operand1: str = "A",
        operand2: str = "B",
    ) -> str:
        """Render an object property as a simple role restriction for logic documentation.

        Args:
            property_iri: The full IRI string of the property to render.
            operand1: The subject placeholder (default "A").
            operand2: The object placeholder (default "B").

        Returns:
            A formatted role restriction string.
        """
        custom_phrases = self.relevant_role_restriction_cnl_phrasing.get(
            URIRef(property_iri)
        )
        if custom_phrases and self.custom_role_rendering:
            property_phrase = f"{operand1} {custom_phrases[0].format(operand2)}"
        else:
            labels = self.ontology.get_annotations(property_iri, RDFS_LABEL)
            if labels:
                prop_label = labels[0]
            else:
                prop_label = _get_local_name(property_iri)
            property_phrase = f"{operand1} '{prop_label}' {operand2}"
        return property_phrase

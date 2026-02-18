"""OWL_DSL - Library for extracting Domain Specific Languages from OWL (using Owlready2)"""

__version__ = "0.1.0"

import warnings
from typing import Union
import types
import owlready2
from owlready2 import Restriction, owl, Construct, EntityClass, ThingClass, PropertyClass, LogicalClassConstruct, Or, \
    And, Not, Inverse, OneOf, ConstrainedDatatype, PropertyChain

try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
except (OSError, ImportError):
    nlp = None

VOWELS = 'aeiou'

_FACETS = {
    "length": "length",
    "min_length": "minLength",
    "max_length": "maxLength",
    "pattern": "pattern",
    "max_inclusive": "\u2264",
    "max_exclusive": "\u003c",
    "min_inclusive": "\u2265",
    "min_exclusive": "\u003e",
    "total_digits": "totalDigits",
    "fraction_digits": "fractionDigits",
}

#Redefined from owlready2.dl_render in order to redefine dl_render_concept_str
_DL_SYNTAX = types.SimpleNamespace(
    SUBCLASS="⊑",
    EQUIVALENT_TO="≡",
    NOT="¬",
    DISJOINT_WITH="⊑" + " " + "¬",
    EXISTS="∃",
    FORALL="∀",
    IN="∈",
    MIN="≥",
    EQUAL="=",
    NOT_EQUAL="≠",
    MAX="≤",
    INVERSE="⁻",
    AND="⊓",
    TOP="⊤",
    BOTTOM="⊥",
    OR="⊔",
    COMP="∘",
    WEDGE="⋀",
    IMPLIES="←",
    COMMA=",",
    SELF="self",
)

def base_uri(uri: str) -> tuple[str, str]:
    """Returns a tuple containing the base URI and the remaining portion."""
    index = uri.rfind('/') + 1
    return uri[:index], uri[index:]


_RESTRICTION_TYPE_FORMATS = {
    owlready2.base.SOME: lambda prop, val, _card: f"{_DL_SYNTAX.EXISTS} {prop} .{val}",
    owlready2.base.ONLY: lambda prop, val, _card: f"{_DL_SYNTAX.FORALL} {prop} .{val}",
    owlready2.base.HAS_SELF: lambda prop, _val, _card: f"{_DL_SYNTAX.EXISTS} {prop} .{_DL_SYNTAX.SELF}",
    owlready2.base.EXACTLY: lambda prop, val, card: f"{_DL_SYNTAX.EQUAL} {card} {prop} .{val}",
    owlready2.base.MIN: lambda prop, val, card: f"{_DL_SYNTAX.MIN} {card} {prop} .{val}",
    owlready2.base.MAX: lambda prop, val, card: f"{_DL_SYNTAX.MAX} {card} {prop} .{val}",
}


def _render_restriction(concept: Restriction) -> str:
    """Render an OWL restriction in Description Logic syntax."""
    rendered_property = dl_render_concept_str(concept.property)

    if concept.type == owlready2.base.VALUE:
        value_str = concept.value.name if isinstance(concept.value, owl.Thing) else concept.value
        return f"{_DL_SYNTAX.EXISTS} {rendered_property} .{{{value_str}}}"

    rendered_value = dl_render_concept_str(concept.value)
    formatter = _RESTRICTION_TYPE_FORMATS.get(concept.type)
    if formatter is not None:
        return formatter(rendered_property, rendered_value, getattr(concept, 'cardinality', None))

    raise NotImplementedError(f"Unknown restriction type: {concept.type}")


def dl_render_concept_str(concept: Union[Construct, EntityClass]) -> str:
    if concept is None:
        return _DL_SYNTAX.BOTTOM
    if isinstance(concept, ThingClass):
        if concept is owl.Thing:
            return _DL_SYNTAX.TOP
        if concept is owl.Nothing:
            return _DL_SYNTAX.BOTTOM
        #Updated to return properly labeled concept
        return f"{concept.name}{' ({})'.format(str(concept.label[0])) if concept.label else ''}"
    if isinstance(concept, PropertyClass):
        return concept.name
    if isinstance(concept, LogicalClassConstruct):
        s = []
        for x in concept.Classes:
            if isinstance(x, LogicalClassConstruct):
                s.append("(" + dl_render_concept_str(x) + ")")
            else:
                s.append(dl_render_concept_str(x))
        if isinstance(concept, Or):
            return (" %s " % _DL_SYNTAX.OR).join(s)
        if isinstance(concept, And):
            return (" %s " % _DL_SYNTAX.AND).join(s)
    if isinstance(concept, Not):
        return "%s %s" % (_DL_SYNTAX.NOT, dl_render_concept_str(concept.Class))
    if isinstance(concept, Inverse):
        return "%s%s" % (dl_render_concept_str(concept.property), _DL_SYNTAX.INVERSE)
    if isinstance(concept, Restriction):
        return _render_restriction(concept)
    if isinstance(concept, OneOf):
        return "{%s}" % (" %s " % _DL_SYNTAX.OR).join("%s" % (item.name if isinstance(item, owl.Thing)
                                                              else item) for item in concept.instances)
    if isinstance(concept, ConstrainedDatatype):
        s = []
        for k in _FACETS:
            v = getattr(concept, k, None)
            if not v is None:
                s.append("%s %s" % (_FACETS[k], v))
        return "%s[%s]" % (concept.base_datatype.__name__, (" %s " % _DL_SYNTAX.COMMA).join(s))
    if isinstance(concept, PropertyChain):
        return (" %s " % _DL_SYNTAX.COMP).join(dl_render_concept_str(property) for property in concept.properties)
    if concept in owlready2.base._universal_datatype_2_abbrev:
        iri = owlready2.base._universal_abbrev_2_iri.get(owlready2.base._universal_datatype_2_abbrev.get(concept))
        if iri.startswith("http://www.w3.org/2001/XMLSchema#"):
            return "xsd:" + iri[33:]
        hash, slash = iri.rindex('#'), iri.rindex('/')
        return iri[max(hash, slash)+1:]
    if owlready2.rdfs_datatype in [some_class.storid for some_class in concept.is_a]: # rdfs:Datatype
        return concept.name
    raise NotImplementedError(concept)


def pretty_print_list(my_list, sep=", ", and_char=", & ", binary_op='and'):
    return and_char.join([sep.join(my_list[:-1]), my_list[-1]]) \
        if len(my_list) > 2 else '{} {} {}'.format(
        my_list[0], binary_op, my_list[1]
    ) if len(my_list) == 2 else my_list[0]


def _indefinite_article(word: str) -> str:
    return "an" if word and word[0].lower() in VOWELS else "a"


def prefix_with_indefinite_article(term: str | None, unquoted:bool = True) -> str:
    if term is None:
        return "something"
    else:
        _term = term if unquoted else f"'{term}'"
        if not nlp is None:
            for idx, token in enumerate(nlp(term)):
                if token.tag_ == 'VBG':
                    return _term
                elif token.tag_ == 'NN' and idx == len(nlp(term)) - 1:
                    return f"{_indefinite_article(term)} " + _term
        else:
            warnings.warn("nlp not initialized")
            return _indefinite_article(term)
        return f"{_indefinite_article(term)} " + _term


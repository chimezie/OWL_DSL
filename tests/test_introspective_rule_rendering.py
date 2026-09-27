from io import StringIO
from pathlib import Path

import pyhornedowl
from pyhornedowl.model import (
    Class,
    ObjectProperty,
    DeclareClass,
    DeclareObjectProperty,
    IRI,
)
from rdflib import Graph, Namespace, Literal, URIRef, RDF
from fuxi.Horn.PositiveConditions import Uniterm
from owl_dsl.rule_renderer import RuleRenderer
from owl_dsl.annotations import configure_cnl_from_annotations
from fuxi.Horn.HornRules import horn_from_n3

DIR = Path(__file__).parent
BASE_URI = "http://example.org/"
OWL_DSL = Namespace("http://purl.org/ontology-dsl#")

# https://notation3.org/#chaining_example
N3_RULES = """
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix : <http://example.org/>.
            
:spiderman a :WebSlinger .
:44th :traffic :heavy .
            
{ ?slinger a :WebSlinger } => { ?slinger :locomotion :flying } .

{ ?heli a :Helicopter } => { ?heli :locomotion :flying  } .

{ ?flyer :locomotion :flying . ?street :traffic :heavy } 
  =>  { ?street :suitable_observer ?flyer } .
"""

N3_RULES_2 = """
@prefix : <http://example.org/>.

{?x :parent ?y. ?y :sister ?z} => {?x :aunt ?z} .
"""

RULE_RENDERINGS = {
    "Every Web Slinger has flying as their means of locomotion.",
    "Every Helicopter has flying as their means of locomotion.",
    "If ?flyer has flying as their means of locomotion and ?street has heavy traffic, "
    "then ?street has ?flyer as a suitable observer.",
}

RULE_RENDERINGS_2 = {
    "If ?x has ?y as their parent and ?y has ?z as their sister, then ?x has ?z as their aunt.",
}


def _build_rule_ontology() -> pyhornedowl.PyIndexedOntology:
    onto = pyhornedowl.PyIndexedOntology()
    onto.prefix_mapping.add_default_prefix_names()
    onto.prefix_mapping.add_prefix("", BASE_URI)

    classes = [
        ("Person", "Person"),
        ("WebSlinger", "Web Slinger"),
        ("Heavy", "heavy"),
        ("flying", "flying"),
        ("Helicopter", "Helicopter"),
    ]
    for suffix, label in classes:
        onto.add_component(DeclareClass(Class(IRI.parse(BASE_URI + suffix))))
        onto.set_label(IRI.parse(BASE_URI + suffix), label)

    properties = [
        ("locomotion", "locomotion", "has {} as their means of locomotion"),
        ("traffic", "traffic", "has {} traffic"),
        ("suitable_observer", "suitable_observer", "has {} as a suitable observer"),
        ("parent", "parent", "has {} as their parent"),
        ("sister", "sister", "has {} as their sister"),
        ("aunt", "aunt", "has {} as their aunt"),
    ]
    for suffix, label, template in properties:
        onto.add_component(
            DeclareObjectProperty(ObjectProperty(IRI.parse(BASE_URI + suffix)))
        )
        onto.set_label(IRI.parse(BASE_URI + suffix), label)

    return onto


def test_rule_rendering():
    program = horn_from_n3(StringIO(N3_RULES))
    onto = _build_rule_ontology()

    graph = Graph()
    for suffix, _label, template in [
        ("locomotion", "locomotion", "has {} as their means of locomotion"),
        ("traffic", "traffic", "has {} traffic"),
        ("suitable_observer", "suitable_observer", "has {} as a suitable observer"),
    ]:
        iri = BASE_URI + suffix
        graph.add((URIRef(iri), OWL_DSL.OWL_DSL_000001, Literal(template)))

    renderer = RuleRenderer(onto, BASE_URI, verbose=False, lowercase_labels=False)
    configure_cnl_from_annotations(renderer, graph)
    for rule in program:
        if not (
            isinstance(rule.formula.body, Uniterm)
            and rule.formula.body.op == RDF.type
            and isinstance(rule.formula.head, Uniterm)
            and rule.formula.head.op == RDF.type
        ):
            phrase = renderer.render_rule(rule)
            assert phrase in RULE_RENDERINGS


def test_rule_rendering_2():
    program = horn_from_n3(StringIO(N3_RULES_2))
    onto = _build_rule_ontology()

    graph = Graph()
    for suffix, _label, template in [
        ("parent", "parent", "has {} as their parent"),
        ("sister", "sister", "has {} as their sister"),
        ("aunt", "aunt", "has {} as their aunt"),
    ]:
        iri = BASE_URI + suffix
        graph.add((URIRef(iri), OWL_DSL.OWL_DSL_000001, Literal(template)))

    renderer = RuleRenderer(onto, BASE_URI, verbose=False, lowercase_labels=False)
    configure_cnl_from_annotations(renderer, graph)
    for rule in program:
        if not (
            isinstance(rule.formula.body, Uniterm)
            and rule.formula.body.op == RDF.type
            and isinstance(rule.formula.head, Uniterm)
            and rule.formula.head.op == RDF.type
        ):
            phrase = renderer.render_rule(rule)
            assert phrase in RULE_RENDERINGS_2

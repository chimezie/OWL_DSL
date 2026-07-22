from __future__ import annotations

from collections.abc import Iterable

from rdflib import BNode, Graph, Literal, RDF, URIRef, Namespace, RDFS
from rdflib.namespace import OWL, Namespace
from rdflib.term import Identifier

BASE_IRI = "https://github.com/chimezie/OWL_DSL/tree/main/ontology_configurations/"
OBO = Namespace("http://purl.obolibrary.org/obo/")
OWL_DSL = Namespace(
    "https://github.com/chimezie/OWL_DSL/tree/main/ontology_configurations/"
)

OWL_DSL_000001 = OWL_DSL.OWL_DSL_000001  # singular predicate string template
OWL_DSL_000002 = OWL_DSL.OWL_DSL_000002  # plural predicate string template
OWL_DSL_000003 = (
    OWL_DSL.OWL_DSL_000003
)  # phrase using the predicate to request a definition of the term
OWL_DSL_000004 = (
    OWL_DSL.OWL_DSL_000004
)  # class inferences to ignore (an RDF collection)
OWL_DSL_000005 = OWL_DSL.OWL_DSL_000005  # expert definition properties
OWL_DSL_000006 = OWL_DSL.OWL_DSL_000006  # standard role restriction is phrasing
OWL_DSL_000007 = OWL_DSL.OWL_DSL_000007  # reflexive roles

DEFAULT_EXPERT_DEFINITION_PROPERTIES = ["http://purl.obolibrary.org/obo/IAO_0000115"]


def _iter_rdf_list(graph: Graph, head: URIRef | BNode) -> Iterable[URIRef | Literal]:
    current = head
    while current and current != RDF.nil:
        first = graph.value(current, RDF.first)
        if first is not None:
            yield first
        current = graph.value(current, RDF.rest)


def _expand_objects(graph: Graph, obj: URIRef | BNode | Literal) -> list[str]:
    if isinstance(obj, (URIRef, Literal)):
        return [str(obj)]
    if isinstance(obj, BNode) and graph.value(obj, RDF.first) is not None:
        return [str(item) for item in _iter_rdf_list(graph, obj)]
    return []


def _objects_as_strings(
    graph: Graph, subject: URIRef | BNode, predicate: URIRef
) -> list[str]:
    values: list[str] = []
    for obj in graph.objects(subject, predicate):
        values.extend(_expand_objects(graph, obj))
    return values


def _first_literal(graph: Graph, subject: URIRef, predicate: URIRef) -> str | None:
    for obj in graph.objects(subject, predicate):
        if isinstance(obj, Literal):
            return str(obj)
    return None


def _get_ontology_subject(graph: Graph) -> URIRef | BNode | None:
    for subj in graph.subjects(RDF.type, OWL.Ontology):
        return subj
    return None


def load_global_annotations(graph: Graph) -> dict[str, object]:
    ontology_subject = _get_ontology_subject(graph)
    if ontology_subject is None:
        return {
            "class_inference_to_ignore": [],
            "expert_definition_properties": DEFAULT_EXPERT_DEFINITION_PROPERTIES,
            "expert_definition_properties_present": False,
            "standard_role_restriction_is_phrasing": [],
        }

    class_inference_to_ignore = _objects_as_strings(
        graph, ontology_subject, OWL_DSL_000004
    )

    expert_definition_properties = _objects_as_strings(
        graph, ontology_subject, OWL_DSL_000005
    )
    expert_definition_properties_present = bool(expert_definition_properties)
    if not expert_definition_properties:
        expert_definition_properties = DEFAULT_EXPERT_DEFINITION_PROPERTIES

    standard_role_restriction_is_phrasing = _objects_as_strings(
        graph, ontology_subject, OWL_DSL_000006
    )

    return {
        "class_inference_to_ignore": class_inference_to_ignore,
        "expert_definition_properties": expert_definition_properties,
        "expert_definition_properties_present": expert_definition_properties_present,
        "standard_role_restriction_is_phrasing": standard_role_restriction_is_phrasing,
    }


def load_property_annotations(
    graph: Graph,
) -> tuple[dict[str, tuple[str | None, str | None, str | None]], dict[str, str]]:
    properties: set[URIRef] = set()

    bindings = f"PREFIX owl_dsl: <{OWL_DSL}>\nBASE {OWL_DSL}\n"

    for predicate in (
        OWL_DSL.OWL_DSL_000001,
        OWL_DSL.OWL_DSL_000002,
        OWL_DSL.OWL_DSL_000003,
        OWL_DSL.OWL_DSL_000007,
    ):
        for subj in graph.subjects(predicate=predicate):
            if isinstance(subj, URIRef):
                properties.add(subj)

    template_map: dict[str, tuple[str | None, str | None, str | None]] = {}
    reflexive_map: dict[str, str] = {}

    template_predicates = [
        OWL_DSL.OWL_DSL_000001,
        OWL_DSL.OWL_DSL_000002,
        OWL_DSL.OWL_DSL_000003,
    ]
    QUERY = (
        f"SELECT ?owl_class ?pred ?template {{ ?owl_class ?pred ?template "
        f"FILTER({' || '.join([f'?pred = <{p}>' for p in template_predicates])}) }}"
    )
    for owl_class, prop, template in graph.query(QUERY):
        singular = _first_literal(graph, prop, OWL_DSL.OWL_DSL_000001)
        plural = _first_literal(graph, prop, OWL_DSL.OWL_DSL_000002)
        prompt = _first_literal(graph, prop, OWL_DSL.OWL_DSL_000003)
        if singular or plural or prompt:
            template_map[str(prop)] = (singular, plural, prompt)

        reflexive_phrase = _first_literal(graph, prop, OWL_DSL.OWL_DSL_000007)
        if reflexive_phrase:
            reflexive_map[str(prop)] = reflexive_phrase

    # for owl_class in graph.query(
    #     f"{bindings}SELECT ?owl_class {{ ?owl_class OWL_DSL_000006 true }}"
    # ):
    #     pass
    #
    return template_map, reflexive_map


def get_annotation_value(
    graph: Graph, subject: URIRef, predicate: URIRef, default: Identifier | None = None
) -> str | None:
    for obj in graph.objects(subject, predicate):
        if isinstance(obj, Literal):
            return str(obj)
    return default


def configure_cnl_from_annotations(handler, graph: Graph) -> None:
    handler._rdflib_graph = graph
    # standard_role_restriction_is_phrasing
    template_predicates = [
        OWL_DSL.OWL_DSL_000001,
        OWL_DSL.OWL_DSL_000002,
        OWL_DSL.OWL_DSL_000003,
    ]
    namespace_bindings = f"BASE <{OWL_DSL}>\nPREFIX owl: <{OWL}>\nPREFIX owl_dsl: <{OWL_DSL}>\nPREFIX rdfs: <{RDFS}>\n"
    QUERY = (
        f"SELECT ?property ?pred ?template {{ ?property ?pred ?template "
        f"FILTER({' || '.join([f'?pred = <{p}>' for p in template_predicates])}) }}"
    )

    # Group template information by annotation_property URI
    template_info = {}

    for ontology_property, annotation_property, template in graph.query(QUERY):
        if ontology_property not in template_info:
            template_info[ontology_property] = {}
        if annotation_property == OWL_DSL.OWL_DSL_000001:
            template_info[ontology_property]["singular"] = str(template)
        elif annotation_property == OWL_DSL.OWL_DSL_000002:
            template_info[ontology_property]["plural"] = str(template)
        elif annotation_property == OWL_DSL.OWL_DSL_000003:
            template_info[ontology_property]["prompt"] = str(template)

    # Iterate over grouped template_info by unique keys
    for prop_uri, templates in template_info.items():
        singular_value = templates.get("singular")
        plural_value = templates.get("plural", singular_value)
        prompt_value = templates.get("prompt")

        if singular_value or plural_value or prompt_value:
            handler.relevant_role_restriction_cnl_phrasing[prop_uri] = (
                singular_value,
                plural_value,
                prompt_value,
            )

    # OWL_DSL_000004: class inference to ignore
    for class_to_ignore in graph.query(
        f"{namespace_bindings}SELECT ?class "
        f"{{ ?class a owl:Class; owl_dsl:OWL_DSL_000004 true }}"
    ):
        handler.class_inference_to_ignore.append(class_to_ignore)

    handler.expert_definition_properties = [OBO.IAO_0000115]
    # OWL_DSL_000005: expert definition properties
    for definition_prop in graph.query(
        f"{namespace_bindings}SELECT ?property "
        f"{{ ?property owl_dsl:OWL_DSL_000005 true }}"
    ):
        handler.expert_definition_properties.append(definition_prop)

    # OWL_DSL_000006: standard role restriction is phrasings :
    for object_property, prop_label in graph.query(
        f"{namespace_bindings}SELECT ?property ?label "
        f"{{ ?property owl_dsl:OWL_DSL_000006 true; rdfs:label ?label }}"
    ):
        handler.relevant_role_restriction_cnl_phrasing[object_property] = (
            f"is {prop_label} " + "{}",
        ) * 2 + ("What is {}" + f" {prop_label}?",)
    # OWL_DSL.OWL_DSL_000007: reflexive roles
    for object_property, template in graph.query(
        f"{namespace_bindings}SELECT ?property ?template "
        f"{{ ?property owl_dsl:OWL_DSL_000007 ?template }}"
    ):
        handler.reflexive_property_customizations[object_property] = str(template)


def apply_annotations_to_handler(handler, graph: Graph) -> tuple[list[str], bool]:
    global_config = load_global_annotations(graph)
    template_map, reflexive_map = load_property_annotations(graph)

    if global_config["class_inference_to_ignore"]:
        handler.class_inference_to_ignore = list(
            dict.fromkeys(
                [
                    *handler.class_inference_to_ignore,
                    *global_config["class_inference_to_ignore"],
                ]
            )
        )

    for prop_iri in global_config["standard_role_restriction_is_phrasing"]:
        if prop_iri in template_map:
            continue
        prop_obj = handler.ontology.search(iri=prop_iri)
        if prop_obj and prop_obj[0].label:
            props = [label for label in prop_obj[0].label if isinstance(label, str)]
            prop_label = props[0] if props else "(no label)"
            handler.relevant_role_restriction_cnl_phrasing[URIRef(prop_iri)] = (
                f"is {prop_label} " + "{}",
            ) * 2 + ("What is {}" + f" {prop_label}?",)

    for prop_iri, (singular, plural, prompt) in template_map.items():
        if not singular or not plural or not prompt:
            existing = handler.relevant_role_restriction_cnl_phrasing.get(
                URIRef(prop_iri)
            )
            if existing:
                singular = singular or existing[0]
                plural = plural or existing[1]
                prompt = prompt or existing[2]
        if singular and plural and prompt:
            handler.relevant_role_restriction_cnl_phrasing[URIRef(prop_iri)] = (
                singular,
                plural,
                prompt,
            )

    for prop_iri, phrase in reflexive_map.items():
        handler.reflexive_property_customizations[URIRef(prop_iri)] = phrase

    return (
        global_config["expert_definition_properties"],
        global_config["expert_definition_properties_present"],
    )


def load_annotations_graph(
    ontology, owl_url_or_path: str | None = None
) -> Graph | None:
    graph = None
    if hasattr(ontology, "world") and hasattr(ontology.world, "as_rdflib_graph"):
        graph = ontology.world.as_rdflib_graph()
    elif owl_url_or_path:
        graph = Graph()
        graph.parse(owl_url_or_path)
    return graph

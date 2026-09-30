from rdflib import URIRef
from pyhornedowl.model import ObjectProperty, ObjectHasSelf
import pyhornedowl
from pyhornedowl.model import IRI

TEST_NS = "http://test.org/onto.owl#"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"


def test_custom_role_restriction_phrasing(cnl_renderer, mock_has_pet, mock_dog):
    custom_phrase = ("has a pet {}", "have pets {}", "What pets does {} have?")
    prop_uri = URIRef(TEST_NS + "has_pet")
    cnl_renderer.relevant_role_restriction_cnl_phrasing[prop_uri] = custom_phrase
    cnl_renderer.custom_role_rendering = True

    rendered = cnl_renderer.render_role_restriction(
        TEST_NS + "has_pet", operand1="The person", operand2="a dog"
    )
    assert "has a pet a dog" in rendered


def test_reflexive_role_rendering(cnl_renderer):
    from rdflib import URIRef
    from pyhornedowl.model import ObjectHasSelf, ObjectProperty
    import pyhornedowl

    prop_uri = URIRef(TEST_NS + "has_pet")
    cnl_renderer.reflexive_property_customization[prop_uri] = (
        "that interacts with itself"
    )

    onto = cnl_renderer.ontology
    has_self = ObjectHasSelf(ObjectProperty(onto.iri(TEST_NS + "has_pet")))

    definitional_phrases = []
    cnl_renderer.extract_definitional_phrases(
        definitional_phrases=definitional_phrases,
        owl_classes=[has_self],
        owl_class_definition="TestClass",
        owl_class_id="TestClass",
        owl_class_name_phrase="the test class",
    )

    assert any(
        "that interacts with itself" in phrase for phrase in definitional_phrases
    )

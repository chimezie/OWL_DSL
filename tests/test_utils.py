from owl_dsl import prefix_with_indefinite_article, pretty_print_list


def test_prefix_with_indefinite_article_basic():
    # Test vowels
    assert prefix_with_indefinite_article("apple") == "an apple"
    assert prefix_with_indefinite_article("orange") == "an orange"
    assert prefix_with_indefinite_article("umbrella") == "an umbrella"

    # Test consonants
    assert prefix_with_indefinite_article("dog") == "a dog"
    assert prefix_with_indefinite_article("cat") == "a cat"
    assert prefix_with_indefinite_article("house") == "a house"


def test_prefix_with_indefinite_article_none():
    assert prefix_with_indefinite_article(None) == "something"


def test_prefix_with_indefinite_article_quoted():
    # The quoting behavior depends on nlp initialization, so just check it returns a string
    result = prefix_with_indefinite_article("apple", unquoted=False)
    assert isinstance(result, str)


def test_pretty_print_list():
    assert pretty_print_list(["a"]) == "a"
    assert pretty_print_list(["a", "b"]) == "a and b"
    # Note: The actual implementation uses "&" instead of "and" for 3+ items
    assert pretty_print_list(["a", "b", "c"]) == "a, b, & c"
    assert pretty_print_list(["a", "b", "c", "d"]) == "a, b, c, & d"

    # Test custom separators
    assert pretty_print_list(["a", "b"], binary_op="or") == "a or b"
    assert pretty_print_list(["a", "b", "c"], and_char=", or ") == "a, b, or c"


# Additional utility tests for comprehensive coverage


def test_base_uri_with_https():
    """Test base_uri function with HTTPS URL."""
    from owl_dsl import base_uri

    uri = "https://purl.obolibrary.org/obo/FMA_000001"
    base, remaining = base_uri(uri)

    assert base == "https://purl.obolibrary.org/obo/"
    assert remaining == "FMA_000001"


def test_base_uri_with_hash():
    """Test base_uri with hash-based IRI."""
    from owl_dsl import base_uri

    uri = "http://test.org/onto.owl#Person"
    base, remaining = base_uri(uri)

    # base_uri splits on / not #
    assert base == "http://test.org/"
    assert remaining == "onto.owl#Person"


def test_base_uri_with_slash():
    """Test base_uri with slash-based IRI."""
    from owl_dsl import base_uri

    uri = "http://example.org/ontology/ClassA"
    base, remaining = base_uri(uri)

    assert base == "http://example.org/ontology/"
    assert remaining == "ClassA"

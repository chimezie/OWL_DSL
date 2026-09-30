"""Regression test for Manchester parser: union-first restriction patterns.

Background
----------
The ELK reasoner sometimes outputs GCI (Generalized Concept Inclusion)
justifications in Manchester syntax where the *object property restriction
follows a parenthesized union* rather than preceding it.  For example::

    (DefiningCharacteristicAbradedSkin or DefiningCharacteristicAbscess) some hasDefiningCharacteristic

This is the reverse of the standard Manchester OWL 2 syntax, where the
restriction keyword (``some`` / ``only`` / ``value`` / ``min`` / ``max`` / ``exactly``)
must directly follow the *object property*, with the *filler* coming after::

    hasDefiningCharacteristic some (DefiningCharacteristicAbradedSkin or DefiningCharacteristicAbscess)

Grammar root cause (``owlapy``'s pegs grammer)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The ``primary`` rule in ``ManchesterOWLSyntaxParser`` tries alternatives in this
order::

    primary = ('not' must_ws)? (data_some_only_res /
                                some_only_res /
                                data_cardinality_res /
                                cardinality_res /
                                data_value_res /
                                value_res /
                                has_self /
                                class_expression)

Where::

    some_only_res = object_property must_ws ('some' / 'only') must_ws primary
    class_expression = class_iri / individual_list / parentheses
    parentheses = '(' maybe_ws union maybe_ws ')'

When the input is ``(A or B or C) some p``:

1. ``primary`` tries ``some_only_res`` — expects an ``object_property``, but
   finds ``(``, so it backtracks.
2. ``primary`` tries ``class_expression`` → ``parentheses`` → ``(A or B or C)``.
   The parenthesised union is consumed **in full** by ``union``.
3. ``primary`` **returns** the matched node, leaving `` some p`` **unconsumed**.
4. The enclosing ``intersection`` / ``union`` rule reports success (the union
   matched in its entirety) but the remaining input triggers the
   ``IncompleteParseError``.

The fix is in the ELK-output consumer (``owl_dsl.reasoner.verbalize_gci_justifications``),
which calls ``owlapy.manchester_to_owl_expression`` on the right-hand side of
GCI strings.  The input must be massaged to place the property restriction
before the union filler.

This test documents the failure mode and verifies the correct syntax round-trips
successfully.
"""

import pytest
import os

# ---------------------------------------------------------------------------
# The bug: owlapy.parser.ManchesterParser v1.6.4 cannot parse expressions
# where a parenthesised union appears BEFORE a restriction keyword.
#
# Reproduction URL (from the NANDA-I taxonomy reasoner crash):
#   File "owl_dsl/reasoner.py", line 469, in verbalize_gci_justifications
#     parsed_expression = manchester_to_owl_expression(
#         ClassB, ontology_namespace_baseuri
#     )
#   ...
#   parsimonious.exceptions.IncompleteParseError:
#     Rule 'union' matched in its entirety, but it didn't consume all the text.
#     The non-matching portion of the text begins with ' some'
#     (line 1, column 62).
# ---------------------------------------------------------------------------

TEST_NS = "https://nanda-i.nursing/ontology/2024-2026/taxonomy#"

# -- ELK-generated patterns that trigger the crash --------------------------

UNION_FIRST_SINGLE = (
    "(DefiningCharacteristicAbradedSkin) some hasDefiningCharacteristic"
)
UNION_FIRST_PAIR = (
    "(DefiningCharacteristicAbradedSkin or DefiningCharacteristicAbscess) "
    "some hasDefiningCharacteristic"
)
UNION_FIRST_TRIPLE = (
    "(DefiningCharacteristicAbradedSkin or DefiningCharacteristicAbscess "
    "or DefiningCharacteristicAcutePain) "
    "some hasDefiningCharacteristic"
)
UNION_FIRST_LONG = (
    "(DefiningCharacteristicAbradedSkin or DefiningCharacteristicAbscess or "
    "DefiningCharacteristicAcutePain or DefiningCharacteristicAlteredSkinColor or "
    "DefiningCharacteristicAlteredTurgor or DefiningCharacteristicBleeding) "
    "some hasDefiningCharacteristic"
)

# -- The same semantics expressed in correct Manchester order ----------------

CORRECT_SINGLE = "hasDefiningCharacteristic some (DefiningCharacteristicAbradedSkin)"
CORRECT_PAIR = (
    "hasDefiningCharacteristic some "
    "(DefiningCharacteristicAbradedSkin or DefiningCharacteristicAbscess)"
)
CORRECT_TRIPLE = (
    "hasDefiningCharacteristic some "
    "(DefiningCharacteristicAbradedSkin or DefiningCharacteristicAbscess "
    "or DefiningCharacteristicAcutePain)"
)
CORRECT_LONG = (
    "hasDefiningCharacteristic some "
    "(DefiningCharacteristicAbradedSkin or DefiningCharacteristicAbscess or "
    "DefiningCharacteristicAcutePain or DefiningCharacteristicAlteredSkinColor or "
    "DefiningCharacteristicAlteredTurgor or DefiningCharacteristicBleeding)"
)

# -- Also test a SubClassOf expression (as seen in ELK GCI output) ----------

GCI_UNION_FIRST = (
    "ImpairedSkinIntegrity SubClassOf "
    "(DefiningCharacteristicAbradedSkin or DefiningCharacteristicAbscess) "
    "some hasDefiningCharacteristic"
)
GCI_CORRECT = (
    "ImpairedSkinIntegrity SubClassOf "
    "hasDefiningCharacteristic some "
    "(DefiningCharacteristicAbradedSkin or DefiningCharacteristicAbscess)"
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_correct_syntax_single():
    """A lone class wrapped in parens as a restriction filler is valid."""
    from owlapy.parser import manchester_to_owl_expression

    result = manchester_to_owl_expression(CORRECT_SINGLE, TEST_NS)
    assert result is not None


def test_correct_syntax_pair():
    """A pair union as a restriction filler is valid."""
    from owlapy.parser import manchester_to_owl_expression

    result = manchester_to_owl_expression(CORRECT_PAIR, TEST_NS)
    assert result is not None


def test_correct_syntax_triple():
    """A triple union as a restriction filler is valid."""
    from owlapy.parser import manchester_to_owl_expression

    result = manchester_to_owl_expression(CORRECT_TRIPLE, TEST_NS)
    assert result is not None


def test_correct_syntax_long():
    """A long union as a restriction filler (6 operands) is valid."""
    from owlapy.parser import manchester_to_owl_expression

    result = manchester_to_owl_expression(CORRECT_LONG, TEST_NS)
    assert result is not None


def test_correct_gci_subclassof():
    """A SubClassOf expression with correct restriction order is valid.

    ``manchester_to_owl_expression`` only parses the *right-hand side* of a
    ``SubClassOf`` axiom (i.e. the restriction expression, without the
    ``ClassName SubClassOf`` prefix).
    """
    from owlapy.parser import manchester_to_owl_expression

    rhs = GCI_CORRECT.split("SubClassOf", 1)[1].strip()
    result = manchester_to_owl_expression(rhs, TEST_NS)
    assert result is not None


# ---------------------------------------------------------------------------
# Failing tests — union-first patterns that trigger the parser bug
# ---------------------------------------------------------------------------


def test_union_first_single_expected_failure():
    """A single class in parens BEFORE a restriction keyword FAILS to parse.

    The parser greedily consumes ``(A)`` as a parenthesized class expression
    and leaves ``some p`` unconsumed, raising ``IncompleteParseError``.
    """
    from owlapy.parser import manchester_to_owl_expression
    from parsimonious.exceptions import IncompleteParseError

    with pytest.raises(IncompleteParseError):
        manchester_to_owl_expression(UNION_FIRST_SINGLE, TEST_NS)


def test_union_first_pair_expected_failure():
    """A pair union in parens BEFORE a restriction keyword FAILS to parse.

    ``(A or B)`` is consumed by the parenthesised-union rule; ``some p``
    remains unconsumed.
    """
    from owlapy.parser import manchester_to_owl_expression
    from parsimonious.exceptions import IncompleteParseError

    with pytest.raises(IncompleteParseError):
        manchester_to_owl_expression(UNION_FIRST_PAIR, TEST_NS)


def test_union_first_triple_expected_failure():
    """A triple union in parens BEFORE a restriction keyword FAILS to parse.

    This is the exact pattern from the ELK reasoner GCI output for
    ``ImpairedSkinIntegrity`` in the NANDA-I taxonomy.
    """
    from owlapy.parser import manchester_to_owl_expression
    from parsimonious.exceptions import IncompleteParseError

    with pytest.raises(IncompleteParseError):
        manchester_to_owl_expression(UNION_FIRST_TRIPLE, TEST_NS)


def test_union_first_long_expected_failure():
    """A long union in parens BEFORE a restriction keyword FAILS to parse.

    Six operands are used to match the defining-characteristics union of
    ``ImpairedSkinIntegrity``.
    """
    from owlapy.parser import manchester_to_owl_expression
    from parsimonious.exceptions import IncompleteParseError

    with pytest.raises(IncompleteParseError):
        manchester_to_owl_expression(UNION_FIRST_LONG, TEST_NS)


def test_gci_union_first_expected_failure():
    """A SubClassOf GCI with union-first restriction order FAILS to parse.

    This mirrors the exact flow in ``reasoner.verbalize_gci_justifications``:
    the ELK explanation line is split on ``SubClassOf``, and the right-hand
    side is a union-first expression that crashes ``manchester_to_owl_expression``.
    """
    from owlapy.parser import manchester_to_owl_expression
    from parsimonious.exceptions import IncompleteParseError

    with pytest.raises(IncompleteParseError):
        manchester_to_owl_expression(GCI_UNION_FIRST, TEST_NS)


# ---------------------------------------------------------------------------
# Round-trip assertion: verify that the workaround in
# reasoner.verbalize_gci_justifications would work.
# ---------------------------------------------------------------------------


def test_reorder_workaround_produces_valid_expression():
    """Demonstrate the fix: reverse the order to ``p some (A or B or C)``.

    This is what a consumer should do before calling
    ``manchester_to_owl_expression`` when a union-first pattern is detected.
    """
    from owlapy.parser import manchester_to_owl_expression

    # Simulate the workaround: extract the parenthesised union and property,
    # then reassemble in property-first order.
    def reorder(expr: str) -> str:
        """Convert '(A or B or C) some p' to 'p some (A or B or C)'."""
        parts = expr.split(" some ", 1)
        if len(parts) != 2:
            return expr
        union_part = parts[0].strip()
        prop_part = parts[1].strip()
        # Strip outer parens from the union if present
        if union_part.startswith("(") and union_part.endswith(")"):
            union_part = union_part[1:-1]
            return f"{prop_part} some ({union_part})"
        return expr

    result = manchester_to_owl_expression(reorder(UNION_FIRST_TRIPLE), TEST_NS)
    assert result is not None

    result = manchester_to_owl_expression(
        reorder(GCI_UNION_FIRST.split(" SubClassOf ", 1)[1]), TEST_NS
    )
    assert result is not None

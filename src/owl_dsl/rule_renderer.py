"""Horn rule rendering for Controlled Natural Language.

This module provides functionality to translate Description Logic (DL) Horn rules
and General Concept Inclusions (GCIs) into human-readable natural language sentences.
It processes logical premises and conclusions to generate narrative explanations
that describe the implications of the ontology's rules.
"""

from __future__ import annotations

from typing import Any

from pyhornedowl import PyIndexedOntology
from rdflib import RDF, RDFS, URIRef, Variable

from fuxi.Horn import PositiveConditions
from fuxi.Horn.PositiveConditions import And, Uniterm

from owl_dsl import prefix_with_indefinite_article, pretty_print_list
from owl_dsl.renderer import CNLRenderer, RDFS_LABEL
from rdflib.term import Literal


class RuleRenderer(CNLRenderer):
    """Renders FuXi Horn rules as CNL sentences using ontology phrase templates.

    Inherits OWL class/property CNL rendering from :class:`~owl_dsl.renderer.CNLRenderer`
    and adds :meth:`render_rule` / :meth:`render_rule_component` for Horn logic.

    Property phrase templates (``OWL_DSL_000001`` annotation values) must be
    loaded into :attr:`relevant_role_restriction_cnl_phrasing` before calling
    :meth:`render_rule`.  Use
    :func:`~owl_dsl.annotations.configure_cnl_from_annotations` to do this from
    the ontology's annotation graph.

    Args:
        ontology: ``PyIndexedOntology`` object whose properties carry the CNL
            annotation templates.
        ontology_namespace: Base URI string of the ontology namespace, used to
            resolve entity labels via ``get_annotations(term, RDFS_LABEL)``.
        verbose: Passed through to :class:`~owl_dsl.renderer.CNLRenderer`.
        custom_role_rendering: When ``True`` (default) CNL phrase templates are
            used; when ``False`` property names are rendered in DL syntax.
        lowercase_labels: When ``True`` (default) entity labels are lower-cased
            before rendering, matching standard OBO Foundry conventions.
        collect_definition_info: Passed through to
            :class:`~owl_dsl.renderer.CNLRenderer`.
    """

    def __init__(
        self,
        ontology: PyIndexedOntology | None,
        ontology_namespace: str,
        verbose: bool = False,
        custom_role_rendering: bool = True,
        lowercase_labels: bool = True,
        collect_definition_info: bool | None = None,
    ) -> None:
        super().__init__(
            ontology=ontology,
            ontology_namespace=ontology_namespace,
            verbose=verbose,
            custom_role_rendering=custom_role_rendering,
            lowercase_labels=lowercase_labels,
            collect_definition_info=collect_definition_info,
        )

    def render_rule(self, rule) -> str:
        """Render a FuXi ``HornClause`` as a CNL sentence.

        Dispatches to :meth:`render_rule_component` for body and head, then
        assembles the final sentence.  A body that is a single class-membership
        Uniterm (``?x rdf:type :C``) produces the ``"Every …"`` form; any other
        body produces the ``"If …, then …"`` conditional form.

        Args:
            rule: A FuXi ``HornClause`` (element of the list returned by
                :func:`fuxi.Horn.HornRules.HornFromN3`).

        Returns:
            A single CNL sentence ending with ``"."``.

        Example — universal rule (body is a class-membership Uniterm)::

            # "Every Web Slinger has flying as their means of locomotion."

        Example — conditional rule (body is a conjunction)::

            # "If ?x has ?y as their parent and ?y has ?z as their sister,
            #  then ?x has ?z as their aunt."

        .. seealso::
            :func:`~owl_dsl.annotations.configure_cnl_from_annotations` —
            must be called before ``render_rule`` to populate phrase templates.
        """
        variables = [
            *(
                rule.formula.body.variables
                if isinstance(rule.formula.body, And)
                else rule.declare
            )
        ]
        head = self.render_rule_component(
            rule.formula.head,
            body_is_conjunction=isinstance(rule.formula.body, And),
            body_variables=variables,
        )
        body = self.render_rule_component(rule.formula.body, rendering_body=True)
        rule_phrase = (
            f"{body} {head}."
            if body.startswith("Every ")
            else f"If {body}, then {head}."
        )
        return rule_phrase

    def get_term_label(self, term: str) -> str:
        """Return the ``rdfs:label`` of an ontology entity identified by IRI.

        Args:
            term: IRI string of the entity (e.g. ``"http://example.org/aunt"``).

        Returns:
            The first ``rdfs:label`` value, as a plain string.

        Raises:
            AttributeError: If the IRI is not found in the ontology.
        """
        if isinstance(term, Literal):
            return None
        elif self.ontology is not None:
            labels = self.ontology.get_annotations(term, RDFS_LABEL)
            if labels:
                return labels[0]

        graph = getattr(self, "_rdflib_graph", None)
        if graph is not None:
            term_ref = term if isinstance(term, URIRef) else URIRef(str(term))
            label = graph.value(term_ref, RDFS.label)
            if label is not None:
                return str(label)

        term_str = str(term)
        if "#" in term_str:
            return term_str.rsplit("#", 1)[-1]
        if "/" in term_str:
            return term_str.rsplit("/", 1)[-1]
        return term_str

    def render_rule_component(
        self,
        rule_component: PositiveConditions,
        body_is_conjunction: bool = False,
        body_variables: list[Variable] | None = None,
        rendering_body: bool = False,
    ) -> str:
        """Recursively render one component of a Horn rule body or head.

        Handles two structural cases:

        **Single Uniterm** — a triple pattern ``(subject, predicate, object)``:

        * ``rdf:type`` predicate → class membership.  Body position: ``"Every
          <label>"``.  Head position: ``"a(n) <label>"``.
        * Other predicate → property assertion.  The registered CNL template for
          the predicate (index 0, singular form) is filled with the rendered
          object term.  When ``body_is_conjunction`` is ``False`` (universal
          rule), the subject variable is prepended to the head phrase so the
          rule reads fluently.

        **Conjunction (And)** — iterates over member Uniterms, interleaving
        class-membership Uniterms immediately before the property triples that
        reference their variables, producing readable output such as::

            "?x has ?y as their parent and ?y has ?z as their sister"

        Args:
            rule_component: A :class:`~fuxi.Horn.PositiveConditions.Uniterm` or
                :class:`~fuxi.Horn.PositiveConditions.And`.
            body_is_conjunction: ``True`` when the rule body is an ``And`` node.
                Suppresses subject-prefix output for head Uniterms (the subject
                is already named in the body).
            body_variables: Variables declared in the rule body, used when
                rendering the head of a conjunction-body rule.
            rendering_body: ``True`` when rendering the body fragment; affects
                whether class-membership Uniterms emit ``"Every …"`` vs.
                ``"a(n) …"``.

        Returns:
            The rendered phrase fragment (no trailing punctuation).

        Note:
            If a property predicate has no CNL template in
            :attr:`relevant_role_restriction_cnl_phrasing`, a default template
            ``"has {} as their <label>"`` is derived from the property's
            ``rdfs:label`` as a fallback.
        """
        if isinstance(rule_component, Uniterm):
            object_term = rule_component.arg[-1]
            if self.is_class_membership_uniterm(rule_component):
                class_label = self.get_term_label(object_term)
                if rendering_body:
                    # Universal antecedent: "Every <C>"
                    return f"Every {class_label}"
                else:
                    # Class-membership in a head/consequent: "?x is a(n) <C>"
                    subject_terms = ", ".join(
                        v.n3() for v in set(rule_component.variables)
                    )
                    return (
                        f"{subject_terms} is "
                        f"{prefix_with_indefinite_article(class_label)}"
                    )
            else:
                custom_phrases = self.relevant_role_restriction_cnl_phrasing.get(
                    rule_component.op
                )
                if custom_phrases is None:
                    prop_label = self.get_term_label(rule_component.op)
                    custom_phrases = (f"has {{}} as their {prop_label}",)
                if any(map(lambda i: isinstance(i, Variable), rule_component.arg)):
                    subject, object_ = rule_component.arg
                    # Prepend the subject only when it is not already named by an
                    # enclosing "Every <C>" antecedent.  Body triples and the head
                    # of a conjunction-body rule keep their explicit subject; the
                    # head of a universal ("Every ...") rule drops it.
                    subject_prefix = (
                        f"{self.render_condition_argument(subject)} "
                        if (rendering_body or body_is_conjunction)
                        else ""
                    )
                    return (
                        f"{subject_prefix}"
                        f"{custom_phrases[0].format(self.render_condition_argument(object_))}"
                    )
                else:
                    term_label = self.render_condition_argument(object_term)
                    return custom_phrases[0].format(term_label)

        elif isinstance(rule_component, And):
            fragments: list[str] = []
            processed_conditions: set[int] = set()

            # Pre-render all items once; pairs of (rendered string, original Uniterm)
            items = [
                (self.render_rule_component(i, rendering_body=rendering_body), i)
                for i in rule_component
            ]

            for rule_string, condition in items:
                if id(condition) in processed_conditions:
                    continue

                # Collect variables in this condition that also appear in a class-membership Uniterm
                vars: list[Variable] = []
                class_instance_variables: dict[Variable, Uniterm] = {}
                for var in [i for i in condition.arg if isinstance(i, Variable)]:
                    for component in [
                        i
                        for i in rule_component
                        if i != condition
                        and isinstance(i, Uniterm)
                        and self.is_class_membership_uniterm(i)
                    ]:
                        # Insert the class-membership fragment immediately before this property fragment
                        class_instance_variables[var] = component
                        vars.append(var)
                        break

                if any(var in class_instance_variables for var in vars):
                    # Emit each class-membership fragment once, then the current property fragment
                    seen_components: set[int] = set()
                    for var in vars:
                        if var in class_instance_variables:
                            membership_component = class_instance_variables[var]
                            if id(membership_component) not in seen_components:
                                membership_string = next(
                                    s for s, c in items if c is membership_component
                                )
                                fragments.append(membership_string)
                                processed_conditions.add(id(membership_component))
                                seen_components.add(id(membership_component))
                    fragments.append(rule_string)
                else:
                    # No class-membership context;
                    return pretty_print_list([i[0] for i in items], and_char=", and ")
                    subject, object_ = condition.arg
                    custom_phrases = self.relevant_role_restriction_cnl_phrasing.get(
                        condition.op
                    )
                    if custom_phrases is None:
                        prop_label = self.get_term_label(condition.op)
                        custom_phrases = (f"has {{}} as their {prop_label}",)
                    object_term = self.render_condition_argument(object_)
                    subject_term = self.render_condition_argument(subject)
                    fragments.append(
                        f"{subject_term} {custom_phrases[0].format(object_term)}"
                    )

            return pretty_print_list(fragments, and_char=", and ")

    def is_class_membership_uniterm(self, rule_component: Uniterm) -> bool:
        """Return ``True`` if *rule_component* asserts ``rdf:type`` membership.

        A Uniterm is a class-membership assertion when its predicate is
        ``rdf:type``; these are rendered as ``"Every <C>"`` (body) or
        ``"a(n) <C>"`` (head) rather than via a property phrase template.

        Args:
            rule_component: The Uniterm to inspect.

        Returns:
            ``True`` iff ``rule_component.op == rdf:type``.

        Examples:
            >>> from unittest.mock import MagicMock
            >>> from rdflib import RDF, URIRef
            >>> from fuxi.Horn.PositiveConditions import Uniterm
            >>> uniterm_type = MagicMock(spec=Uniterm)
            >>> uniterm_type.op = RDF.type
            >>> renderer = MagicMock(spec=RuleRenderer)
            >>> RuleRenderer.is_class_membership_uniterm(renderer, uniterm_type)
            True
            >>> uniterm_prop = MagicMock(spec=Uniterm)
            >>> uniterm_prop.op = URIRef("http://example.org/parent")
            >>> RuleRenderer.is_class_membership_uniterm(renderer, uniterm_prop)
            False
        """
        return rule_component.op == RDF.type

    def render_condition_argument(self, object_term) -> str:
        """Render a single Uniterm argument as a CNL token.

        Variables become ``"?<name>"``; IRI terms are looked up in the ontology
        and their ``rdfs:label`` is returned.

        Args:
            object_term: A :class:`rdflib.Variable` or an IRI string/URIRef.

        Returns:
            ``"?<name>"`` for variables; the entity's ``rdfs:label`` for IRIs.

        Examples:
            >>> from rdflib import Variable
            >>> from unittest.mock import MagicMock
            >>> renderer = MagicMock(spec=RuleRenderer)
            >>> RuleRenderer.render_condition_argument(renderer, Variable("x"))
            '?x'
        """
        return (
            f"?{object_term}"
            if isinstance(object_term, Variable)
            else (
                f"'{str(object_term)}'"
                if isinstance(object_term, Literal)
                else self.get_term_label(object_term)
            )
        )

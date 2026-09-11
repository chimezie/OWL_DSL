# OWL_DSL

A Python library for transforming OWL ontologies into human-readable Controlled Natural Language (CNL).
It bridges the gap between formal Description Logic (DL) and domain experts by rendering OWL 2 ontology class
expressions, Horn rules, and logical entailments as fluent English NL sentences in a configurable way, 
for use with Natural Language Processing tools such as Large Language Models (LLMs).

It primarily targets the [OWL 2 EL profile](https://www.w3.org/TR/owl2-profiles/#Feature_Overview)
while maintaining broad compatibility with other OWL 2 profiles.

## Table of Contents

- [Core Concepts](#core-concepts)
- [Dependencies](#dependencies)
- [Installation](#installation)
- [Getting Started (Python API)](#getting-started-python-api)
- [Configuration](#configuration)
  - [OWL Annotation Properties](#owl-annotation-properties)
  - [YAML Configuration File](#yaml-configuration-file)
- [CLI Tools](#cli-tools)
  - [owl_dsl.review](#owl_dslreview)
  - [owl_dsl.reason](#owl_dslreason)
  - [owl_dsl.render_rules](#owl_dslrender_rules)
- [Horn Rule Rendering (Python API)](#horn-rule-rendering-python-api)
- [Tests](#tests)
- [Citations](#citations)

## Core Concepts

OWL_DSL is built around a few key components:

- **Rendering Engine** (`owl_dsl.renderer.CNLRenderer`): Converts DL axioms into English sentences using py-horned-owl's axiom-centric model and a configurable set of phrasing templates.
- **Horn Rule Renderer** (`owl_dsl.rule_renderer.RuleRenderer`): Extends the rendering engine to translate FuXi Horn rules (parsed from Notation 3, or RIF, et.) into CNL.
- **Annotation Loading** (`owl_dsl.annotations`): Reads OWL annotation properties from an RDF graph to configure phrasing templates, definition properties, and other rendering settings.
- **CLI Tools**:
  - `owl_dsl.review`: Review class definitions, find classes/properties, load ontologies, and lint annotations.
  - `owl_dsl.reason`: Extract and explain logical entailments using the ELK reasoner via ROBOT.
  - `owl_dsl.render_rules`: Extract Horn rules from an ontology via FuXi DLP and render them as CNL sentences.
- **Configuration**: Uses either OWL annotation properties embedded in the ontology (preferred) or a YAML-based configuration-file to customize how terms are rendered. It has one such file for OBO Ontologies

## Dependencies

| Library | Purpose |
|---------|---------|
| [py-horned-owl](https://ontology-tools.github.io/py-horned-owl/) | Primary OWL library — loads and queries OWL ontologies |
| [owlready2](https://github.com/pwin/owlready2) | Legacy/limited use — reasoning path only |
| [owlapy](https://github.com/dice-group/owlapy) | OWL API for Python — Manchester parsing and reasoning |
| [rdflib](https://github.com/RDFLib/rdflib) | RDF graph library — SPARQL queries and graph manipulation |
| [Click](https://click.palletsprojects.com/) | CLI framework |
| [FuXi](https://github.com/RDFLib/FuXi) | InfixOWL syntax, DLP Horn rule extraction, and reasoning |
| [spaCy](https://spacy.io/) (optional) | Indefinite article selection (a/an) via `en_core_web_sm` |
| [ROBOT](https://robot.obolibrary.org/) (optional, for reasoning) | ELK reasoner integration for entailment explanation |

## Installation

### From PyPI

```bash
pip install owl_dsl
```

With NLP support (spaCy for indefinite article selection):

```bash
pip install owl_dsl[nlp]
```

Then download the spaCy model:

```bash
python -m spacy download en_core_web_sm
```

### From Source

```bash
git clone https://github.com/chimezie/OWL_DSL.git
cd OWL_DSL
pip install -e .
```

For development:

```bash
pip install -e ".[test,nlp,docs]"
```

### Installing with uv

```bash
git clone https://github.com/chimezie/OWL_DSL.git owl_dsl
uv venv
source .venv/bin/activate
uv pip install owl_dsl
```

## Getting Started (Python API)

The simplest way to see OWL_DSL in action is to load an ontology and render a class:

```python
from pyhornedowl import open_ontology
from owl_dsl.renderer import CNLRenderer

# 1. Load your ontology
ontology = open_ontology("path/to/ontology.owl")
handler = CNLRenderer(ontology, "http://example.org#")

# 2. Render classes to natural language
for class_iri in ontology.get_classes():
    labels = ontology.get_annotations(class_iri, "rdfs:label")
    if labels:
        print(f"{labels[0]}: {handler.handle_owl_class(class_iri)}")
```

The `CNLRenderer` analyzes the logical structure of OWL 2 classes and generates natural English descriptions, with 
automated indefinite article selection (a/an), logical constructs (AND, OR, NOT), cardinality and role restrictions, 
and custom phrasing for specific properties.

## Configuration

There are two ways to configure how OWL_DSL renders terms:

### OWL Annotation Properties (Preferred)

The recommended approach is to embed the CNL configuration directly in your ontology using custom OWL 2 annotation properties,
combining the rendering logic with the knowledge model so the ontology is self-documenting and portable as well as
machine-understandable.

The annotation properties are defined in the namespace
`https://github.com/chimezie/OWL_DSL/tree/main/ontology_configurations/`:

| Annotation | Purpose |
|---|---|
| `OWL_DSL_000001` | Singular predicate string template (e.g., `"has {} as their means of locomotion"`) |
| `OWL_DSL_000002` | Plural predicate string template |
| `OWL_DSL_000003` | Prompt phrase using the predicate to request a definition |
| `OWL_DSL_000004` | Class inferences to ignore (an RDF collection of class IRIs) |
| `OWL_DSL_000005` | Expert definition properties (e.g., `IAO_0000115`) |
| `OWL_DSL_000006` | Standard role restriction "is phrasing" — marks properties whose CNL template is derived as `"is <label> {}"` |
| `OWL_DSL_000007` | Reflexive roles — custom phrasing for reflexive property restrictions |

When annotations are present, use `configure_cnl_from_annotations` to load them into a renderer:

```python
from owl_dsl.annotations import configure_cnl_from_annotations
from rdflib import Graph

# Load the OWL file separately with rdflib when ontology is a PyIndexedOntology
graph = Graph().parse("path/to/ontology.owl")
configure_cnl_from_annotations(handler, graph)
```

### YAML Configuration File

You can also use an external YAML configuration file for rapid prototyping or when annotations are not available.
OWL_DSL includes a sample config in `ontology_configurations/OBO.CNL.yaml` with templates for ontologies in the
[Open Biological and Biomedical Ontology Foundry](https://obofoundry.org/).

The YAML file supports the following directives:

#### tooling.expert_definition_properties

Specifies annotation properties that carry human-readable definitions. For example, the IAO definition property:

```yaml
tooling:
  expert_definition_properties: ['http://purl.obolibrary.org/obo/IAO_0000115']
```

#### standard_role_restriction_is_phrasing

A list of property URIs whose CNL template is determined by the pattern `"is <label> {}"`, derived from the
property's `rdfs:label`.

#### role_restriction_phrasing

Custom phrasing for role restrictions, with singular, plural, and definition prompt forms:

```yaml
role_restriction_phrasing:
  'http://purl.obolibrary.org/obo/RO_0002496':
    - 'began during or after {}'
    - 'began during or after {}'
    - 'What does {} begin during or after?'
```

#### reflexive_roles

Custom phrasing for reflexive property restrictions:

```yaml
reflexive_roles:
  - 'http://purl.obolibrary.org/obo/RO_0002481':
    - 'that interacts with itself via kinase activity'
```

#### role_restriction_wo_articles

A list of property URIs for which the CNL rendering should omit indefinite articles.

To use a configuration file from Python:

```python
from owl_dsl.annotations import resolve_definition_properties

# Use a YAML file as a fallback for annotations in an ontology
definition_properties, _ = resolve_definition_properties(handler, None, "path/to/ontology.owl", "path/to/config.yaml")
```

#### class_inference_to_ignore

Classes whose entailed superclasses are too general to render usefully (e.g., upper ontology terms):

```yaml
class_inference_to_ignore: ['material entity', 'anatomical entity', 'process']
```

## CLI Tools

### owl_dsl.review

The `owl_dsl.review` command lets you load ontologies, render classes, find classes/properties, and lint
annotation coverage without writing Python.

```bash
$ owl_dsl.review --help
Usage: owl_dsl.review [OPTIONS] [OWL_URL_OR_PATH]

Options:
  -a, --action [render_class|find_properties|load_owl|destroy_sqlite|
                find_classes|list_ontologies|lint_ontology]
                                  Action to perform  [required]
  --by-id                         Find ontology class by ID (otherwise by
                                  rdfs:label)
  --class-reference TEXT          The ID (or label) of the Uberon class
  --class-search TEXT             The string to use for searching for a class
  --regex-search / --no-regex-search
  --verbose / --no-verbose
  --exact-class-labels / --no-exact-class-labels
                                  Render OWL class labels as is (don't
                                  convert to lower case by default)
  --configuration-file TEXT       Path to configuration YAML file for NL
                                  rendering of ontology terms
  --sqlite-file TEXT              Location of SQLite file used for
                                  persistence  [required]
  --prefix TEXT                   Filter properties by URI prefix (only for
                                  'find_properties' action)
  --prop-reference-label TEXT     Filter properties by rdfs:label using
                                  REGEX (only for 'find_properties' action)
  --show-property-definition-usage
                                  Show class definition examples for listed
                                  properties (only for 'find_properties'
                                  action)
  --limit INTEGER                 Limit number of results (only for
                                  'find_properties' action with
                                  --show-property-definition-usage)
  --ontology-uri TEXT             The URI of the ontology  [required]
  --ontology-namespace-baseuri TEXT
                                  The base URI of the ontology namespace
                                  [required]
  --help                          Show this message and exit.
```

The `--ontology-uri` option specifies the URI of the ontology into which the ontology is loaded.
The `--ontology-namespace-baseuri` specifies the base URI used to resolve entity local names.

OWL_DSL loads ontologies directly using `pyhornedowl.open_ontology()`. The `--sqlite-file` option specifies the location of the persistence database.

#### Actions

| Action | Description                                                        |
|---|--------------------------------------------------------------------|
| `load_owl` | Load an OWL file into the SQLite backend (needed for inference)    |
| `render_class` | Render an OWL class definition as CNL (default)                    |
| `find_classes` | Search for classes by label (substring or regex)                   |
| `find_properties` | List properties, optionally filtered by prefix or label regex      |
| `lint_ontology` | Interactively inspect and annotate ontology classes and properties |
| `list_ontologies` | Show all ontologies loaded in the SQLite backend                   |
| `destroy_sqlite` | Remove the SQLite persistence file                                 |

#### Rendering a Class

Once the ontology is loaded, classes can be rendered via label or local identifier:

```bash
owl_dsl.review --ontology-uri "http://purl.obolibrary.org/obo/uberon/uberon-base.owl#" \
               --configuration-file ontology_configurations/OBO.CNL.yaml \
               --sqlite-file /tmp/uberon.sqlite3 \
               --ontology-namespace-baseuri=http://purl.obolibrary.org/obo/ \
               --class-reference "vestibular aqueduct"
```

Output includes the URI, label, textual definition (from the annotation property defined in configuration),
and a logical definition rendered as CNL:

```
# http://purl.obolibrary.org/obo/UBERON_0002279 (vestibular aqueduct) #
## Textual definition ##
At the hinder part of the medial wall of the vestibule is the orifice...

## Logical definition ##
The vestibular aqueduct is defined in Uber-anatomy ontology as a foramen
of skull that is a conduit for a vein of vestibular aqueduct. It is a
foramen of skull. It is part of an osseus labyrinth vestibule. It is a
conduit for a vein of vestibular aqueduct
```

The same class can be rendered using its local identifier:

```bash
owl_dsl.review ... --by-id --class-reference UBERON_0002279
```

The `--exact-class-labels` option renders labels as-is (no lowercasing), which is useful when later referring
to classes by exact label via `--class-reference`.

#### Finding Properties

List properties filtered by URI prefix:

```bash
owl_dsl.review ... -a find_properties \
    --prefix http://purl.obolibrary.org/obo/BFO_ \
    --show-property-definition-usage --limit 1
```

The `--show-property-definition-usage` flag includes example class definitions that reference each property.
Use `--limit` to control how many examples to show per property.

### owl_dsl.reason

The `owl_dsl.reason` command explains logical entailments using the ELK reasoner (via ROBOT) and renders
justifications for General Concept Inclusion (GCI) axioms in natural language.

```bash
$ owl_dsl.reason --help
Usage: owl_dsl.reason [OPTIONS] [OWL_URL_OR_PATH]

Options:
  -a, --action [explain_logical_inferences|justify_gci]
                                  Action to perform  [required]
  --ontology-uri TEXT             The URI of the ontology  [required]
  --ontology-namespace-baseuri TEXT
                                  The base URI of the ontology namespace
                                  [required]
  --sqlite-file TEXT              Location of SQLite file used for
                                  persistence  [required]
  --configuration-file TEXT       Path to configuration YAML file for NL
                                  rendering of ontology terms  [required]
  --class-reference TEXT          The IRI (or label) of the class
  --manchester-owl-expression TEXT
                                  Manchester OWL expression for GCI (used
                                  with justify_gci)
  --by-id                         Find ontology class by ID (otherwise by
                                  rdfs:label)
  --verbose / --no-verbose
  --exact-class-labels / --no-exact-class-labels
                                  Render OWL class labels as is (don't
                                  convert to lower case by default)
  --help                          Show this message and exit.
```

#### Explaining Logical Inferences

The `explain_logical_inferences` action displays logically entailed GCI axioms
(subClassOf/subsumption) that are *not* directly asserted in the ontology, using
the ELK reasoner:

```bash
owl_dsl.reason --ontology-uri "http://purl.obolibrary.org/obo/uberon/uberon-base.owl#" \
               --configuration-file ontology_configurations/OBO.CNL.yaml \
               --sqlite-file /tmp/ontology.sqlite3 \
               --ontology-namespace-baseuri=http://purl.obolibrary.org/obo/ \
               --class-reference "vestibular aqueduct" uberon-base-plus-ro.owl
```

Output shows a chain of justifications explaining how the entailed subsumption is derived:

```
How is every 'vestibular aqueduct' (UBERON_0002279) a 'bone foramen'?

  Every vestibular aqueduct is a foramen of skull that is a conduit for
  a vein of vestibular aqueduct and vice versa.
    Every foramen of skull is a bone foramen
```

#### Skipping General Classes

Classes that are too high in an upper ontology (e.g., BFO terms) can be excluded from
entailment output via the `class_inference_to_ignore` configuration directive in the YAML file.

#### Justifying Custom GCI Axioms

The `justify_gci` action explains an arbitrary GCI axiom expressed in
[Manchester OWL 2 syntax](https://www.w3.org/TR/owl2-manchester-syntax/):

```bash
owl_dsl.reason ... -a justify_gci \
    --class-reference "histamine secretion mediated by IgE immunoglobulin" \
    --manchester-owl-expression "'process' and 'part of' some 'inflammatory response'"
```

The `--manchester-owl-expression` option accepts labels (single-quoted) to refer to classes
and properties. The command then generates a human-readable chain of justifications showing
why the subsumption holds, including domain/range axioms, subproperty chains, and
equivalence relationships.

### owl_dsl.render_rules

The `owl_dsl.render_rules` command extracts Horn rules from an OWL ontology using FuXi's
Description Logic Programming (DLP) system and renders each rule as a CNL sentence via
`RuleRenderer`.

```bash
$ owl_dsl.render_rules --help
Usage: owl_dsl.render_rules [OPTIONS] [OWL_URL_OR_PATH]

  Render Horn rules extracted from an OWL ontology as CNL sentences.

  Loads the ontology from OWL_URL_OR_PATH (a file path or URL) or from a
  previously-populated SQLite backend (--sqlite-file), extracts Horn rules
  via FuXi's DLP system, and prints each rule as a natural-language sentence.

Options:
  --ontology-uri TEXT             URI of the ontology. Inferred from the OWL
                                  file when a local path is given.
  --ontology-namespace-baseuri TEXT
                                  Base URI of the ontology namespace. Defaults
                                  to --ontology-uri when omitted.
  --sqlite-file TEXT              SQLite backend file for an already-loaded
                                   world.
  --configuration-file TEXT       YAML configuration file for CNL rendering
                                  (same format as owl_dsl.review). When omitted,
                                  OWL_DSL_000001 annotations in the ontology
                                  are used.
  --skip-subclass-rules / --no-skip-subclass-rules
                                  Skip pure rdf:type → rdf:type rules (already
                                  covered by OWL class rendering).
  --verbose / --no-verbose
  --help                          Show this message and exit.

  Example (from file):
    owl_dsl.render_rules --ontology-uri http://example.org/ \
        --ontology-namespace-baseuri http://example.org/ \
        path/to/my.owl

  Example (from SQLite world):
    owl_dsl.render_rules --ontology-uri http://example.org/ \
        --ontology-namespace-baseuri http://example.org/ \
        --sqlite-file my_world.sqlite
```

Derived predicates are identified automatically from the rule heads; hybrid predicates
(those that appear both as derived and as direct facts) are reported in verbose mode.

Property phrase templates are loaded from `OWL_DSL_000001` annotations on object properties
in the ontology graph. Properties without annotations fall back to a default template
derived from the property's `rdfs:label`. An optional YAML configuration file can supplement
or override annotation-derived templates.

## Horn Rule Rendering (Python API)

The `RuleRenderer` class extends `CNLRenderer` to render FuXi Horn rules as CNL sentences,
reusing the same property phrase templates that drive OWL class rendering.

A Horn rule `{ body } => { head }` is rendered as:

- `"Every <Class> <phrase>."` — when the body is a single `rdf:type` assertion (universal rule).
- `"If <body phrases>, then <head phrase>."` — when the body is a conjunction of property triples.

### Example

```python
from io import StringIO
from fuxi.Horn.HornRules import HornFromN3
from fuxi.Horn.PositiveConditions import Uniterm
from rdflib import RDF
from pyhornedowl import open_ontology, PyIndexedOntology
from pyhornedowl.components import DeclareClass, DeclareObjectProperty, AnnotationAssertion
from owl_dsl.rule_renderer import RuleRenderer
from owl_dsl.annotations import configure_cnl_from_annotations
from rdflib import Graph

BASE_URI = "http://example.org/"
OWL_DSL_URI = "https://github.com/chimezie/OWL_DSL/tree/main/ontology_configurations/"

N3_RULES = """
@prefix : <http://example.org/>.
{ ?slinger a :WebSlinger } => { ?slinger :locomotion :flying } .
{ ?heli a :Helicopter } => { ?heli :locomotion :flying } .
{ ?flyer :locomotion :flying . ?street :traffic :heavy }
    => { ?street :suitable_observer ?flyer } .
"""

program = list(HornFromN3(StringIO(N3_RULES)))

# Use PyIndexedOntology to define the ontology structure
ontology = PyIndexedOntology()
ontology.add_component(DeclareClass(BASE_URI + "WebSlinger"))
ontology.add_component(DeclareClass(BASE_URI + "Helicopter"))
ontology.add_component(DeclareClass(BASE_URI + "flying"))
ontology.add_component(DeclareClass(BASE_URI + "heavy"))

ontology.add_component(DeclareObjectProperty(BASE_URI + "locomotion"))
ontology.add_component(DeclareObjectProperty(BASE_URI + "traffic"))
ontology.add_component(DeclareObjectProperty(BASE_URI + "suitable_observer"))

# Add labels and CNL templates as annotations
# Note: In a real scenario, these would be in the OWL file
ontology.add_component(AnnotationAssertion(BASE_URI + "WebSlinger", "rdfs:label", "Web Slinger"))
ontology.add_component(AnnotationAssertion(BASE_URI + "Helicopter", "rdfs:label", "Helicopter"))
ontology.add_component(AnnotationAssertion(BASE_URI + "flying", "rdfs:label", "flying"))
ontology.add_component(AnnotationAssertion(BASE_URI + "heavy", "rdfs:label", "heavy"))

ontology.add_component(AnnotationAssertion(BASE_URI + "locomotion", "rdfs:label", "locomotion"))
ontology.add_component(AnnotationAssertion(BASE_URI + "locomotion", OWL_DSL_URI + "OWL_DSL_000001", "has {} as their means of locomotion"))

ontology.add_component(AnnotationAssertion(BASE_URI + "traffic", "rdfs:label", "traffic"))
ontology.add_component(AnnotationAssertion(BASE_URI + "traffic", OWL_DSL_URI + "OWL_DSL_000001", "has {} traffic"))

ontology.add_component(AnnotationAssertion(BASE_URI + "suitable_observer", "rdfs:label", "suitable_observer"))
ontology.add_component(AnnotationAssertion(BASE_URI + "suitable_observer", OWL_DSL_URI + "OWL_DSL_000001", "has {} as a suitable observer"))

# Create an rdflib graph for the renderer to load annotations from
graph = ontology.as_rdflib_graph()
renderer = RuleRenderer(ontology, BASE_URI, verbose=False, lowercase_labels=False)
configure_cnl_from_annotations(renderer, graph)

for rule in program:
    # Skip pure rdf:type => rdf:type rules (rendered by CNLRenderer)
    if not (isinstance(rule.formula.body, Uniterm) and
            rule.formula.body.op == RDF.type and
            isinstance(rule.formula.head, Uniterm) and
            rule.formula.head.op == RDF.type):
        print(renderer.render_rule(rule))
```

Output:

```
Every Web Slinger has flying as their means of locomotion.
Every Helicopter has flying as their means of locomotion.
If ?flyer has flying as their means of locomotion and ?street has heavy traffic,
then ?street has ?flyer as a suitable observer.
```

### Rule Rendering Summary

| Body | Head | Output form |
|---|---|---|
| `?x rdf:type :C` | property triple | `Every <C-label> <phrase>.` |
| conjunction of property triples | property triple | `If <conj phrases>, then <head phrase>.` |

Pure `rdf:type => rdf:type` rules (OWL subclass axioms) are typically skipped, since
`CNLRenderer` already handles OWL class rendering.

### Alternative (pure rdflib / InfixOwl)

```python
from rdflib import Graph, Namespace, RDF
from fuxi.Horn.HornRules import HornFromN3
from fuxi.Horn.PositiveConditions import Uniterm
from fuxi.Syntax.InfixOWL import Class, Property, AnnotationProperty, GraphContext
from owl_dsl.rule_renderer import RuleRenderer
from owl_dsl.annotations import configure_cnl_from_annotations

BASE_URI = "http://example.org/"
NS = Namespace(BASE_URI)
OWL_DSL = Namespace("https://github.com/chimezie/OWL_DSL/tree/main/ontology_configurations/")

program = list(HornFromN3(StringIO(N3_RULES)))
graph = Graph()

with GraphContext(graph, {"ex": NS}):
    phrase = AnnotationProperty(OWL_DSL.OWL_DSL_000001)
    Class(NS.WebSlinger).set_label("Web Slinger")
    Class(NS.Helicopter).set_label("Helicopter")
    Class(NS.flying).set_label("flying")

    locomotion = Property(NS.locomotion).set_label("locomotion")
    locomotion.set_annotation(phrase, "has {} as their means of locomotion")
    traffic = Property(NS.traffic).set_label("traffic")
    traffic.set_annotation(phrase, "has {} traffic")
    suitable_observer = Property(NS.suitable_observer).set_label("suitable_observer")
    suitable_observer.set_annotation(phrase, "has {} as a suitable observer")
    Class(NS.heavy).set_label("heavy")

renderer = RuleRenderer(None, BASE_URI, verbose=False, lowercase_labels=False)
configure_cnl_from_annotations(renderer, graph)

for rule in program:
    if not (isinstance(rule.formula.body, Uniterm) and
            rule.formula.body.op == RDF.type and
            isinstance(rule.formula.head, Uniterm) and
            rule.formula.head.op == RDF.type):
        print(renderer.render_rule(rule))
```

Notes:
- Keep the `@prefix : <http://example.org/>` in the N3 rules consistent with the ontology base URI.
- Property CNL phrases are taken from `OWL_DSL_000001` annotations on object properties.
- If your rules use `rdf:type` clauses, ensure class labels are present.
- `configure_cnl_from_annotations` must receive the rdflib graph that contains the annotations.

## Tests

```console
uv run --active --extra nlp pytest --disable-warnings tests/[...]
```

For reasoning tests, [ROBOT](https://robot.obolibrary.org/) must be installed and on your PATH.

## Citations

1. Fuchs, N. E., Kaljurand, K., & Kuhn, T. (2008). *Attempto controlled english for knowledge representation*. In Reasoning Web: 4th International Summer School 2008, Venice, Italy, September 7-11, 2008, Tutorial Lectures (pp. 104-124). Berlin, Heidelberg: Springer Berlin Heidelberg.
2. Rosse, Cornelius, and José LV Mejino Jr. *A reference ontology for biomedical informatics: the Foundational Model of Anatomy.* Journal of biomedical informatics 36.6 (2003): 478-500.
3. Ogbuji, Chimezie, and Rong Xu. *Lattices for representing and analyzing organogenesis.* Conference on Semantics in Healthcare and Life Sciences (CSHALS 2014), 2014.

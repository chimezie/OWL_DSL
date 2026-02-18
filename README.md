# Generative Redfoot
A Python Library for managing a Domain Specific Language (DSL) for an Ontology using OWL, Controlled Natural Languages 
(CNLs) [1], and naturally rendering definitions of its terms for use with Natural Language (NL) Processing tools such
as Large Language Models (LLMs), vectorization for use with In-context learning (ICL), and other applications of 
standardized ontologies artifacts like these (GO, OBO, SNOMED CT, and other standarized logic-based biomedical ontologies).

## Table of Contents
- [Introduction](#introduction)
- [Install](#installation)
- [Options](#options)
- [CNL configuration](#cnl-configuration)
- [Loading Ontology](#loading-ontology)
- [Rendering Classes](#rendering-classes)
- [Listing Properties](#listing-properties)
- [Curate OWL DSLs](#curate-owl-dsls)

## Introduction 
This library started as the script used to generate [Grammatical Ontology Anatomist dataset](cogbuji/MrGrammaticalOntology_anatomist),
extracted from the Web Ontology Language (OWL) representation of the Foundational Model of Anatomy [2] using Owlready2 to 
facilitate the extraction of the logical axioms in the FMA into a Controlled Natural Language (CNL) for use in 
serializing ontology as corpus for use in training Medical Large Language Models to be conversant in canonical, human anatomy.

It uses Owlready2 as an Object Relational Mapper (ORM) between the OWL assertions and their corresponding Description Logics
constructs, extends it with syntax serialization using the CNL defined for the ontology and the conventions.

As a result of the many [issues](https://github.com/cmungall/fma-fixes/issues/1) with the OWL representation of the FMA
for any contemporary work, the script was rewritten for use with [Uberon](https://obophenotype.github.io/uberon/),
a multi-species anatomy ontology, which had been useful in the past for prior bioinformatic research [3] by the author 
involving the use of anatomical knowledge representation for studying organigenesis.

It was also re-written for use with any OWL ontology that followed some basic conventions:

- **rdfs:label** annotation properties are used to label the classes and properties
- a definition annotation is provided for human-readable definitions of classes and properties (such as the `definition` annotation property from the Information Artifact Ontology (IAO) (`http://purl.obolibrary.org/obo/IAO_0000115`))
- A CNL configuration file that specifies textual templates for rendering classes, properties, and role restrictions in the ontology in NL.

## Installation

Below is an example of installing the library from the Github repository (after cloning it locally), using uv to 
[install it to a separate virtual environment](https://docs.astral.sh/uv/pip/environments/):

```bash
$ uv venv scratch
$ source scratch/bin/activate
(scratch) $ uv pip install .
(scratch) $uv run owl_dsl.corpus --ontology-uri "http://purl.obolibrary.org/obo/uberon/uberon-full.owl#" \
                                 --ontology-namespace-baseuri http://purl.obolibrary.org/obo/ \
                                --class-reference "vestibular aqueduct"
[..snip..]
Loaded ontology
Definition: At the hinder part of the medial wall of the vestibule is the orifice of the vestibular aqueduct, which extends to the posterior surface of the petrous portion of the temporal bone. It transmits a small vein, and contains a tubular prolongation of the membranous labyrinth, the ductus endolymphaticus, which ends in a cul-de-sac between the layers of the dura mater within the cranial cavity. [WP,unvetted]. # 
# http://purl.obolibrary.org/obo/UBERON_0002279 # 
The vestibular aqueduct is defined in Uberon as a foramen of skull that is a conduit for a vein of vestibular aqueduct. It is a foramen of skull. It is part of an osseus labyrinth vestibule. It is a conduit for a vein of vestibular aqueduct
```

## Options

The full command-line options are:

```bash
$ owl_dsl.corpus --help
Usage: owl_dsl.corpus [OPTIONS] [OWL_FILE]

Options:
  -a, --action [render_class|list_properties|load_owl|render_all_classes]
                                  Action to perform  [required]
  --by-id                         Find Uberon class by ID (otherwise by
                                  rdfs:label)
  --class-reference TEXT          The ID (or label) of the Uberon class
  --semantic-verbosity BOOLEAN    Just summarize training data
  --verbose / --no-verbose
  --configuration-file TEXT       Path to configuration YAML file
  --sqlite-file TEXT              Location of SQLite file (defaults to
                                  '/tmp/fma.sqlite3')
  --prefix TEXT                   Filter properties by URI prefix (only for
                                  'list_properties' action)
  --prop-reference-label TEXT     Filter properties by label using REGEX (only
                                  for 'list_properties' action)
  --show-property-definition-usage
                                  Show property definition usage references
                                  (only for 'list_properties' action)
  --limit INTEGER                 Limit number of results (only for
                                  'list_properties' action with --show-
                                  property-definition-usage)
  --ontology-uri TEXT             The URI of the ontology  [required]
  --ontology-namespace-baseuri TEXT
                                  The base URI of the ontology namespace
                                  [required]
  --help                          Show this message and exit.
```

Most importantly, the `--ontology-uri` is used to specify the URI/IRI of the world/ontology into which the
ontology is loaded and from.  The `--ontology-namespace-baseuri` option is used to specify the base URI of the ontology 
namespace. Also, OWL_DSL will use Owlready2's SQL Lite database to cache the ontology and will default to a file
located at `/tmp/fma.sqlite3`, but can be specified using the `--sqlite-file` option.

## CNL configuration

In order to use the owl_dsl.corpus script, you need to provide a configuration file that specifies the textual templates
for rendering classes and properties in a specified ontology in NL. 

OWL_DSL includes a config in the `ontology_configurations` directory named Uberon.CNL.yaml.

They are expected to define the following directives:

### tooling.expert_definition_properties

If it defines a section like this (for example for the [IAO ontology](https://obofoundry.org/ontology/iao.html)'s 
definition property):
```yaml
tooling:
  expert_definition_properties: ['http://purl.obolibrary.org/obo/IAO_0000115', #Information Artifact Ontology (IAO) define
                                  # A phrase describing how a term should be used and/or a citation to a work which uses
                                  # it. May also include other kinds of examples that facilitate immediate understanding,
                                  # such as widely know prototypes or instances of a class, or cases where a relation is
                                  # said to hold.
                                  ]
```

Then the property `IAO_0000115` will be used to render the definition of classes and properties in the ontology.

### standard_role_restriction_is_phrasing

Any properties specified in a list of URIs in a section with key that is the same as the heading for this section are
roles whose CNL templates can be deterministically determined via (where `prop_label` is the _*rdfs:label*_ of the property):

> is [prop_label]

And the definition prompt is assumed to be:

> What is {} [prop_label]?'

Which will not render property without using the `role_restriction_phrasing` directive.

### role_restriction_phrasing

In order to render a fully custom defintion prompt (and singular/plural rendering of a role restriction), you
can use this directive in this way:

```yaml
role_restriction_phrasing:
  # existence starts during or after
  # x existence starts during or after y if and only if the time point at which x starts is after or equivalent to the
  # time point at which y starts. Formally: x existence starts during or after y iff α (x) >= α (y).
  'http://purl.obolibrary.org/obo/RO_0002496':
    - 'began during or after {}'
    - 'began during or after {}'
    - 'What does {} begin during or after?'
```

It expects 3 items under the URI of the property as top item.  The first two are the singular/plural rendering of the role restrictions
The final is the definition prompt.

If only two are specified, the first is used for both singular the second renderings and the last one for the definition prompt.

### reflexive_role

## Loading Ontology
An ontology (Oberon in this case) can be initially loaded this way:

```bash
$ owl_dsl.corpus -a load_owl /path/to/uberon-full.owl
```

## Rendering Classes
Once the ontology is loaded, classes can be rendered using the `render_class` action, which is the default action and used
if none is specified via the `-a/--action` option.For example, the `vestibular aqueduct` Uberon class from before can be 
rendered by its ontology local identifier (`UBERON_0002279`) as an alternative:

```bash
$ owl_dsl.corpus -a render_class --ontology-uri "http://purl.obolibrary.org/obo/uberon/uberon-full.owl#" \
                                 --ontology-namespace-baseuri http://purl.obolibrary.org/obo/ \
                                 --by-id --class-reference UBERON_0002279
```

Note, the script complains about nlp not being initialized.  This can be addressed by installing spacy and:

```bash
$ uv run spacy download en_core_web_sm
```

If using uv or just

```bash
spacy download en_core_web_sm
```

Otherwise

## Listing Properties

The `list_properties` action can be used to list all properties in the ontology, matched by a specified URI  
or a REGEX pattern to apply to their rdfs:label values.  The `--show-property-definition-usage`, if specified, will
cause an example class, whose definition directly refers to the property in a GCI, or more (via the ``--limit``` toption).

For example, we can find all the BFO properties 
defined in the ontology:

```bash
$ owl_dsl.corpus --ontology-uri "http://purl.obolibrary.org/obo/uberon/uberon-full.owl#" \
                 --ontology-namespace-baseuri http://purl.obolibrary.org/obo/ -a list_properties \
                 --prefix http://purl.obolibrary.org/obo/BFO_ --show-property-definition-usage --limit 1
-  http://purl.obolibrary.org/obo/BFO_0000050 'part of' "a core relation that holds between a part and its whole"
	- http://purl.obolibrary.org/obo/GO_0061224 'mesonephric glomerulus development'
	- The mesonephric glomerulus development is defined in Uber-anatomy ontology as an anatomical structure development that results in the development of a mesonephric glomerulus. It is a glomerulus development. It is part of a mesonephric nephron development. It results in the development of a mesonephric glomerulus
[..snip..]
-  http://purl.obolibrary.org/obo/BFO_0000063 'precedes' "x precedes y if and only if the time point at which x ends is before or equivalent to the time point at which y starts. Formally: x precedes y iff ω(x) <= α(y), where α is a function that maps a process to a start point, and ω is a function that maps a process to an end point."
	- http://purl.obolibrary.org/obo/CL_0009086 'endothelial cell of respiratory system lymphatic vessel'
	- The endothelial cell of respiratory system lymphatic vessel is defined in Uber-anatomy ontology as an endothelial cell that is part of a respiratory system lymphatic vessel. It is an endothelial cell of lymphatic vessel. It is part of a respiratory system lymphatic vessel endothelium
[..snip..]                 
```

## Curate OWL DSLs
You can use a combination of the `list_properties` and `render_class` actions to browse the vocabulary of the ontology.
and find _"verbalizations"_ of the ontology terms that are awkward, identify the roles involved in the restriction 
expression used to render those awkward phrases, and update the CNL configuration with entries
for the following, as an example additions to an existing CNL configuration that address the awkward phrases:

```yaml
standard_role_restriction_is_phrasing:
  - http://purl.obolibrary.org/obo/uberon/core#proximally_connected_to
  - http://purl.obolibrary.org/obo/uberon/core#distally_connected_to
```

```bash
$ owl_dsl.corpus --ontology-uri "http://purl.obolibrary.org/obo/uberon/uberon-full.owl#" \
                 --ontology-namespace-baseuri http://purl.obolibrary.org/obo/ --class-reference "tarsal region"
Loaded ontology
Definition: Mesopodial segment of the pes, including the tarsal skeleton and associated tissues. # 
# http://purl.obolibrary.org/obo/UBERON_0004454 # 
The tarsal region is defined in Uber-anatomy ontology as a mesopodium region that is part of a pes. It is a mesopodium region. It is a 
lower limb segment. It is part of a pes. It has a tarsal skeleton as its skeleton. It distally connected to a metatarsus 
region. It proximally connected to a hindlimb zeugopod
````

The awkward phrases:
> It distally connected to a metatarsus 
> region. It proximally connected to a hindlimb zeugopod

After adding updating the configuration, the phrases are rendered correctly:

```bash
$ owl_dsl.corpus --ontology-uri "http://purl.obolibrary.org/obo/uberon/uberon-full.owl#" \
                 --ontology-namespace-baseuri http://purl.obolibrary.org/obo/ --class-reference "tarsal region"
Loaded ontology
Definition: Mesopodial segment of the pes, including the tarsal skeleton and associated tissues. # 
# http://purl.obolibrary.org/obo/UBERON_0004454 # 
The tarsal region is defined in Uber-anatomy ontology as a mesopodium region that is part of a pes. It is a mesopodium region. It is a lower limb segment. It is part of a pes. It has a tarsal skeleton as its skeleton. It is distally connected to a metatarsus region. It is proximally connected to a hindlimb zeugopod
```

# Citations #
1. Fuchs, N. E., Kaljurand, K., & Kuhn, T. (2008). *Attempto controlled english for knowledge representation*. In Reasoning Web: 4th International Summer School 2008, Venice, Italy, September 7-11, 2008, Tutorial Lectures (pp. 104-124). Berlin, Heidelberg: Springer Berlin Heidelberg.
2. Rosse, Cornelius, and José LV Mejino Jr. *A reference ontology for biomedical informatics: the Foundational Model of Anatomy.* Journal of biomedical informatics 36.6 (2003): 478-500.
3. Ogbuji, Chimezie, and Rong Xu. *Lattices for representing and analyzing organogenesis.* Conference on Semantics in Healthcare and Life Sciences (CSHALS 2014), 2014. 


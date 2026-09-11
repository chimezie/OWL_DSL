# OWL_DSL Project

This project helps to render [OWL 2 ontologies](https://www.w3.org/TR/owl-overview/) as natural language sentences
that a domain expert without knowledge of [Description Logic](https://en.wikipedia.org/wiki/Description_logic) or mathematical logic can understand.
It primarily uses [py-horned-owl](https://ontology-tools.github.io/py-horned-owl/) (a Rust-backed, axiom-centric OWL model)
for ontology loading and rendering, and [owlapy](https://github.com/dice-group/owlapy) for ELK reasoning and Manchester
syntax parsing.

## Loading an ontology
An ontology is loaded directly from an OWL file using py-horned-owl:

```python
from pyhornedowl import open_ontology
ontology = open_ontology(owl_url_or_path)
```

An instance of `owl_dsl.renderer.CNLRenderer` can be instantiated:
```python
renderer = CNLRenderer(ontology, ontology_namespace_uri)
```
A configuration file (`configuration_file`), a YAML file, can be used with the renderer to get the definition properties:

```python
from owl_dsl.annotations import resolve_definition_properties
definition_properties, _ = resolve_definition_properties(handler, None, None, configuration_file)
```

Most importantly, `renderer` has a `handle_owl_class` method that takes a class IRI string
and returns a human-readable description of the class as a string.

The rendering capability, which should have full unit test coverage, is designed to provide a clear and concise 
representation of OWL classes in a natural language format and is in the `owl_dsl.renderer` module.

The SQLite backend used by the reasoning path can be destroyed by removing the corresponding SQLite file (`sqlite_file`):
```python
os.remove(sqlite_file)
```

## Project Structure

- `src/owl_dsl/` - Core code for the application
- `src/owl_dsl/cli.py` - The core library for the owl_dsl.review command
- `src/owl_dsl/reasoner.py` - The core library for the owl_dsl.reason command
- `tests/` - Contains unit tests for the owl_dsl commands

## Code Standards

- Follow "Black" Python coding convention

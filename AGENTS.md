# OWL_DSL Project

This project helps to render [OWL 2 ontologies](https://www.w3.org/TR/owl-overview/) as natural language sentences
that a domain expert without knowledge of [Description Logic](https://en.wikipedia.org/wiki/Description_logic) or mathematical logic can understand.
It primarily uses [owlready2](https://github.com/pwin/owlready2) and [owlpy2](https://github.com/dice-group/owlapy)

## Loading an ontology
An ontology needs to be loaded first (`owl_url_or_path` is a file path to an OWL ontology and `ontology_uri` is the 
base IRI to set for the ontology):

```python
from owlready2 import get_ontology, default_world
ontology = get_ontology(owl_url_or_path).load()
ontology.set_base_iri(ontology_uri, rename_entities=False)
default_world.save()

print(f"Saved {owl_url_or_path} to {ontology_uri}", default_world.ontologies)
```
An instance of `owl_dsl.renderer.CNLRenderer` can be instanciated:
```python
renderer = CNLRenderer(ontology, ontology_uri)
```
A configuration file (`configuration_file`), a YAML file, can be used with the render to get the definition properties:

```python
from owl_dsl.cli import setup_configuration
definition_properties = setup_configuration(handler, configuration_file)
```

Most importantly, `renderer` has a `handle_owl_class` method that takes a single argument, an instance of `owlready2.ThingClass`
and returns a human-readable description of the class as a string.

The rendering capability, which should have full unit test coverage, is designed to provide a clear and concise 
representation of OWL classes in a natural language format and is in the `owl_dsl.renderer` module.

The owlready2 'word' can be destroyed by removing the corresponding SQLIte file (`sqlite_file`):
```python
os.remove(sqlite_file)
```

## Project Structure

- `src/owl_dsl/` - Core code for the application
- `src/owl_dsl/cli.py` - The core library for the owl_dsl.review command
- `src/owl_dsl/reasoner.py` - The core library for the owl_dsl.reason command
- `tests/` - Contains unit tests for the owl_dsl commands

## Code Standards

- Use TypeScript with strict mode enabled
- Follow "Black" Python coding convention

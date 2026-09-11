Usage Guide
============

This guide walks you through the common workflows for using OWL_DSL, from basic rendering to advanced configuration and CLI usage.

Working with the Python API
---------------------------

The core of OWL_DSL is the ``CNLRenderer``. It takes a ``PyIndexedOntology`` and a base URI, and provides methods to verbalize OWL entities.

Basic Rendering Workflow
~~~~~~~~~~~~~~~~~~~~~~~~

To render an OWL class, follow these steps:

1. **Load the Ontology**: Use ``pyhornedowl.open_ontology()`` to load your `.owl` file.
2. **Initialize Renderer**: Create a ``CNLRenderer`` instance.
3. **Render Terms**: Call ``handle_owl_class`` on a class object.

.. code-block:: python

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

Customizing Render Output
~~~~~~~~~~~~~~~~~~~~~~~~~~

The primary way to configure how terms are rendered in OWL_DSL is through **OWL 2 Annotations** embedded directly in your ontology. By using specific annotation properties, you can define human-readable labels, alternative terms, and detailed definitions that the renderer uses to construct natural language sentences.

This approach ensures that the rendering logic remains coupled with the knowledge model, making the ontology self-documenting and portable across different tools.

While annotations are the preferred method, you can also use a YAML configuration file for external overrides or rapid prototyping:

.. code-block:: python

from owl_dsl.annotations import resolve_definition_properties

# Load external overrides from a YAML file
definition_properties, _ = resolve_definition_properties(handler, None, None, "path/to/config.yaml")

Command Line Interface
----------------------

OWL_DSL provides several CLI tools for reviewing and reasoning over your ontologies without writing Python code.

* ``owl_dsl.review``: Render OWL classes as controlled natural language, list properties, and find classes.
* ``owl_dsl.reason``: Explain logical inferences using the ELK reasoner.
* ``owl_dsl.render_rules``: Render Horn rules and property chains as natural language sentences.

For detailed help on each command, run the command with the `--help` flag.

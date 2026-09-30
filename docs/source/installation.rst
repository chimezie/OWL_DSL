Installation & Getting Started
=================================

Getting Started Quickly
-----------------------

The fastest way to see OWL_DSL in action is to install the library and run a simple rendering script.

**1. Install OWL_DSL**

.. code-block:: bash

   pip install owl_dsl[nlp]

**2. Your First Rendering**

Assuming you have an OWL file (`my_ontology.owl`), you can render its classes to natural language with a few lines of Python:

.. code-block:: python

    from pyhornedowl import open_ontology
    from owl_dsl.renderer import CNLRenderer

    # Load your ontology
    ontology = open_ontology("my_ontology.owl")
    renderer = CNLRenderer(ontology, "http://example.org#")

    # Render classes to natural language
    for class_iri in ontology.get_classes():
        labels = ontology.get_annotations(class_iri, "rdfs:label")
        if labels:
            print(f"{labels[0]}: {renderer.handle_owl_class(class_iri)}")


Full Installation Options
-------------------------

From PyPI
---------

.. code-block:: bash

   pip install owl_dsl

With NLP support (spaCy for indefinite article selection):

.. code-block:: bash

   pip install owl_dsl[nlp]

From Source
-----------

.. code-block:: bash

   git clone https://github.com/chimezie/OWL_DSL.git
   cd OWL_DSL
   pip install -e .

For development:

.. code-block:: bash

   pip install -e ".[test,nlp,docs]"

Dependencies
------------

* `py-horned-owl <https://ontology-tools.github.io/py-horned-owl/>`_ -- Primary OWL library for loading and querying ontologies
* `owlready2 <https://github.com/pwin/owlready2>`_ -- Legacy/limited use (reasoning path only)
* `owlapy <https://github.com/dice-group/owlapy>`_ -- OWL API for Python
* `rdflib <https://github.com/RDFLib/rdflib>`_ -- RDF graph library
* `Click <https://click.palletsprojects.com/>`_ -- CLI framework
* `FuXi <https://github.com/RDFLib/FuXi>`_ -- InfixOWL and reasoning


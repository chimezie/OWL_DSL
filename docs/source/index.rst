OWL_DSL Documentation
======================

A Python library for transforming OWL ontologies into human-readable Controlled Natural Languages (CNLs). 
OWL_DSL allows domain experts to understand complex ontological definitions and supports the integration 
of these definitions with Natural Language Processing tools like Large Language Models (LLMs).

It primarily targets the `OWL 2 EL profile <https://www.w3.org/TR/owl2-profiles/#Feature_Overview>`_ 
while maintaining compatibility with broader OWL 2 features.

.. toctree::
   :maxdepth: 2
   :caption: User Guide:

   installation
   usage

.. toctree::
   :maxdepth: 2
   :caption: Technical Reference:

   api

Core Concepts
-------------

OWL_DSL is built around a few key components:

* **Rendering Engine** (``owl_dsl.renderer``): The heart of the library, which converts Description Logic axioms into English sentences.
* **CLI Tools**:
    * ``owl_dsl.review``: For reviewing class definitions and property usage.
    * ``owl_dsl.reason``: For extracting and explaining logical entailments.
    * ``owl_dsl.render_rules``: For translating SWRL and property chains into natural language.
* **Configuration**: Uses YAML-based definition properties and OWL annotations to customize how terms are rendered.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

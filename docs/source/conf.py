import sys
from pathlib import Path

sys.path.insert(0, str(Path("../../src").resolve()))

project = "OWL_DSL"
copyright = "2025, Chimezie Ogbuji"
author = "Chimezie Ogbuji"
release = "0.2.2"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
]

templates_path = ["_templates"]
exclude_patterns = []

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "undoc-members": True,
}

autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True

suppress_warnings = [
    "sphinx_autodoc_typehints.forward_reference",
]

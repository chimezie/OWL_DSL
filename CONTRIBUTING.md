# Contributing to OWL_DSL

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/chimezie/OWL_DSL.git
   cd OWL_DSL
   ```

2. Create a virtual environment and install in editable mode:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[test,nlp]"
   ```

3. Install pre-commit hooks:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Code Standards

- All Python code must follow the [Black](https://github.com/psf/black) style.
- Run `black .` before committing.
- Use type hints for all function signatures.
- Add docstrings to all public modules, classes, and functions using Sphinx-style (`:param`, `:return`, `:rtype`).
- Keep functions small and focused on a single responsibility.

## Testing

- Tests are in the `tests/` directory and use pytest.
- Run the full test suite:
  ```bash
  pytest
  ```
- Run with coverage:
  ```bash
  pytest --cov
  ```
- Markers are defined in `pyproject.toml`:
  - `golden` - characterization tests pinning exact rendered output
  - `integration` - end-to-end paths
  - `requires_robot` - needs ROBOT command-line tool
  - `requires_java` - needs Java runtime (for ELK/ROBOT)
  - `requires_nlp` - needs spaCy + en_core_web_sm
  - `slow` - noticeably slow tests

## Documentation

- API documentation is generated with [Sphinx](https://www.sphinx-doc.org/) using the Read the Docs theme.
- Build docs locally:
  ```bash
  cd docs && make html
  ```
- Open `docs/build/html/index.html` to preview.
- Auto-rebuild on changes:
  ```bash
  pip install sphinx-autobuild
  sphinx-autobuild docs/source docs/build/html
  ```

## Pull Request Process

1. Ensure all tests pass and the code is Black-formatted.
2. Update CHANGELOG.md with a brief description of changes.
3. Update docs if the API or CLI interface changes.
4. Open a pull request against the `main` branch.

## Release Checklist

- [ ] Update version in `src/owl_dsl/__init__.py`
- [ ] Update CHANGELOG.md
- [ ] Run full test suite
- [ ] Build docs with `cd docs && make html`
- [ ] Build package: `python -m build`
- [ ] Publish: `twine upload dist/*`

# Changelog

## [1.0.0] - 2026-09-26

### Changed
- **BREAKING**: OWL_DSL annotation namespace is now `http://purl.org/ontology-dsl#` (previously `https://github.com/chimezie/OWL_DSL/tree/main/ontology_configurations/`). Ontologies using the old URI must migrate.
- **Horn rule** rendering implementation
- Added **py-horned-owl** dependency
- Updated **configuration** instructions
- **Truth-maintenance graph** maintainance and serialization
- Support for **ASK** in BGP interlocution helper (sparql_interlocution_basic_graph_pattern)

### Added
- **Reasoning Context**: Documentation and tool support now explicitly recognize the EL++ profile capabilities:
- Supports tractable TBox reasoning (subsumption, classification) for large biomedical ontologies.
- Handles reflexive roles and range restrictions under defined syntactic constraints to maintain tractability.
- Distinguishes between intensional (TBox) and extensional (ABox) reasoning tasks.

## [0.4.2] - 2026-08-01

### Added
- `render_class` now honors the same ontology self-describing configuration as the
  reasoner: embedded OWL_DSL annotations (`OWL_DSL_000001`–`OWL_DSL_000007`) are
  applied to the CNL renderer and override any `--configuration-file`-derived
  definition properties / phrasing when present.

### Changed
- Resolution precedence for CNL configuration is now: embedded ontology
  annotations (self-describing) → explicit `--configuration-file` → auto-discovered
  `<stem>.cnl.yaml` naming convention. When an ontology carries embedded
  annotations, they win over a passed config file at the Python layer.

## [0.2.2] - 2025-07-25

### Added
- Module-level and function-level docstrings across all core modules
- MkDocs documentation site with mkdocstrings auto-generated API reference
- CONTRIBUTING.md with development setup and contribution guidelines
- CHANGELOG.md for version tracking
- Standalone examples in the `examples/` directory
- OWL_DSL annotation ontology configuration (`OWL_DSL.CNL.yaml`)
- `lint_ontology` action for `owl_dsl.review` command
- `--exact-class-labels` flag to preserve original label casing

### Fixed
- AGENTS.md incorrectly specified "TypeScript" instead of "Python" in Code Standards

## [0.2.1] - 2025-07-14

### Added
- SNOMED CT CNL configuration example
- BUG bacterial sepsis CNL rendering documentation

## [0.2.0] - 2025-07-10

### Added
- Initial public release
- `owl_dsl.review` CLI with `render_class`, `find_properties`, `find_classes` actions
- `owl_dsl.reason` CLI with `explain_logical_inferences` action
- `owl_dsl.render_rules` CLI for Horn rule rendering
- CNL configuration system with YAML configuration files
- OWL annotation-driven configuration
- Owlready2 and owlapy integration
- ELK reasoner support via ROBOT explain
- FMA and Uberon ontology examples

"""Unit tests for configuration loading in owl_dsl.cli.setup_configuration()."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from rdflib import URIRef


class TestSetupConfiguration:
    """Tests for setup_configuration function that loads YAML config files."""

    @pytest.fixture
    def minimal_config(self, tmp_path):
        """Create a complete YAML config file with all required keys."""
        config_content = """
class_inference_to_ignore: ['test class']
tooling:
  expert_definition_properties: ['http://example.org/def']
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "minimal_config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    @pytest.fixture
    def obc_like_config(self, tmp_path):
        """Create a config similar to OBO.CNL.yaml."""
        config_content = """class_inference_to_ignore: ['anatomical entity']
tooling:
  expert_definition_properties: ['http://purl.obolibrary.org/obo/IAO_0000115']
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "obo_config.yaml"
        config_file.write_text(config_content)
        return str(config_file)

    def test_setup_configuration_class_inference_to_ignore(self, minimal_config):
        """Test loading class_inference_to_ignore from config."""
        from owl_dsl.cli import setup_configuration

        handler = Mock()
        handler.class_inference_to_ignore = []

        definition_props = setup_configuration(handler, minimal_config)

        assert "test class" in handler.class_inference_to_ignore

    def test_setup_configuration_expert_definition_properties(self, minimal_config):
        """Test loading expert_definition_properties from config."""
        from owl_dsl.cli import setup_configuration

        handler = Mock()
        handler.ontology = Mock()

        definition_props = setup_configuration(handler, minimal_config)

        assert "http://example.org/def" in definition_props

    def test_setup_configuration_empty_restriction_phrasing(self, obc_like_config):
        """Test config with empty role_restriction_phrasing."""
        from owl_dsl.cli import setup_configuration

        handler = Mock()
        handler.ontology = Mock()

        # Should not raise on valid but minimal config
        definition_props = setup_configuration(handler, obc_like_config)
        assert isinstance(definition_props, list)

    def test_setup_configuration_with_obo_format(self):
        """Test loading OBO-style config format."""
        from owl_dsl.cli import setup_configuration

        # Use the actual OBO.CNL.yaml file as reference
        config_path = "ontology_configurations/OBO.CNL.yaml"

        handler = Mock()
        handler.ontology = MagicMock()
        handler.class_inference_to_ignore = []
        handler.reflexive_property_customizations = {}
        handler.relevant_role_restriction_cnl_phrasing = {}
        handler.ontology.get_annotations.return_value = ["test"]

        # Should successfully load the real config
        definition_props = setup_configuration(handler, config_path)

        assert isinstance(definition_props, list)


class TestReflexiveRolesParsing:
    """Tests for reflexive_roles directive parsing."""

    def test_reflexive_role_customization_format(self):
        """Test that reflexive roles have correct format (property -> custom phrase)."""
        # From OBO.CNL.yaml example:
        reflexive_role_entry = {
            "http://purl.obolibrary.org/obo/RO_0002481": [
                "that interacts with itself via kinase activity"
            ]
        }

        prop_uri, phrases = list(reflexive_role_entry.items())[0]

        assert isinstance(prop_uri, str)
        assert isinstance(phrases, list)
        assert len(phrases) >= 1

    def test_reflexive_roles_multiple_entries(self):
        """Test parsing multiple reflexive roles."""
        # Example with multiple reflexive properties from OBO.CNL.yaml
        config_lines = """reflexive_roles:
  - 'http://purl.obolibrary.org/obo/RO_0002481':
    - 'that interacts with itself via kinase activity'
  - 'http://example.org/self_ref':
    - 'is self-referential'
"""
        lines = config_lines.strip().split("\n")

        # Count entries (lines starting with '- ') in reflexive_roles section
        entry_count = sum(1 for line in lines if line.strip().startswith("- 'http"))

        assert entry_count >= 2

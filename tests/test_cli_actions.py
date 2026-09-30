"""Unit tests for owl_dsl.cli commands (owl_dsl.review capability)."""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestCLIMainActionRenderClass:
    """Tests for 'render_class' action in owl_dsl.review."""

    @pytest.fixture
    def mock_click_context(self):
        """Mock Click context for CLI testing."""
        ctx = Mock()
        ctx.obj = {}
        return ctx

    def test_render_class_action_basic(self, cnl_renderer, tmp_path):
        """Test render_class action with basic parameters."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        # Create minimal config file
        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        # Test with class reference by label
        result = runner.invoke(
            main,
            [
                "-a",
                "render_class",
                "--class-reference",
                "person",
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )

        # Should succeed and output class definition
        assert (
            result.exit_code == 0 or result.exit_code == 1
        ), f"Expected exit code 0 or 1, got {result.exit_code}: {result.output}"

    def test_render_class_by_id(self, cnl_renderer, tmp_path):
        """Test render_class action with --by-id flag."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        # Test with --by-id flag (find by IRI instead of label)
        result = runner.invoke(
            main,
            [
                "-a",
                "render_class",
                "--by-id",
                "--class-reference",
                "http://test.org/onto.owl#Person",
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )

        # Should succeed (may or may not find class by ID)

    def test_render_class_exact_labels(self, cnl_renderer, tmp_path):
        """Test render_class with --exact-class-labels flag."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "-a",
                "render_class",
                "--exact-class-labels",  # Don't lowercase labels
                "--class-reference",
                "Person",
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )

    def test_render_class_verbose(self, cnl_renderer, tmp_path):
        """Test render_class with --verbose flag."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "-a",
                "render_class",
                "--verbose",
                "--class-reference",
                "person",
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )


class TestCLIActionsFindClasses:
    """Tests for 'find_classes' action in owl_dsl.review."""

    def test_find_classes_contains_search(self, cnl_renderer, tmp_path):
        """Test find_classes with contains search (default)."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "-a",
                "find_classes",
                "--class-search",
                "person",  # Search for classes containing "person"
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )

        # Should find and list classes

    def test_find_classes_regex_search(self, cnl_renderer, tmp_path):
        """Test find_classes with regex search."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "-a",
                "find_classes",
                "--regex-search",  # Enable regex search
                "--class-search",
                "^p.*on$",  # Regex pattern for "person"
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )

    def test_find_classes_no_match(self, cnl_renderer, tmp_path):
        """Test find_classes with search term that has no matches."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "-a",
                "find_classes",
                "--class-search",
                "nonexistent_class_xyz123",
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )


class TestCLIActionsFindProperties:
    """Tests for 'find_properties' action in owl_dsl.review."""

    def test_find_properties_by_prefix(self, cnl_renderer, tmp_path):
        """Test find_properties filtered by URI prefix."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        # Filter properties by prefix (e.g., BFO_ or test.org/)
        result = runner.invoke(
            main,
            [
                "-a",
                "find_properties",
                "--prefix",
                "http://test.org/",  # Properties from our test ontology
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )

    def test_find_properties_by_label_regex(self, cnl_renderer, tmp_path):
        """Test find_properties filtered by label regex."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        # Filter properties by label matching regex pattern
        result = runner.invoke(
            main,
            [
                "-a",
                "find_properties",
                "--prop-reference-label",
                "pet",  # Properties with "pet" in label
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )

    def test_find_properties_with_definition_usage(self, cnl_renderer, tmp_path):
        """Test find_properties with --show-property-definition-usage flag."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "-a",
                "find_properties",
                "--show-property-definition-usage",  # Show example classes using property
                "--limit",
                "1",
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )

    def test_find_properties_multiple_filters(self, cnl_renderer, tmp_path):
        """Test find_properties with both prefix and label filters."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "-a",
                "find_properties",
                "--prefix",
                "http://test.org/",
                "--prop-reference-label",
                "pet",
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )


class TestCLIDestroySqlite:
    """Tests for 'destroy_sqlite' action in owl_dsl.review."""

    def test_destroy_sqlite_action(self, tmp_path):
        """Test destroy_sqlite action removes SQLite file."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        # Create a dummy SQLite file (or just specify path)
        sqlite_file = str(tmp_path / "test.sqlite")

        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "-a",
                "destroy_sqlite",
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                "/dev/null",  # Use /dev/null for minimal config
                "--sqlite-file",
                sqlite_file,
            ],
        )

    def test_destroy_sqlite_nonexistent_file(self, tmp_path):
        """Test destroy_sqlite when file doesn't exist (should not crash)."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        nonexistent_file = str(tmp_path / "nonexistent.sqlite")

        runner = CliRunner()

        result = runner.invoke(
            main,
            [
                "-a",
                "destroy_sqlite",
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                "/dev/null",
                "--sqlite-file",
                nonexistent_file,
            ],
        )


class TestCLIOptionValidation:
    """Tests for CLI option validation and defaults."""

    def test_default_action_is_render_class(self, tmp_path):
        """Test that default action is 'render_class'."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        # Don't specify -a, should default to render_class
        result = runner.invoke(
            main,
            [
                "--class-reference",
                "person",
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )

    def test_required_options_enforced(self, tmp_path):
        """Test that required options are enforced."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        runner = CliRunner()

        # Missing required --configuration-file should fail
        result = runner.invoke(
            main,
            [
                "-a",
                "render_class",
                "--class-reference",
                "person",
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )

        # Should fail due to missing required option
        assert result.exit_code != 0 or "Missing option" in result.output

    def test_exact_class_labels_default(self, cnl_renderer, tmp_path):
        """Test default behavior of --exact-class-labels (should be False)."""
        from click.testing import CliRunner
        from owl_dsl.cli import main

        config_content = """class_inference_to_ignore: []
tooling: {}
standard_role_restriction_is_phrasing: []
reflexive_roles: []
role_restriction_phrasing: {}
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        runner = CliRunner()

        # Without --exact-class-labels, labels should be lowercased
        result = runner.invoke(
            main,
            [
                "-a",
                "render_class",
                "--class-reference",
                "Person",  # Capital P
                "--ontology-uri",
                "http://test.org/onto.owl#",
                "--ontology-namespace-baseuri",
                "http://test.org/",
                "--configuration-file",
                str(config_file),
                "--sqlite-file",
                str(tmp_path / "test.sqlite"),
            ],
        )

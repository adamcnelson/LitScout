"""Tests for configuration loading and validation."""

import tempfile
from pathlib import Path

import pytest

from litscout.config import Config, ConfigError


def test_config_loads_valid_yaml():
    """Test that valid config loads correctly."""
    config_content = """
output_dir: "~/test/reports"
top_k_per_topic: 5
initial_lookback_days: 7

topics:
  - name: "Test Topic"
    query: "test query"
    sources:
      - pubmed
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()

        config = Config.from_yaml(f.name)

        assert config.top_k_per_topic == 5
        assert config.initial_lookback_days == 7
        assert len(config.topics) == 1
        assert config.topics[0].name == "Test Topic"
        assert "test" in str(config.output_dir)


def test_config_expands_tilde():
    """Test that ~ in output_dir is expanded."""
    config_content = """
output_dir: "~/litscout/reports"
topics:
  - name: "Test"
    query: "test"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()

        config = Config.from_yaml(f.name)

        assert "~" not in str(config.output_dir)
        assert config.output_dir.is_absolute()


def test_config_validates_missing_topics():
    """Test that missing topics raises ConfigError."""
    config_content = """
output_dir: "./reports"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()

        with pytest.raises(ConfigError, match="No topics defined"):
            Config.from_yaml(f.name)


def test_config_validates_invalid_source():
    """Test that invalid source raises ConfigError."""
    config_content = """
output_dir: "./reports"
topics:
  - name: "Test"
    query: "test"
    sources:
      - invalid_source
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()

        with pytest.raises(ConfigError, match="invalid source"):
            Config.from_yaml(f.name)


def test_config_validates_missing_query():
    """Test that missing query raises ConfigError."""
    config_content = """
output_dir: "./reports"
topics:
  - name: "Test Topic"
    sources:
      - pubmed
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()

        with pytest.raises(ConfigError, match="missing 'query'"):
            Config.from_yaml(f.name)


def test_config_email_disabled_by_default():
    """Test that email notifications are disabled by default."""
    config_content = """
output_dir: "./reports"
topics:
  - name: "Test"
    query: "test"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()

        config = Config.from_yaml(f.name)

        assert config.notifications.email.enabled is False


def test_config_validates_email_enabled_without_recipient():
    """Test that enabling email without recipient raises error."""
    config_content = """
output_dir: "./reports"
notifications:
  email:
    enabled: true
    to: ""
topics:
  - name: "Test"
    query: "test"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()

        with pytest.raises(ConfigError, match="'to' address is empty"):
            Config.from_yaml(f.name)

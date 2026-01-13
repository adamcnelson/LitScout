"""Tests for CLI commands."""

import subprocess
import sys
import tempfile
from pathlib import Path


def test_cli_help():
    """Test that --help works."""
    result = subprocess.run(
        [sys.executable, "-m", "litscout", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "litscout" in result.stdout
    assert "init" in result.stdout
    assert "run" in result.stdout
    assert "doctor" in result.stdout


def test_cli_version():
    """Test that --version works."""
    result = subprocess.run(
        [sys.executable, "-m", "litscout", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "litscout" in result.stdout


def test_cli_init_creates_structure():
    """Test that init creates project structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, "-m", "litscout", "init", "--path", tmpdir],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Check directories created
        assert (Path(tmpdir) / "config").is_dir()
        assert (Path(tmpdir) / "prompts").is_dir()
        assert (Path(tmpdir) / "reports").is_dir()
        assert (Path(tmpdir) / "data").is_dir()

        # Check files created
        assert (Path(tmpdir) / "config" / "config.yaml").is_file()
        assert (Path(tmpdir) / "config" / "config.example.yaml").is_file()
        assert (Path(tmpdir) / "prompts" / "summary.md").is_file()


def test_cli_run_requires_config():
    """Test that run fails without config."""
    result = subprocess.run(
        [sys.executable, "-m", "litscout", "run"],
        capture_output=True,
        text=True,
        env={"PATH": "", "HOME": "/tmp"},  # Clear LITSCOUT_CONFIG
    )
    # Should fail because no config found
    assert result.returncode != 0 or "No config" in result.stderr or "not found" in result.stderr

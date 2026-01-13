"""Tests for report generation."""

import tempfile
from datetime import datetime
from pathlib import Path

from litscout.db import Paper
from litscout.report import generate_report


def test_generate_report_creates_file():
    """Test that generate_report creates a markdown file."""
    papers_by_topic = {
        "Test Topic": [
            Paper(
                id="test:123",
                doi="10.1234/test",
                arxiv_id=None,
                title="Test Paper Title",
                authors="Test Author",
                abstract="This is a test abstract.",
                url="https://example.com/paper",
                source="pubmed",
                published_date="2024-01-01",
                topic="Test Topic",
                first_seen=datetime.now().isoformat(),
                summary="Test summary content.",
            )
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        report_path = generate_report(papers_by_topic, output_dir)

        assert report_path.exists()
        assert report_path.suffix == ".md"

        content = report_path.read_text()
        assert "Test Topic" in content
        assert "Test Paper Title" in content
        assert "Test Author" in content
        assert "Test summary content." in content


def test_generate_report_handles_empty_topics():
    """Test that generate_report handles topics with no papers."""
    papers_by_topic = {
        "Empty Topic": [],
        "Topic With Paper": [
            Paper(
                id="test:456",
                doi=None,
                arxiv_id=None,
                title="Another Paper",
                authors="Another Author",
                abstract="Abstract text.",
                url="https://example.com/paper2",
                source="biorxiv",
                published_date="2024-01-02",
                topic="Topic With Paper",
                first_seen=datetime.now().isoformat(),
            )
        ],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        report_path = generate_report(papers_by_topic, output_dir)

        content = report_path.read_text()
        assert "Empty Topic" in content
        assert "No new papers found" in content
        assert "Another Paper" in content

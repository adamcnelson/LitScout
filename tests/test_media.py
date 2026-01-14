"""Tests for media collection utilities."""

import pytest

from litscout.sources.collect_podcasts import _parse_duration
from litscout.sources.collect_youtube import _parse_iso8601_duration


class TestPodcastDurationParsing:
    """Tests for podcast RSS duration parsing."""

    def test_parse_duration_hms_format(self):
        """Test parsing HH:MM:SS format."""
        entry = {"itunes_duration": "1:30:45"}
        assert _parse_duration(entry) == 91  # 1h30m + round up from 45s

    def test_parse_duration_ms_format(self):
        """Test parsing MM:SS format."""
        entry = {"itunes_duration": "45:30"}
        assert _parse_duration(entry) == 46  # 45m + round up from 30s

    def test_parse_duration_seconds_int(self):
        """Test parsing duration as integer seconds."""
        entry = {"itunes_duration": 3600}
        assert _parse_duration(entry) == 60

    def test_parse_duration_seconds_string(self):
        """Test parsing duration as string seconds."""
        entry = {"itunes_duration": "3600"}
        assert _parse_duration(entry) == 60

    def test_parse_duration_no_rounding(self):
        """Test that seconds < 30 don't round up."""
        entry = {"itunes_duration": "45:20"}
        assert _parse_duration(entry) == 45  # No round up

    def test_parse_duration_empty(self):
        """Test missing duration returns 0."""
        assert _parse_duration({}) == 0
        assert _parse_duration({"itunes_duration": ""}) == 0

    def test_parse_duration_fallback_field(self):
        """Test fallback to 'duration' field."""
        entry = {"duration": "30:00"}
        assert _parse_duration(entry) == 30


class TestYouTubeDurationParsing:
    """Tests for YouTube ISO 8601 duration parsing."""

    def test_parse_iso8601_full_format(self):
        """Test parsing PT1H30M15S format."""
        assert _parse_iso8601_duration("PT1H30M15S") == 90

    def test_parse_iso8601_hours_minutes(self):
        """Test parsing PT2H45M format."""
        assert _parse_iso8601_duration("PT2H45M") == 165

    def test_parse_iso8601_minutes_seconds(self):
        """Test parsing PT45M30S format."""
        assert _parse_iso8601_duration("PT45M30S") == 46  # rounds up

    def test_parse_iso8601_minutes_only(self):
        """Test parsing PT45M format."""
        assert _parse_iso8601_duration("PT45M") == 45

    def test_parse_iso8601_seconds_only(self):
        """Test parsing PT3600S format."""
        assert _parse_iso8601_duration("PT3600S") == 60

    def test_parse_iso8601_hours_only(self):
        """Test parsing PT2H format."""
        assert _parse_iso8601_duration("PT2H") == 120

    def test_parse_iso8601_empty(self):
        """Test empty string returns 0."""
        assert _parse_iso8601_duration("") == 0
        assert _parse_iso8601_duration("PT0M") == 0

    def test_parse_iso8601_no_rounding(self):
        """Test seconds < 30 don't round up."""
        assert _parse_iso8601_duration("PT45M20S") == 45

"""Tests for clinical trials collection utilities."""

from litscout.sources.collect_trials import (
    ClinicalTrial,
    _filter_by_phase,
    _filter_by_recency,
    _get_phase_number,
    _parse_phase,
    _score_trial,
)


class TestParsePhase:
    """Tests for phase parsing."""

    def test_parse_single_phase(self):
        """Test parsing a single phase."""
        assert _parse_phase(["PHASE2"]) == "Phase 2"
        assert _parse_phase(["PHASE3"]) == "Phase 3"
        assert _parse_phase(["PHASE1"]) == "Phase 1"

    def test_parse_combined_phases(self):
        """Test parsing combined phases."""
        assert _parse_phase(["PHASE2", "PHASE3"]) == "Phase 2/Phase 3"
        assert _parse_phase(["PHASE1", "PHASE2"]) == "Phase 1/Phase 2"

    def test_parse_early_phase(self):
        """Test parsing early phase 1."""
        assert _parse_phase(["EARLY_PHASE1"]) == "Early Phase 1"

    def test_parse_na_phase(self):
        """Test parsing N/A phase."""
        assert _parse_phase([]) == "N/A"
        assert _parse_phase(["NA"]) == "N/A"

    def test_parse_phase4(self):
        """Test parsing phase 4."""
        assert _parse_phase(["PHASE4"]) == "Phase 4"


class TestGetPhaseNumber:
    """Tests for extracting phase numbers."""

    def test_phase_numbers(self):
        """Test extracting phase numbers from trial."""
        trial = _make_trial(phase="Phase 2")
        assert _get_phase_number(trial) == 2

        trial = _make_trial(phase="Phase 3")
        assert _get_phase_number(trial) == 3

        trial = _make_trial(phase="Phase 1")
        assert _get_phase_number(trial) == 1

        trial = _make_trial(phase="Phase 4")
        assert _get_phase_number(trial) == 4

    def test_combined_phase_returns_max(self):
        """Test that combined phases return the higher phase."""
        trial = _make_trial(phase="Phase 2/Phase 3")
        assert _get_phase_number(trial) == 3

    def test_early_phase(self):
        """Test early phase returns 0."""
        trial = _make_trial(phase="Early Phase 1")
        assert _get_phase_number(trial) == 0

    def test_na_phase(self):
        """Test N/A phase returns -1."""
        trial = _make_trial(phase="N/A")
        assert _get_phase_number(trial) == -1


class TestFilterByPhase:
    """Tests for phase filtering."""

    def test_filter_phase2_min(self):
        """Test filtering by minimum phase 2."""
        trial_p2 = _make_trial(phase="Phase 2")
        trial_p1 = _make_trial(phase="Phase 1")
        trial_p3 = _make_trial(phase="Phase 3")

        assert _filter_by_phase(trial_p2, min_phase=2) is True
        assert _filter_by_phase(trial_p3, min_phase=2) is True
        assert _filter_by_phase(trial_p1, min_phase=2) is False

    def test_filter_phase1_min(self):
        """Test filtering by minimum phase 1."""
        trial_p1 = _make_trial(phase="Phase 1")
        trial_early = _make_trial(phase="Early Phase 1")

        assert _filter_by_phase(trial_p1, min_phase=1) is True
        assert _filter_by_phase(trial_early, min_phase=1) is False

    def test_filter_allows_higher_phases(self):
        """Test that higher phases pass lower minimum."""
        trial_p3 = _make_trial(phase="Phase 3")
        assert _filter_by_phase(trial_p3, min_phase=1) is True


class TestFilterByRecency:
    """Tests for recency filtering."""

    def test_recent_trial_passes(self):
        """Test that a recent trial passes the filter."""
        trial = _make_trial(last_update_posted="2026-01-15")
        assert _filter_by_recency(trial, recency_days=30) is True

    def test_old_trial_fails(self):
        """Test that an old trial fails the filter."""
        trial = _make_trial(last_update_posted="2025-01-01")
        assert _filter_by_recency(trial, recency_days=30) is False

    def test_missing_date_fails(self):
        """Test that missing date fails the filter."""
        trial = _make_trial(last_update_posted="")
        assert _filter_by_recency(trial, recency_days=30) is False

    def test_yyyy_mm_format(self):
        """Test that YYYY-MM format is handled."""
        trial = _make_trial(last_update_posted="2026-01")
        assert _filter_by_recency(trial, recency_days=60) is True


class TestScoreTrial:
    """Tests for trial scoring."""

    def test_scoring_is_deterministic(self):
        """Test that scoring the same trial gives the same result."""
        trial = _make_trial(
            phase="Phase 2",
            status="RECRUITING",
            last_update_posted="2026-01-15",
            conditions=["Alzheimer's disease"],
        )
        query = "Alzheimer disease tau"

        score1 = _score_trial(trial, query)
        score2 = _score_trial(trial, query)

        assert score1 == score2

    def test_higher_phase_scores_higher(self):
        """Test that higher phase trials score higher."""
        trial_p2 = _make_trial(phase="Phase 2", status="RECRUITING")
        trial_p3 = _make_trial(phase="Phase 3", status="RECRUITING")

        score_p2 = _score_trial(trial_p2, "test")
        score_p3 = _score_trial(trial_p3, "test")

        assert score_p3 > score_p2

    def test_recruiting_scores_higher_than_completed(self):
        """Test that recruiting trials score higher than completed."""
        trial_recruiting = _make_trial(status="RECRUITING")
        trial_completed = _make_trial(status="COMPLETED")

        score_recruiting = _score_trial(trial_recruiting, "test")
        score_completed = _score_trial(trial_completed, "test")

        assert score_recruiting > score_completed

    def test_keyword_match_increases_score(self):
        """Test that keyword matches increase score."""
        trial = _make_trial(
            title="A Study of Tau Protein in Alzheimer Disease",
            conditions=["Alzheimer's Disease"],
        )

        score_match = _score_trial(trial, "Alzheimer tau protein")
        score_no_match = _score_trial(trial, "cancer treatment")

        assert score_match > score_no_match


def _make_trial(
    nct_id: str = "NCT12345678",
    title: str = "Test Trial",
    phase: str = "Phase 2",
    status: str = "RECRUITING",
    conditions: list[str] | None = None,
    interventions: list[str] | None = None,
    last_update_posted: str = "2026-01-15",
    brief_summary: str = "Test summary",
    enrollment: int | None = 100,
    **kwargs,
) -> ClinicalTrial:
    """Helper to create a test trial."""
    return ClinicalTrial(
        id=nct_id,
        nct_id=nct_id,
        title=title,
        brief_summary=brief_summary,
        phase=phase,
        status=status,
        conditions=conditions or [],
        interventions=interventions or [],
        sponsor="Test Sponsor",
        collaborators=[],
        url=f"https://clinicaltrials.gov/study/{nct_id}",
        last_update_posted=last_update_posted,
        study_start_date="2025-01-01",
        primary_completion_date="2027-01-01",
        enrollment=enrollment,
    )

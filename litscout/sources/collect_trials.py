"""Clinical trials collector using ClinicalTrials.gov API v2."""

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

from litscout.config import TrialsConfig

logger = logging.getLogger(__name__)

CTGOV_API_BASE = "https://clinicaltrials.gov/api/v2/studies"

# Fields to request from the API
API_FIELDS = [
    "NCTId",
    "BriefTitle",
    "BriefSummary",
    "Phase",
    "OverallStatus",
    "Condition",
    "InterventionName",
    "LeadSponsorName",
    "CollaboratorName",
    "LastUpdatePostDate",
    "StartDate",
    "PrimaryCompletionDate",
    "EnrollmentCount",
]

# Neurodegenerative disease terms for scoring
NEURODEGENERATIVE_TERMS = [
    "alzheimer",
    "parkinson",
    "huntington",
    "als",
    "amyotrophic lateral sclerosis",
    "frontotemporal",
    "dementia",
    "neurodegeneration",
    "tauopathy",
    "synucleinopathy",
    "motor neuron",
    "multiple sclerosis",
    "lewy body",
]

# Neuropsychiatric terms for scoring
NEUROPSYCHIATRIC_TERMS = [
    "schizophrenia",
    "depression",
    "bipolar",
    "anxiety",
    "ptsd",
    "autism",
    "adhd",
    "ocd",
    "substance use",
    "addiction",
    "psychosis",
    "mood disorder",
]

# Phase weights for scoring (higher = more weight)
PHASE_WEIGHTS = {
    "PHASE1": 1.0,
    "PHASE2": 1.5,
    "PHASE3": 2.0,
    "PHASE4": 1.2,
    "EARLY_PHASE1": 0.8,
    "NA": 0.5,
}

# Status weights (higher = preferred)
STATUS_WEIGHTS = {
    "RECRUITING": 2.0,
    "ACTIVE_NOT_RECRUITING": 1.5,
    "NOT_YET_RECRUITING": 1.3,
    "COMPLETED": 1.0,
    "ENROLLING_BY_INVITATION": 0.8,
}


@dataclass
class ClinicalTrial:
    """A clinical trial from ClinicalTrials.gov."""

    id: str  # NCT ID
    nct_id: str
    title: str
    brief_summary: str
    phase: str  # "Phase 2", "Phase 2/Phase 3"
    status: str  # "RECRUITING", "COMPLETED"
    conditions: list[str]
    interventions: list[str]
    sponsor: str
    collaborators: list[str]
    url: str
    last_update_posted: str
    study_start_date: str
    primary_completion_date: Optional[str]
    enrollment: Optional[int]
    relevance_summary: Optional[str] = None  # Claude "why it matters"


def collect_trials(
    query: str,
    config: TrialsConfig,
    cache_dir: Path | None = None,
) -> list[ClinicalTrial]:
    """
    Collect clinical trials matching the query.

    Uses ClinicalTrials.gov API v2 to search for trials and filter by
    phase, status, and recency.
    """
    if not config.enabled:
        return []

    # Use config query override if set
    search_query = config.query if config.query else query

    logger.info(f"Searching ClinicalTrials.gov for: {search_query}")

    # Try to load from cache first
    if cache_dir:
        cached = _load_from_cache(search_query, config, cache_dir)
        if cached is not None:
            logger.info(f"Loaded {len(cached)} trials from cache")
            return cached[: config.n]

    # Fetch from API
    trials = _fetch_trials_from_api(search_query, config)

    if not trials:
        logger.warning("No trials found from ClinicalTrials.gov")
        return []

    logger.info(f"Found {len(trials)} trials, applying filters...")

    # Filter trials
    filtered = []
    for trial in trials:
        if not _filter_by_phase(trial, config.min_phase):
            continue
        if not _filter_by_status(trial, config.status_allow):
            continue
        if not _filter_by_recency(trial, config.recency_days):
            continue
        if _matches_exclude_terms(trial, config.exclude_terms):
            continue
        if config.include_conditions and not _matches_conditions(
            trial, config.include_conditions
        ):
            continue
        filtered.append(trial)

    logger.info(f"Filtered to {len(filtered)} trials")

    # Score and sort
    scored = [(trial, _score_trial(trial, search_query)) for trial in filtered]
    scored.sort(key=lambda x: x[1], reverse=True)
    result = [trial for trial, _ in scored]

    # Save to cache
    if cache_dir:
        _save_to_cache(search_query, config, result, cache_dir)

    logger.info(f"Returning top {config.n} trials")
    return result[: config.n]


def _fetch_trials_from_api(query: str, config: TrialsConfig) -> list[ClinicalTrial]:
    """Fetch trials from ClinicalTrials.gov API with pagination."""
    trials: list[ClinicalTrial] = []
    page_token: Optional[str] = None
    max_pages = 5  # Limit to prevent excessive API calls

    # Build status filter
    status_filter = ",".join(config.status_allow)

    for page in range(max_pages):
        params = {
            "query.term": query,
            "filter.overallStatus": status_filter,
            "pageSize": 100,
            "fields": ",".join(API_FIELDS),
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            resp = requests.get(CTGOV_API_BASE, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f"ClinicalTrials.gov API request failed: {e}")
            break
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse API response: {e}")
            break

        studies = data.get("studies", [])
        for study in studies:
            trial = _parse_trial(study)
            if trial:
                trials.append(trial)

        # Check for next page
        page_token = data.get("nextPageToken")
        if not page_token:
            break

        # Rate limiting: 0.5s delay between pages
        time.sleep(0.5)

    return trials


def _parse_trial(data: dict) -> Optional[ClinicalTrial]:
    """Parse a trial from API response into ClinicalTrial dataclass."""
    try:
        protocol = data.get("protocolSection", {})
        id_module = protocol.get("identificationModule", {})
        status_module = protocol.get("statusModule", {})
        desc_module = protocol.get("descriptionModule", {})
        design_module = protocol.get("designModule", {})
        cond_module = protocol.get("conditionsModule", {})
        interv_module = protocol.get("armsInterventionsModule", {})
        sponsor_module = protocol.get("sponsorCollaboratorsModule", {})

        nct_id = id_module.get("nctId", "")
        if not nct_id:
            return None

        # Parse phases
        phases = design_module.get("phases", [])
        phase_str = _parse_phase(phases)

        # Parse conditions
        conditions = cond_module.get("conditions", [])

        # Parse interventions
        interventions = []
        for interv in interv_module.get("interventions", []):
            name = interv.get("name", "")
            if name:
                interventions.append(name)

        # Parse sponsor and collaborators
        sponsor = ""
        lead_sponsor = sponsor_module.get("leadSponsor", {})
        if lead_sponsor:
            sponsor = lead_sponsor.get("name", "")

        collaborators = []
        for collab in sponsor_module.get("collaborators", []):
            name = collab.get("name", "")
            if name:
                collaborators.append(name)

        # Parse dates
        last_update = status_module.get("lastUpdatePostDateStruct", {}).get("date", "")
        start_date = status_module.get("startDateStruct", {}).get("date", "")
        completion_date = status_module.get("primaryCompletionDateStruct", {}).get(
            "date"
        )

        # Parse enrollment
        enrollment = design_module.get("enrollmentInfo", {}).get("count")

        return ClinicalTrial(
            id=nct_id,
            nct_id=nct_id,
            title=id_module.get("briefTitle", "Unknown Title"),
            brief_summary=desc_module.get("briefSummary", ""),
            phase=phase_str,
            status=status_module.get("overallStatus", "UNKNOWN"),
            conditions=conditions,
            interventions=interventions,
            sponsor=sponsor,
            collaborators=collaborators,
            url=f"https://clinicaltrials.gov/study/{nct_id}",
            last_update_posted=last_update,
            study_start_date=start_date,
            primary_completion_date=completion_date,
            enrollment=enrollment,
        )
    except Exception as e:
        logger.warning(f"Failed to parse trial: {e}")
        return None


def _parse_phase(phase_list: list[str]) -> str:
    """
    Parse phase list into human-readable string.

    Examples:
    - ["PHASE2"] -> "Phase 2"
    - ["PHASE2", "PHASE3"] -> "Phase 2/Phase 3"
    - ["EARLY_PHASE1"] -> "Early Phase 1"
    - [] or ["NA"] -> "N/A"
    """
    if not phase_list or phase_list == ["NA"]:
        return "N/A"

    readable = []
    for phase in phase_list:
        if phase == "EARLY_PHASE1":
            readable.append("Early Phase 1")
        elif phase.startswith("PHASE"):
            num = phase.replace("PHASE", "")
            readable.append(f"Phase {num}")
        else:
            readable.append(phase)

    return "/".join(readable)


def _get_phase_number(trial: ClinicalTrial) -> int:
    """Extract the maximum phase number from a trial."""
    phase_str = trial.phase.lower()

    # Check early phase first (before "phase 1" check)
    if "early phase" in phase_str:
        return 0
    if "phase 4" in phase_str or "phase4" in phase_str:
        return 4
    if "phase 3" in phase_str or "phase3" in phase_str:
        return 3
    if "phase 2" in phase_str or "phase2" in phase_str:
        return 2
    if "phase 1" in phase_str or "phase1" in phase_str:
        return 1

    return -1  # N/A or unknown


def _filter_by_phase(trial: ClinicalTrial, min_phase: int) -> bool:
    """Filter trial by minimum phase requirement."""
    phase_num = _get_phase_number(trial)
    return phase_num >= min_phase


def _filter_by_status(trial: ClinicalTrial, allowed_statuses: list[str]) -> bool:
    """Filter trial by allowed statuses."""
    return trial.status in allowed_statuses


def _filter_by_recency(trial: ClinicalTrial, recency_days: int) -> bool:
    """Filter trial by last update date recency."""
    if not trial.last_update_posted:
        return False

    try:
        # Parse date (format: YYYY-MM-DD or YYYY-MM)
        date_str = trial.last_update_posted
        if len(date_str) == 7:  # YYYY-MM format
            date_str += "-01"
        update_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )

        cutoff = datetime.now(timezone.utc) - timedelta(days=recency_days)
        return update_date >= cutoff
    except ValueError:
        return True  # Include if we can't parse the date


def _matches_exclude_terms(trial: ClinicalTrial, exclude_terms: list[str]) -> bool:
    """Check if trial matches any exclude terms."""
    if not exclude_terms:
        return False

    combined = (
        f"{trial.title} {trial.brief_summary} {' '.join(trial.conditions)}".lower()
    )

    for term in exclude_terms:
        if term.lower() in combined:
            return True
    return False


def _matches_conditions(trial: ClinicalTrial, include_conditions: list[str]) -> bool:
    """Check if trial matches any of the required conditions."""
    combined = f"{' '.join(trial.conditions)} {trial.title}".lower()

    for condition in include_conditions:
        if condition.lower() in combined:
            return True
    return False


def _score_trial(trial: ClinicalTrial, query: str) -> float:
    """
    Score a trial for relevance and importance.

    Factors:
    - Recency (more recent = higher score)
    - Phase weight (Phase 3 > Phase 2 > Phase 1)
    - Status weight (Recruiting > Completed)
    - Keyword match with query
    - Disease category match
    """
    score = 0.0

    # Recency score (0-30 points based on days since last update)
    if trial.last_update_posted:
        try:
            date_str = trial.last_update_posted
            if len(date_str) == 7:
                date_str += "-01"
            update_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            days_ago = (datetime.now(timezone.utc) - update_date).days
            recency_score = max(0, 30 - days_ago)
            score += recency_score
        except ValueError:
            pass

    # Phase weight (0-20 points)
    phase_upper = trial.phase.upper().replace(" ", "").replace("/", "")
    for phase_key, weight in PHASE_WEIGHTS.items():
        if phase_key in phase_upper:
            score += weight * 10
            break

    # Status weight (0-20 points)
    status_weight = STATUS_WEIGHTS.get(trial.status, 0.5)
    score += status_weight * 10

    # Query keyword match (0-20 points)
    combined = (
        f"{trial.title} {trial.brief_summary} {' '.join(trial.conditions)}".lower()
    )
    query_terms = query.lower().split()
    matches = sum(1 for term in query_terms if term in combined and len(term) > 3)
    score += min(matches * 4, 20)

    # Disease category bonus (0-10 points)
    for term in NEURODEGENERATIVE_TERMS + NEUROPSYCHIATRIC_TERMS:
        if term in combined:
            score += 10
            break

    # Enrollment bonus (larger = more significant)
    if trial.enrollment and trial.enrollment > 100:
        score += min(trial.enrollment / 100, 10)

    return score


def _get_cache_key(query: str, config: TrialsConfig) -> str:
    """Generate a cache key for the query and config."""
    key_data = f"{query}|{config.min_phase}|{config.recency_days}|{','.join(sorted(config.status_allow))}"
    return hashlib.md5(key_data.encode()).hexdigest()[:12]


def _load_from_cache(
    query: str,
    config: TrialsConfig,
    cache_dir: Path,
) -> Optional[list[ClinicalTrial]]:
    """Load cached trials if available and not expired."""
    cache_key = _get_cache_key(query, config)
    cache_file = cache_dir / f"{cache_key}.json"

    if not cache_file.exists():
        return None

    try:
        with open(cache_file) as f:
            data = json.load(f)

        # Check cache expiry (24 hours)
        cached_at = datetime.fromisoformat(data["cached_at"])
        if datetime.now(timezone.utc) - cached_at > timedelta(hours=24):
            return None

        trials = [ClinicalTrial(**t) for t in data["trials"]]
        return trials
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"Failed to load cache: {e}")
        return None


def _save_to_cache(
    query: str,
    config: TrialsConfig,
    trials: list[ClinicalTrial],
    cache_dir: Path,
) -> None:
    """Save trials to cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = _get_cache_key(query, config)
    cache_file = cache_dir / f"{cache_key}.json"

    try:
        data = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "trials": [asdict(t) for t in trials],
        }
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)
    except (OSError, TypeError) as e:
        logger.warning(f"Failed to save cache: {e}")

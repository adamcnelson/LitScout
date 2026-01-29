"""bioRxiv and medRxiv fetcher using their API."""

import time
from datetime import datetime, timedelta
from typing import Iterator

import requests

from ..db import Paper, generate_paper_id

BIORXIV_API_URL = "https://api.biorxiv.org/details"


def fetch_biorxiv(
    query: str,
    topic: str,
    since: datetime | None = None,
    max_results: int = 100,
) -> Iterator[Paper]:
    """Fetch papers from bioRxiv matching the query."""
    yield from _fetch_rxiv("biorxiv", query, topic, since, max_results)


def fetch_medrxiv(
    query: str,
    topic: str,
    since: datetime | None = None,
    max_results: int = 100,
) -> Iterator[Paper]:
    """Fetch papers from medRxiv matching the query."""
    yield from _fetch_rxiv("medrxiv", query, topic, since, max_results)


def _fetch_rxiv(
    server: str,
    query: str,
    topic: str,
    since: datetime | None,
    max_results: int,
) -> Iterator[Paper]:
    """Fetch papers from bioRxiv/medRxiv API."""
    # The API returns papers by date range, not by search query
    # We'll fetch recent papers and filter locally
    if since is None:
        since = datetime.now() - timedelta(days=30)

    start_date = since.strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    # API endpoint format: /details/{server}/{start}/{end}/{cursor}
    cursor = 0
    query_groups = _parse_query_groups(query)
    found = 0

    while found < max_results:
        url = f"{BIORXIV_API_URL}/{server}/{start_date}/{end_date}/{cursor}"

        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"{server} fetch error: {e}")
            return

        messages = data.get("messages", [])
        if messages and messages[0].get("status") == "no posts found":
            return

        collection = data.get("collection", [])
        if not collection:
            return

        for item in collection:
            paper = _parse_item(item, server, topic, query_groups)
            if paper:
                yield paper
                found += 1
                if found >= max_results:
                    return

        # Check if more results available
        total_raw = messages[0].get("total", 0) if messages else 0
        total = int(total_raw) if total_raw else 0
        cursor += len(collection)
        if cursor >= total:
            return

        time.sleep(0.5)  # Rate limiting


def _parse_query_groups(query: str) -> list[list[str]]:
    """
    Parse a boolean query into AND-connected groups of OR terms.

    Example: "(A OR B) AND (C OR D)" -> [['a', 'b'], ['c', 'd']]

    Each inner list is an OR group; all groups must match (AND logic).
    """
    import re

    # Normalize whitespace
    query = " ".join(query.split())

    # Split on AND (case insensitive) to get groups
    and_parts = re.split(r"\s+AND\s+", query, flags=re.IGNORECASE)

    groups = []
    for part in and_parts:
        # Remove outer parentheses
        part = part.strip()
        while part.startswith("(") and part.endswith(")"):
            part = part[1:-1].strip()

        # Split on OR to get terms within this group
        or_parts = re.split(r"\s+OR\s+", part, flags=re.IGNORECASE)

        terms = []
        for term in or_parts:
            term = term.strip()
            # Remove parentheses and quotes
            term = re.sub(r"[()]", "", term)

            # Handle quoted phrases
            if term.startswith('"') and term.endswith('"'):
                term = term[1:-1]

            # Handle wildcards (keep as prefix match)
            term = term.lower().strip()

            if len(term) >= 2:  # Skip very short terms
                terms.append(term)

        if terms:
            groups.append(terms)

    return groups


def _term_matches(text: str, term: str) -> bool:
    """Check if a term matches in text, supporting wildcards."""
    if term.endswith("*"):
        # Prefix match
        prefix = term[:-1]
        return prefix in text
    else:
        # Exact word or phrase match
        return term in text


def _matches_query(text: str, query_groups: list[list[str]]) -> bool:
    """
    Check if text matches the query using proper AND/OR logic.

    All groups must match (AND). Within each group, any term matching suffices (OR).
    """
    if not query_groups:
        return True

    text_lower = text.lower()

    # ALL groups must match (AND logic between groups)
    for group in query_groups:
        # At least ONE term in the group must match (OR logic within group)
        group_matched = any(_term_matches(text_lower, term) for term in group)
        if not group_matched:
            return False

    return True


def _parse_item(
    item: dict, server: str, topic: str, query_groups: list[list[str]]
) -> Paper | None:
    """Parse a bioRxiv/medRxiv API item into a Paper."""
    title = item.get("title", "")
    abstract = item.get("abstract", "")

    # Filter by query (since API doesn't support search)
    searchable = f"{title} {abstract}"
    if query_groups and not _matches_query(searchable, query_groups):
        return None

    doi = item.get("doi", "")
    if not doi:
        return None

    authors = item.get("authors", "")
    # Truncate long author lists
    if authors:
        author_list = authors.split(";")
        if len(author_list) > 5:
            authors = "; ".join(author_list[:5]) + " et al."

    pub_date = item.get("date", "")
    url = f"https://www.{server}.org/content/{doi}"

    paper_id = generate_paper_id(doi, None, title)

    return Paper(
        id=paper_id,
        doi=doi,
        arxiv_id=None,
        title=title,
        authors=authors,
        abstract=abstract,
        url=url,
        source=server,
        published_date=pub_date,
        topic=topic,
        first_seen=datetime.now().isoformat(),
    )

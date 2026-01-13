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
    query_terms = _extract_query_terms(query)
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
            paper = _parse_item(item, server, topic, query_terms)
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


def _extract_query_terms(query: str) -> list[str]:
    """Extract searchable terms from a query string."""
    import re

    # Remove boolean operators and parentheses
    query = re.sub(r"\b(AND|OR|NOT)\b", " ", query, flags=re.IGNORECASE)
    query = re.sub(r"[()]", " ", query)
    # Extract quoted phrases and individual terms
    terms = []
    # Quoted phrases
    for match in re.findall(r'"([^"]+)"', query):
        terms.append(match.lower())
    # Remove quoted parts and get remaining terms
    query = re.sub(r'"[^"]*"', " ", query)
    for term in query.split():
        term = term.strip().lower()
        # Skip wildcards at the end, but keep the base term
        if term.endswith("*"):
            term = term[:-1]
        if len(term) >= 3:  # Skip very short terms
            terms.append(term)
    return terms


def _matches_query(text: str, terms: list[str]) -> bool:
    """Check if text contains any of the query terms."""
    text_lower = text.lower()
    # Match if any term is found
    return any(term in text_lower for term in terms)


def _parse_item(item: dict, server: str, topic: str, query_terms: list[str]) -> Paper | None:
    """Parse a bioRxiv/medRxiv API item into a Paper."""
    title = item.get("title", "")
    abstract = item.get("abstract", "")

    # Filter by query terms (since API doesn't support search)
    searchable = f"{title} {abstract}"
    if query_terms and not _matches_query(searchable, query_terms):
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

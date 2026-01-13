"""arXiv fetcher using Atom API."""

import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Iterator
from urllib.parse import quote

import requests

from ..db import Paper, generate_paper_id

ARXIV_API_URL = "https://export.arxiv.org/api/query"


def fetch_arxiv(
    query: str,
    topic: str,
    since: datetime | None = None,
    max_results: int = 100,
) -> Iterator[Paper]:
    """Fetch papers from arXiv matching the query."""
    # arXiv uses a different query syntax - convert boolean operators
    arxiv_query = _convert_query(query)

    params = {
        "search_query": arxiv_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    try:
        resp = requests.get(ARXIV_API_URL, params=params, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"arXiv fetch error: {e}")
        return

    # Parse Atom feed
    root = ET.fromstring(resp.content)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    for entry in root.findall("atom:entry", ns):
        try:
            paper = _parse_entry(entry, ns, topic, since)
            if paper:
                yield paper
        except Exception as e:
            print(f"Error parsing arXiv entry: {e}")
            continue

        time.sleep(0.1)  # Be nice to arXiv


def _convert_query(query: str) -> str:
    """Convert PubMed-style query to arXiv query syntax."""
    # arXiv uses 'all:' prefix for searching all fields
    # Remove field specifiers like [dp]
    import re

    q = re.sub(r"\[\w+\]", "", query)
    # arXiv prefers AND/OR in lowercase or as operators
    # Wrap terms for better matching
    q = f"all:{q}"
    return q


def _parse_entry(
    entry: ET.Element, ns: dict, topic: str, since: datetime | None
) -> Paper | None:
    """Parse an arXiv Atom entry into a Paper."""
    # Published date
    published_elem = entry.find("atom:published", ns)
    if published_elem is None or not published_elem.text:
        return None

    published_str = published_elem.text
    try:
        published_date = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
    except ValueError:
        published_date = datetime.now()

    # Filter by date if specified
    if since and published_date.replace(tzinfo=None) < since:
        return None

    # Title
    title_elem = entry.find("atom:title", ns)
    title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else ""
    if not title:
        return None

    # Abstract
    summary_elem = entry.find("atom:summary", ns)
    abstract = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else ""

    # Authors
    authors = []
    for author in entry.findall("atom:author", ns):
        name_elem = author.find("atom:name", ns)
        if name_elem is not None and name_elem.text:
            authors.append(name_elem.text)
    authors_str = ", ".join(authors[:5])
    if len(authors) > 5:
        authors_str += " et al."

    # arXiv ID and URL
    id_elem = entry.find("atom:id", ns)
    if id_elem is None or not id_elem.text:
        return None

    url = id_elem.text
    # Extract arXiv ID from URL (e.g., http://arxiv.org/abs/2301.12345v1)
    arxiv_id = url.split("/abs/")[-1] if "/abs/" in url else url.split("/")[-1]
    # Remove version suffix for consistent ID
    arxiv_id_base = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id

    # DOI (if available via link)
    doi = None
    for link in entry.findall("atom:link", ns):
        if link.get("title") == "doi":
            doi_url = link.get("href", "")
            if "doi.org/" in doi_url:
                doi = doi_url.split("doi.org/")[-1]

    paper_id = generate_paper_id(doi, arxiv_id_base, title)

    return Paper(
        id=paper_id,
        doi=doi,
        arxiv_id=arxiv_id_base,
        title=title,
        authors=authors_str,
        abstract=abstract,
        url=url,
        source="arxiv",
        published_date=published_date.strftime("%Y-%m-%d"),
        topic=topic,
        first_seen=datetime.now().isoformat(),
    )

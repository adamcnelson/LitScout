"""PubMed fetcher using NCBI E-utilities API."""

import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Iterator
from urllib.parse import quote

import requests

from ..db import Paper, generate_paper_id

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def fetch_pubmed(
    query: str,
    topic: str,
    since: datetime | None = None,
    max_results: int = 100,
) -> Iterator[Paper]:
    """Fetch papers from PubMed matching the query."""
    # Build date filter
    date_filter = ""
    if since:
        date_str = since.strftime("%Y/%m/%d")
        today_str = datetime.now().strftime("%Y/%m/%d")
        date_filter = f" AND ({date_str}:{today_str}[dp])"

    full_query = query + date_filter

    # Step 1: Search for IDs
    search_params = {
        "db": "pubmed",
        "term": full_query,
        "retmax": max_results,
        "retmode": "json",
        "sort": "date",
    }

    try:
        resp = requests.get(ESEARCH_URL, params=search_params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"PubMed search error: {e}")
        return

    id_list = data.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        return

    # Step 2: Fetch article details
    time.sleep(0.34)  # Rate limit: 3 requests/second without API key

    fetch_params = {
        "db": "pubmed",
        "id": ",".join(id_list),
        "retmode": "xml",
    }

    try:
        resp = requests.get(EFETCH_URL, params=fetch_params, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"PubMed fetch error: {e}")
        return

    # Parse XML response
    root = ET.fromstring(resp.content)

    for article in root.findall(".//PubmedArticle"):
        try:
            paper = _parse_article(article, topic)
            if paper:
                yield paper
        except Exception as e:
            print(f"Error parsing PubMed article: {e}")
            continue


def _parse_article(article: ET.Element, topic: str) -> Paper | None:
    """Parse a PubMed article XML element into a Paper."""
    medline = article.find("MedlineCitation")
    if medline is None:
        return None

    pmid_elem = medline.find("PMID")
    if pmid_elem is None:
        return None
    pmid = pmid_elem.text

    article_elem = medline.find("Article")
    if article_elem is None:
        return None

    # Title
    title_elem = article_elem.find("ArticleTitle")
    title = title_elem.text if title_elem is not None and title_elem.text else ""
    if not title:
        return None

    # Abstract
    abstract_elem = article_elem.find("Abstract/AbstractText")
    abstract = ""
    if abstract_elem is not None:
        # Handle structured abstracts
        abstract_parts = article_elem.findall("Abstract/AbstractText")
        abstract_texts = []
        for part in abstract_parts:
            label = part.get("Label", "")
            text = part.text or ""
            if label:
                abstract_texts.append(f"{label}: {text}")
            else:
                abstract_texts.append(text)
        abstract = " ".join(abstract_texts)

    # Authors
    authors = []
    author_list = article_elem.find("AuthorList")
    if author_list is not None:
        for author in author_list.findall("Author"):
            lastname = author.find("LastName")
            forename = author.find("ForeName")
            if lastname is not None and lastname.text:
                name = lastname.text
                if forename is not None and forename.text:
                    name = f"{forename.text} {lastname.text}"
                authors.append(name)
    authors_str = ", ".join(authors[:5])
    if len(authors) > 5:
        authors_str += " et al."

    # DOI
    doi = None
    article_ids = article.findall(".//ArticleId")
    for aid in article_ids:
        if aid.get("IdType") == "doi":
            doi = aid.text
            break

    # Publication date
    pub_date = ""
    date_elem = article_elem.find("Journal/JournalIssue/PubDate")
    if date_elem is not None:
        year = date_elem.find("Year")
        month = date_elem.find("Month")
        day = date_elem.find("Day")
        if year is not None and year.text:
            pub_date = year.text
            if month is not None and month.text:
                pub_date += f"-{month.text}"
                if day is not None and day.text:
                    pub_date += f"-{day.text}"

    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    paper_id = generate_paper_id(doi, None, title)

    return Paper(
        id=paper_id,
        doi=doi,
        arxiv_id=None,
        title=title,
        authors=authors_str,
        abstract=abstract,
        url=url,
        source="pubmed",
        published_date=pub_date,
        topic=topic,
        first_seen=datetime.now().isoformat(),
    )

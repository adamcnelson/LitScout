"""SQLite database for tracking seen papers and run state."""

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


@dataclass
class Paper:
    """A paper record."""

    id: str  # Unique identifier (DOI, arXiv ID, or normalized title hash)
    doi: str | None
    arxiv_id: str | None
    title: str
    authors: str
    abstract: str
    url: str
    source: str  # pubmed, arxiv, biorxiv, medrxiv
    published_date: str
    topic: str
    first_seen: str
    summary: str | None = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    doi TEXT,
    arxiv_id TEXT,
    title TEXT NOT NULL,
    authors TEXT,
    abstract TEXT,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    published_date TEXT,
    topic TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_papers_topic ON papers(topic);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id);

CREATE TABLE IF NOT EXISTS run_state (
    topic TEXT NOT NULL,
    source TEXT NOT NULL,
    last_run TEXT NOT NULL,
    PRIMARY KEY (topic, source)
);
"""


class Database:
    """SQLite database manager for LitScout."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_last_run(self, topic: str, source: str) -> datetime | None:
        """Get the last run timestamp for a topic/source pair."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_run FROM run_state WHERE topic = ? AND source = ?",
                (topic, source),
            ).fetchone()
            if row:
                return datetime.fromisoformat(row["last_run"])
            return None

    def set_last_run(self, topic: str, source: str, timestamp: datetime) -> None:
        """Update the last run timestamp for a topic/source pair."""
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO run_state (topic, source, last_run)
                   VALUES (?, ?, ?)""",
                (topic, source, timestamp.isoformat()),
            )

    def paper_exists(self, paper_id: str) -> bool:
        """Check if a paper has already been seen."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM papers WHERE id = ?", (paper_id,)
            ).fetchone()
            return row is not None

    def add_paper(self, paper: Paper) -> bool:
        """Add a paper if it doesn't exist. Returns True if added."""
        if self.paper_exists(paper.id):
            return False
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO papers
                   (id, doi, arxiv_id, title, authors, abstract, url, source,
                    published_date, topic, first_seen, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    paper.id,
                    paper.doi,
                    paper.arxiv_id,
                    paper.title,
                    paper.authors,
                    paper.abstract,
                    paper.url,
                    paper.source,
                    paper.published_date,
                    paper.topic,
                    paper.first_seen,
                    paper.summary,
                ),
            )
        return True

    def update_summary(self, paper_id: str, summary: str) -> None:
        """Update the summary for a paper."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE papers SET summary = ? WHERE id = ?",
                (summary, paper_id),
            )

    def get_paper(self, paper_id: str) -> Paper | None:
        """Get a paper by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE id = ?", (paper_id,)
            ).fetchone()
            if row:
                return Paper(**dict(row))
            return None


def normalize_title(title: str) -> str:
    """Normalize a title for deduplication."""
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def generate_paper_id(doi: str | None, arxiv_id: str | None, title: str) -> str:
    """Generate a unique ID for a paper, preferring DOI > arXiv ID > title hash."""
    if doi:
        return f"doi:{doi}"
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    import hashlib

    normalized = normalize_title(title)
    return f"title:{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"

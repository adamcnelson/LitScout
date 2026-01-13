"""Simple ranking for papers."""

from datetime import datetime

from .db import Paper


def rank_papers(papers: list[Paper], top_k: int) -> list[Paper]:
    """Rank papers by recency and return top_k."""
    def score(paper: Paper) -> float:
        """Score a paper based on recency."""
        # Parse publication date
        try:
            if paper.published_date:
                # Handle various date formats
                date_str = paper.published_date
                for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
                    try:
                        pub_date = datetime.strptime(date_str[:len(fmt.replace("%", ""))+fmt.count("-")], fmt)
                        break
                    except ValueError:
                        continue
                else:
                    pub_date = datetime.now()
            else:
                pub_date = datetime.now()
        except Exception:
            pub_date = datetime.now()

        # Days since publication (more recent = higher score)
        days_old = (datetime.now() - pub_date).days
        recency_score = max(0, 100 - days_old)

        # Bonus for having abstract (more informative)
        abstract_score = 20 if paper.abstract and len(paper.abstract) > 100 else 0

        # Bonus for having DOI (likely peer-reviewed or formal preprint)
        doi_score = 10 if paper.doi else 0

        return recency_score + abstract_score + doi_score

    # Sort by score descending
    ranked = sorted(papers, key=score, reverse=True)
    return ranked[:top_k]

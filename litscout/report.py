"""Markdown report generation."""

from datetime import datetime
from pathlib import Path

from .db import Paper


def generate_report(
    papers_by_topic: dict[str, list[Paper]],
    output_dir: Path,
) -> Path:
    """Generate a Markdown report with all topics and papers."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    report_path = output_dir / f"litscout_report_{timestamp}.md"

    lines = [
        f"# LitScout Report",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
    ]

    total_papers = sum(len(papers) for papers in papers_by_topic.values())
    lines.append(f"**Total new papers found: {total_papers}**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Table of contents
    lines.append("## Table of Contents")
    lines.append("")
    for topic_name in papers_by_topic.keys():
        anchor = topic_name.lower().replace(" ", "-").replace("/", "").replace("&", "and")
        paper_count = len(papers_by_topic[topic_name])
        lines.append(f"- [{topic_name}](#{anchor}) ({paper_count} papers)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Topic sections
    for topic_name, papers in papers_by_topic.items():
        lines.append(f"## {topic_name}")
        lines.append("")

        if not papers:
            lines.append("*No new papers found for this topic.*")
            lines.append("")
            continue

        for i, paper in enumerate(papers, 1):
            lines.append(f"### {i}. {paper.title}")
            lines.append("")
            lines.append(f"**Authors:** {paper.authors}")
            lines.append("")
            lines.append(f"**Source:** {paper.source} | **Published:** {paper.published_date}")
            lines.append("")
            lines.append(f"**Link:** [{paper.url}]({paper.url})")
            lines.append("")

            if paper.summary:
                lines.append(paper.summary)
            else:
                lines.append("*Summary not available.*")

            lines.append("")
            lines.append("---")
            lines.append("")

    report_content = "\n".join(lines)
    report_path.write_text(report_content)

    return report_path

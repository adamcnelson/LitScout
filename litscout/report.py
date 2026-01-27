"""Markdown report generation."""

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .db import Paper

if TYPE_CHECKING:
    from .sources.collect_podcasts import PodcastEpisode
    from .sources.collect_trials import ClinicalTrial
    from .sources.collect_youtube import YouTubeVideo


def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def generate_report(
    papers_by_topic: dict[str, list[Paper]],
    output_dir: Path,
    podcasts_by_topic: dict[str, list["PodcastEpisode"]] | None = None,
    videos_by_topic: dict[str, list["YouTubeVideo"]] | None = None,
    trials_by_topic: dict[str, list["ClinicalTrial"]] | None = None,
    docs_dir: Path | None = None,
) -> Path:
    """Generate a Markdown report with all topics, papers, and media.

    Args:
        papers_by_topic: Papers organized by topic name
        output_dir: Directory for the main report output
        podcasts_by_topic: Podcast episodes by topic
        videos_by_topic: YouTube videos by topic
        trials_by_topic: Clinical trials by topic
        docs_dir: Optional docs directory for MkDocs publishing

    Returns:
        Path to the generated report
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    report_path = output_dir / f"litscout_report_{timestamp}.md"

    podcasts_by_topic = podcasts_by_topic or {}
    videos_by_topic = videos_by_topic or {}
    trials_by_topic = trials_by_topic or {}

    lines = [
        f"# LitScout Report",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
    ]

    total_papers = sum(len(papers) for papers in papers_by_topic.values())
    total_podcasts = sum(len(eps) for eps in podcasts_by_topic.values())
    total_videos = sum(len(vids) for vids in videos_by_topic.values())
    total_trials = sum(len(trs) for trs in trials_by_topic.values())

    lines.append(f"**Total new papers found: {total_papers}**")
    if total_podcasts > 0:
        lines.append(f"**Total podcast episodes: {total_podcasts}**")
    if total_videos > 0:
        lines.append(f"**Total YouTube videos: {total_videos}**")
    if total_trials > 0:
        lines.append(f"**Total clinical trials: {total_trials}**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Table of contents
    lines.append("## Table of Contents")
    lines.append("")
    for topic_name in papers_by_topic.keys():
        anchor = topic_name.lower().replace(" ", "-").replace("/", "").replace("&", "and")
        paper_count = len(papers_by_topic[topic_name])
        podcast_count = len(podcasts_by_topic.get(topic_name, []))
        video_count = len(videos_by_topic.get(topic_name, []))
        trial_count = len(trials_by_topic.get(topic_name, []))

        counts = [f"{paper_count} papers"]
        if podcast_count > 0:
            counts.append(f"{podcast_count} podcasts")
        if video_count > 0:
            counts.append(f"{video_count} videos")
        if trial_count > 0:
            counts.append(f"{trial_count} trials")

        lines.append(f"- [{topic_name}](#{anchor}) ({', '.join(counts)})")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Topic sections
    for topic_name, papers in papers_by_topic.items():
        lines.append(f"## {topic_name}")
        lines.append("")

        # Papers section
        if papers:
            lines.append("### Papers")
            lines.append("")
            for i, paper in enumerate(papers, 1):
                lines.append(f"#### {i}. {paper.title}")
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
        else:
            lines.append("*No new papers found for this topic.*")
            lines.append("")

        # Podcasts section
        podcasts = podcasts_by_topic.get(topic_name, [])
        if podcasts:
            lines.append("### Podcast Episodes")
            lines.append("")
            for i, ep in enumerate(podcasts, 1):
                lines.append(f"#### {i}. {ep.title}")
                lines.append("")
                lines.append(f"**Show:** {ep.show_name}")
                lines.append("")
                lines.append(f"**Published:** {ep.published_date} | **Duration:** {ep.duration_minutes} min")
                lines.append("")
                if ep.url:
                    lines.append(f"**Link:** [{ep.url}]({ep.url})")
                    lines.append("")
                if ep.description:
                    # Truncate long descriptions
                    desc = ep.description[:500]
                    if len(ep.description) > 500:
                        desc += "..."
                    lines.append(f"> {desc}")
                    lines.append("")

        # YouTube section
        videos = videos_by_topic.get(topic_name, [])
        if videos:
            lines.append("### YouTube Videos")
            lines.append("")
            for i, vid in enumerate(videos, 1):
                lines.append(f"#### {i}. {vid.title}")
                lines.append("")
                lines.append(f"**Channel:** {vid.channel_name}")
                lines.append("")
                duration_str = f"{vid.duration_minutes} min"
                views_str = f" | **Views:** {vid.view_count:,}" if vid.view_count else ""
                lines.append(f"**Published:** {vid.published_date} | **Duration:** {duration_str}{views_str}")
                lines.append("")
                lines.append(f"**Link:** [{vid.url}]({vid.url})")
                lines.append("")
                if vid.description:
                    # Truncate long descriptions
                    desc = vid.description[:500]
                    if len(vid.description) > 500:
                        desc += "..."
                    lines.append(f"> {desc}")
                    lines.append("")

        # Clinical trials section
        trials = trials_by_topic.get(topic_name, [])
        if trials:
            lines.append("### Clinical Trials")
            lines.append("")
            for i, trial in enumerate(trials, 1):
                lines.append(f"#### {i}. [{trial.title}]({trial.url})")
                lines.append("")
                lines.append(
                    f"**NCT ID:** {trial.nct_id} | **Phase:** {trial.phase} | **Status:** {trial.status}"
                )
                lines.append("")

                if trial.conditions:
                    lines.append(f"**Conditions:** {', '.join(trial.conditions)}")
                    lines.append("")

                if trial.interventions:
                    lines.append(f"**Interventions:** {', '.join(trial.interventions)}")
                    lines.append("")

                sponsor_info = f"**Sponsor:** {trial.sponsor}"
                if trial.collaborators:
                    sponsor_info += f" | **Collaborators:** {', '.join(trial.collaborators)}"
                lines.append(sponsor_info)
                lines.append("")

                dates_info = f"**Last Updated:** {trial.last_update_posted}"
                if trial.study_start_date:
                    dates_info += f" | **Study Start:** {trial.study_start_date}"
                if trial.enrollment:
                    dates_info += f" | **Enrollment:** {trial.enrollment:,}"
                lines.append(dates_info)
                lines.append("")

                if trial.relevance_summary:
                    lines.append(f"**Why it matters:** {trial.relevance_summary}")
                    lines.append("")

                if trial.brief_summary:
                    # Truncate long summaries
                    summary = trial.brief_summary[:600]
                    if len(trial.brief_summary) > 600:
                        summary += "..."
                    lines.append(f"> {summary}")
                    lines.append("")

        lines.append("---")
        lines.append("")

    report_content = "\n".join(lines)
    report_path.write_text(report_content)

    # Also write to docs/reports/ for MkDocs publishing
    if docs_dir:
        _write_docs_reports(
            docs_dir,
            papers_by_topic,
            podcasts_by_topic,
            videos_by_topic,
            trials_by_topic,
        )

    return report_path


def _write_docs_reports(
    docs_dir: Path,
    papers_by_topic: dict[str, list[Paper]],
    podcasts_by_topic: dict[str, list["PodcastEpisode"]] | None,
    videos_by_topic: dict[str, list["YouTubeVideo"]] | None,
    trials_by_topic: dict[str, list["ClinicalTrial"]] | None,
) -> None:
    """Write per-topic reports to docs/reports/ and regenerate the archive index."""
    reports_dir = docs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    podcasts_by_topic = podcasts_by_topic or {}
    videos_by_topic = videos_by_topic or {}
    trials_by_topic = trials_by_topic or {}

    date_str = datetime.now().strftime("%Y-%m-%d")

    # Write a report file for each topic
    for topic_name, papers in papers_by_topic.items():
        topic_slug = _slugify(topic_name)
        filename = f"{date_str}--{topic_slug}.md"
        report_path = reports_dir / filename

        lines = [
            f"# {topic_name}",
            "",
            f"*Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
        ]

        # Summary counts
        paper_count = len(papers)
        podcast_count = len(podcasts_by_topic.get(topic_name, []))
        video_count = len(videos_by_topic.get(topic_name, []))
        trial_count = len(trials_by_topic.get(topic_name, []))

        counts = [f"**{paper_count} papers**"]
        if podcast_count > 0:
            counts.append(f"**{podcast_count} podcasts**")
        if video_count > 0:
            counts.append(f"**{video_count} videos**")
        if trial_count > 0:
            counts.append(f"**{trial_count} trials**")

        lines.append(" | ".join(counts))
        lines.append("")
        lines.append("---")
        lines.append("")

        # Papers section
        if papers:
            lines.append("## Papers")
            lines.append("")
            for i, paper in enumerate(papers, 1):
                lines.append(f"### {i}. {paper.title}")
                lines.append("")
                lines.append(f"**Authors:** {paper.authors}")
                lines.append("")
                lines.append(
                    f"**Source:** {paper.source} | **Published:** {paper.published_date}"
                )
                lines.append("")
                lines.append(f"**Link:** [{paper.url}]({paper.url})")
                lines.append("")
                if paper.summary:
                    lines.append(paper.summary)
                else:
                    lines.append("*Summary not available.*")
                lines.append("")

        # Podcasts section
        podcasts = podcasts_by_topic.get(topic_name, [])
        if podcasts:
            lines.append("## Podcast Episodes")
            lines.append("")
            for i, ep in enumerate(podcasts, 1):
                lines.append(f"### {i}. {ep.title}")
                lines.append("")
                lines.append(f"**Show:** {ep.show_name}")
                lines.append("")
                lines.append(
                    f"**Published:** {ep.published_date} | **Duration:** {ep.duration_minutes} min"
                )
                lines.append("")
                if ep.url:
                    lines.append(f"**Link:** [{ep.url}]({ep.url})")
                    lines.append("")
                if ep.description:
                    desc = ep.description[:500]
                    if len(ep.description) > 500:
                        desc += "..."
                    lines.append(f"> {desc}")
                    lines.append("")

        # YouTube section
        videos = videos_by_topic.get(topic_name, [])
        if videos:
            lines.append("## YouTube Videos")
            lines.append("")
            for i, vid in enumerate(videos, 1):
                lines.append(f"### {i}. {vid.title}")
                lines.append("")
                lines.append(f"**Channel:** {vid.channel_name}")
                lines.append("")
                duration_str = f"{vid.duration_minutes} min"
                views_str = f" | **Views:** {vid.view_count:,}" if vid.view_count else ""
                lines.append(
                    f"**Published:** {vid.published_date} | **Duration:** {duration_str}{views_str}"
                )
                lines.append("")
                lines.append(f"**Link:** [{vid.url}]({vid.url})")
                lines.append("")
                if vid.description:
                    desc = vid.description[:500]
                    if len(vid.description) > 500:
                        desc += "..."
                    lines.append(f"> {desc}")
                    lines.append("")

        # Clinical trials section
        trials = trials_by_topic.get(topic_name, [])
        if trials:
            lines.append("## Clinical Trials")
            lines.append("")
            for i, trial in enumerate(trials, 1):
                lines.append(f"### {i}. [{trial.title}]({trial.url})")
                lines.append("")
                lines.append(
                    f"**NCT ID:** {trial.nct_id} | **Phase:** {trial.phase} | **Status:** {trial.status}"
                )
                lines.append("")
                if trial.conditions:
                    lines.append(f"**Conditions:** {', '.join(trial.conditions)}")
                    lines.append("")
                if trial.interventions:
                    lines.append(f"**Interventions:** {', '.join(trial.interventions)}")
                    lines.append("")
                sponsor_info = f"**Sponsor:** {trial.sponsor}"
                if trial.collaborators:
                    sponsor_info += f" | **Collaborators:** {', '.join(trial.collaborators)}"
                lines.append(sponsor_info)
                lines.append("")
                if trial.relevance_summary:
                    lines.append(f"**Why it matters:** {trial.relevance_summary}")
                    lines.append("")
                if trial.brief_summary:
                    summary = trial.brief_summary[:600]
                    if len(trial.brief_summary) > 600:
                        summary += "..."
                    lines.append(f"> {summary}")
                    lines.append("")

        report_path.write_text("\n".join(lines))

    # Regenerate the archive index
    _regenerate_archive_index(reports_dir)


def _regenerate_archive_index(reports_dir: Path) -> None:
    """Regenerate docs/reports/index.md with links to all reports."""
    # Find all report files (YYYY-MM-DD--topic-slug.md)
    report_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})--(.+)\.md$")
    reports: list[tuple[str, str, str]] = []  # (date, slug, filename)

    for path in reports_dir.glob("*.md"):
        if path.name == "index.md":
            continue
        match = report_pattern.match(path.name)
        if match:
            date_str, slug = match.groups()
            reports.append((date_str, slug, path.name))

    # Sort by date (newest first), then by slug
    reports.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # Group by topic (slug)
    topics: dict[str, list[tuple[str, str]]] = {}
    for date_str, slug, filename in reports:
        if slug not in topics:
            topics[slug] = []
        topics[slug].append((date_str, filename))

    # Build the index
    lines = [
        "# Reports Archive",
        "",
    ]

    if not reports:
        lines.append("*No reports generated yet. Run `litscout run` to generate your first report.*")
    else:
        # Latest reports section
        lines.append("## Latest Reports")
        lines.append("")

        # Show most recent report for each topic
        seen_slugs = set()
        for date_str, slug, filename in reports:
            if slug not in seen_slugs:
                # Convert slug back to readable title
                title = slug.replace("-", " ").title()
                lines.append(f"- [{title}]({filename}) — {date_str}")
                seen_slugs.add(slug)
        lines.append("")

        # All reports by topic
        lines.append("## All Reports by Topic")
        lines.append("")

        for slug in sorted(topics.keys()):
            title = slug.replace("-", " ").title()
            lines.append(f"### {title}")
            lines.append("")
            for date_str, filename in topics[slug]:
                lines.append(f"- [{date_str}]({filename})")
            lines.append("")

    index_path = reports_dir / "index.md"
    index_path.write_text("\n".join(lines))

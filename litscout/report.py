"""Markdown report generation."""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .db import Paper

if TYPE_CHECKING:
    from .sources.collect_podcasts import PodcastEpisode
    from .sources.collect_trials import ClinicalTrial
    from .sources.collect_youtube import YouTubeVideo


def generate_report(
    papers_by_topic: dict[str, list[Paper]],
    output_dir: Path,
    podcasts_by_topic: dict[str, list["PodcastEpisode"]] | None = None,
    videos_by_topic: dict[str, list["YouTubeVideo"]] | None = None,
    trials_by_topic: dict[str, list["ClinicalTrial"]] | None = None,
) -> Path:
    """Generate a Markdown report with all topics, papers, and media."""
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

    return report_path

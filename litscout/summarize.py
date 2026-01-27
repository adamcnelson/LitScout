"""Paper summarization using Claude API."""

from pathlib import Path
from typing import TYPE_CHECKING

import anthropic

from .db import Paper

if TYPE_CHECKING:
    from .sources.collect_trials import ClinicalTrial


def load_prompt_template(prompt_path: Path | None = None) -> str:
    """Load the summary prompt template."""
    if prompt_path is None:
        # Default location
        prompt_path = Path(__file__).parent.parent / "prompts" / "summary.md"

    if prompt_path.exists():
        return prompt_path.read_text()

    # Fallback minimal prompt
    return """Summarize this paper based on title and abstract only.
Provide: one-sentence claim, key methods, key results, limitations."""


def summarize_paper(paper: Paper, prompt_template: str | None = None) -> str:
    """Generate a summary for a paper using Claude."""
    if prompt_template is None:
        prompt_template = load_prompt_template()

    # Build the paper context
    paper_context = f"""Title: {paper.title}

Authors: {paper.authors}

Source: {paper.source}
Published: {paper.published_date}
URL: {paper.url}

Abstract:
{paper.abstract if paper.abstract else "(No abstract available)"}
"""

    client = anthropic.Anthropic()

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt_template}\n\n---\n\n{paper_context}",
                }
            ],
        )
        return message.content[0].text
    except anthropic.APIError as e:
        return f"(Summary unavailable: {e})"


def load_trial_prompt_template(prompt_path: Path | None = None) -> str:
    """Load the trial summary prompt template."""
    if prompt_path is None:
        prompt_path = Path(__file__).parent.parent / "prompts" / "trial_summary.md"

    if prompt_path.exists():
        return prompt_path.read_text()

    # Fallback minimal prompt
    return """Summarize why this clinical trial matters in 2-3 sentences.
Focus on novel mechanisms, potential impact, and unique study design aspects."""


def summarize_trial(
    trial: "ClinicalTrial", prompt_template: str | None = None
) -> str:
    """Generate a 'why it matters' summary for a clinical trial using Claude."""
    if prompt_template is None:
        prompt_template = load_trial_prompt_template()

    # Build the trial context
    conditions_str = ", ".join(trial.conditions) if trial.conditions else "N/A"
    interventions_str = ", ".join(trial.interventions) if trial.interventions else "N/A"
    collaborators_str = ", ".join(trial.collaborators) if trial.collaborators else "N/A"

    trial_context = f"""NCT ID: {trial.nct_id}
Title: {trial.title}
Phase: {trial.phase}
Status: {trial.status}
Conditions: {conditions_str}
Interventions: {interventions_str}
Sponsor: {trial.sponsor}
Collaborators: {collaborators_str}
Enrollment: {trial.enrollment if trial.enrollment else 'Not specified'}
Study Start: {trial.study_start_date}
Primary Completion: {trial.primary_completion_date or 'Not specified'}

Brief Summary:
{trial.brief_summary if trial.brief_summary else '(No summary available)'}
"""

    client = anthropic.Anthropic()

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt_template}\n\n---\n\n{trial_context}",
                }
            ],
        )
        return message.content[0].text
    except anthropic.APIError as e:
        return f"(Summary unavailable: {e})"

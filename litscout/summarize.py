"""Paper summarization using Claude API."""

from pathlib import Path

import anthropic

from .db import Paper


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

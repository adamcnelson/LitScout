# LitScout (Claude Code instructions)

Goal: build a local CLI that runs scheduled literature searches across PubMed + preprints,
dedupes/ranks results for each topic, summarizes top papers via Claude using prompts/summary.md,
and writes a Markdown report to output_dir in config/config.yaml.

Constraints:
- Use title + abstract + metadata only for summaries (no full-text scraping for now).
- Keep diffs small and reviewable.
- Store state in SQLite so runs are incremental (no re-summarizing previously seen items).
- Output: max top_k_per_topic links per topic in each report, with stable URLs.
- Provide a simple CLI: `python -m litscout run --config config/config.yaml`
- Put generated reports in the config output_dir.

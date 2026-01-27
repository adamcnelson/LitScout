# LitScout

**Automated literature search and summarization for scientific research.**

LitScout is a CLI tool that runs scheduled literature searches across PubMed, preprints (bioRxiv, medRxiv, arXiv), podcasts, YouTube, and ClinicalTrials.gov. It dedupes and ranks results for each topic, summarizes top papers via Claude, and generates Markdown reports.

## Features

- **Multi-source search**: PubMed, bioRxiv, medRxiv, arXiv
- **Media collection**: Podcasts and YouTube videos
- **Clinical trials**: ClinicalTrials.gov integration
- **AI summarization**: Claude-powered paper summaries
- **Incremental updates**: SQLite-backed state for efficient runs
- **Configurable topics**: YAML-based topic definitions

## Quick Start

```bash
# Install
pip install -e .

# Initialize a project
litscout init --path ./my-project

# Run a search
litscout run --config config/config.yaml
```

## Reports

Browse the [Reports Archive](reports/index.md) for all generated literature reports.

## Links

- [GitHub Repository](https://github.com/adamcnelson/LitScout)
- [Report an Issue](https://github.com/adamcnelson/LitScout/issues)

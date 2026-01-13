# LitScout

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Automated literature search and summarization CLI. LitScout searches PubMed, arXiv, bioRxiv, and medRxiv for papers matching your topics, deduplicates results, ranks by recency, summarizes top papers using Claude, and generates Markdown reports.

## Features

- **Multi-source search**: PubMed, arXiv, bioRxiv, medRxiv
- **Incremental updates**: Only fetches new papers since last run
- **AI summarization**: Structured summaries via Claude API
- **Deduplication**: By DOI, arXiv ID, or normalized title
- **Customizable prompts**: Edit the summary template to your needs
- **Email notifications**: Optional alerts via macOS Mail (disabled by default)

## Quickstart

### 1. Install

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/LitScout.git
cd LitScout

# Install (creates 'litscout' command)
pip install -e .
```

### 2. Set up API key

```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

### 3. Initialize a project

```bash
litscout init --path ./my-literature-watch
cd my-literature-watch
```

This creates:
```
my-literature-watch/
├── config/
│   ├── config.yaml          # Your configuration (edit this)
│   └── config.example.yaml  # Reference template
├── prompts/
│   └── summary.md           # Summary prompt template
├── reports/                  # Generated reports go here
└── data/                     # Database storage
```

### 4. Configure your topics

Edit `config/config.yaml`:

```yaml
output_dir: "./reports"
top_k_per_topic: 10
initial_lookback_days: 14

topics:
  - name: "My Research Area"
    query: >
      (keyword1 OR keyword2) AND (keyword3 OR keyword4)
    sources:
      - pubmed
      - biorxiv
```

### 5. Run

```bash
litscout run
```

## CLI Reference

```
litscout --help
litscout init --help
litscout run --help
litscout doctor --help
```

### Commands

| Command | Description |
|---------|-------------|
| `litscout init` | Initialize a new project with config and directories |
| `litscout run` | Run literature search and generate report |
| `litscout doctor` | Check configuration and dependencies |

### Run Options

| Flag | Description |
|------|-------------|
| `--config`, `-c` | Path to config.yaml |
| `--dry-run` | Fetch papers but don't save report or update state |
| `--no-summarize` | Skip Claude summarization (faster testing) |
| `--verbose`, `-v` | Show detailed progress |
| `--quiet`, `-q` | Only show errors |
| `--email` | Enable email notification for this run |
| `--no-email` | Disable email notification for this run |
| `--email-to` | Override email recipient |

### Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Required for Claude summarization |
| `LITSCOUT_CONFIG` | Default config file path |

## Configuration

### Full config example

```yaml
# Where to save reports (~ is expanded)
output_dir: "~/Documents/LitScout/reports"

# Number of top papers per topic in report
top_k_per_topic: 10

# Days to look back on first run
initial_lookback_days: 14

# Email notifications (optional, disabled by default)
notifications:
  email:
    enabled: false
    to: "you@example.com"
    subject_prefix: "LitScout"
    attach_report: true
    include_top_links_in_body: true

# Search topics
topics:
  - name: "Topic Name"
    query: >
      (term1 OR term2) AND (term3 OR term4)
    exclude:
      - protocol
      - corrigendum
    sources:
      - pubmed
      - biorxiv
      - medrxiv
      - arxiv
```

### Query syntax

Queries use PubMed-style boolean syntax:
- `AND`, `OR` for combining terms
- Parentheses for grouping
- Quotes for exact phrases: `"cell painting"`
- Wildcards: `neurodegen*`

### Available sources

| Source | Description |
|--------|-------------|
| `pubmed` | PubMed/MEDLINE via NCBI E-utilities |
| `arxiv` | arXiv preprints |
| `biorxiv` | bioRxiv preprints |
| `medrxiv` | medRxiv preprints |

## Scheduling

### macOS (launchd)

Create `~/Library/LaunchAgents/com.litscout.daily.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.litscout.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/litscout</string>
        <string>run</string>
        <string>--config</string>
        <string>/path/to/your/config/config.yaml</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>ANTHROPIC_API_KEY</key>
        <string>your-api-key</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/litscout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/litscout.err</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.litscout.daily.plist
```

### Linux (cron)

```bash
# Edit crontab
crontab -e

# Add line (runs daily at 8am)
0 8 * * * ANTHROPIC_API_KEY=your-key /usr/local/bin/litscout run -c /path/to/config.yaml
```

## Email Notifications (Optional)

Email is **disabled by default**. To enable:

### Option 1: Config file

```yaml
notifications:
  email:
    enabled: true
    to: "you@example.com"
```

### Option 2: CLI flag

```bash
litscout run --email --email-to you@example.com
```

### Requirements (macOS only)

- macOS with Mail.app configured
- Grant automation permission: **System Settings > Privacy & Security > Automation** → allow Terminal to control Mail

Email failures are non-fatal—the report is still generated.

## Customizing Summaries

Edit `prompts/summary.md` to change how papers are summarized. The default template produces:

- One-sentence claim
- Why this matters (2-3 bullets)
- What they did (3-6 bullets)
- Key results (3-6 bullets)
- Limitations (2-4 bullets)
- Tags (5-10 keywords)

## Troubleshooting

### Check your setup

```bash
litscout doctor
```

### Common issues

**"ANTHROPIC_API_KEY not set"**
```bash
export ANTHROPIC_API_KEY=your-key
```

**"No config file found"**
```bash
litscout run --config path/to/config.yaml
# or
export LITSCOUT_CONFIG=path/to/config.yaml
```

**"Invalid source: xyz"**
Valid sources are: `pubmed`, `arxiv`, `biorxiv`, `medrxiv`

**Email not sending**
- Ensure Mail.app is configured
- Grant automation permission in System Settings
- Check `--email` flag or `notifications.email.enabled: true`

### Reset state

To re-fetch all papers:
```bash
rm config/litscout.db
litscout run
```

## Project Structure

```
litscout/
├── __init__.py
├── __main__.py      # CLI entry point
├── config.py        # Config loading and validation
├── db.py            # SQLite database
├── notifier.py      # Email notifications
├── rank.py          # Paper ranking
├── report.py        # Markdown generation
├── summarize.py     # Claude API calls
└── sources/
    ├── __init__.py
    ├── pubmed.py    # PubMed fetcher
    ├── arxiv.py     # arXiv fetcher
    └── biorxiv.py   # bioRxiv/medRxiv fetcher
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

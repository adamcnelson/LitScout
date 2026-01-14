"""CLI entry point for LitScout."""

import argparse
import os
import re
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from . import __version__
from .config import Config, ConfigError
from .db import Database, Paper
from .notifier import create_notifier
from .rank import rank_papers
from .report import generate_report
from .sources import fetch_arxiv, fetch_biorxiv, fetch_medrxiv, fetch_pubmed
from .summarize import load_prompt_template, summarize_paper

# Map source names to fetcher functions
SOURCE_FETCHERS = {
    "pubmed": fetch_pubmed,
    "arxiv": fetch_arxiv,
    "biorxiv": fetch_biorxiv,
    "medrxiv": fetch_medrxiv,
}

# Verbosity levels
QUIET = 0
NORMAL = 1
VERBOSE = 2


class Logger:
    """Simple logger with verbosity control."""

    def __init__(self, verbosity: int = NORMAL):
        self.verbosity = verbosity

    def info(self, msg: str) -> None:
        if self.verbosity >= NORMAL:
            print(msg)

    def verbose(self, msg: str) -> None:
        if self.verbosity >= VERBOSE:
            print(f"  {msg}")

    def warning(self, msg: str) -> None:
        print(f"Warning: {msg}", file=sys.stderr)

    def error(self, msg: str) -> None:
        print(f"Error: {msg}", file=sys.stderr)


def get_config_path(args_config: str | None) -> str:
    """Get config path from args or environment variable."""
    if args_config:
        return args_config

    env_config = os.environ.get("LITSCOUT_CONFIG")
    if env_config:
        return env_config

    # Check for config in current directory
    default_paths = [
        "config/config.yaml",
        "config.yaml",
        "litscout.yaml",
    ]
    for path in default_paths:
        if Path(path).exists():
            return path

    return None


def get_last_report_timestamp(output_dir: Path) -> datetime | None:
    """Find the most recent report and extract its timestamp.

    Report files are named: litscout_report_YYYY-MM-DD_HHMMSS.md
    Returns the datetime from the most recent report, or None if no reports exist.
    """
    if not output_dir.exists():
        return None

    # Pattern: litscout_report_2026-01-12_133343.md
    pattern = re.compile(r"litscout_report_(\d{4}-\d{2}-\d{2}_\d{6})\.md$")

    latest_timestamp = None
    for report_file in output_dir.glob("litscout_report_*.md"):
        match = pattern.match(report_file.name)
        if match:
            try:
                timestamp = datetime.strptime(match.group(1), "%Y-%m-%d_%H%M%S")
                if latest_timestamp is None or timestamp > latest_timestamp:
                    latest_timestamp = timestamp
            except ValueError:
                continue

    return latest_timestamp


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new LitScout project."""
    base_path = Path(args.path).resolve()
    log = Logger(NORMAL)

    log.info(f"Initializing LitScout project in {base_path}")

    # Create directories
    dirs = ["config", "prompts", "reports", "data"]
    for d in dirs:
        dir_path = base_path / d
        dir_path.mkdir(parents=True, exist_ok=True)
        log.info(f"  Created {d}/")

    # Write config.yaml
    config_content = '''output_dir: "./reports"
top_k_per_topic: 10
initial_lookback_days: 14

# Notifications (optional, disabled by default)
notifications:
  email:
    enabled: false
    to: ""
    subject_prefix: "LitScout"
    attach_report: true
    include_top_links_in_body: true

# Define your search topics
topics:
  - name: "Example Topic"
    query: >
      (keyword1 OR keyword2) AND (keyword3 OR keyword4)
    exclude:
      - protocol
      - corrigendum
      - retraction
    sources:
      - pubmed
      - biorxiv
      - medrxiv
'''
    config_path = base_path / "config" / "config.yaml"
    config_path.write_text(config_content)
    log.info("  Created config/config.yaml")

    # Write config.example.yaml (same content)
    example_path = base_path / "config" / "config.example.yaml"
    example_path.write_text(config_content)
    log.info("  Created config/config.example.yaml")

    # Write prompts/summary.md
    prompt_content = '''You are my literature scout. Use ONLY the provided title + abstract + metadata.
Do not invent details.

Write a concise, structured summary in Markdown with these sections:

## One-sentence claim
- A single sentence stating the paper's main claim.

## Why this matters
- 2–3 bullets focusing on novelty and impact.

## What they did
- 3–6 bullets on model system, key methods, and study design (stay high-level).

## Key results
- 3–6 bullets.
- If numbers are in the abstract, include them. If not, keep qualitative.

## Limitations / open questions
- 2–4 bullets. Be fair and specific.

## Tags
- 5–10 short tags (e.g., microglia, iPSC, organoid, phenomics, AD, CRISPR)

Rules:
- If the abstract is missing or uninformative, say so and keep it short.
- No hype. No speculation beyond what the abstract supports.
'''
    prompt_path = base_path / "prompts" / "summary.md"
    prompt_path.write_text(prompt_content)
    log.info("  Created prompts/summary.md")

    # Write .gitignore
    gitignore_content = '''# LitScout
data/*.db
reports/
config/config.yaml

# Python
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/

# OS
.DS_Store
'''
    gitignore_path = base_path / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(gitignore_content)
        log.info("  Created .gitignore")

    log.info("")
    log.info("Done! Next steps:")
    log.info("  1. Edit config/config.yaml with your search topics")
    log.info("  2. Set ANTHROPIC_API_KEY environment variable")
    log.info(f"  3. Run: litscout run --config {config_path}")

    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check LitScout configuration and dependencies."""
    log = Logger(NORMAL)
    issues = []

    log.info("LitScout Doctor")
    log.info("=" * 40)

    # Check Python version
    py_version = sys.version_info
    if py_version >= (3, 10):
        log.info(f"[OK] Python {py_version.major}.{py_version.minor}.{py_version.micro}")
    else:
        log.info(f"[!!] Python {py_version.major}.{py_version.minor} (need 3.10+)")
        issues.append("Python 3.10+ required")

    # Check Anthropic API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        log.info(f"[OK] ANTHROPIC_API_KEY set ({len(api_key)} chars)")
    else:
        log.info("[!!] ANTHROPIC_API_KEY not set")
        issues.append("ANTHROPIC_API_KEY environment variable not set")

    # Check config file
    config_path = get_config_path(args.config)
    if config_path and Path(config_path).exists():
        log.info(f"[OK] Config found: {config_path}")
        try:
            config = Config.from_yaml(config_path)
            log.info(f"     {len(config.topics)} topic(s) configured")
            log.info(f"     Output: {config.output_dir}")
        except ConfigError as e:
            log.info(f"[!!] Config error: {e}")
            issues.append(f"Config validation failed: {e}")
        except Exception as e:
            log.info(f"[!!] Config parse error: {e}")
            issues.append(f"Config parse failed: {e}")
    else:
        log.info("[!!] No config file found")
        issues.append("No config file found (use --config or LITSCOUT_CONFIG)")

    # Check dependencies
    log.info("")
    log.info("Dependencies:")
    for pkg in ["anthropic", "yaml", "requests"]:
        try:
            __import__(pkg)
            log.info(f"  [OK] {pkg}")
        except ImportError:
            log.info(f"  [!!] {pkg} not installed")
            issues.append(f"Missing dependency: {pkg}")

    # Check macOS Mail (for notifications)
    if sys.platform == "darwin":
        log.info("")
        log.info("macOS Mail (for email notifications):")
        log.info("  [--] Available (test with --email flag)")
    else:
        log.info("")
        log.info("Email notifications:")
        log.info("  [--] macOS Mail not available (non-macOS system)")

    # Summary
    log.info("")
    log.info("=" * 40)
    if issues:
        log.info(f"Found {len(issues)} issue(s):")
        for issue in issues:
            log.info(f"  - {issue}")
        return 1
    else:
        log.info("All checks passed!")
        return 0


def cmd_run(
    config_path: str,
    dry_run: bool = False,
    no_summarize: bool = False,
    email_enabled: bool | None = None,
    email_to: str | None = None,
    email_attach: bool | None = None,
    verbosity: int = NORMAL,
) -> int:
    """Run the literature search pipeline."""
    log = Logger(verbosity)

    # Validate config path
    if not config_path:
        log.error("No config file specified. Use --config or set LITSCOUT_CONFIG.")
        return 1

    if not Path(config_path).exists():
        log.error(f"Config file not found: {config_path}")
        return 1

    # Load and validate config
    try:
        config = Config.from_yaml(config_path)
    except ConfigError as e:
        log.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        log.error(f"Failed to load config: {e}")
        return 1

    config_dir = Path(config_path).parent

    # Apply CLI overrides for email settings
    email_config = config.notifications.email
    if email_enabled is not None:
        email_config = replace(email_config, enabled=email_enabled)
    if email_to is not None:
        email_config = replace(email_config, to=email_to)
    if email_attach is not None:
        email_config = replace(email_config, attach_report=email_attach)

    # Initialize database
    db_path = config_dir / "litscout.db"
    db = Database(db_path)

    # Load prompt template
    prompt_path = config_dir.parent / "prompts" / "summary.md"
    prompt_template = load_prompt_template(prompt_path)

    papers_by_topic: dict[str, list[Paper]] = {}
    now = datetime.now()

    # Check for last report timestamp (for lookback on manual runs)
    last_report_time = get_last_report_timestamp(config.output_dir)

    log.info(f"LitScout run started at {now.strftime('%Y-%m-%d %H:%M:%S')}")
    log.verbose(f"Config: {config_path}")
    log.verbose(f"Database: {db_path}")
    if last_report_time:
        log.verbose(f"Last report: {last_report_time.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"Topics: {len(config.topics)}")
    log.info("")

    for topic in config.topics:
        log.info(f"Processing topic: {topic.name}")
        topic_papers: list[Paper] = []

        for source in topic.sources:
            fetcher = SOURCE_FETCHERS.get(source)
            if not fetcher:
                log.warning(f"Unknown source: {source}, skipping")
                continue

            # Determine date range:
            # 1. Use database last_run if available (scheduled/incremental runs)
            # 2. Fall back to last report timestamp (manual runs catch up)
            # 3. Otherwise use initial_lookback_days (first run)
            last_run = db.get_last_run(topic.name, source)
            if last_run:
                since = last_run
                log.verbose(f"{source}: incremental from {since.strftime('%Y-%m-%d')}")
            elif last_report_time:
                since = last_report_time
                log.verbose(f"{source}: from last report ({since.strftime('%Y-%m-%d %H:%M')})")
            else:
                since = now - timedelta(days=config.initial_lookback_days)
                log.verbose(f"{source}: initial lookback ({config.initial_lookback_days} days)")

            # Fetch papers
            try:
                new_papers = list(fetcher(topic.query, topic.name, since))
                log.verbose(f"{source}: found {len(new_papers)} papers")
            except Exception as e:
                log.warning(f"Error fetching from {source}: {e}")
                continue

            # Filter exclusions and dedupe
            added = 0
            for paper in new_papers:
                # Check exclusions
                skip = False
                for exclude_term in topic.exclude:
                    if exclude_term.lower() in paper.title.lower():
                        skip = True
                        break
                if skip:
                    continue

                # Add to database (deduplication happens here)
                if db.add_paper(paper):
                    topic_papers.append(paper)
                    added += 1

            log.verbose(f"{source}: added {added} new papers")

            # Update last run timestamp
            if not dry_run:
                db.set_last_run(topic.name, source, now)

        # Rank and select top papers
        if topic_papers:
            top_papers = rank_papers(topic_papers, config.top_k_per_topic)
            log.info(f"  Selected top {len(top_papers)} papers")

            # Summarize papers
            if not no_summarize:
                for paper in top_papers:
                    if not paper.summary:
                        log.verbose(f"Summarizing: {paper.title[:50]}...")
                        try:
                            summary = summarize_paper(paper, prompt_template)
                            paper.summary = summary
                            db.update_summary(paper.id, summary)
                        except Exception as e:
                            log.warning(f"Error summarizing: {e}")

            papers_by_topic[topic.name] = top_papers
        else:
            papers_by_topic[topic.name] = []
            log.info("  No new papers found")

        log.info("")

    # Generate report
    if not dry_run:
        report_path = generate_report(papers_by_topic, config.output_dir)
        log.info(f"Report generated: {report_path}")

        # Send notification (failures are non-fatal)
        notifier = create_notifier(email_config)
        try:
            notifier.notify(papers_by_topic, report_path)
        except Exception as e:
            log.warning(f"Notification failed: {e}")
    else:
        log.info("Dry run complete - no report generated")

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="litscout",
        description="Automated literature search and summarization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  litscout init --path ./my-project    Initialize a new project
  litscout run --config config.yaml    Run literature search
  litscout doctor                      Check configuration

Environment variables:
  LITSCOUT_CONFIG    Default config file path
  ANTHROPIC_API_KEY  API key for Claude summarization
""",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # Init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new LitScout project",
        description="Create project structure with config, prompts, and directories.",
    )
    init_parser.add_argument(
        "--path",
        "-p",
        default=".",
        help="Directory to initialize (default: current directory)",
    )

    # Run command
    run_parser = subparsers.add_parser(
        "run",
        help="Run literature search",
        description="Fetch papers, summarize, and generate report.",
    )
    run_parser.add_argument(
        "--config",
        "-c",
        help="Path to config.yaml (or set LITSCOUT_CONFIG)",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and rank papers but don't update state or generate report",
    )
    run_parser.add_argument(
        "--no-summarize",
        action="store_true",
        help="Skip Claude summarization (faster, for testing)",
    )
    run_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress",
    )
    run_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only show errors and warnings",
    )

    # Email notification overrides
    email_group = run_parser.add_mutually_exclusive_group()
    email_group.add_argument(
        "--email",
        action="store_true",
        dest="email_enabled",
        default=None,
        help="Enable email notification (overrides config)",
    )
    email_group.add_argument(
        "--no-email",
        action="store_false",
        dest="email_enabled",
        help="Disable email notification (overrides config)",
    )
    run_parser.add_argument(
        "--email-to",
        metavar="ADDRESS",
        help="Email recipient (overrides config)",
    )
    attach_group = run_parser.add_mutually_exclusive_group()
    attach_group.add_argument(
        "--email-attach",
        action="store_true",
        dest="email_attach",
        default=None,
        help="Attach report to email (overrides config)",
    )
    attach_group.add_argument(
        "--no-email-attach",
        action="store_false",
        dest="email_attach",
        help="Don't attach report to email (overrides config)",
    )

    # Doctor command
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check configuration and dependencies",
        description="Verify that LitScout is properly configured.",
    )
    doctor_parser.add_argument(
        "--config",
        "-c",
        help="Path to config.yaml to check",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    try:
        if args.command == "init":
            return cmd_init(args)

        elif args.command == "doctor":
            return cmd_doctor(args)

        elif args.command == "run":
            # Determine verbosity
            if args.quiet:
                verbosity = QUIET
            elif args.verbose:
                verbosity = VERBOSE
            else:
                verbosity = NORMAL

            # Get config path
            config_path = get_config_path(args.config)

            return cmd_run(
                config_path,
                args.dry_run,
                args.no_summarize,
                email_enabled=args.email_enabled,
                email_to=args.email_to,
                email_attach=args.email_attach,
                verbosity=verbosity,
            )

    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

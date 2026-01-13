"""Notification system with pluggable notifiers."""

import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from .config import EmailConfig
from .db import Paper


class Notifier(ABC):
    """Abstract base class for notifiers."""

    @abstractmethod
    def notify(
        self,
        papers_by_topic: dict[str, list[Paper]],
        report_path: Path,
    ) -> bool:
        """Send notification. Returns True on success, False on failure."""
        pass


class NullNotifier(Notifier):
    """No-op notifier that does nothing."""

    def notify(
        self,
        papers_by_topic: dict[str, list[Paper]],
        report_path: Path,
    ) -> bool:
        return True


class MacOSMailNotifier(Notifier):
    """Send notifications via macOS Mail.app using AppleScript."""

    def __init__(self, config: EmailConfig):
        self.config = config

    def notify(
        self,
        papers_by_topic: dict[str, list[Paper]],
        report_path: Path,
    ) -> bool:
        """Send email notification via macOS Mail.app."""
        if not self.config.to:
            print("Warning: Email enabled but no recipient configured, skipping")
            return False

        # Build subject with date
        run_date = datetime.now().strftime("%Y-%m-%d")
        subject = f"{self.config.subject_prefix} — {run_date}"

        # Build body
        body = self._build_body(papers_by_topic, report_path)

        # Find the AppleScript
        script_path = Path(__file__).parent.parent / "scripts" / "send_mail.applescript"
        if not script_path.exists():
            print(f"Warning: AppleScript not found at {script_path}, skipping email")
            return False

        # Build osascript command
        cmd = [
            "osascript",
            str(script_path),
            self.config.to,
            subject,
            body,
        ]

        # Add attachment if configured
        if self.config.attach_report and report_path.exists():
            cmd.append(str(report_path))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                print(f"Email sent to {self.config.to}")
                return True
            else:
                print(f"Warning: Email failed: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print("Warning: Email send timed out")
            return False
        except Exception as e:
            print(f"Warning: Email error: {e}")
            return False

    def _build_body(
        self,
        papers_by_topic: dict[str, list[Paper]],
        report_path: Path,
    ) -> str:
        """Build the email body with a summary of papers found."""
        lines = [
            "LitScout has completed a literature search.",
            "",
            f"Report saved to: {report_path}",
            "",
        ]

        total_papers = sum(len(papers) for papers in papers_by_topic.values())
        lines.append(f"Total new papers found: {total_papers}")
        lines.append("")

        if self.config.include_top_links_in_body and total_papers > 0:
            lines.append("=" * 50)
            lines.append("")

            for topic_name, papers in papers_by_topic.items():
                if not papers:
                    continue

                lines.append(f"## {topic_name}")
                lines.append("")

                for paper in papers:
                    lines.append(f"- {paper.title}")
                    lines.append(f"  {paper.url}")
                    lines.append("")

        return "\n".join(lines)


def create_notifier(email_config: EmailConfig) -> Notifier:
    """Factory function to create the appropriate notifier."""
    if email_config.enabled:
        return MacOSMailNotifier(email_config)
    return NullNotifier()

"""Configuration loader for LitScout."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Raised when configuration is invalid."""

    pass


VALID_SOURCES = {"pubmed", "arxiv", "biorxiv", "medrxiv"}


@dataclass
class Topic:
    """A search topic configuration."""

    name: str
    query: str
    sources: list[str]
    exclude: list[str] = field(default_factory=list)


@dataclass
class EmailConfig:
    """Email notification configuration."""

    enabled: bool = False
    to: str = ""
    subject_prefix: str = "LitScout Report"
    attach_report: bool = True
    include_top_links_in_body: bool = True


@dataclass
class NotificationsConfig:
    """Notifications configuration."""

    email: EmailConfig = field(default_factory=EmailConfig)


@dataclass
class Config:
    """Main configuration for LitScout."""

    output_dir: Path
    top_k_per_topic: int
    initial_lookback_days: int
    topics: list[Topic]
    notifications: NotificationsConfig

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """Load configuration from a YAML file."""
        path = Path(path)

        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML syntax: {e}")

        if not data:
            raise ConfigError("Config file is empty")

        # Validate and parse output_dir
        if "output_dir" not in data:
            raise ConfigError("Missing required field: output_dir")

        output_dir = Path(os.path.expanduser(data["output_dir"]))

        # Validate topics
        if "topics" not in data or not data["topics"]:
            raise ConfigError("No topics defined. Add at least one topic to 'topics' list.")

        topics = []
        for i, t in enumerate(data["topics"]):
            if not isinstance(t, dict):
                raise ConfigError(f"Topic {i + 1}: must be a dictionary")

            if "name" not in t:
                raise ConfigError(f"Topic {i + 1}: missing 'name' field")

            if "query" not in t:
                raise ConfigError(f"Topic '{t['name']}': missing 'query' field")

            sources = t.get("sources", ["pubmed"])
            invalid_sources = set(sources) - VALID_SOURCES
            if invalid_sources:
                raise ConfigError(
                    f"Topic '{t['name']}': invalid source(s): {', '.join(invalid_sources)}. "
                    f"Valid sources: {', '.join(sorted(VALID_SOURCES))}"
                )

            topics.append(
                Topic(
                    name=t["name"],
                    query=t["query"].strip(),
                    sources=sources,
                    exclude=t.get("exclude", []),
                )
            )

        # Validate numeric fields
        top_k = data.get("top_k_per_topic", 5)
        if not isinstance(top_k, int) or top_k < 1:
            raise ConfigError("top_k_per_topic must be a positive integer")

        lookback = data.get("initial_lookback_days", 14)
        if not isinstance(lookback, int) or lookback < 1:
            raise ConfigError("initial_lookback_days must be a positive integer")

        # Parse notifications config (supports both old 'email' and new 'notifications.email')
        notifications_data = data.get("notifications", {})
        email_data = notifications_data.get("email", {})

        # Backwards compatibility: check for top-level 'email' key
        if not email_data and "email" in data:
            email_data = data["email"]

        email = EmailConfig(
            enabled=email_data.get("enabled", False),
            to=email_data.get("to", ""),
            subject_prefix=email_data.get("subject_prefix", "LitScout Report"),
            attach_report=email_data.get("attach_report", True),
            include_top_links_in_body=email_data.get("include_top_links_in_body", True),
        )

        # Warn if email enabled but no recipient
        if email.enabled and not email.to:
            raise ConfigError("Email notifications enabled but 'to' address is empty")

        return cls(
            output_dir=output_dir,
            top_k_per_topic=top_k,
            initial_lookback_days=lookback,
            topics=topics,
            notifications=NotificationsConfig(email=email),
        )

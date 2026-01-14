"""Configuration loader for LitScout."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Raised when configuration is invalid."""

    pass


VALID_SOURCES = {"pubmed", "arxiv", "biorxiv", "medrxiv"}

# Default shows/channels to favor
DEFAULT_PODCAST_SHOWS = [
    "Biotech 2050",
    "Biotech Hangout",
    "Huberman Lab",
    "JAMA Neurology",
    "The Bio Report",
    "The Long Run",
    "Dementia Untangled",
    "The Readout Loud",
    "ECNP Podcast",
]

DEFAULT_YOUTUBE_CHANNELS = [
    "Big Think",
    "Labroots",
    "Recursion",
    "Life Science Connect",
    "Society for Neuroscience",
    "Simons Foundation",
    "Allen Institute",
    "UsAgainstAlzheimer's",
    "European College of Neuropsychopharmacology",
    "HumanBrainProject",
    "Vibe Bio",
    "Institute for Systems Biology",
    "FENS",
    "Cosyne Talks",
    "Brain Space Initiative",
    "Broad Institute",
]

DEFAULT_INTERVIEW_SIGNALS = [
    "interview",
    "conversation",
    "discusses",
    "talks with",
    "speaks with",
    "guest",
    "featuring",
    "with dr",
    "with professor",
]

DEFAULT_SOLO_BLOCK_SIGNALS = [
    "solo episode",
    "my thoughts on",
    "i think",
    "hot take",
    "rant",
    "speculation",
]

DEFAULT_SEMINAR_SIGNALS = [
    "seminar",
    "lecture",
    "webinar",
    "talk",
    "presentation",
    "keynote",
    "symposium",
    "conference",
    "panel",
]


@dataclass
class PodcastConfig:
    """Podcast collection configuration."""

    enabled: bool = True
    n: int = 4
    min_minutes: int = 30
    recency_days: int = 30
    query: str = ""  # Override topic query if set
    allow_shows: list[str] = field(default_factory=list)
    block_shows: list[str] = field(default_factory=list)
    require_interview_signals: list[str] = field(default_factory=list)
    block_solo_signals: list[str] = field(default_factory=list)


@dataclass
class YouTubeConfig:
    """YouTube collection configuration."""

    enabled: bool = True
    n: int = 4
    min_minutes: int = 45
    recency_days: int = 30
    query: str = ""  # Override topic query if set
    allow_channels: list[str] = field(default_factory=list)
    block_channels: list[str] = field(default_factory=list)
    require_title_signals: list[str] = field(default_factory=list)


@dataclass
class MediaConfig:
    """Media collection configuration for a topic."""

    podcasts: PodcastConfig = field(default_factory=PodcastConfig)
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)


@dataclass
class Topic:
    """A search topic configuration."""

    name: str
    query: str
    sources: list[str]
    exclude: list[str] = field(default_factory=list)
    media: MediaConfig = field(default_factory=MediaConfig)


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

            # Parse media config
            media_data = t.get("media", {})
            media_config = _parse_media_config(media_data, t["name"])

            topics.append(
                Topic(
                    name=t["name"],
                    query=t["query"].strip(),
                    sources=sources,
                    exclude=t.get("exclude", []),
                    media=media_config,
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


def _parse_media_config(media_data: dict, topic_name: str) -> MediaConfig:
    """Parse media configuration for a topic."""
    podcasts_data = media_data.get("podcasts", {})
    youtube_data = media_data.get("youtube", {})

    # Handle podcasts: false to disable
    if podcasts_data is False:
        podcasts = PodcastConfig(enabled=False)
    elif isinstance(podcasts_data, dict):
        podcasts = PodcastConfig(
            enabled=podcasts_data.get("enabled", True),
            n=podcasts_data.get("n", 4),
            min_minutes=podcasts_data.get("min_minutes", 30),
            recency_days=podcasts_data.get("recency_days", 30),
            query=podcasts_data.get("query", ""),
            allow_shows=podcasts_data.get("allow_shows", DEFAULT_PODCAST_SHOWS.copy()),
            block_shows=podcasts_data.get("block_shows", []),
            require_interview_signals=podcasts_data.get(
                "require_interview_signals", DEFAULT_INTERVIEW_SIGNALS.copy()
            ),
            block_solo_signals=podcasts_data.get(
                "block_solo_signals", DEFAULT_SOLO_BLOCK_SIGNALS.copy()
            ),
        )
    else:
        podcasts = PodcastConfig(
            allow_shows=DEFAULT_PODCAST_SHOWS.copy(),
            require_interview_signals=DEFAULT_INTERVIEW_SIGNALS.copy(),
            block_solo_signals=DEFAULT_SOLO_BLOCK_SIGNALS.copy(),
        )

    # Handle youtube: false to disable
    if youtube_data is False:
        youtube = YouTubeConfig(enabled=False)
    elif isinstance(youtube_data, dict):
        youtube = YouTubeConfig(
            enabled=youtube_data.get("enabled", True),
            n=youtube_data.get("n", 4),
            min_minutes=youtube_data.get("min_minutes", 45),
            recency_days=youtube_data.get("recency_days", 30),
            query=youtube_data.get("query", ""),
            allow_channels=youtube_data.get("allow_channels", DEFAULT_YOUTUBE_CHANNELS.copy()),
            block_channels=youtube_data.get("block_channels", []),
            require_title_signals=youtube_data.get(
                "require_title_signals", DEFAULT_SEMINAR_SIGNALS.copy()
            ),
        )
    else:
        youtube = YouTubeConfig(
            allow_channels=DEFAULT_YOUTUBE_CHANNELS.copy(),
            require_title_signals=DEFAULT_SEMINAR_SIGNALS.copy(),
        )

    return MediaConfig(podcasts=podcasts, youtube=youtube)

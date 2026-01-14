"""Podcast collector using iTunes Search API and RSS parsing."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus

import feedparser
import requests

from litscout.config import PodcastConfig

logger = logging.getLogger(__name__)


@dataclass
class PodcastEpisode:
    """A podcast episode."""

    id: str
    title: str
    show_name: str
    description: str
    url: str
    audio_url: str
    published_date: str
    duration_minutes: int
    show_artwork_url: Optional[str] = None


def collect_podcasts(
    query: str,
    config: PodcastConfig,
) -> list[PodcastEpisode]:
    """
    Collect podcast episodes matching the query.

    Uses iTunes Search API to find podcasts, then parses their RSS feeds
    to get recent episodes.
    """
    if not config.enabled:
        return []

    # Use config query override if set
    search_query = config.query if config.query else query

    logger.info(f"Searching podcasts for: {search_query}")

    # Search for podcasts via iTunes
    podcasts = _search_itunes_podcasts(search_query, limit=20)

    if not podcasts:
        logger.warning("No podcasts found via iTunes search")
        return []

    logger.info(f"Found {len(podcasts)} podcasts, fetching episodes...")

    # Collect episodes from RSS feeds
    all_episodes: list[PodcastEpisode] = []
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=config.recency_days)

    for podcast in podcasts:
        show_name = podcast.get("collectionName", "")

        # Apply show filters
        if not _show_allowed(show_name, config.allow_shows, config.block_shows):
            continue

        feed_url = podcast.get("feedUrl")
        if not feed_url:
            continue

        episodes = _parse_rss_feed(
            feed_url,
            show_name,
            podcast.get("artworkUrl600"),
            cutoff_date,
            config.min_minutes,
        )

        # Apply signal filters
        for ep in episodes:
            if _passes_signal_filters(
                ep.title,
                ep.description,
                config.require_interview_signals,
                config.block_solo_signals,
            ):
                all_episodes.append(ep)

    # Sort by date (newest first) and return top N
    all_episodes.sort(key=lambda e: e.published_date, reverse=True)

    logger.info(f"Collected {len(all_episodes)} matching episodes, returning top {config.n}")
    return all_episodes[: config.n]


def _search_itunes_podcasts(query: str, limit: int = 20) -> list[dict]:
    """Search iTunes for podcasts matching the query."""
    url = f"https://itunes.apple.com/search?term={quote_plus(query)}&media=podcast&limit={limit}"

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except requests.RequestException as e:
        logger.error(f"iTunes search failed: {e}")
        return []


def _show_allowed(
    show_name: str,
    allow_list: list[str],
    block_list: list[str],
) -> bool:
    """Check if a show passes allow/block filters."""
    show_lower = show_name.lower()

    # Block list takes priority
    for blocked in block_list:
        if blocked.lower() in show_lower:
            return False

    # If allow list is empty, allow all (that aren't blocked)
    if not allow_list:
        return True

    # Check if show matches any allowed name
    for allowed in allow_list:
        if allowed.lower() in show_lower:
            return True

    return False


def _parse_rss_feed(
    feed_url: str,
    show_name: str,
    artwork_url: Optional[str],
    cutoff_date: datetime,
    min_minutes: int,
) -> list[PodcastEpisode]:
    """Parse a podcast RSS feed and return recent episodes."""
    try:
        feed = feedparser.parse(feed_url)
    except Exception as e:
        logger.warning(f"Failed to parse RSS feed {feed_url}: {e}")
        return []

    episodes = []

    for entry in feed.entries:
        # Parse published date
        pub_date = _parse_feed_date(entry)
        if not pub_date or pub_date < cutoff_date:
            continue

        # Parse duration
        duration = _parse_duration(entry)
        if duration < min_minutes:
            continue

        # Get audio URL from enclosures
        audio_url = ""
        for enclosure in entry.get("enclosures", []):
            if "audio" in enclosure.get("type", ""):
                audio_url = enclosure.get("href", "")
                break

        # Create episode
        ep_id = entry.get("id", entry.get("link", f"{show_name}:{entry.get('title', '')}"))

        episodes.append(
            PodcastEpisode(
                id=ep_id,
                title=entry.get("title", "Unknown Title"),
                show_name=show_name,
                description=entry.get("summary", entry.get("description", "")),
                url=entry.get("link", ""),
                audio_url=audio_url,
                published_date=pub_date.strftime("%Y-%m-%d"),
                duration_minutes=duration,
                show_artwork_url=artwork_url,
            )
        )

    return episodes


def _parse_feed_date(entry: dict) -> Optional[datetime]:
    """Parse the publication date from a feed entry."""
    # feedparser usually provides a parsed time tuple
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass

    # Fallback to string parsing
    date_str = entry.get("published", entry.get("pubDate", ""))
    if date_str:
        try:
            # Try common formats
            for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass

    return None


def _parse_duration(entry: dict) -> int:
    """
    Parse episode duration in minutes from RSS entry.

    Handles various formats:
    - itunes:duration as seconds (integer)
    - itunes:duration as HH:MM:SS or MM:SS
    - duration field
    """
    # Check itunes:duration (most common)
    duration_raw = entry.get("itunes_duration", entry.get("duration", ""))

    if not duration_raw:
        return 0

    # If it's already a number (seconds)
    if isinstance(duration_raw, (int, float)):
        return int(duration_raw) // 60

    # Try to parse as integer seconds
    try:
        return int(duration_raw) // 60
    except ValueError:
        pass

    # Parse time format (HH:MM:SS or MM:SS)
    duration_str = str(duration_raw)
    parts = duration_str.split(":")

    try:
        if len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            return hours * 60 + minutes + (1 if seconds >= 30 else 0)
        elif len(parts) == 2:
            minutes, seconds = map(int, parts)
            return minutes + (1 if seconds >= 30 else 0)
        elif len(parts) == 1:
            return int(parts[0]) // 60
    except ValueError:
        pass

    return 0


def _passes_signal_filters(
    title: str,
    description: str,
    require_signals: list[str],
    block_signals: list[str],
) -> bool:
    """Check if episode passes interview/solo signal filters."""
    combined = f"{title} {description}".lower()

    # Check block signals first
    for signal in block_signals:
        if signal.lower() in combined:
            return False

    # If no required signals, pass
    if not require_signals:
        return True

    # Check for at least one required signal
    for signal in require_signals:
        if signal.lower() in combined:
            return True

    return False

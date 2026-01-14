"""YouTube video collector using YouTube Data API v3."""

import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus

import requests

from litscout.config import YouTubeConfig

logger = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


@dataclass
class YouTubeVideo:
    """A YouTube video."""

    id: str
    title: str
    channel_name: str
    description: str
    url: str
    thumbnail_url: str
    published_date: str
    duration_minutes: int
    view_count: Optional[int] = None


def collect_youtube(
    query: str,
    config: YouTubeConfig,
) -> list[YouTubeVideo]:
    """
    Collect YouTube videos matching the query.

    Uses YouTube Data API v3 to search for videos and filter by
    duration, recency, and channel.
    """
    if not config.enabled:
        return []

    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        logger.warning("YOUTUBE_API_KEY not set, skipping YouTube collection")
        return []

    # Use config query override if set
    search_query = config.query if config.query else query

    # Add seminar-related terms to improve search results
    enhanced_query = f"{search_query} (seminar OR lecture OR talk OR webinar)"

    logger.info(f"Searching YouTube for: {search_query}")

    # Calculate date cutoff for API
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=config.recency_days)
    published_after = cutoff_date.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Search for videos
    video_ids = _search_videos(api_key, enhanced_query, published_after, limit=50)

    if not video_ids:
        logger.warning("No YouTube videos found")
        return []

    # Get video details (duration, channel, etc.)
    videos = _get_video_details(api_key, video_ids)

    logger.info(f"Found {len(videos)} videos, applying filters...")

    # Filter videos
    filtered_videos: list[YouTubeVideo] = []

    for video in videos:
        # Duration filter
        if video.duration_minutes < config.min_minutes:
            continue

        # Channel filters
        if not _channel_allowed(video.channel_name, config.allow_channels, config.block_channels):
            continue

        # Title signal filters
        if not _passes_title_signals(video.title, config.require_title_signals):
            continue

        filtered_videos.append(video)

    # Sort by date (newest first) and return top N
    filtered_videos.sort(key=lambda v: v.published_date, reverse=True)

    logger.info(f"Filtered to {len(filtered_videos)} videos, returning top {config.n}")
    return filtered_videos[: config.n]


def _search_videos(
    api_key: str,
    query: str,
    published_after: str,
    limit: int = 50,
) -> list[str]:
    """Search YouTube for videos and return video IDs."""
    url = (
        f"{YOUTUBE_API_BASE}/search"
        f"?part=snippet"
        f"&type=video"
        f"&q={quote_plus(query)}"
        f"&publishedAfter={published_after}"
        f"&maxResults={limit}"
        f"&order=date"
        f"&videoDuration=long"  # Filter for videos > 20 minutes
        f"&key={api_key}"
    )

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        video_ids = []
        for item in data.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if video_id:
                video_ids.append(video_id)

        return video_ids

    except requests.RequestException as e:
        logger.error(f"YouTube search failed: {e}")
        return []


def _get_video_details(api_key: str, video_ids: list[str]) -> list[YouTubeVideo]:
    """Get detailed information for a list of video IDs."""
    if not video_ids:
        return []

    # API accepts up to 50 IDs at once
    ids_str = ",".join(video_ids[:50])

    url = (
        f"{YOUTUBE_API_BASE}/videos"
        f"?part=snippet,contentDetails,statistics"
        f"&id={ids_str}"
        f"&key={api_key}"
    )

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        videos = []
        for item in data.get("items", []):
            video_id = item.get("id")
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            statistics = item.get("statistics", {})

            # Parse duration from ISO 8601 format
            duration_str = content_details.get("duration", "PT0M")
            duration_minutes = _parse_iso8601_duration(duration_str)

            # Parse published date
            published_str = snippet.get("publishedAt", "")
            try:
                published_date = published_str[:10]  # YYYY-MM-DD
            except (TypeError, IndexError):
                published_date = ""

            # Get view count
            view_count = None
            if "viewCount" in statistics:
                try:
                    view_count = int(statistics["viewCount"])
                except (ValueError, TypeError):
                    pass

            videos.append(
                YouTubeVideo(
                    id=video_id,
                    title=snippet.get("title", "Unknown Title"),
                    channel_name=snippet.get("channelTitle", "Unknown Channel"),
                    description=snippet.get("description", ""),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    thumbnail_url=snippet.get("thumbnails", {})
                    .get("high", {})
                    .get("url", ""),
                    published_date=published_date,
                    duration_minutes=duration_minutes,
                    view_count=view_count,
                )
            )

        return videos

    except requests.RequestException as e:
        logger.error(f"YouTube video details request failed: {e}")
        return []


def _parse_iso8601_duration(duration_str: str) -> int:
    """
    Parse ISO 8601 duration format to minutes.

    Examples:
    - PT1H30M15S -> 90
    - PT45M -> 45
    - PT3600S -> 60
    """
    if not duration_str:
        return 0

    # Match hours, minutes, seconds
    hours = 0
    minutes = 0
    seconds = 0

    # Extract hours
    hour_match = re.search(r"(\d+)H", duration_str)
    if hour_match:
        hours = int(hour_match.group(1))

    # Extract minutes
    min_match = re.search(r"(\d+)M", duration_str)
    if min_match:
        minutes = int(min_match.group(1))

    # Extract seconds
    sec_match = re.search(r"(\d+)S", duration_str)
    if sec_match:
        seconds = int(sec_match.group(1))

    # Convert everything to total seconds, then to minutes with rounding
    total_seconds = hours * 3600 + minutes * 60 + seconds
    total_minutes = total_seconds // 60
    remainder = total_seconds % 60
    if remainder >= 30:
        total_minutes += 1

    return total_minutes


def _channel_allowed(
    channel_name: str,
    allow_list: list[str],
    block_list: list[str],
) -> bool:
    """Check if a channel passes allow/block filters."""
    channel_lower = channel_name.lower()

    # Block list takes priority
    for blocked in block_list:
        if blocked.lower() in channel_lower:
            return False

    # If allow list is empty, allow all (that aren't blocked)
    if not allow_list:
        return True

    # Check if channel matches any allowed name
    for allowed in allow_list:
        if allowed.lower() in channel_lower:
            return True

    return False


def _passes_title_signals(title: str, require_signals: list[str]) -> bool:
    """Check if video title contains required signals."""
    if not require_signals:
        return True

    title_lower = title.lower()

    for signal in require_signals:
        if signal.lower() in title_lower:
            return True

    return False

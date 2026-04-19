from __future__ import annotations

from typing import Any, Dict

try:
    from yt_dlp import YoutubeDL
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False


# yt-dlp returns category names; the Kaggle dataset uses numeric IDs.
# Map common category names to YouTube's standard category IDs so the
# fetched video lines up with your benchmark-by-category lookup.
CATEGORY_NAME_TO_ID = {
    "Film & Animation": 1,
    "Autos & Vehicles": 2,
    "Music": 10,
    "Pets & Animals": 15,
    "Sports": 17,
    "Travel & Events": 19,
    "Gaming": 20,
    "People & Blogs": 22,
    "Comedy": 23,
    "Entertainment": 24,
    "News & Politics": 25,
    "Howto & Style": 26,
    "Education": 27,
    "Science & Technology": 28,
    "Nonprofits & Activism": 29,
}


class YouTubeFetchError(Exception):
    pass


def fetch_video_metadata(url: str) -> Dict[str, Any]:
    """
    Fetch public metadata for a YouTube video using yt-dlp.
    No API key required. Raises YouTubeFetchError on failure.
    """
    if not YT_DLP_AVAILABLE:
        raise YouTubeFetchError("yt-dlp is not installed. Run: pip install yt-dlp")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise YouTubeFetchError(f"Failed to fetch video metadata: {e}")

    if not info:
        raise YouTubeFetchError("No metadata returned from YouTube")

    categories = info.get("categories") or []
    category_name = categories[0] if categories else None
    category_id = CATEGORY_NAME_TO_ID.get(category_name, 24)

    upload_date = info.get("upload_date")
    publish_time = None
    if upload_date and len(upload_date) == 8:
        publish_time = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}T00:00:00"

    tags = info.get("tags") or []

    return {
        "youtube_video_id": info.get("id"),
        "title": info.get("title") or "Untitled video",
        "description": info.get("description") or "",
        "views_total": int(info.get("view_count") or 0),
        "likes": int(info.get("like_count") or 0),
        "comments": int(info.get("comment_count") or 0),
        "category_id": category_id,
        "category_name": category_name,
        "publish_time": publish_time,
        "channel": info.get("channel") or info.get("uploader"),
        "channel_id": info.get("channel_id"),
        "duration_seconds": info.get("duration"),
        "thumbnail_url": info.get("thumbnail"),
        "tags": tags[:20],
        "fetch_source": "yt_dlp_public_metadata",
    }
from urllib.parse import urlparse, parse_qs


def extract_video_id(value: str) -> str:
    """
    Extract a YouTube video ID from a URL or return the ID directly.

    Supports:
    - youtube.com/watch?v=...
    - youtu.be/...
    - youtube.com/shorts/...
    """

    value = value.strip()

    # Already a video ID
    if "youtube.com" not in value and "youtu.be" not in value:
        return value

    parsed = urlparse(value)

    # Standard YouTube URL and Shorts
    if parsed.hostname in {
        "www.youtube.com",
        "youtube.com",
        "m.youtube.com",
    }:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v")

            if video_id:
                return video_id[0]

        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1].split("/")[0]

    # Short YouTube URL
    if parsed.hostname == "youtu.be":
        return parsed.path.lstrip("/").split("/")[0]

    raise ValueError(
        f"Could not extract YouTube video ID from: {value}"
    )
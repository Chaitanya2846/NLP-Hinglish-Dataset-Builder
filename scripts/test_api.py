"""Smoke test: is the API key valid and the API enabled?"""

import sys

from utils import execute_with_retry, get_youtube


if len(sys.argv) != 2:
    sys.exit("Usage: python scripts/test_api.py VIDEO_ID")


youtube = get_youtube()

resp = execute_with_retry(
    youtube.videos().list(
        part="snippet",
        id=sys.argv[1],
    )
)

if not resp.get("items"):
    sys.exit(
        "API works, but the video was not found "
        "(wrong ID, private or deleted)."
    )

print(
    "API OK. Title:",
    resp["items"][0]["snippet"]["title"],
)
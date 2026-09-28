"""Print metadata for one video (confirms the video is accessible)."""

import sys
from utils import fetch_video_metadata, get_youtube


if len(sys.argv) != 2:
    sys.exit("Usage: python scripts/get_video_info.py VIDEO_ID")


meta = fetch_video_metadata(get_youtube(), [sys.argv[1]])

if sys.argv[1] not in meta:
    sys.exit("Video not found / not accessible")


m = meta[sys.argv[1]]

print("Title:     ", m["video_title"])
print("Channel:   ", m["channel_title"])
print("Published: ", m["video_published_at"])
print("Views:     ", m["view_count"])
print(
    "Comments:  ",
    m["comment_count"]
    if m["comment_count"] is not None
    else "disabled/unavailable"
)
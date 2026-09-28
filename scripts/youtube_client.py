import os

from dotenv import load_dotenv
from googleapiclient.discovery import build


load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")

if not API_KEY:
    raise RuntimeError("YOUTUBE_API_KEY not found in .env")


def get_youtube_client():
    return build(
        "youtube",
        "v3",
        developerKey=API_KEY,
    )
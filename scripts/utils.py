"""Shared helpers for the Beyond Words YouTube scraper."""

import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import httplib2
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")

RUNS_DIR = ROOT / "data" / "raw" / "runs"
LOGS_DIR = ROOT / "logs"


COLUMNS = [
    "run_id",
    "scraped_at",
    "video_id",
    "video_title",
    "channel_title",
    "category",
    "search_query",
    "comment_id",
    "parent_comment_id",
    "comment_type",
    "text",
    "like_count",
    "reply_count",
    "published_at",
    "updated_at",
]


DEFAULT_CONFIG = {
    "max_comments_per_video": 500,
    "include_replies": False,
    "text_format": "plainText",
    "order": "time",
    "request_delay_seconds": 0.2,
    "max_retries": 5,
    "output_csv": "data/raw/youtube_comments_raw.csv",
    "output_json": "data/raw/youtube_comments_raw.json",
}


RETRYABLE_STATUS = {429, 500, 502, 503, 504}

RETRYABLE_REASONS = {
    "rateLimitExceeded",
    "userRateLimitExceeded",
    "backendError",
    "internalError",
}

QUOTA_REASONS = {
    "quotaExceeded",
    "dailyLimitExceeded",
}


# ---------- exceptions ----------

class ScraperError(Exception):
    pass


class QuotaExceededError(ScraperError):
    pass


class CommentsDisabledError(ScraperError):
    pass


class NotFoundError(ScraperError):
    pass


class ApiError(ScraperError):
    def __init__(self, status, reason):
        super().__init__(f"HTTP {status} / {reason}")
        self.status = status
        self.reason = reason


# ---------- basics ----------

def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_run_id():
    return datetime.now().strftime("run_%Y%m%d_%H%M%S")


def load_json(path, default=None):
    path = Path(path)

    if not path.exists():
        return default

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json_atomic(path, obj):
    """Write JSON atomically so a crash doesn't leave a half-written file."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(path.suffix + ".tmp")

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(
            obj,
            f,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(tmp, path)


def load_config():
    cfg = dict(DEFAULT_CONFIG)

    config_path = ROOT / "config" / "scraper_config.json"

    cfg.update(load_json(config_path, {}) or {})

    return cfg


def setup_logging(name="scraper", level=logging.INFO):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        LOGS_DIR / "scraper.log",
        encoding="utf-8",
    )

    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


# ---------- API ----------

def get_youtube():
    key = os.getenv("YOUTUBE_API_KEY")

    if not key:
        raise RuntimeError(
            "YOUTUBE_API_KEY is missing (check your .env file)"
        )

    return build(
        "youtube",
        "v3",
        developerKey=key,
        cache_discovery=False,
    )


def error_reason(err):
    """Extract the machine-readable reason from an HttpError."""

    try:
        data = json.loads(err.content.decode("utf-8"))

        return data["error"]["errors"][0]["reason"]

    except Exception:
        return "unknown"


def execute_with_retry(request, max_retries=5, base_delay=1.0):
    """
    Execute an API request.

    Retries transient failures using exponential backoff + jitter.
    """

    for attempt in range(max_retries + 1):

        try:
            return request.execute()

        except HttpError as e:

            status = e.resp.status
            reason = error_reason(e)

            if reason in QUOTA_REASONS:
                raise QuotaExceededError(reason) from e

            if reason == "commentsDisabled":
                raise CommentsDisabledError(reason) from e

            if status == 404:
                raise NotFoundError(reason) from e

            retryable = (
                status in RETRYABLE_STATUS
                or reason in RETRYABLE_REASONS
            )

            if not retryable or attempt == max_retries:
                raise ApiError(status, reason) from e

        except (
            httplib2.HttpLib2Error,
            ConnectionError,
            TimeoutError,
            OSError,
        ) as e:

            if attempt == max_retries:
                raise ApiError(
                    0,
                    type(e).__name__,
                ) from e

        time.sleep(
            base_delay * (2 ** attempt)
            + random.uniform(0, 1)
        )


def fetch_video_metadata(
    youtube,
    video_ids,
    max_retries=5,
):
    """
    Return:

        {
            video_id: metadata
        }

    Missing/private/deleted/invalid IDs are absent.
    """

    meta = {}

    for i in range(0, len(video_ids), 50):

        chunk = video_ids[i:i + 50]

        response = execute_with_retry(
            youtube.videos().list(
                part="snippet,statistics",
                id=",".join(chunk),
            ),
            max_retries,
        )

        for item in response.get("items", []):

            snippet = item["snippet"]
            statistics = item.get("statistics", {})

            meta[item["id"]] = {
                "video_id": item["id"],
                "video_title": snippet.get("title", ""),
                "channel_title": snippet.get(
                    "channelTitle",
                    "",
                ),
                "video_published_at": snippet.get(
                    "publishedAt",
                    "",
                ),
                "view_count": int(
                    statistics.get("viewCount", 0)
                ),
                "comment_count": (
                    int(statistics["commentCount"])
                    if "commentCount" in statistics
                    else None
                ),
            }

    return meta


# ---------- storage ----------

def load_seen_ids(directory=RUNS_DIR):
    """
    Load every comment_id already stored in JSONL run files.

    A truncated final line caused by a crash is ignored.
    """

    seen = set()

    directory = Path(directory)

    if not directory.exists():
        return seen

    for path in directory.glob("*.jsonl"):

        with open(path, encoding="utf-8") as f:

            for line in f:

                try:
                    seen.add(
                        json.loads(line)["comment_id"]
                    )

                except (json.JSONDecodeError, KeyError):
                    continue

    return seen
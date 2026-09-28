"""Scrape every video in config/videos.json with resume support.

Statuses per video:
    completed | comments_disabled | not_found | failed | in_progress

Re-running with the SAME --run-id skips finished videos
and resumes in_progress ones.
"""

import argparse

import pandas as pd
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from scrape_video import scrape_video

from utils import (
    LOGS_DIR,
    ROOT,
    RUNS_DIR,
    ApiError,
    CommentsDisabledError,
    NotFoundError,
    QuotaExceededError,
    fetch_video_metadata,
    get_youtube,
    load_config,
    load_json,
    load_seen_ids,
    new_run_id,
    save_json_atomic,
    setup_logging,
    utc_now_iso,
)


TERMINAL = {
    "completed",
    "comments_disabled",
    "not_found",
}


def main():

    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--run-id",
        default=None,
        help="reuse an existing run id to resume",
    )

    ap.add_argument(
        "--max-videos",
        type=int,
        default=None,
        help="only process the first N videos",
    )

    ap.add_argument(
        "--retry-failed",
        action="store_true",
        help="also retry videos marked 'failed'",
    )

    args = ap.parse_args()

    cfg = load_config()

    log = setup_logging()

    youtube = get_youtube()

    videos_cfg = load_json(
        ROOT / "config" / "videos.json",
        {},
    ).get(
        "videos",
        [],
    )

    # Remove duplicate video IDs.
    unique = []
    seen_video_ids = set()

    for v in videos_cfg:

        if v["video_id"] not in seen_video_ids:

            seen_video_ids.add(
                v["video_id"]
            )

            unique.append(v)

    if args.max_videos:
        unique = unique[
            : args.max_videos
        ]

    if not unique:
        raise SystemExit(
            "config/videos.json contains no videos"
        )

    run_id = (
        args.run_id
        or new_run_id()
    )

    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    out_path = (
        RUNS_DIR
        / f"{run_id}.jsonl"
    )

    status_path = (
        LOGS_DIR
        / f"status_{run_id}.json"
    )

    status = load_json(
        status_path,
        {},
    ) or {}

    seen_ids = load_seen_ids()

    def save():
        save_json_atomic(
            status_path,
            status,
        )

    log.info(
        "RUN %s | %d videos | replies=%s | max/video=%s",
        run_id,
        len(unique),
        cfg["include_replies"],
        cfg["max_comments_per_video"],
    )

    # Fetch metadata for all videos first.
    meta = fetch_video_metadata(
        youtube,
        [v["video_id"] for v in unique],
        cfg["max_retries"],
    )

    # Save metadata snapshot.
    meta_rows = [
        {
            **meta[v["video_id"]],
            "category": v.get(
                "category",
                "",
            ),
        }
        for v in unique
        if v["video_id"] in meta
    ]

    if meta_rows:

        meta_path = (
            ROOT
            / "data"
            / "metadata"
            / "videos_metadata.csv"
        )

        meta_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        pd.DataFrame(
            meta_rows
        ).to_csv(
            meta_path,
            index=False,
            encoding="utf-8-sig",
        )

    quota_hit = False

    with logging_redirect_tqdm():

        for entry in tqdm(
            unique,
            desc="videos",
        ):

            vid = entry["video_id"]

            state = status.setdefault(
                vid,
                {},
            )

            prev = state.get(
                "status"
            )

            # Skip videos already completed.
            if (
                prev in TERMINAL
                or (
                    prev == "failed"
                    and not args.retry_failed
                )
            ):

                log.info(
                    "SKIP %s (%s)",
                    vid,
                    prev,
                )

                continue

            m = meta.get(vid)

            # Video doesn't exist / inaccessible.
            if m is None:

                state.update(
                    status="not_found",
                    comments=0,
                    updated_at=utc_now_iso(),
                )

                log.warning(
                    "%s → not found / private / deleted",
                    vid,
                )

                save()

                continue

            state["video_title"] = (
                m["video_title"]
            )

            # Comments disabled.
            if m["comment_count"] is None:

                state.update(
                    status="comments_disabled",
                    comments=0,
                    updated_at=utc_now_iso(),
                )

                log.warning(
                    "%s → comments unavailable (pre-check)",
                    vid,
                )

                save()

                continue

            video = {
                **entry,
                **m,
            }

            try:

                scrape_video(
                    youtube,
                    video,
                    cfg,
                    run_id,
                    out_path,
                    seen_ids,
                    state,
                    log,
                    save_state=save,
                )

            except QuotaExceededError:

                state["status"] = (
                    "in_progress"
                )

                save()

                log.error(
                    "QUOTA EXCEEDED at %s. "
                    "Resume with --run-id %s",
                    vid,
                    run_id,
                )

                quota_hit = True

                break

            except CommentsDisabledError:

                state.update(
                    status="comments_disabled",
                    updated_at=utc_now_iso(),
                )

                log.warning(
                    "%s → comments disabled",
                    vid,
                )

            except NotFoundError:

                state.update(
                    status="not_found",
                    updated_at=utc_now_iso(),
                )

                log.warning(
                    "%s → not found",
                    vid,
                )

            except ApiError as e:

                state.update(
                    status="failed",
                    error=str(e),
                    updated_at=utc_now_iso(),
                )

                log.error(
                    "%s → API error: %s",
                    vid,
                    e,
                )

            except Exception as e:

                # One failed video should not stop the whole run.
                state.update(
                    status="failed",
                    error=repr(e),
                    updated_at=utc_now_iso(),
                )

                log.exception(
                    "%s → unexpected error",
                    vid,
                )

            save()

    # -------------------------
    # Summary
    # -------------------------

    counts = {}

    for st in status.values():

        key = st.get(
            "status",
            "unknown",
        )

        counts[key] = (
            counts.get(key, 0)
            + 1
        )

    total = sum(
        st.get(
            "comments",
            0,
        )
        for st in status.values()
    )

    log.info(
        "SUMMARY %s | videos=%d | statuses=%s | comments=%d",
        run_id,
        len(status),
        counts,
        total,
    )

    print(
        f"\nRun: {run_id}"
        f"\nStatuses: {counts}"
        f"\nComments this run: {total}"
    )

    if quota_hit:

        print(
            "Quota exhausted. Resume later: "
            f"python scripts/scrape_multiple_videos.py "
            f"--run-id {run_id}"
        )

    print(
        "Next: python scripts/consolidate.py"
    )


if __name__ == "__main__":
    main()
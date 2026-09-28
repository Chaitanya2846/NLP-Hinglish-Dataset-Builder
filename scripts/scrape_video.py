"""Scrape all (or up to a limit of) comments for one video.

Design:
    - one page at a time, rows appended to a JSONL file after every page
    - comment_id de-duplication via seen_ids
    - progress (comments, pages, next_page_token) kept in state for resume
"""

import argparse
import json
import time

from utils import (
    RUNS_DIR,
    ApiError,
    execute_with_retry,
    fetch_video_metadata,
    get_youtube,
    load_config,
    load_seen_ids,
    new_run_id,
    setup_logging,
    utc_now_iso,
)


def build_row(resource, video, comment_type, run_id, reply_count=None):
    """Convert an API comment resource into one raw record."""

    s = resource["snippet"]

    return {
        "run_id": run_id,
        "scraped_at": utc_now_iso(),
        "video_id": video["video_id"],
        "video_title": video.get("video_title", ""),
        "channel_title": video.get("channel_title", ""),
        "category": video.get("category", ""),
        "search_query": video.get("search_query", ""),
        "comment_id": resource["id"],
        "parent_comment_id": s.get("parentId", ""),
        "comment_type": comment_type,
        "text": s.get("textDisplay", ""),
        "like_count": s.get("likeCount", 0),
        "reply_count": "" if reply_count is None else reply_count,
        "published_at": s.get("publishedAt", ""),
        "updated_at": s.get("updatedAt", ""),
    }


def fetch_replies(youtube, parent_id, cfg):
    """Yield every reply of a top-level comment."""

    token = None

    while True:
        resp = execute_with_retry(
            youtube.comments().list(
                part="snippet",
                parentId=parent_id,
                maxResults=100,
                pageToken=token,
                textFormat=cfg["text_format"],
            ),
            cfg["max_retries"],
        )

        yield from resp.get("items", [])

        token = resp.get("nextPageToken")

        if not token:
            return

        time.sleep(cfg["request_delay_seconds"])


def scrape_video(
    youtube,
    video,
    cfg,
    run_id,
    out_path,
    seen_ids,
    state,
    log,
    save_state=None,
):
    """Scrape one video and update its progress state."""

    vid = video["video_id"]

    max_comments = cfg.get("max_comments_per_video") or None
    include_replies = cfg["include_replies"]

    collected = state.get("comments", 0)
    pages = state.get("pages", 0)
    page_token = state.get("next_page_token")

    resumed_with_token = page_token is not None

    state["status"] = "in_progress"

    limit_hit = False

    log.info(
        "START %s | %s | resume_token=%s",
        vid,
        video.get("video_title", ""),
        resumed_with_token,
    )

    with open(out_path, "a", encoding="utf-8") as out:

        while True:

            try:
                resp = execute_with_retry(
                    youtube.commentThreads().list(
                        part="snippet,replies"
                        if include_replies
                        else "snippet",
                        videoId=vid,
                        maxResults=100,
                        order=cfg["order"],
                        pageToken=page_token,
                        textFormat=cfg["text_format"],
                    ),
                    cfg["max_retries"],
                )

            except ApiError as e:

                # Restart if the saved page token is no longer valid.
                if page_token and e.status == 400:

                    log.warning(
                        "%s: page token rejected (%s); restarting video",
                        vid,
                        e,
                    )

                    page_token = None
                    continue

                raise

            new_rows = []

            for thread in resp.get("items", []):

                top = thread["snippet"]["topLevelComment"]

                total_replies = thread["snippet"].get(
                    "totalReplyCount",
                    0,
                )

                candidates = [
                    (
                        top,
                        "top_level",
                        total_replies,
                    )
                ]

                if include_replies and total_replies:

                    inline = (
                        thread
                        .get("replies", {})
                        .get("comments", [])
                    )

                    replies = (
                        inline
                        if len(inline) >= total_replies
                        else list(
                            fetch_replies(
                                youtube,
                                top["id"],
                                cfg,
                            )
                        )
                    )

                    candidates += [
                        (r, "reply", None)
                        for r in replies
                    ]

                for resource, ctype, rc in candidates:

                    if resource["id"] in seen_ids:
                        continue

                    if (
                        max_comments
                        and collected + len(new_rows)
                        >= max_comments
                    ):
                        limit_hit = True
                        break

                    seen_ids.add(resource["id"])

                    new_rows.append(
                        build_row(
                            resource,
                            video,
                            ctype,
                            run_id,
                            rc,
                        )
                    )

                if limit_hit:
                    break

            # Write the page before saving progress.
            for row in new_rows:
                out.write(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                    )
                    + "\n"
                )

            out.flush()

            collected += len(new_rows)
            pages += 1

            page_token = (
                None
                if limit_hit
                else resp.get("nextPageToken")
            )

            state.update(
                comments=collected,
                pages=pages,
                next_page_token=page_token,
                updated_at=utc_now_iso(),
            )

            if save_state:
                save_state()

            log.info(
                "%s page %d: +%d (total %d)",
                vid,
                pages,
                len(new_rows),
                collected,
            )

            if limit_hit or not page_token:
                break

            time.sleep(
                cfg["request_delay_seconds"]
            )

    state["status"] = "completed"

    state["stopped_reason"] = (
        "limit_reached"
        if limit_hit
        else "all_pages"
    )

    state["next_page_token"] = None

    if save_state:
        save_state()

    log.info(
        "DONE %s → %d comments in %d pages (%s)",
        vid,
        collected,
        pages,
        state["stopped_reason"],
    )

    return state


def main():

    ap = argparse.ArgumentParser(
        description="Scrape comments for a single video"
    )

    ap.add_argument(
        "video_id"
    )

    ap.add_argument(
        "--category",
        default="",
    )

    ap.add_argument(
        "--max-comments",
        type=int,
        default=None,
    )

    ap.add_argument(
        "--include-replies",
        action="store_true",
    )

    ap.add_argument(
        "--run-id",
        default=None,
    )

    args = ap.parse_args()

    cfg = load_config()

    if args.max_comments is not None:
        cfg["max_comments_per_video"] = (
            args.max_comments
        )

    log = setup_logging()

    youtube = get_youtube()

    meta = fetch_video_metadata(
        youtube,
        [args.video_id],
        cfg["max_retries"],
    )

    if args.video_id not in meta:
        raise SystemExit(
            "Video not found / not accessible"
        )

    video = {
        **meta[args.video_id],
        "category": args.category,
    }

    run_id = args.run_id or new_run_id()

    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    out_path = (
        RUNS_DIR
        / f"{run_id}.jsonl"
    )

    state = {}

    scrape_video(
        youtube,
        video,
        cfg,
        run_id,
        out_path,
        load_seen_ids(),
        state,
        log,
    )

    print(
        f"Collected {state['comments']} comments "
        f"→ {out_path}"
    )


if __name__ == "__main__":
    main()


from scripts.extract_video import extract_video_id

from scripts.utils import (
    RUNS_DIR,
    fetch_video_metadata,
    get_youtube,
    load_config,
    load_seen_ids,
    new_run_id,
    setup_logging,
)

from scripts.scrape_video import scrape_video


def scrape_from_url(url):
    """
    Scrape comments from a YouTube URL
    using the existing scrape_video() function.
    """

    # 1. Extract video ID
    video_id = extract_video_id(url)

    print(f"Video ID: {video_id}")

    # 2. Load existing configuration
    cfg = load_config()

    # 3. Setup YouTube API
    youtube = get_youtube()

    # 4. Get video metadata
    meta = fetch_video_metadata(
        youtube,
        [video_id],
        cfg["max_retries"],
    )

    if video_id not in meta:
        raise ValueError(
            "Video not found or not accessible."
        )

    # 5. Build video object
    video = {
        **meta[video_id],
        "category": "",
        "search_query": "",
    }

    # 6. Create run
    run_id = new_run_id()

    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    out_path = (
        RUNS_DIR
        / f"{run_id}.jsonl"
    )

    # 7. Logging
    log = setup_logging()

    # 8. Initial state
    state = {}

    # 9. Run existing scraper
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

    return {
        "video_id": video_id,
        "video_title": video.get("video_title", ""),
        "comments": state.get("comments", 0),
        "run_id": run_id,
        "output_path": str(out_path),
    }


if __name__ == "__main__":

    url = input(
        "Enter YouTube video URL: "
    ).strip()

    try:

        result = scrape_from_url(url)

        print("\nScraping completed!")
        print(
            f"Video: {result['video_title']}"
        )
        print(
            f"Comments: {result['comments']}"
        )
        print(
            f"Output: {result['output_path']}"
        )

    except Exception as e:

        print(
            f"\nError: {e}"
        )
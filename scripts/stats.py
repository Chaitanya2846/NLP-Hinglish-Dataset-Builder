"""Collection statistics (scraping only)."""

import json
import pandas as pd
from utils import LOGS_DIR, ROOT, load_config, load_json, save_json_atomic


def main():
    cfg = load_config()

    df = pd.read_csv(
        ROOT / cfg["output_csv"],
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig"
    )

    status = {}

    for p in sorted(LOGS_DIR.glob("status_*.json")):
        status.update(load_json(p, {}) or {})

    by_status = {}

    for st in status.values():
        k = st.get("status", "unknown")
        by_status[k] = by_status.get(k, 0) + 1

    videos_with_comments = df["video_id"].nunique()

    stats = {
        "videos_attempted": len(status),
        "videos_by_status": by_status,
        "videos_with_comments": int(videos_with_comments),
        "total_comments": int(len(df)),
        "top_level_comments": int(
            (df["comment_type"] == "top_level").sum()
        ),
        "replies": int(
            (df["comment_type"] == "reply").sum()
        ),
        "avg_comments_per_video": round(
            len(df) / max(videos_with_comments, 1),
            1
        ),
        "comments_by_category": (
            df.groupby("category").size().to_dict()
        ),
        "earliest_comment": df["published_at"].min(),
        "latest_comment": df["published_at"].max(),
        "runs": sorted(df["run_id"].unique().tolist()),
    }

    save_json_atomic(
        ROOT / "data" / "raw" / "collection_stats.json",
        stats
    )

    print(
        json.dumps(
            stats,
            indent=2,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
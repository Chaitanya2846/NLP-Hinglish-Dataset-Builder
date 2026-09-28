"""Merge all data/raw/runs/*.jsonl → de-duplicated CSV (+ JSON)."""

import json
import pandas as pd
from utils import COLUMNS, ROOT, RUNS_DIR, load_config


def main():
    cfg = load_config()

    rows, bad = [], 0

    for path in sorted(RUNS_DIR.glob("*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    bad += 1

    if not rows:
        raise SystemExit("No rows found in data/raw/runs/")

    df = pd.DataFrame(rows, columns=COLUMNS)

    before = len(df)

    df = df.drop_duplicates(
        subset=["comment_id"],
        keep="first"
    )

    df = df.sort_values(
        ["video_id", "published_at", "comment_id"]
    ).reset_index(drop=True)

    csv_path = ROOT / cfg["output_csv"]

    csv_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    df.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig"
    )

    if cfg.get("output_json"):
        df.to_json(
            ROOT / cfg["output_json"],
            orient="records",
            force_ascii=False,
            indent=2
        )

    print(
        f"Read {before} rows | "
        f"dropped {before - len(df)} duplicates | "
        f"skipped {bad} corrupt lines | "
        f"wrote {len(df)} rows → {csv_path}"
    )


if __name__ == "__main__":
    main()
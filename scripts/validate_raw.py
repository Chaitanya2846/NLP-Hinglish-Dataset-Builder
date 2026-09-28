"""Integrity checks for data/raw/youtube_comments_raw.csv."""

import sys
import pandas as pd
from utils import COLUMNS, ROOT, load_config


def main():
    csv_path = ROOT / load_config()["output_csv"]

    df = pd.read_csv(
        csv_path,
        dtype=str,
        keep_default_na=False,
        encoding="utf-8-sig"
    )

    errors, warnings = [], []

    # Check required columns
    missing = [c for c in COLUMNS if c not in df.columns]

    if missing:
        errors.append(f"missing columns: {missing}")

    # Check duplicate comment IDs
    if "comment_id" in df:
        dups = int(df["comment_id"].duplicated().sum())

        if dups:
            errors.append(f"{dups} duplicate comment_id values")

    # Check empty required fields
    for col in [
        "video_id",
        "comment_id",
        "published_at",
        "scraped_at",
        "comment_type"
    ]:
        if col in df:
            n = int((df[col].str.strip() == "").sum())

            if n:
                errors.append(f"{n} rows with empty {col}")

    # Check text
    if "text" in df:
        n_empty = int(
            (df["text"].str.strip() == "").sum()
        )

        if n_empty:
            warnings.append(
                f"{n_empty} rows with empty text "
                "(emoji-only/stripped comments are possible)"
            )

        mojibake = int(
            df["text"].str.contains(
                "Ã|â€|\ufffd",
                regex=True
            ).sum()
        )

        if mojibake:
            errors.append(
                f"{mojibake} rows look like encoding damage "
                "(mojibake / U+FFFD)"
            )

    # Basic statistics
    print(
        f"Rows: {len(df)} | "
        f"videos: {df['video_id'].nunique() if 'video_id' in df else '?'}"
    )

    if "text" in df:
        print(
            "Rows with Devanagari characters:",
            int(
                df["text"].str.contains(
                    r"[\u0900-\u097F]",
                    regex=True
                ).sum()
            )
        )

        print(
            "Rows with emoji:",
            int(
                df["text"].str.contains(
                    r"[\U0001F300-\U0001FAFF]",
                    regex=True
                ).sum()
            )
        )

        print(
            "Rows containing a newline:",
            int(
                df["text"].str.contains("\n").sum()
            )
        )

    # Print warnings
    for w in warnings:
        print("WARNING:", w)

    # Print errors
    for e in errors:
        print("ERROR:  ", e)

    if errors:
        sys.exit(1)

    print("Validation passed.")


if __name__ == "__main__":
    main()
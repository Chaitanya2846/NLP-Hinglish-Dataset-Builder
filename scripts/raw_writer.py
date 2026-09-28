import json
from pathlib import Path

import pandas as pd

from schema import RAW_COLUMNS


def write_json(rows, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            rows,
            f,
            ensure_ascii=False,
            indent=2,
        )


def write_csv(rows, output_path):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(rows, columns=RAW_COLUMNS)

    df.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )


def read_raw_csv(input_path):
    return pd.read_csv(
        input_path,
        encoding="utf-8-sig",
        keep_default_na=False,
    )
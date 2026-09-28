import json


def read_scraped_comments(file_path):
    """Read scraped JSONL comments into a list of dictionaries."""

    comments = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            comments.append(json.loads(line))

    return comments


if __name__ == "__main__":
    print("This module is meant to be imported.")
from raw_writer import write_json, write_csv, read_raw_csv


def test_raw_text_is_preserved(tmp_path):
    rows = [
        {
            "run_id": "test-run",
            "scraped_at": "2026-09-28T12:00:00Z",
            "video_id": "ABC123",
            "video_title": "Test Video",
            "channel_title": "Test Channel",
            "category": "college",
            "search_query": "",
            "comment_id": "COMMENT123",
            "parent_comment_id": "",
            "comment_type": "top_level",
            "text": "Brooooo ye kyaaa hai 😂",
            "like_count": 5,
            "reply_count": 2,
            "published_at": "2026-09-28T11:00:00Z",
            "updated_at": "2026-09-28T11:00:00Z",
        }
    ]

    json_path = tmp_path / "comments.json"
    csv_path = tmp_path / "comments.csv"

    write_json(rows, json_path)
    write_csv(rows, csv_path)

    loaded = read_raw_csv(csv_path)

    assert loaded.iloc[0]["text"] == "Brooooo ye kyaaa hai 😂"
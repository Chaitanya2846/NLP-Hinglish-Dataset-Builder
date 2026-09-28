from video_utils import extract_video_id


def test_standard_youtube_url():
    assert (
        extract_video_id("https://www.youtube.com/watch?v=ABC123")
        == "ABC123"
    )


def test_youtu_be_url():
    assert (
        extract_video_id("https://youtu.be/ABC123")
        == "ABC123"
    )


def test_shorts_url():
    assert (
        extract_video_id("https://www.youtube.com/shorts/ABC123")
        == "ABC123"
    )


def test_raw_video_id():
    assert extract_video_id("ABC123") == "ABC123"
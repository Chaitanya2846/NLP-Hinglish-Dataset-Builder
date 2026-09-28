from urllib.parse import urlparse, parse_qs


def extract_video_id(url):
    url = url.strip()
    parsed = urlparse(url)

    # youtube.com/watch?v=...
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        query = parse_qs(parsed.query)

        if "v" in query:
            return query["v"][0]

        # youtube.com/shorts/...
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[1].split("/")[0]

    # youtu.be/...
    if parsed.hostname == "youtu.be":
        return parsed.path.strip("/").split("/")[0]

    raise ValueError("Invalid YouTube URL")


if __name__ == "__main__":

    test_urls = [
        "https://www.youtube.com/watch?v=CMK2cf_d1TU",
        "https://youtu.be/CMK2cf_d1TU",
        "https://www.youtube.com/shorts/CMK2cf_d1TU",
    ]

    for url in test_urls:
        print(url)
        print("Video ID:", extract_video_id(url))
        print()
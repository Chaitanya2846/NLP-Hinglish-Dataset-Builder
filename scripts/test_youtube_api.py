from youtube_client import get_youtube_client


youtube = get_youtube_client()

response = youtube.videos().list(
    part="snippet,statistics",
    id="dQw4w9WgXcQ",
).execute()

if response.get("items"):
    video = response["items"][0]

    print("API connection successful!")
    print("Video ID:", video["id"])
    print("Title:", video["snippet"]["title"])
    print("Channel:", video["snippet"]["channelTitle"])
    print("Statistics:", video.get("statistics", {}))
else:
    print("Video not found.")
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
import os
import json
import urllib.request
import re
from datetime import date

app = FastAPI()

SITE_URL = "https://ytdecode.vercel.app"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_transcript(video_id):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        # Try English first
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            return ' '.join([t['text'] for t in transcript_list])
        except:
            pass
        # Try any available language
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        for transcript in transcripts:
            try:
                data = transcript.fetch()
                return ' '.join([t['text'] for t in data])
            except:
                continue
        return None
    except Exception as e:
        return None

def get_video_info(video_id):
    """Get title and other info by fetching YouTube page"""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        with urllib.request.urlopen(req, timeout=10) as res:
            html = res.read().decode('utf-8', errors='ignore')

        # Extract title
        title = ""
        title_match = re.search(r'"title":"([^"]+)"', html)
        if title_match:
            title = title_match.group(1).encode().decode('unicode_escape') if '\\u' in title_match.group(1) else title_match.group(1)

        if not title:
            title_match = re.search(r'<title>(.+?) - YouTube</title>', html)
            if title_match:
                title = title_match.group(1)

        # Extract description
        description = ""
        desc_match = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)\"', html)
        if desc_match:
            desc_raw = desc_match.group(1)
            description = desc_raw.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')

        # Extract view count
        views = 0
        views_match = re.search(r'"viewCount":"(\d+)"', html)
        if views_match:
            views = int(views_match.group(1))

        # Extract channel name
        channel = ""
        channel_match = re.search(r'"channelName":"([^"]+)"', html)
        if not channel_match:
            channel_match = re.search(r'"ownerChannelName":"([^"]+)"', html)
        if channel_match:
            channel = channel_match.group(1)

        # Extract publish date
        published = ""
        date_match = re.search(r'"publishDate":"([^"]+)"', html)
        if date_match:
            published = date_match.group(1)[:10]

        # Extract tags
        tags = []
        tags_match = re.search(r'"keywords":\[([^\]]+)\]', html)
        if tags_match:
            tags_str = tags_match.group(1)
            tags = re.findall(r'"([^"]+)"', tags_str)

        # Extract duration
        duration = ""
        dur_match = re.search(r'"lengthSeconds":"(\d+)"', html)
        if dur_match:
            secs = int(dur_match.group(1))
            h = secs // 3600
            m = (secs % 3600) // 60
            s = secs % 60
            if h:
                duration = f"{h}h {m}m {s}s"
            else:
                duration = f"{m}m {s}s"

        # Extract likes
        likes = 0
        likes_match = re.search(r'"label":"([\d,]+) likes"', html)
        if likes_match:
            likes = int(likes_match.group(1).replace(',', ''))

        return {
            "title": title or "Title not available",
            "description": description or "",
            "views": views,
            "likes": likes,
            "channel": channel or "",
            "published": published or "",
            "duration": duration or "",
            "tags": tags,
        }
    except Exception as e:
        return {
            "title": "Title not available",
            "description": "",
            "views": 0,
            "likes": 0,
            "channel": "",
            "published": "",
            "duration": "",
            "tags": [],
        }

def get_thumbnails(video_id):
    thumbnails = []
    quality_map = [
        ("maxresdefault", "Max Resolution", 1280, 720),
        ("sddefault", "Standard", 640, 480),
        ("hqdefault", "High", 480, 360),
        ("mqdefault", "Medium", 320, 180),
        ("default", "Default", 120, 90),
    ]
    for filename, label, w, h in quality_map:
        url = f"https://i.ytimg.com/vi/{video_id}/{filename}.jpg"
        thumbnails.append({
            "quality": label,
            "url": url,
            "width": w,
            "height": h
        })
    return thumbnails

@app.get("/", response_class=HTMLResponse)
def home():
    path = os.path.join(BASE_DIR, "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return PlainTextResponse(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n"
    )

@app.get("/sitemap.xml")
def sitemap_xml():
    today = date.today().isoformat()
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{SITE_URL}/</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>
</urlset>'''
    return Response(content=xml, media_type="application/xml")

@app.post("/api/analyze")
async def analyze(request: Request):
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid request.")

    video_id = body.get("video_id", "").strip()
    if not video_id:
        raise HTTPException(status_code=400, detail="Video ID is required.")

    # Get video info by scraping YouTube page
    info = get_video_info(video_id)

    # Get transcript
    transcript = get_transcript(video_id)

    # Get thumbnails
    thumbnails = get_thumbnails(video_id)
    thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    return {
        "video_id": video_id,
        "title": info["title"],
        "description": info["description"],
        "tags": info["tags"],
        "views": info["views"],
        "likes": info["likes"],
        "comments": 0,
        "published": info["published"],
        "duration": info["duration"],
        "channel": info["channel"],
        "thumbnail_url": thumbnail_url,
        "thumbnails": thumbnails,
        "transcript": transcript or "Transcript not available for this video (captions may be disabled).",
    }

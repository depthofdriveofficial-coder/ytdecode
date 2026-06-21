from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.middleware.gzip import GZipMiddleware
import os
import json
import urllib.request
import urllib.parse
import re
from datetime import date

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=500)

SITE_URL = "https://ytdecode.vercel.app"
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def youtube_request(endpoint, params):
    params['key'] = YOUTUBE_API_KEY
    query = urllib.parse.urlencode(params)
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?{query}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(status_code=e.code, detail=f"YouTube API error: {e.read().decode()}")

def get_transcript(video_id):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join([t['text'] for t in transcript_list])
    except Exception:
        return None

def format_duration(iso_duration):
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration or '')
    if not match:
        return 'N/A'
    h, m, s = match.groups()
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s: parts.append(f"{s}s")
    return ' '.join(parts) or 'N/A'

def format_date(date_str):
    if not date_str:
        return 'N/A'
    return date_str[:10]

@app.get("/", response_class=HTMLResponse)
def home():
    path = os.path.join(BASE_DIR, "index.html")
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    headers = {"Cache-Control": "public, max-age=0, s-maxage=3600, stale-while-revalidate=86400"}
    return HTMLResponse(content=html, headers=headers)

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    content = (
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n"
    )
    return PlainTextResponse(content=content, headers={"Cache-Control": "public, max-age=86400"})

@app.get("/sitemap.xml")
def sitemap_xml():
    today = date.today().isoformat()
    urls = [
        {"loc": f"{SITE_URL}/", "lastmod": today, "changefreq": "weekly", "priority": "1.0"},
    ]
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        parts.append(
            f"  <url><loc>{u['loc']}</loc><lastmod>{u['lastmod']}</lastmod>"
            f"<changefreq>{u['changefreq']}</changefreq><priority>{u['priority']}</priority></url>"
        )
    parts.append("</urlset>")
    xml = "\n".join(parts)
    return Response(content=xml, media_type="application/xml",
                    headers={"Cache-Control": "public, max-age=86400"})

@app.post("/api/analyze")
async def analyze(request: Request):
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid request.")

    video_id = body.get("video_id", "").strip()
    if not video_id:
        raise HTTPException(status_code=400, detail="Video ID is required.")

    data = youtube_request("videos", {
        "part": "snippet,statistics,contentDetails",
        "id": video_id
    })

    if not data.get("items"):
        raise HTTPException(status_code=404, detail="Video not found. Please check the URL.")

    item = data["items"][0]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    content = item.get("contentDetails", {})

    thumbs_raw = snippet.get("thumbnails", {})
    thumbnails = []
    quality_map = {
        "maxres": ("Max Resolution", 1280, 720),
        "standard": ("Standard", 640, 480),
        "high": ("High", 480, 360),
        "medium": ("Medium", 320, 180),
        "default": ("Default", 120, 90),
    }
    for key, (label, w, h) in quality_map.items():
        if key in thumbs_raw:
            thumbnails.append({
                "quality": label,
                "url": thumbs_raw[key]["url"],
                "width": thumbs_raw[key].get("width", w),
                "height": thumbs_raw[key].get("height", h)
            })

    transcript = get_transcript(video_id)

    return {
        "video_id": video_id,
        "title": snippet.get("title", ""),
        "description": snippet.get("description", ""),
        "tags": snippet.get("tags", []),
        "views": int(stats.get("viewCount", 0)),
        "likes": int(stats.get("likeCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
        "published": format_date(snippet.get("publishedAt")),
        "duration": format_duration(content.get("duration")),
        "channel": snippet.get("channelTitle", ""),
        "thumbnail_url": thumbs_raw.get("high", {}).get("url", ""),
        "thumbnails": thumbnails,
        "transcript": transcript or "Transcript not available for this video (captions may be disabled).",
    }

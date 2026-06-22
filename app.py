from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
import os
import json
import urllib.request
import urllib.parse
import re
from datetime import date

app = FastAPI()

SITE_URL = "https://ytdecode.vercel.app"
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = "youtube-v3-lite.p.rapidapi.com"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def rapidapi_request(endpoint, params):
    if not RAPIDAPI_KEY:
        raise HTTPException(status_code=500, detail="API key not configured.")
    query = urllib.parse.urlencode(params)
    url = f"https://{RAPIDAPI_HOST}/{endpoint}?{query}"
    req = urllib.request.Request(url, headers={
        "Content-Type": "application/json",
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise HTTPException(status_code=e.code, detail=f"API error: {error_body}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")

def get_transcript(video_id):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join([t['text'] for t in transcript_list])
    except Exception:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcripts.find_generated_transcript(['en', 'ur', 'hi'])
            return ' '.join([t['text'] for t in transcript.fetch()])
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

    # Get video details from RapidAPI
    data = rapidapi_request("videos", {
        "id": video_id,
        "part": "snippet,contentDetails,statistics"
    })

    items = data.get("items", [])
    if not items:
        raise HTTPException(status_code=404, detail="Video not found. Please check the URL.")

    item = items[0]
    snippet = item.get("snippet", {})
    stats = item.get("statistics", {})
    content = item.get("contentDetails", {})

    # Thumbnails
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

    # Transcript
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


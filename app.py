from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
import os
import re
from datetime import date

app = FastAPI()

SITE_URL = "https://ytdecode.vercel.app"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_transcript(video_id):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        try:
            data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            return ' '.join([t['text'] for t in data])
        except:
            pass
        transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
        for t in transcripts:
            try:
                return ' '.join([x['text'] for x in t.fetch()])
            except:
                continue
    except:
        pass
    return None

def get_thumbnails(video_id):
    return [
        {"quality": "Max Resolution", "url": f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg", "width": 1280, "height": 720},
        {"quality": "Standard", "url": f"https://i.ytimg.com/vi/{video_id}/sddefault.jpg", "width": 640, "height": 480},
        {"quality": "High", "url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg", "width": 480, "height": 360},
        {"quality": "Medium", "url": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg", "width": 320, "height": 180},
    ]

@app.get("/", response_class=HTMLResponse)
def home():
    path = os.path.join(BASE_DIR, "index.html")
    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return PlainTextResponse(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n")

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

    transcript = get_transcript(video_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Could not extract transcript. This video may have captions disabled.")

    thumbnails = get_thumbnails(video_id)

    return {
        "video_id": video_id,
        "title": f"YouTube Video ({video_id})",
        "description": "",
        "tags": [],
        "views": 0,
        "likes": 0,
        "comments": 0,
        "published": "",
        "duration": "",
        "channel": "",
        "thumbnail_url": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "thumbnails": thumbnails,
        "transcript": transcript,
    }

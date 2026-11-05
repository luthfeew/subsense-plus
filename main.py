import asyncio
import base64
import json
import os
import sys
import urllib.parse

# Ensure Windows terminal prints UTF-8 cleanly
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import httpx

from scraper import JumpscareScraper
from injector import inject_jumpscares

app = FastAPI(title="SubSense+ Subtitle Addon")

# Enable CORS for Stremio Web and Nuvio
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
CONFIGURE_HTML_PATH = os.path.join(TEMPLATES_DIR, "configure.html")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

scraper = JumpscareScraper()

DEFAULT_SUBSENSE_BASE = "https://subsense.elfhosted.com"

MANIFEST = {
    "id": "org.subsense.plus",
    "version": "1.0.5",
    "name": "SubSense+",
    "description": "Enhanced SubSense subtitles with smart viewing enhancements, jumpscare alerts, and more.",
    "resources": [
        "subtitles"
    ],
    "types": [
        "movie",
        "series",
        "subtitles"
    ],
    "idPrefixes": [
        "tt",
        "kitsu"
    ],
    "catalogs": [],
    "behaviorHints": {
        "configurable": True,
        "configurationRequired": False
    }
}

def decode_user_config(config_str: Optional[str]) -> Dict[str, Any]:
    """
    Decodes base64-encoded configuration dictionary.
    """
    default_cfg = {"subsense": "default", "lead": 5.0, "filter": "all", "tmdb_key": ""}
    if not config_str or config_str == "manifest.json":
        return default_cfg.copy()
    try:
        raw_json = base64.b64decode(config_str).decode('utf-8')
        data = json.loads(raw_json)
        if "tmdb_key" not in data:
            data["tmdb_key"] = ""
        return data
    except Exception:
        return default_cfg.copy()

def get_subsense_base(config: Dict[str, Any]) -> str:
    subsense_input = config.get("subsense", "default")
    if not subsense_input or subsense_input == "default":
        return DEFAULT_SUBSENSE_BASE
    
    unquoted = urllib.parse.unquote(subsense_input).strip()
    # Normalize stremio:// to https://
    if unquoted.startswith("stremio://"):
        unquoted = "https://" + unquoted[10:]
    
    unquoted = unquoted.rstrip('/')
    
    # Strip known trailing routes from user-copied URLs
    for suffix in ["/manifest.json", "/configure"]:
        if unquoted.endswith(suffix):
            unquoted = unquoted[:-len(suffix)]
            unquoted = unquoted.rstrip('/')
            
    return unquoted

@app.get("/")
async def root():
    return RedirectResponse(url="/configure")

@app.get("/configure", response_class=HTMLResponse)
async def configure(request: Request):
    if os.path.exists(CONFIGURE_HTML_PATH):
        with open(CONFIGURE_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Configure HTML not found</h1>", status_code=404)


@app.get("/api/test-download")
async def test_download(url: str):
    results = {}
    headers_list = [
        ("browser", BROWSER_HEADERS),
        ("stremio", {"User-Agent": "Stremio/4.4.168", "Accept": "*/*"}),
        ("okhttp", {"User-Agent": "okhttp/4.9.0", "Accept": "*/*"}),
        ("exoplayer", {"User-Agent": "ExoPlayer/2.18.1", "Accept": "*/*"}),
        ("curl", {"User-Agent": "curl/8.4.0", "Accept": "*/*"}),
        ("empty", {}),
    ]
    for name, hdrs in headers_list:
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=hdrs) as client:
                r = await client.get(url)
                results[name] = {
                    "status": r.status_code,
                    "length": len(r.text),
                    "server": r.headers.get("server", ""),
                    "cf_mitigated": r.headers.get("cf-mitigated", ""),
                    "sample": r.text[:150]
                }
        except Exception as e:
            results[name] = {"error": str(e)}
    return results

@app.get("/api/validate-subsense")
async def validate_subsense(url: str):
    """
    Validates whether the provided SubSense URL is reachable and provides subtitles.
    """
    if not url or not url.strip():
        return {"valid": False, "error": "URL cannot be empty"}

    cleaned_base = get_subsense_base({"subsense": url})
    manifest_url = f"{cleaned_base}/manifest.json"

    async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
        try:
            resp = await client.get(manifest_url)
            if resp.status_code == 200:
                data = resp.json()
                resources = data.get("resources", [])
                has_subtitles = any(
                    r == "subtitles" or (isinstance(r, dict) and r.get("name") == "subtitles")
                    for r in resources
                )
                if has_subtitles:
                    return {
                        "valid": True,
                        "name": data.get("name", "SubSense"),
                        "version": data.get("version", "")
                    }
                return {
                    "valid": False,
                    "error": "Manifest reached, but it does not support subtitles."
                }
            return {
                "valid": False,
                "error": f"Server responded with HTTP {resp.status_code}"
            }
        except Exception as e:
            return {
                "valid": False,
                "error": f"Connection failed ({str(e)[:50]})"
            }

@app.get("/api/validate-tmdb")
async def validate_tmdb(key: str):
    """
    Validates whether the provided TMDB API key is active and authorized.
    """
    clean_key = key.strip()
    if not clean_key:
        return {"valid": False, "error": "API Key cannot be empty"}

    # TMDB authentication check endpoint
    url = f"https://api.themoviedb.org/3/authentication?api_key={clean_key}"
    async with httpx.AsyncClient(timeout=6.0) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return {"valid": True, "message": "Valid TMDB API Key (Connected)"}
            elif resp.status_code == 401:
                return {"valid": False, "error": "Invalid TMDB API Key (401 Unauthorized)"}
            return {"valid": False, "error": f"TMDB returned HTTP {resp.status_code}"}
        except Exception as e:
            return {"valid": False, "error": f"Connection error: {str(e)[:40]}"}

@app.get("/manifest.json")
async def default_manifest(request: Request):
    host = str(request.base_url).rstrip('/')
    m = dict(MANIFEST)
    m["logo"] = f"{host}/static/logo.png"
    return m

@app.get("/{user_config}/manifest.json")
async def user_manifest(user_config: str, request: Request):
    host = str(request.base_url).rstrip('/')
    custom_manifest = dict(MANIFEST)
    custom_manifest["name"] = "SubSense+"
    custom_manifest["logo"] = f"{host}/static/logo.png"
    return custom_manifest

async def handle_subtitles_request(
    user_config: Optional[str],
    media_type: str,
    media_id: str,
    extra: Optional[str],
    request: Request
):
    config = decode_user_config(user_config)
    subsense_base = get_subsense_base(config)
    lead_time = float(config.get("lead", 5.0))
    filter_type = config.get("filter", "all")
    tmdb_key = config.get("tmdb_key", "")

    # Build upstream SubSense URL
    if extra:
        upstream_url = f"{subsense_base}/subtitles/{media_type}/{media_id}/{extra}.json"
    else:
        upstream_url = f"{subsense_base}/subtitles/{media_type}/{media_id}.json"

    print(f"[Proxy] Forwarding subtitle request to: {upstream_url}")

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        try:
            resp = await client.get(upstream_url)
            if resp.status_code != 200:
                print(f"[Proxy] Upstream returned status {resp.status_code}")
                return {"subtitles": []}
            data = resp.json()
        except Exception as e:
            print(f"[Proxy] Failed connecting to upstream SubSense: {e}")
            return {"subtitles": []}

    subtitles = data.get("subtitles", [])
    if not subtitles:
        return {"subtitles": []}

    host = str(request.base_url).rstrip('/')
    proxied_subtitles = []

    for sub in subtitles:
        orig_url = sub.get("url")
        if not orig_url:
            continue

        encoded_url = urllib.parse.quote(orig_url, safe='')
        proxy_url = (
            f"{host}/proxy-sub/{media_id}.srt?"
            f"imdb={media_id}&type={media_type}&lead={lead_time}&filter={filter_type}"
            f"&tmdb_key={urllib.parse.quote(tmdb_key)}"
            f"&sub_url={encoded_url}"
        )

        # Preserve ALL original fields from upstream SubSense (fileName, source, releaseName, releases, etc.)
        proxied_sub = dict(sub)
        proxied_sub["id"] = f"subsense-plus-{sub.get('id', 'sub')}"
        proxied_sub["url"] = proxy_url
        proxied_subtitles.append(proxied_sub)

    return {"subtitles": proxied_subtitles}

@app.get("/subtitles/{media_type}/{media_id}.json")
async def get_subtitles_default(media_type: str, media_id: str, request: Request):
    return await handle_subtitles_request(None, media_type, media_id, None, request)

@app.get("/subtitles/{media_type}/{media_id}/{extra}.json")
async def get_subtitles_extra_default(media_type: str, media_id: str, extra: str, request: Request):
    return await handle_subtitles_request(None, media_type, media_id, extra, request)

@app.get("/{user_config}/subtitles/{media_type}/{media_id}.json")
async def get_subtitles_custom(user_config: str, media_type: str, media_id: str, request: Request):
    return await handle_subtitles_request(user_config, media_type, media_id, None, request)

@app.get("/{user_config}/subtitles/{media_type}/{media_id}/{extra}.json")
async def get_subtitles_extra_custom(user_config: str, media_type: str, media_id: str, extra: str, request: Request):
    return await handle_subtitles_request(user_config, media_type, media_id, extra, request)


async def fetch_subtitle_content(url: str) -> Optional[str]:
    """
    Downloads subtitle content from upstream with Chrome TLS impersonation (curl_cffi)
    to bypass Cloudflare WAF on dl.opensubtitles.org and other protected subtitle providers.
    Falls back to httpx if curl_cffi encounters an issue.
    """
    # 1. Try curl_cffi with Chrome 120 TLS fingerprint (bypasses Cloudflare on dl.opensubtitles.org)
    try:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate="chrome120") as s:
            r = await s.get(url, timeout=12.0)
            if r.status_code == 200 and r.text and len(r.text.strip()) > 10:
                if "<html" not in r.text[:100].lower() or "WEBVTT" in r.text[:50]:
                    return r.text
                print(f"[Injector] curl_cffi received HTML/challenge instead of subtitle from {url}")
            else:
                print(f"[Injector] curl_cffi returned HTTP {r.status_code} for {url}")
    except Exception as e:
        print(f"[Injector] curl_cffi error fetching subtitle: {e}")

    # 2. Fallback to httpx
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and resp.text.strip():
                if "<html" not in resp.text[:100].lower() or "WEBVTT" in resp.text[:50]:
                    return resp.text
            print(f"[Injector] httpx returned HTTP {resp.status_code} for {url}")
    except Exception as e:
        print(f"[Injector] httpx error fetching subtitle: {e}")

    return None

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
}

@app.get("/proxy-sub/{filename}")
@app.get("/proxy-sub")
async def proxy_subtitle(
    imdb: str,
    filename: Optional[str] = None,
    type: str = "movie",
    sub_url: str = "",
    lead: float = 5.0,
    filter: str = "all",
    tmdb_key: str = ""
):
    if not sub_url:
        raise HTTPException(status_code=400, detail="Missing sub_url parameter")

    actual_sub_url = urllib.parse.unquote(sub_url)
    print(f"[Injector] Downloading subtitle from {actual_sub_url} for IMDb {imdb}...")

    original_content = await fetch_subtitle_content(actual_sub_url)
    if not original_content:
        print(f"[Injector] Upstream could not be fetched. Seamlessly redirecting client to original subtitle.")
        return RedirectResponse(url=actual_sub_url, status_code=307)

    try:
        jumpscares = await asyncio.wait_for(
            scraper.get_jumpscares_for_id(type, imdb, tmdb_api_key=tmdb_key or None),
            timeout=12.0
        )
        if filter == "major":
            jumpscares = [j for j in jumpscares if j.get("intensity", "").lower() == "major"]

        print(f"[Injector] Injecting {len(jumpscares)} jumpscare warnings with {lead}s lead time...")
        modified_content = inject_jumpscares(
            subtitle_content=original_content,
            jumpscares=jumpscares,
            lead_time_seconds=lead
        )
    except Exception as e:
        print(f"[Injector] Error or timeout during warning injection ({e}), serving original subtitle directly.")
        modified_content = original_content

    is_vtt = "WEBVTT" in modified_content[:50]
    media_type = "text/vtt; charset=utf-8" if is_vtt else "application/x-subrip; charset=utf-8"
    out_filename = filename or f"{imdb}.srt"

    return Response(
        content=modified_content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{out_filename}"',
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="SubSense+ Subtitle Addon")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debugging output (displays full jumpscare timestamps list in terminal)."
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable local cache to force live scraping from WhenJumpScare / NotScare every time."
    )
    parser.add_argument(
        "--tmdb-key",
        type=str,
        default=os.environ.get("TMDB_API_KEY", ""),
        help="Optional personal TMDB API key for guaranteed 100% TMDB ID resolution."
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 8000)),
        help="Port to run the server on (default: 8000 or $PORT)."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind the server to (default: 0.0.0.0)."
    )

    args, _ = parser.parse_known_args()

    if args.verbose:
        os.environ["VERBOSE"] = "1"
        scraper.verbose = True
        print("[Config] 🐛 Verbose debugging ENABLED. Full timestamps will be printed.")

    if args.no_cache:
        os.environ["NO_CACHE"] = "1"
        scraper.no_cache = True
        print("[Config] 🚫 Local cache DISABLED. Live scraping forced for all requests.")

    if args.tmdb_key:
        os.environ["TMDB_API_KEY"] = args.tmdb_key
        print("[Config] 🔑 Personal TMDB API Key loaded.")

    print(f"Starting SubSense+ server at http://127.0.0.1:{args.port} ...")
    uvicorn.run("main:app", host=args.host, port=args.port, reload=True)

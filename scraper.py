import re
import json
import os
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup

CACHE_FILE = os.path.join(os.path.dirname(__file__), "jumpscares_cache.json")

# Pre-seeded jumpscares for popular titles to ensure immediate reliability & offline dev
DEFAULT_SEED_DATA = {
    "tt1457767": {  # The Conjuring (2013)
        "title": "The Conjuring",
        "year": "2013",
        "jumpscares": [
            {"time": 216, "intensity": "Minor", "description": "Loud bang in house"},
            {"time": 2226, "intensity": "Minor", "description": "Paintings falling off wall"},
            {"time": 2560, "intensity": "Major", "description": "Monster on top of closet"},
            {"time": 3020, "intensity": "Major", "description": "Clap clap in cellar"},
            {"time": 4739, "intensity": "Major", "description": "Music box reflection lady"},
            {"time": 5113, "intensity": "Minor", "description": "Child pulled in bed"}
        ]
    },
    "tt1591095": {  # Insidious (2011)
        "title": "Insidious",
        "year": "2011",
        "jumpscares": [
            {"time": 815, "intensity": "Minor", "description": "Ladder cracks in attic"},
            {"time": 1820, "intensity": "Minor", "description": "Alarm system goes off"},
            {"time": 2420, "intensity": "Major", "description": "Red-faced demon behind Josh"},
            {"time": 3280, "intensity": "Major", "description": "Dancing boy appears"},
            {"time": 5908, "intensity": "Minor", "description": "Final confrontation screamer"}
        ]
    },
    "tt15474916": {  # Smile (2022)
        "title": "Smile",
        "year": "2022",
        "jumpscares": [
            {"time": 110, "intensity": "Major", "description": "Patient stands up smiling"},
            {"time": 2340, "intensity": "Minor", "description": "Cat birthday gift box"},
            {"time": 4150, "intensity": "Major", "description": "Sister's head drops at car window"},
            {"time": 6438, "intensity": "Major", "description": "Monster rips off face"}
        ]
    },
    "tt26657236": {  # Backrooms (2026)
        "title": "Backrooms",
        "year": "2026",
        "jumpscares": [
            {"time": 233, "intensity": "Minor", "description": "Sudden noise in hallway"},
            {"time": 252, "intensity": "Minor", "description": "Door slams shut"},
            {"time": 384, "intensity": "Minor", "description": "Figure in distance"},
            {"time": 2189, "intensity": "Minor", "description": "Loud screech"},
            {"time": 3116, "intensity": "Minor", "description": "Movement behind wall"},
            {"time": 3149, "intensity": "Minor", "description": "Flickering entity"},
            {"time": 3349, "intensity": "Minor", "description": "Ceiling crack"},
            {"time": 3550, "intensity": "Minor", "description": "Sudden whisper"},
            {"time": 3597, "intensity": "Minor", "description": "Shadow charges"},
            {"time": 4325, "intensity": "Major", "description": "Monster lunges forward"},
            {"time": 4709, "intensity": "Minor", "description": "Alarm blare"},
            {"time": 5627, "intensity": "Major", "description": "Full entity ambush"},
            {"time": 5707, "intensity": "Minor", "description": "Final screech"}
        ]
    },
    "tt37281055": {  # Buddy (2026)
        "title": "Buddy",
        "year": "2026",
        "jumpscares": [
            {"time": 1237, "intensity": "Minor", "description": "Scare at 00:20:37"},
            {"time": 1263, "intensity": "Minor", "description": "Scare at 00:21:03"},
            {"time": 2698, "intensity": "Minor", "description": "Scare at 00:44:58"},
            {"time": 4026, "intensity": "Minor", "description": "Scare at 01:07:06"},
            {"time": 4576, "intensity": "Minor", "description": "Scare at 01:16:16"},
            {"time": 4604, "intensity": "Minor", "description": "Scare at 01:16:44"},
            {"time": 4960, "intensity": "Minor", "description": "Scare at 01:22:40"}
        ]
    },
    "tt36893729": {  # Ice Cream Man (2026)
        "title": "Ice Cream Man",
        "year": "2026",
        "jumpscares": [
            {"time": 1526, "intensity": "Minor", "description": "Children burst through door at 00:25:26"},
            {"time": 1994, "intensity": "Minor", "description": "Scare at 00:33:14"},
            {"time": 2780, "intensity": "Minor", "description": "Scare at 00:46:20"},
            {"time": 3250, "intensity": "Minor", "description": "Scare at 00:54:10"},
            {"time": 3515, "intensity": "Minor", "description": "Scare at 00:58:35"},
            {"time": 3940, "intensity": "Minor", "description": "Scare at 01:05:40"},
            {"time": 4323, "intensity": "Minor", "description": "Scare at 01:12:03"}
        ]
    }
}

class JumpscareScraper:
    def __init__(self, no_cache: bool = False, verbose: bool = False):
        self.no_cache = no_cache or os.environ.get("NO_CACHE", "0") == "1"
        self.verbose = verbose or os.environ.get("VERBOSE", "0") == "1"
        self.cache: Dict[str, Any] = self._load_cache()

    def _format_seconds(self, seconds: float) -> str:
        seconds = max(0.0, float(seconds))
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def print_jumpscares_debug(self, label: str, jumpscares: List[Dict[str, Any]]):
        """
        Prints a formatted list of jumpscare timestamps for debugging.
        Safe for all Windows terminal encodings.
        """
        print("\n" + "=" * 65)
        print(f"[DEBUG] Jumpscare Timestamps for: {label}")
        print(f"   Total scares: {len(jumpscares)}")
        print("-" * 65)
        if not jumpscares:
            print("   (No jumpscares found for this title)")
        else:
            for idx, js in enumerate(jumpscares, 1):
                sec = float(js.get("time", 0))
                time_str = self._format_seconds(sec)
                alert_time_str = self._format_seconds(max(0.0, sec - 5.0))
                intensity = js.get("intensity", "Minor")
                desc = js.get("description", "-")
                print(f"   {idx:02d}. [{time_str}] ({intensity:5s}) | Alert triggers at: {alert_time_str} | {desc}")
        print("=" * 65 + "\n")

    def _load_cache(self) -> Dict[str, Any]:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge with default seed data
                    for k, v in DEFAULT_SEED_DATA.items():
                        if k not in data:
                            data[k] = v
                    return data
            except Exception as e:
                print(f"[Cache] Error reading cache file: {e}")
        return DEFAULT_SEED_DATA.copy()

    def _save_cache(self):
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Cache] Error saving cache: {e}")

    async def get_metadata_from_cinemeta(self, media_type: str, imdb_id: str) -> Optional[Dict[str, str]]:
        """
        Uses Stremio's free official Cinemeta API to fetch movie title & release year from IMDb ID.
        """
        clean_id = imdb_id.split(':')[0]
        url = f"https://v3-cinemeta.strem.io/meta/{media_type}/{clean_id}.json"
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json().get("meta", {})
                    name = data.get("name")
                    year = data.get("year", "")
                    if name:
                        return {"title": name, "year": str(year)}
            except Exception as e:
                print(f"[Cinemeta] Failed to fetch metadata for {clean_id}: {e}")
        return None

    def _parse_timestamp_to_seconds(self, ts_str: str) -> Optional[float]:
        """
        Converts MM:SS or HH:MM:SS to seconds.
        """
        ts_str = ts_str.strip()
        parts = ts_str.split(':')
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + float(parts[1])
        except ValueError:
            pass
        return None

    async def get_tmdb_id_from_imdb(self, imdb_id: str, title: Optional[str] = None, year: Optional[str] = None, tmdb_api_key: Optional[str] = None) -> Optional[str]:
        """
        Resolves TMDB ID from IMDb ID using:
        1. User-supplied TMDB API Key / env TMDB_API_KEY (if available)
        2. Stremio's public TMDB Addon metadata endpoints
        3. DuckDuckGo / Bing search discovery
        4. Wikidata SPARQL
        """
        clean_id = imdb_id.split(':')[0]
        active_key = tmdb_api_key or os.environ.get("TMDB_API_KEY")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

        async with httpx.AsyncClient(timeout=7.0, headers=headers, follow_redirects=True) as client:
            # 1. Official TMDB API (if valid key is provided)
            if active_key:
                try:
                    url = f"https://api.themoviedb.org/3/find/{clean_id}?api_key={active_key}&external_source=imdb_id"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        results = resp.json().get("movie_results", [])
                        if results:
                            tmdb_id = str(results[0].get("id"))
                            print(f"[Scraper] Resolved TMDB ID via TMDB Find API: {tmdb_id} for {clean_id}")
                            return tmdb_id
                except Exception:
                    pass

                if title:
                    try:
                        encoded_title = urllib.parse.quote(title)
                        url = f"https://api.themoviedb.org/3/search/movie?api_key={active_key}&query={encoded_title}"
                        if year:
                            url += f"&year={year}"
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            results = resp.json().get("results", [])
                            if results:
                                tmdb_id = str(results[0].get("id"))
                                print(f"[Scraper] Resolved TMDB ID via TMDB Search API: {tmdb_id} for '{title}'")
                                return tmdb_id
                    except Exception:
                        pass

            # 2. Query Stremio public TMDB Addon metadata instances
            stremio_tmdb_urls = [
                f"https://94c8cb9f702d-tmdb-addon.baby-beamup.club/meta/movie/{clean_id}.json",
                f"https://tmdb.elfhosted.com/meta/movie/{clean_id}.json"
            ]
            for t_url in stremio_tmdb_urls:
                try:
                    resp = await client.get(t_url)
                    if resp.status_code == 200:
                        meta = resp.json().get("meta", {})
                        t_id = meta.get("moviedb_id") or meta.get("tmdb_id")
                        raw_id = meta.get("id", "")
                        if not t_id and raw_id.startswith("tmdb:"):
                            t_id = raw_id.replace("tmdb:", "")
                        if t_id:
                            print(f"[Scraper] Resolved TMDB ID via Stremio TMDB Addon: {t_id} for {clean_id}")
                            return str(t_id)
                except Exception:
                    pass

            # 3. DuckDuckGo search for themoviedb.org
            if title:
                try:
                    q = f"site:themoviedb.org/movie/ {title} {year or ''}".strip()
                    ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
                    resp = await client.get(ddg_url)
                    if resp.status_code == 200:
                        matches = re.findall(r'themoviedb\.org/movie/(\d+)', resp.text)
                        if matches:
                            tmdb_id = matches[0]
                            print(f"[Scraper] Resolved TMDB ID via Search Engine: {tmdb_id} for '{title}'")
                            return tmdb_id
                except Exception:
                    pass

            # 4. Fallback to Wikidata SPARQL
            try:
                sparql_url = (
                    "https://query.wikidata.org/sparql?query="
                    f"SELECT ?tmdb WHERE {{ ?item wdt:P345 '{clean_id}' . ?item wdt:P4947 ?tmdb }}&format=json"
                )
                resp = await client.get(sparql_url)
                if resp.status_code == 200:
                    bindings = resp.json().get("results", {}).get("bindings", [])
                    if bindings:
                        tmdb_id = bindings[0].get("tmdb", {}).get("value")
                        if tmdb_id:
                            print(f"[Scraper] Resolved TMDB ID via Wikidata: {tmdb_id} for {clean_id}")
                            return str(tmdb_id)
            except Exception:
                pass

        return None

    async def discover_whenjumpscare_url(self, title: str, year: str) -> Optional[str]:
        """
        Discovers the direct WhenJumpScare movie page URL using search engines.
        Matches URLs like: https://www.whenjumpscare.com/movie/1083381-backrooms-2026
        """
        query = f"site:whenjumpscare.com/movie/ {title} {year or ''}".strip()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

        async with httpx.AsyncClient(timeout=8.0, headers=headers, follow_redirects=True) as client:
            # 1. Try DuckDuckGo HTML
            try:
                ddg_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
                resp = await client.get(ddg_url)
                if resp.status_code == 200:
                    matches = re.findall(r'whenjumpscare\.com/movie/([0-9]+-[a-zA-Z0-9\-]+)', resp.text)
                    if matches:
                        url = f"https://www.whenjumpscare.com/movie/{matches[0]}"
                        print(f"[Scraper] Discovered WhenJumpScare URL via DuckDuckGo: {url}")
                        return url
            except Exception:
                pass

            # 2. Try DuckDuckGo Lite
            try:
                ddg_lite = "https://lite.duckduckgo.com/lite/"
                resp = await client.post(ddg_lite, data={"q": query})
                if resp.status_code == 200:
                    matches = re.findall(r'whenjumpscare\.com/movie/([0-9]+-[a-zA-Z0-9\-]+)', resp.text)
                    if matches:
                        url = f"https://www.whenjumpscare.com/movie/{matches[0]}"
                        print(f"[Scraper] Discovered WhenJumpScare URL via DuckDuckGo Lite: {url}")
                        return url
            except Exception:
                pass

            # 3. Try Bing Search
            try:
                bing_url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
                resp = await client.get(bing_url)
                if resp.status_code == 200:
                    matches = re.findall(r'whenjumpscare\.com/movie/([0-9]+-[a-zA-Z0-9\-]+)', resp.text)
                    if matches:
                        url = f"https://www.whenjumpscare.com/movie/{matches[0]}"
                        print(f"[Scraper] Discovered WhenJumpScare URL via Bing: {url}")
                        return url
            except Exception:
                pass

        return None

    def _slugify(self, text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^a-z0-9]+', '-', text)
        return text.strip('-')

    async def scrape_whenjumpscare(
        self,
        title: str,
        year: str,
        tmdb_id: Optional[str] = None,
        direct_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Attempts to scrape jumpscare timestamps from https://www.whenjumpscare.com/
        Supports TMDB ID pattern: /movie/{tmdb_id}-{slug}-{year}
        Parses Next.js __NEXT_DATA__, downloadable .SRT, and 'The scare sheet' table.
        """
        jumpscares: List[Dict[str, Any]] = []
        slug_raw = self._slugify(title)
        
        slug_candidates = [
            slug_raw,
            f"{slug_raw}-{year}",
            slug_raw.replace("the-", "", 1) if slug_raw.startswith("the-") else f"the-{slug_raw}",
            f"{slug_raw.replace('the-', '', 1)}-{year}" if slug_raw.startswith("the-") else f"the-{slug_raw}-{year}"
        ]

        candidate_urls = []
        if direct_url:
            candidate_urls.append(direct_url)
        
        # Priority 1: WhenJumpScare URLs with TMDB ID prefix (e.g. /movie/1083381-backrooms-2026)
        if tmdb_id:
            for s in slug_candidates:
                candidate_urls.extend([
                    f"https://www.whenjumpscare.com/movie/{tmdb_id}-{s}",
                    f"https://www.whenjumpscare.com/movie/{tmdb_id}-{s}-{year}",
                ])
            candidate_urls.append(f"https://www.whenjumpscare.com/movie/{tmdb_id}")

        # Priority 2: Generic slugs
        for s in slug_candidates:
            candidate_urls.extend([
                f"https://www.whenjumpscare.com/movie/{s}",
                f"https://www.whenjumpscare.com/{s}"
            ])

        # Deduplicate preserving order
        seen_urls = set()
        unique_urls = []
        for u in candidate_urls:
            if u not in seen_urls:
                seen_urls.add(u)
                unique_urls.append(u)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

        # Regex targeting "The scare sheet" cards:
        # e.g., "01 00:20:37 MINOR SPOILER" or "00:20:37 MINOR"
        scare_row_pattern = re.compile(
            r'(?:^|\b|\n)(?:\d{1,2}\s+)?(\d{1,2}:\d{2}(?::\d{2})?)\s*(MAJOR|MINOR)\b',
            re.IGNORECASE
        )

        async with httpx.AsyncClient(timeout=10.0, headers=headers, follow_redirects=True) as client:
            for url in unique_urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        print(f"[WhenJumpScare] Successfully opened page: {url}")

                        # 1. Check for Next.js __NEXT_DATA__ JSON props
                        next_script = soup.find("script", id="__NEXT_DATA__")
                        if next_script and next_script.string:
                            try:
                                next_json = json.loads(next_script.string)
                                page_props = next_json.get("props", {}).get("pageProps", {})
                                raw_scares = (
                                    page_props.get("scares") or
                                    page_props.get("jumpscares") or
                                    page_props.get("movie", {}).get("scares") or
                                    page_props.get("movie", {}).get("jumpscares") or
                                    page_props.get("movie", {}).get("scare_sheet")
                                )
                                if raw_scares and isinstance(raw_scares, list):
                                    for item in raw_scares:
                                        t_val = item.get("time") or item.get("timestamp") or item.get("seconds")
                                        if isinstance(t_val, str):
                                            sec = self._parse_timestamp_to_seconds(t_val)
                                        elif isinstance(t_val, (int, float)):
                                            sec = float(t_val)
                                        else:
                                            sec = None
                                        if sec and sec > 10:
                                            intensity = str(item.get("intensity") or item.get("type") or "Minor").capitalize()
                                            desc = str(item.get("description") or item.get("desc") or f"Jump scare at {t_val}")
                                            if not any(abs(j["time"] - sec) < 5 for j in jumpscares):
                                                jumpscares.append({
                                                    "time": sec,
                                                    "intensity": "Major" if "major" in intensity.lower() else "Minor",
                                                    "description": desc[:80]
                                                })
                                    if jumpscares:
                                        jumpscares.sort(key=lambda x: x["time"])
                                        print(f"[WhenJumpScare] Extracted {len(jumpscares)} jumpscares via __NEXT_DATA__ from {url}!")
                                        return jumpscares
                            except Exception:
                                pass

                        # 2. Check for Warning Subtitle (.SRT) link
                        srt_link_elem = soup.find("a", href=re.compile(r'\.srt', re.IGNORECASE))
                        if srt_link_elem and srt_link_elem.get("href"):
                            srt_url = urllib.parse.urljoin(url, srt_link_elem["href"])
                            try:
                                srt_resp = await client.get(srt_url)
                                if srt_resp.status_code == 200:
                                    srt_text = srt_resp.text
                                    for line in srt_text.splitlines():
                                        ts_match = re.search(r'(\d{2}:\d{2}:\d{2}(?:[,\.]\d{1,3})?)\s*-->', line)
                                        if ts_match:
                                            sec = self._parse_timestamp_to_seconds(ts_match.group(1).replace(',', '.'))
                                            # Subtitles are timed ~5s ahead, adjust to actual scare time
                                            actual_sec = sec + 5.0
                                            if not any(abs(j["time"] - actual_sec) < 5 for j in jumpscares):
                                                jumpscares.append({
                                                    "time": actual_sec,
                                                    "intensity": "Minor",
                                                    "description": f"Jump scare at {self._format_seconds(actual_sec)}"
                                                })
                                    if jumpscares:
                                        jumpscares.sort(key=lambda x: x["time"])
                                        print(f"[WhenJumpScare] Extracted {len(jumpscares)} jumpscares via official SRT from {url}!")
                                        return jumpscares
                            except Exception:
                                pass

                        # 3. Parse "The scare sheet" table in HTML DOM
                        page_text = soup.get_text(separator="\n")
                        for match in scare_row_pattern.finditer(page_text):
                            ts_str, intensity_str = match.groups()
                            sec = self._parse_timestamp_to_seconds(ts_str)
                            if sec and sec > 10:
                                intensity = intensity_str.capitalize()
                                if not any(abs(j["time"] - sec) < 5 for j in jumpscares):
                                    jumpscares.append({
                                        "time": sec,
                                        "intensity": intensity,
                                        "description": f"Jump scare ({intensity}) at {ts_str}"
                                    })

                        if jumpscares:
                            jumpscares.sort(key=lambda x: x["time"])
                            print(f"[WhenJumpScare] Extracted {len(jumpscares)} jumpscares from {url}!")
                            return jumpscares
                except Exception:
                    pass

        return jumpscares

    async def scrape_notscare(self, title: str, year: str) -> List[Dict[str, Any]]:
        """
        Fallback scraper for https://notscare.me/
        URL format: https://notscare.me/movies/jump-scares-in-{slug}-{year}
        Accurately parses exact jumpscare cards without header/footer/runtime false positives.
        """
        jumpscares: List[Dict[str, Any]] = []
        slug_raw = self._slugify(title)

        slug_candidates = [
            f"{slug_raw}-{year}",
            slug_raw,
            f"{slug_raw.replace('the-', '', 1)}-{year}" if slug_raw.startswith("the-") else f"the-{slug_raw}-{year}",
            slug_raw.replace("the-", "", 1) if slug_raw.startswith("the-") else f"the-{slug_raw}"
        ]

        candidate_urls = []
        for s in slug_candidates:
            candidate_urls.extend([
                f"https://notscare.me/movies/jump-scares-in-{s}",
                f"https://notscare.me/movie/jump-scares-in-{s}",
                f"https://notscare.me/movies/{s}",
                f"https://notscare.me/movie/{s}",
                f"https://notscare.me/{s}"
            ])

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # Regex patterns targeting exact NotScare jumpscare cards:
        # e.g. "00:06:24 Minor The figure is standing around the corner..."
        # or   "Minor 00:06:24 The figure is standing..."
        # Strips out "Submitted by", "Jump to", "Report", etc.
        pat1 = re.compile(
            r'(\d{1,2}:\d{2}(?::\d{2})?)\s*(Major|Minor)\s*(.+?)(?=\s*(?:Submitted by|Jump to|Report|\n|$))',
            re.IGNORECASE
        )
        pat2 = re.compile(
            r'(Major|Minor)\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*(.+?)(?=\s*(?:Submitted by|Jump to|Report|\n|$))',
            re.IGNORECASE
        )

        async with httpx.AsyncClient(timeout=10.0, headers=headers, follow_redirects=True) as client:
            for url in candidate_urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        print(f"[NotScare] Successfully opened page: {url}")

                        # Remove script, style, nav, and header tags to prevent metadata/runtime false positives
                        for tag in soup(["script", "style", "nav", "header", "footer"]):
                            tag.decompose()

                        full_page_text = soup.get_text(separator="\n")

                        # Extract using Pattern 1: [Timestamp] [Intensity] [Description]
                        for match in pat1.finditer(full_page_text):
                            ts_str, intensity_str, desc = match.groups()
                            sec = self._parse_timestamp_to_seconds(ts_str)
                            if sec and sec > 30:
                                intensity = intensity_str.capitalize()
                                cleaned_desc = desc.strip()
                                # Clean up trailing noise
                                cleaned_desc = re.sub(r'\s*(?:Submitted by.*|Jump to.*|Report.*)$', '', cleaned_desc, flags=re.IGNORECASE).strip()
                                if not any(abs(j["time"] - sec) < 5 for j in jumpscares):
                                    jumpscares.append({
                                        "time": sec,
                                        "intensity": intensity,
                                        "description": cleaned_desc[:80] if cleaned_desc else f"Scare at {ts_str}"
                                    })

                        # Extract using Pattern 2: [Intensity] [Timestamp] [Description]
                        for match in pat2.finditer(full_page_text):
                            intensity_str, ts_str, desc = match.groups()
                            sec = self._parse_timestamp_to_seconds(ts_str)
                            if sec and sec > 30:
                                intensity = intensity_str.capitalize()
                                cleaned_desc = desc.strip()
                                cleaned_desc = re.sub(r'\s*(?:Submitted by.*|Jump to.*|Report.*)$', '', cleaned_desc, flags=re.IGNORECASE).strip()
                                if not any(abs(j["time"] - sec) < 5 for j in jumpscares):
                                    jumpscares.append({
                                        "time": sec,
                                        "intensity": intensity,
                                        "description": cleaned_desc[:80] if cleaned_desc else f"Scare at {ts_str}"
                                    })

                        if jumpscares:
                            jumpscares.sort(key=lambda x: x["time"])
                            print(f"[NotScare] Extracted {len(jumpscares)} verified jumpscares from {url}!")
                            return jumpscares
                except Exception as e:
                    pass

        return jumpscares

    async def get_jumpscares_for_id(self, media_type: str, imdb_id: str, tmdb_api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Main method to get jumpscares: checks cache -> Cinemeta -> WhenJumpScare -> NotScare.me fallback.
        """
        clean_id = imdb_id.split(':')[0]
        
        # 1. Check local cache (skipped if --no-cache is set)
        if not self.no_cache and clean_id in self.cache:
            jumpscares = self.cache[clean_id].get("jumpscares", [])
            print(f"[Scraper] Returning cached jumpscares for {clean_id} ({len(jumpscares)} found)")
            if self.verbose:
                title = self.cache[clean_id].get("title", clean_id)
                self.print_jumpscares_debug(f"{title} [{clean_id}] (Cache)", jumpscares)
            return jumpscares
        elif self.no_cache:
            print(f"[Scraper] Cache disabled (--no-cache), forcing live scrape for {clean_id}...")

        # 2. Resolve title from Cinemeta
        meta = await self.get_metadata_from_cinemeta(media_type, clean_id)
        if not meta or not meta.get("title"):
            print(f"[Scraper] Could not find metadata for {clean_id}")
            return []

        title = meta["title"]
        year = meta["year"]

        # 3. Discover direct WhenJumpScare URL or TMDB ID
        print(f"[Scraper] Discovering WhenJumpScare / TMDB data for '{title}' ({year})...")
        direct_url = await self.discover_whenjumpscare_url(title, year)

        # Extract TMDB ID from discovered URL if possible (e.g. 1083381 from /movie/1083381-backrooms-2026)
        tmdb_id = None
        if direct_url:
            match = re.search(r'/movie/(\d+)', direct_url)
            if match:
                tmdb_id = match.group(1)
                print(f"[Scraper] Extracted TMDB ID: {tmdb_id} from discovered URL")

        if not tmdb_id:
            tmdb_id = await self.get_tmdb_id_from_imdb(clean_id, title=title, year=year, tmdb_api_key=tmdb_api_key)

        print(f"[Scraper] Searching jumpscares for '{title}' ({year}) [TMDB: {tmdb_id or 'None'}] on WhenJumpScare...")

        # 4. Scrape WhenJumpScare.com (with direct URL and TMDB ID prefix support)
        jumpscares = await self.scrape_whenjumpscare(title, year, tmdb_id=tmdb_id, direct_url=direct_url)

        # 5. Fallback: NotScare.me (https://notscare.me/)
        if not jumpscares:
            print(f"[Scraper] WhenJumpScare returned no results for '{title}', trying NotScare.me fallback...")
            jumpscares = await self.scrape_notscare(title, year)

        # 6. Debug output & cache saving
        if self.verbose:
            self.print_jumpscares_debug(f"'{title}' ({year}) [{clean_id}] (Live Scraped)", jumpscares)

        if jumpscares and not self.no_cache:
            print(f"[Scraper] Saved {len(jumpscares)} jumpscares to cache for '{title}'!")
            self.cache[clean_id] = {
                "title": title,
                "year": year,
                "jumpscares": jumpscares
            }
            self._save_cache()

        return jumpscares

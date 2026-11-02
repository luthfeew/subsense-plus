# SubSense+

A lightweight Python addon for **Stremio** and **Nuvio** that enhances your **SubSense** subtitles with smart viewing enhancements, jumpscare alerts, and more. Powered by [SubSense](https://subsense.nepiraw.com/), [WhenJumpScare.com](https://www.whenjumpscare.com/), and [NotScare.me](https://notscare.me/).

---

## ✨ Features
1. **Enhanced SubSense Experience:** Integrates seamlessly with your SubSense setup with smart enhancements.
2. **Dialogue Preserved:** Dialogue lines are never overwritten or removed. The warning is neatly prepended above dialog or placed in quiet gaps.
3. **Clean & Minimal Design:** Displays a simple yellow subtitle banner:
   ```
   ⚠️ Jumpscare ⚠️
   ```
4. **Customizable Lead Time:** Default 5 seconds ahead (configurable from 3 to 15 seconds).
5. **Accurate Timestamps:** Uses crowdsourced jump scare timestamps from **WhenJumpScare.com** (with fallback support & local cache).
6. **TMDB Integration:** Optional TMDB API key support for 100% precise movie matching on WhenJumpScare.
7. **Universal Compatibility:** Works smoothly on Stremio (PC, Android, Android TV) and Nuvio Media Center.
8. **Web Configurator:** Includes a web interface to configure your SubSense link, warning lead time, and TMDB key.

---

## 🛠️ Architecture

```
[ Stremio / Nuvio ]
        │
        ▼ (1) Requests subtitle for a movie (e.g. Backrooms - tt26657236)
[ SubSense+ Addon (FastAPI) ]
        │
        ├──► (2) Fetches original subtitle from SubSense
        ├──► (3) Fetches jumpscares: WhenJumpScare.com -> Fallback to NotScare.me
        │
        ▼ (4) Injects yellow warning tag 5 seconds before scare
        │     ⚠️ Jumpscare ⚠️
        │     "Don't open that door!"
        │
        ▼ (5) Serves modified subtitle back to player
[ Media Player ]
```

---

## 📦 Project Structure
```
jumpscare-stremio-addon/
├── main.py                  # FastAPI server (Stremio Addon Protocol & Subtitle Proxy)
├── injector.py              # SRT/VTT parser & subtitle merging engine
├── scraper.py               # WhenJumpScare scraper & Cinemeta metadata resolver
├── jumpscares_cache.json    # Local cache for movie jumpscare timestamps
├── templates/
│   └── configure.html       # Web configuration dashboard
├── requirements.txt         # Dependencies
└── README.md
```

---

## 💻 Running Locally

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Server
```bash
python main.py
```
The server will start at `http://127.0.0.1:7000`.

#### Optional CLI Arguments (Debugging & Testing):
* **`-v` / `--verbose`:** Enables detailed debugging output, showing the full numbered list of jumpscare timestamps, intensity, and trigger times in your terminal.
* **`--no-cache`:** Disables local cache to force live scraping from WhenJumpScare and NotScare for every request.
* **`--tmdb-key <key>`:** Sets your TMDB API key directly from CLI (or set via `TMDB_API_KEY` environment variable).
* **`--port <port>`:** Custom port (default: 7000).

```bash
# Example: Run with full timestamps debugging, live scraping, and TMDB key:
python main.py -v --no-cache --tmdb-key YOUR_TMDB_API_KEY
```

### 3. Open Configuration Page
In your browser, visit:
👉 **`http://127.0.0.1:7000/configure`**

* Paste your custom SubSense manifest URL (or leave blank for default).
* Choose your preferred warning lead time (default: 5 seconds).
* Click **"Install to Stremio / Nuvio"** or copy the manifest link.

---

## 🌐 Deploy to Cloud (Free 24/7 Hosting)
To use the addon on Android TV and mobile without needing your PC on:

### Option A: Render.com (Free)
1. Push this folder to a GitHub repository.
2. Go to [render.com](https://render.com) and create a **New Web Service**.
3. Select your repository and set:
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Once deployed, copy your Render URL:
   `https://your-service.onrender.com/manifest.json`

### Option B: Hugging Face Spaces (Free)
1. Create a new Space on [huggingface.co/spaces](https://huggingface.co/spaces) with **FastAPI** or **Docker**.
2. Upload the project files (`main.py`, `injector.py`, `scraper.py`, `requirements.txt`, `templates/`).
3. Your Space will build and provide a public HTTPS URL.

---

## 📱 Installation in Stremio & Nuvio

### In Stremio:
1. Open Stremio -> Go to **Add-ons**.
2. Paste the manifest link (e.g. `http://127.0.0.1:7000/manifest.json`) in the search bar.
3. Click **Install**.

### In Nuvio:
1. Open Nuvio -> **Settings** -> **Add-ons / Plugins**.
2. Select **Add from URL**.
3. Paste the manifest URL and save.

During playback, select your preferred subtitle track provided by **`SubSense+`**!

"""Constants: channel list, output paths, API key."""

import os

from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Any of: youtube.com/@handle, youtube.com/channel/UC..., youtube.com/user/name.
# Legacy youtube.com/c/name URLs are not resolvable by the API; use the @handle instead.
CHANNEL_URLS = [
    'https://www.youtube.com/@MrBeast',
    'https://www.youtube.com/@mkbhd',
    'https://www.youtube.com/@NickDiGiovanni'
    
]

# Only videos published within this window are pulled (uploads are paged newest-first
# and paging stops at the cutoff). A channel posting daily costs ~15 quota units per run.
LOOKBACK_DAYS = 365

# Where CSVs go. Default is data/raw inside the repo (gitignored). To share with the team,
# point this at a Google Drive for Desktop folder instead, e.g.
# DATA_DIR = os.path.expanduser("~/Library/CloudStorage/GoogleDrive-<acct>/My Drive/DSO 585/Project/data")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
VIDEOS_PATH = os.path.join(DATA_DIR, "videos.csv")
SNAPSHOTS_PATH = os.path.join(DATA_DIR, "engagement_snapshots.csv")
CHANNELS_PATH = os.path.join(DATA_DIR, "channels.csv")
TRAITS_PATH = os.path.join(os.path.dirname(DATA_DIR), "interim", "video_traits.csv")

# --- Trait tagging (Gemini, watches the YouTube video directly) ---
TAGGING_MODEL = "gemini-3.8-flash"
TAGGING_PROMPT_VERSION = "v1"   # bump when traits.py or the prompt changes; rows are keyed on it
# Free tier allows 8 hours of YouTube video per day; stop the run at 7.5h to leave margin.
DAILY_VIDEO_SECONDS = 7.5 * 3600
# Videos longer than this are scored on their first MAX_VIDEO_SECONDS only (caps tokens).
MAX_VIDEO_SECONDS = 30 * 60
# Several videos go in one request (API allows 10). Batch is capped by total video time to
# stay well inside the 1M-token context (~100 tokens per second of video).
MAX_VIDEOS_PER_REQUEST = 10
MAX_SECONDS_PER_REQUEST = 2 * 3600
SECONDS_BETWEEN_REQUESTS = 4

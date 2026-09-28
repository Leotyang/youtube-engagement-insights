"""Constants: channel list, output paths, API key."""

import os

from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

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

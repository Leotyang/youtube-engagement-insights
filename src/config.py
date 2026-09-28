"""Shared constants: secrets, channel list, trait taxonomy, file paths.

Works both locally (.env via python-dotenv) and in Colab (Secrets tab via
google.colab.userdata). Import as `from src import config` with the repo root on sys.path.
"""

import os

from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(PROJECT_DIR, "data", "raw")
INTERIM_DIR = os.path.join(PROJECT_DIR, "data", "interim")
PROCESSED_DIR = os.path.join(PROJECT_DIR, "data", "processed")
for data_dir in [RAW_DIR, INTERIM_DIR, PROCESSED_DIR]:
    os.makedirs(data_dir, exist_ok=True)

VIDEOS_PATH = os.path.join(RAW_DIR, "videos.csv")
SNAPSHOTS_PATH = os.path.join(RAW_DIR, "engagement_snapshots.csv")
TAGGED_VIDEOS_PATH = os.path.join(INTERIM_DIR, "videos_tagged.csv")


def get_secret(name):
    # Colab stores secrets in its Secrets tab, not env vars; fall through to .env locally.
    try:
        from google.colab import userdata
        value = userdata.get(name)
        if value:
            return value
    except Exception:
        pass
    return os.environ.get(name)


YOUTUBE_API_KEY = get_secret("YOUTUBE_API_KEY")
ANTHROPIC_API_KEY = get_secret("ANTHROPIC_API_KEY")

# Channel IDs to pull (the "UC..." string in a channel's URL or page source).
# Handles like "@mkbhd" are not accepted here; convert with youtube_api.channel_id_from_handle().
CHANNEL_IDS = [
    # "UCBJycsmduvYEL83R_U4JriQ",  # example: Marques Brownlee (MKBHD)
]

# Cap per channel so a huge back-catalog doesn't eat the 10,000-unit daily quota.
MAX_VIDEOS_PER_CHANNEL = 200

# Trait taxonomy per README §3c — the fixed schema every video is tagged against.
TRAIT_TAXONOMY = {
    "topic": "Primary subject matter of the video (e.g. gaming, cooking, finance).",
    "format": "Structural format (e.g. tutorial, vlog, listicle, reaction, review).",
    "hashtags_tags": "Notable hashtags/tags used and their apparent purpose.",
    "creator_background": "Observable creator persona/background signals (e.g. solo, duo, expert framing).",
    "theme": "Overarching narrative or emotional theme (e.g. humor, inspiration, controversy).",
    "industry_niche": "Broader industry/niche the video belongs to.",
}

# Tagging is a short classification call per video. Sonnet 5.5 is the current mid-tier;
# claude-haiku-4-5 is the cheaper option once the taxonomy is stable and volume goes up.
TAGGING_MODEL = "claude-sonnet-5-5"
TAGGING_PROMPT_VERSION = "v1"

"""Settings maintained by hand: where things live (sheet, BigQuery, local files), the scope of what gets pulled
and tagged, the tagging model, and the budget. Calibrated tuning (request sizing, retries, batching) lives at
the top of the script that uses it."""

import os

from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# The team Google Sheet holds the creator list (tab SHEET_TAB: Channel Name / URL / Genre / Size)
# and the trait list (tab TRAITS_TAB: Category / Scale / Trait / Definition). It must be shared
# with the service account. The creator list decides which channels exist in BigQuery.
SHEET_ID = "1Kj8agduMgsqmKxH6e_7Bhzcbthilx9GxStnHAIUX3Ew"
SHEET_TAB = "Channel Selection"
TRAITS_TAB = "Content Traits"

GCP_PROJECT_ID = "dso-585-project-16336"
BQ_DATASET = "youtube"
BQ_LOCATION = "US"

# Ingest pulls each channel's videos published in this window.
LOOKBACK_DAYS = 365

# Local CSV copies, written only by --env local runs. Default is data/ inside the repo (gitignored).
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CHANNELS_PATH = os.path.join(DATA_DIR, "channels.csv")
VIDEOS_PATH = os.path.join(DATA_DIR, "videos.csv")
VIDEO_SNAPSHOTS_PATH = os.path.join(DATA_DIR, "video_daily_snapshots.csv")
CHANNEL_SNAPSHOTS_PATH = os.path.join(DATA_DIR, "channel_daily_snapshots.csv")
LLM_TAGGED_PATH = os.path.join(DATA_DIR, "llm_tagged.csv")

# Trait tagging: Gemini on Vertex AI, authenticated as the service account (Agent Platform User role).
# The 3.x models are only served from the "global" location.
TAGGING_MODEL = "gemini-3.1-flash-lite"
TAGGING_LOCATION = "global"

# Which videos get tagged: each channel's MAX_VIDEOS_PER_CHANNEL most recent uploads no longer than
# MAX_VIDEO_SECONDS. Raising either later tags only the newly eligible videos.
MAX_VIDEO_SECONDS = 30 * 60
MAX_VIDEOS_PER_CHANNEL = 50

# A tagging run stops before its estimated spend passes this.
MAX_SPEND_PER_RUN_USD = 25

# List prices, $ per 1M tokens (Google's Gemini pricing page, 2026-10-15); update when Google changes them.
INPUT_PRICE_PER_M = 0.25
OUTPUT_PRICE_PER_M = 1.50

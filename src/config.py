"""Constants: sheet + BigQuery locations, ingest window, trait-tagging knobs, API key."""

import os

from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# The team Google Sheet holds the creator list (tab SHEET_TAB: Channel Name / URL / Genre / Size)
# and the trait list (tab TRAITS_TAB: Category / Scale / Trait / Definition). It must be shared
# with the service account. See src/sheet.py and src/traits.py.
SHEET_ID = "1Kj8agduMgsqmKxH6e_7Bhzcbthilx9GxStnHAIUX3Ew"
SHEET_TAB = "Channel Selection"
TRAITS_TAB = "Content Traits"

# BigQuery destination. Set BQ_DATASET=youtube_dev in the environment to run any script against a
# separate dev dataset (created on first use) instead of the production tables.
GCP_PROJECT_ID = "dso-585-project-16336"
BQ_DATASET = os.getenv("BQ_DATASET", "youtube")
BQ_LOCATION = "US"

# Only videos published within this window are pulled (uploads are paged newest-first
# and paging stops at the cutoff). A channel posting daily costs ~15 quota units per run.
LOOKBACK_DAYS = 365

# Ingest deletes every row of a channel that is no longer on the sheet. Snapshot history can't be
# re-pulled, so a run that would remove more channels than this stops instead (likely a sheet
# mistake); pass --allow-mass-removal to go ahead.
MAX_CHANNELS_REMOVED_PER_RUN = 5

# Where CSVs go. Default is data/raw inside the repo (gitignored). To share with the team,
# point this at a Google Drive for Desktop folder instead, e.g.
# DATA_DIR = os.path.expanduser("~/Library/CloudStorage/GoogleDrive-<acct>/My Drive/DSO 585/Project/data")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
VIDEOS_PATH = os.path.join(DATA_DIR, "videos.csv")
VIDEO_SNAPSHOTS_PATH = os.path.join(DATA_DIR, "video_daily_snapshots.csv")
CHANNELS_PATH = os.path.join(DATA_DIR, "channels.csv")
LLM_TAGGED_PATH = os.path.join(os.path.dirname(DATA_DIR), "interim", "llm_tagged.csv")
MODEL_MATRIX_PATH = os.path.join(os.path.dirname(DATA_DIR), "processed", "model_matrix.csv")

# Analysis freeze: notebooks use only videos with llm_tagged.tagged_at before this instant, so results stay
# reproducible while the nightly tagger keeps adding rows. 2026-10-15 15:30 PT.
ANALYSIS_TAGGED_BEFORE = "2026-10-15 22:30:00 UTC"

# Channels to leave out of trait tagging (ingest still pulls them, e.g. for EDA). Keyed by
# YouTube channel id -> why; their traits wouldn't be something a creator can act on.
TAGGING_SKIP_CHANNELS = {
    "UCrp_UI8XtuYfpiqluWLD7Lw": "CNBC Television - news (11.8k videos/yr)",
}

# --- Trait tagging (Gemini on Vertex AI / Agent Platform; it watches the YouTube video directly) ---
# Auth is the same service account (needs the Agent Platform User role); no API key.
# gemini-3.1-flash-lite won the 2026-10-15 pilot: ~3x cheaper than gemini-3.8-flash and much
# closer to the team's manual tags. The 3.x models are only served from the "global" location.
TAGGING_MODEL = "gemini-3.1-flash-lite"
TAGGING_LOCATION = "global"

# Which videos get tagged. Videos longer than MAX_VIDEO_SECONDS are not tagged at all; of the
# rest, each channel's MAX_VIDEOS_PER_CHANNEL most recent are. Raising either later tags only the
# newly eligible videos (anything already in llm_tagged is skipped).
MAX_VIDEO_SECONDS = 30 * 60
MAX_VIDEOS_PER_CHANNEL = 50

# Request sizing. One video per request: on 2026-10-15 half of the 3-video requests failed on GitHub (504
# deadline / 429) and fell back to one video at a time, making a run ~3x slower than single requests
# (74 videos/h vs ~10-29x real time per single request). A single video's request is what reliably succeeds.
MAX_VIDEOS_PER_REQUEST = 1
MAX_SECONDS_PER_REQUEST = 45 * 60
# Requests in flight at once. Each waits ~0.5-2 min on Gemini; more in flight is faster but raises the odds of
# 429 "resource exhausted" from Google's shared capacity (8 on 2026-10-15 got a lot of them, 3 was too slow).
PARALLEL_REQUESTS = 5
SECONDS_BETWEEN_REQUESTS = 3   # stagger between starting requests
REQUEST_TIMEOUT_SECONDS = 600  # a request that hangs this long is abandoned (and retried)
# Retries for 429/5xx/timeouts/dropped connections: waits of ~10, 20, 40, 80 s (each randomized +-50%) between attempts.
MAX_REQUEST_ATTEMPTS = 5
RETRY_BASE_SECONDS = 10
# Results are written to BigQuery in groups: every SAVE_EVERY_ROWS videos or SAVE_EVERY_SECONDS, whichever is first.
# One write per video would run into BigQuery's daily limit on load jobs per table (about 1,500).
SAVE_EVERY_ROWS = 10
SAVE_EVERY_SECONDS = 120
# Stop the run (next run resumes) after this many batches in a row tag nothing.
MAX_CONSECUTIVE_FAILED_BATCHES = 3

# Run guards: stop before the estimated spend or wall time passes these (GitHub jobs die at 6h).
MAX_SPEND_PER_RUN_USD = 25
MAX_RUNTIME_MINUTES = 300

# Cost model. Prices are list $/1M tokens from Google's Gemini API pricing page (2026-10-15);
# Vertex billing may differ. Token rates were measured in the pilot.
INPUT_PRICE_PER_M = 0.25
OUTPUT_PRICE_PER_M = 1.50
VIDEO_TOKENS_PER_SECOND = 91
PROMPT_TOKENS_PER_REQUEST = 4000
OUTPUT_TOKENS_PER_VIDEO = 800

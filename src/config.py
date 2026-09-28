"""Shared constants: channel list, file paths, and API key loading."""

import os
from dotenv import load_dotenv

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Channel IDs to pull (the "UC..." string in a channel's URL or page source).
# Fill this in as we choose training channels. Handles like "@mkbhd" are not
# accepted here; convert them with youtube_api.channel_id_from_handle().
CHANNEL_IDS = [
    # "UCBJycsmduvYEL83R_U4JriQ",  # example: Marques Brownlee (MKBHD)
]

# Cap per channel so a huge back-catalog doesn't eat the daily quota.
MAX_VIDEOS_PER_CHANNEL = 200

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
VIDEOS_PATH = os.path.join(RAW_DIR, "videos.csv")
SNAPSHOTS_PATH = os.path.join(RAW_DIR, "engagement_snapshots.csv")

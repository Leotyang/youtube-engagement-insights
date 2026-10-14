"""Read the team's creator list from the Google Sheet (tab SHEET_TAB, columns A:D).

Auth is Application Default Credentials: GOOGLE_APPLICATION_CREDENTIALS must point at the
service-account key, and the sheet must be shared with that service account's email.
"""

import os
import re
import sys

import google.auth
import pandas as pd
from googleapiclient.discovery import build

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SHEET_ID, SHEET_TAB

# Scheme, www./m. and everything after the channel id are all optional, so
# "youtube.com/@x", "https://www.youtube.com/@x/videos?si=1" and a bare "@x" all resolve.
CHANNEL_PATTERN = re.compile(
    r"^\s*(?:(?:https?://)?(?:(?:www|m)\.)?youtube\.com/)?(@[\w.\-%]+|channel/UC[\w\-]+|user/[\w.\-]+)", re.IGNORECASE
)


def get_creators():
    """DataFrame with team_name, channel_url, team_genre, team_size for every row whose URL
    the YouTube API can resolve (@handle, /channel/UC..., /user/...), normalized to https://www.youtube.com/<that>.
    Others (search links, legacy /c/ links) are skipped with a warning."""
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    rows = build("sheets", "v4", credentials=credentials).spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{SHEET_TAB}'!A:D"
    ).execute().get("values", [])

    creators = []
    for row in rows[1:]:
        # The Sheets API drops trailing empty cells, so short rows need padding.
        name, url, genre, size = [cell.strip() for cell in row + [""] * (4 - len(row))]
        if not url:
            print(f"Sheet: no URL for '{name}', skipping")
            continue
        match = CHANNEL_PATTERN.match(url)
        if not match:
            print(f"Sheet: '{name}' URL isn't an @handle, /channel/ or /user/ link, skipping: {url}")
            continue
        url = "https://www.youtube.com/" + match.group(1)
        creators.append({"team_name": name, "channel_url": url, "team_genre": genre, "team_size": size})
    return pd.DataFrame(creators)

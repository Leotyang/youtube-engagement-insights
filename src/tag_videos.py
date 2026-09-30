"""Score every video in videos.csv on the traits in traits.py using Gemini, which watches
the YouTube videos directly (frames + audio) from their public URLs.

Videos are sent several per request (see MAX_VIDEOS_PER_REQUEST / MAX_SECONDS_PER_REQUEST);
each video block is named with its video ID and the JSON response is keyed by those IDs.

Resumable: skips videos already scored under the current TAGGING_PROMPT_VERSION, stops when
the day's video budget (DAILY_VIDEO_SECONDS) is used up or the API stays rate-limited, and
appends to data/interim/video_traits.csv after every request.

Usage:  python src/tag_videos.py            # tag everything remaining (within budget)
        python src/tag_videos.py 5          # tag at most 5 videos (for a spot check)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
from google import genai

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (GEMINI_API_KEY, TAGGING_MODEL, TAGGING_PROMPT_VERSION, DAILY_VIDEO_SECONDS,
                    MAX_VIDEO_SECONDS, MAX_VIDEOS_PER_REQUEST, MAX_SECONDS_PER_REQUEST,
                    SECONDS_BETWEEN_REQUESTS, VIDEOS_PATH, TRAITS_PATH)
from traits import TRAITS, SCALE

if not GEMINI_API_KEY:
    sys.exit("GEMINI_API_KEY is empty. Get one at https://aistudio.google.com/apikey and add it to .env.")
if not os.path.exists(VIDEOS_PATH):
    sys.exit(f"{VIDEOS_PATH} not found. Run python src/ingest.py first.")

max_videos = int(sys.argv[1]) if len(sys.argv) > 1 else None

PROMPT = """You are scoring {n} YouTube videos against a fixed list of content traits. Each video
block is named with its video ID; score each video independently.

{scale}

Traits to score:
{traits}

Videos:
{videos}

Watch every video, then return a JSON object with one key per video ID, each holding an
object with exactly one integer (0-4) per trait key."""

TRAIT_SCHEMA = {
    "type": "object",
    "properties": {trait: {"type": "integer", "minimum": 0, "maximum": 4} for trait in TRAITS},
    "required": list(TRAITS),
}

client = genai.Client(api_key=GEMINI_API_KEY)

df_videos = pd.read_csv(VIDEOS_PATH)
df_done = pd.read_csv(TRAITS_PATH) if os.path.exists(TRAITS_PATH) else pd.DataFrame(columns=["video_id", "prompt_version"])
already = set(df_done.loc[df_done["prompt_version"] == TAGGING_PROMPT_VERSION, "video_id"])
df_todo = df_videos[~df_videos["id"].isin(already)].sort_values("snippet.publishedAt", ascending=False)
if max_videos:
    df_todo = df_todo.head(max_videos)
df_todo = df_todo.assign(scored_seconds=df_todo["duration_seconds"].clip(upper=MAX_VIDEO_SECONDS))
print(f"{len(already)} already tagged under {TAGGING_PROMPT_VERSION}; {len(df_todo)} to do this run")

# Greedy batching: newest first, cut a batch when it hits the count or duration cap.
batches = []
current = []
current_seconds = 0
for _, video in df_todo.iterrows():
    if current and (len(current) >= MAX_VIDEOS_PER_REQUEST or current_seconds + video["scored_seconds"] > MAX_SECONDS_PER_REQUEST):
        batches.append(current)
        current = []
        current_seconds = 0
    current.append(video)
    current_seconds += video["scored_seconds"]
if current:
    batches.append(current)

os.makedirs(os.path.dirname(TRAITS_PATH), exist_ok=True)
seconds_used = 0
tagged = 0
for batch_number, batch in enumerate(batches, start=1):
    batch_seconds = sum(video["scored_seconds"] for video in batch)
    if seconds_used + batch_seconds > DAILY_VIDEO_SECONDS:
        print(f"Daily video budget reached ({seconds_used / 3600:.1f}h). Re-run tomorrow to continue.")
        break

    video_blocks = []
    video_lines = []
    for video in batch:
        block = {"type": "video", "uri": f"https://www.youtube.com/watch?v={video['id']}", "name": video["id"]}
        if video["duration_seconds"] > MAX_VIDEO_SECONDS:
            block["processing"] = {"type": "static", "start_offset": "0s", "end_offset": f"{MAX_VIDEO_SECONDS}s"}
        video_blocks.append(block)
        description = str(video["snippet.description"] if pd.notna(video["snippet.description"]) else "")[:300].replace("\n", " ")
        video_lines.append(f"- {video['id']}: \"{video['snippet.title']}\" — {description}")

    prompt = PROMPT.format(
        n=len(batch),
        scale=SCALE,
        traits="\n".join(f"- {trait}: {definition}" for trait, definition in TRAITS.items()),
        videos="\n".join(video_lines),
    )
    response_schema = {
        "type": "object",
        "properties": {video["id"]: TRAIT_SCHEMA for video in batch},
        "required": [video["id"] for video in batch],
    }

    scores_by_id = None
    quota_hit = False
    for attempt in range(3):
        try:
            interaction = client.interactions.create(
                model=TAGGING_MODEL,
                input=video_blocks + [{"type": "text", "text": prompt}],
                response_format={"type": "text", "mime_type": "application/json", "schema": response_schema},
            )
            scores_by_id = json.loads(interaction.output_text)
            break
        except Exception as error:
            # The interactions client raises its own error classes; the HTTP status is only
            # reliably present in the message text ("Error code: 429 ..."), so match on that.
            is_busy = "503" in str(error) or "429" in str(error)
            if not is_busy:
                print(f"Batch {batch_number} failed ({type(error).__name__}): {str(error)[:200]}")
                break
            if attempt == 2:
                quota_hit = "429" in str(error)
                break
            print(f"API busy/rate-limited ({type(error).__name__}), retrying in {60 * (attempt + 1)}s...")
            time.sleep(60 * (attempt + 1))
    if quota_hit:
        print("Still rate-limited after retries; daily quota is likely used up. Re-run tomorrow to continue.")
        break
    if scores_by_id is None:
        continue

    tagged_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for video in batch:
        scores = scores_by_id.get(video["id"])
        if not scores:
            print(f"  No scores returned for {video['id']}; it will be retried next run")
            continue
        rows.append({"video_id": video["id"], "channel_id": video["snippet.channelId"], "title": video["snippet.title"],
                     **{f"trait_{trait}": scores.get(trait) for trait in TRAITS},
                     "model": TAGGING_MODEL, "prompt_version": TAGGING_PROMPT_VERSION,
                     "scored_seconds": video["scored_seconds"], "tagged_at": tagged_at})
        print(f"  {video['snippet.channelTitle']} | {video['snippet.title'][:55]} -> {scores}")
    pd.DataFrame(rows).to_csv(TRAITS_PATH, mode="a", index=False, header=not os.path.exists(TRAITS_PATH))

    seconds_used += batch_seconds
    tagged += len(rows)
    print(f"Batch {batch_number}/{len(batches)}: {len(rows)} videos, {batch_seconds / 60:.0f} min of video, 1 request")
    time.sleep(SECONDS_BETWEEN_REQUESTS)

print(f"Tagged {tagged} videos ({seconds_used / 3600:.2f}h of video) in {min(batch_number, len(batches)) if batches else 0} request(s) -> {TRAITS_PATH}")

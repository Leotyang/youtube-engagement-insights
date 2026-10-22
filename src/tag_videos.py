"""Tag videos with content traits using Gemini on Vertex AI (Agent Platform), which watches each
YouTube video directly (frames + audio) from its public URL.

Which videos: rows of BigQuery `videos` no longer than MAX_VIDEO_SECONDS, outside
TAGGING_SKIP_CHANNELS, among each channel's MAX_VIDEOS_PER_CHANNEL most recent such uploads, and
not yet in `llm_tagged`. The queue runs in rank order (every
channel's newest video, then every channel's 2nd newest, ...), so a run that stops early still
leaves a balanced sample. Raising either cap later tags only the newly eligible videos.

Traits come from the team sheet (traits.py). Linear traits are scored 0-4, Binary traits 0/1.
Results are appended to BigQuery `llm_tagged`, one row per video, with the trait scores as columns plus
model, a fingerprint of the trait list, and token usage of the request. Rows are written in small groups
(every SAVE_EVERY_ROWS videos or SAVE_EVERY_SECONDS, whichever comes first, and when the run ends or is
cancelled), which keeps the number of BigQuery load jobs per day well under its limit.

Requests run PARALLEL_REQUESTS at a time. A run stops early (the next run resumes) when it nears
MAX_SPEND_PER_RUN_USD or MAX_RUNTIME_MINUTES, or after MAX_CONSECUTIVE_FAILED_BATCHES batches in
a row tag nothing (usually Gemini capacity errors that outlast the retries).

Usage:
  python src/tag_videos.py --dry-run           queue size, video hours, estimated cost; no API calls
  python src/tag_videos.py --max-videos 3      small test
  python src/tag_videos.py                     whole queue (stops at MAX_SPEND_PER_RUN_USD / MAX_RUNTIME_MINUTES)
  --env local (default) also appends a CSV backup; --env github writes BigQuery only
"""

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone

import pandas as pd
from google import genai
from google.cloud import bigquery
from google.genai import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bigquery_io import get_client as get_bq_client, query_rows, set_column_descriptions, write_table
from config import (GCP_PROJECT_ID, BQ_DATASET, TAGGING_MODEL, TAGGING_LOCATION,
                    MAX_VIDEO_SECONDS, MAX_VIDEOS_PER_CHANNEL, MAX_VIDEOS_PER_REQUEST, MAX_SECONDS_PER_REQUEST,
                    SECONDS_BETWEEN_REQUESTS, PARALLEL_REQUESTS, REQUEST_TIMEOUT_SECONDS, MAX_CONSECUTIVE_FAILED_BATCHES,
                    MAX_REQUEST_ATTEMPTS, RETRY_BASE_SECONDS, SAVE_EVERY_ROWS, SAVE_EVERY_SECONDS,
                    MAX_SPEND_PER_RUN_USD, MAX_RUNTIME_MINUTES, INPUT_PRICE_PER_M,
                    OUTPUT_PRICE_PER_M, VIDEO_TOKENS_PER_SECOND, PROMPT_TOKENS_PER_REQUEST, OUTPUT_TOKENS_PER_VIDEO,
                    TAGGING_SKIP_CHANNELS, LLM_TAGGED_PATH)
from traits import get_traits

parser = argparse.ArgumentParser()
parser.add_argument("--env", choices=["local", "github"], default="local")
parser.add_argument("--max-videos", type=int, default=None, help="tag at most this many videos this run")
parser.add_argument("--dry-run", action="store_true", help="print the queue and cost estimate, call nothing")
args = parser.parse_args()

LINEAR_SCALE = """Score every [0-4] trait on this universal scale. Read "X" as the trait being scored.
0 - Absent. Nothing in the video is X. A viewer would not associate the video with X.
1 - Incidental. The creator did not intend X, but some part of the video has X value implicitly.
2 - Explicit segment. The video as a whole is not X, but at least one part is deliberately X and signaled as such.
3 - Featured. X is one of the video's stated purposes; a substantial dedicated portion is X, but the video also does other things.
4 - Defining. The video is X and nothing else. Remove X and there is no video left.
Tie-breakers: intent beats accident (explicit framing -> at least 2); coverage moves you up (segment 2, major portion 3, whole 4); when torn between two levels, pick the lower."""

BINARY_SCALE = ("Binary traits are marked [0/1]: score 1 if the trait is present anywhere in the video, even briefly; "
                "score 0 if absent. When unsure, score 0.")

PROMPT = """You are scoring {n} YouTube video(s) against a fixed list of content traits. Each video is preceded by a text
line giving its video ID; score each video independently.

{linear_scale}

{binary_scale}

Traits to score:
{traits}

Videos:
{videos}

Watch every video, then return a JSON object with one key per video ID, each holding an object with exactly one integer
per trait key (0-4 for [0-4] traits, 0 or 1 for [0/1] traits)."""

traits = get_traits()
trait_columns = [trait["column"] for trait in traits]
# Fingerprint of the trait list, so a sheet edit can't silently mix two trait sets in llm_tagged.
traits_hash = hashlib.sha256(json.dumps(traits, sort_keys=True).encode()).hexdigest()[:12]
trait_lines = "\n".join(
    f"- {trait['column']} [{'0/1' if trait['scale'] == 'binary' else '0-4'}]: {trait['definition']}" for trait in traits
)
trait_schema = {
    "type": "object",
    "properties": {trait["column"]: {"type": "integer", "minimum": 0, "maximum": 1 if trait["scale"] == "binary" else 4} for trait in traits},
    "required": trait_columns,
}
print(f"{len(traits)} traits from the sheet ({sum(trait['scale'] == 'binary' for trait in traits)} binary), "
      f"traits hash {traits_hash}")

bq_client = get_bq_client()
tagged_table = f"{GCP_PROJECT_ID}.{BQ_DATASET}.llm_tagged"
hashes_in_table = [row.traits_hash for row in query_rows(bq_client, f"SELECT DISTINCT traits_hash FROM `{tagged_table}`")]
if hashes_in_table and traits_hash not in hashes_in_table:
    sys.exit(f"The trait list in the sheet changed since the rows in llm_tagged were tagged (hash {traits_hash}, "
             f"table has {hashes_in_table}). Tagging now would mix two trait sets. Revert the sheet edit, or "
             f"clear llm_tagged to re-tag every video with the new list.")

queue_rows = query_rows(bq_client, f"""
    SELECT id, snippet_channelId AS channel_id, snippet_channelTitle AS channel_title, snippet_title AS title,
           snippet_description AS description, duration_seconds, channel_rank
    FROM (
      SELECT *, ROW_NUMBER() OVER (PARTITION BY snippet_channelId ORDER BY snippet_publishedAt DESC) AS channel_rank
      FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.videos`
      WHERE duration_seconds > 0 AND duration_seconds <= @max_seconds AND snippet_channelId NOT IN UNNEST(@skip)
    )
    WHERE channel_rank <= @per_channel
    ORDER BY channel_rank, channel_id""", [
    bigquery.ScalarQueryParameter("max_seconds", "FLOAT64", MAX_VIDEO_SECONDS),
    bigquery.ArrayQueryParameter("skip", "STRING", list(TAGGING_SKIP_CHANNELS)),
    bigquery.ScalarQueryParameter("per_channel", "INT64", MAX_VIDEOS_PER_CHANNEL),
])
if not queue_rows:
    sys.exit("No eligible videos in BigQuery `videos`. Run python src/ingest.py first.")
df_queue = pd.DataFrame([dict(row.items()) for row in queue_rows])
tagged_ids = [row.id for row in query_rows(bq_client, f"SELECT id FROM `{tagged_table}`")]
eligible = len(df_queue)
df_queue = df_queue[~df_queue["id"].isin(tagged_ids)]
if args.max_videos is not None:
    df_queue = df_queue.head(args.max_videos)

# Greedy batching in queue order: cut a request at MAX_VIDEOS_PER_REQUEST or MAX_SECONDS_PER_REQUEST.
batches = []
current = []
current_seconds = 0
for _, video in df_queue.iterrows():
    if current and (len(current) >= MAX_VIDEOS_PER_REQUEST or current_seconds + video["duration_seconds"] > MAX_SECONDS_PER_REQUEST):
        batches.append(current)
        current = []
        current_seconds = 0
    current.append(video)
    current_seconds += video["duration_seconds"]
if current:
    batches.append(current)


def estimate_cost(video_seconds, n_videos, n_requests):
    input_tokens = video_seconds * VIDEO_TOKENS_PER_SECOND + n_requests * PROMPT_TOKENS_PER_REQUEST
    return input_tokens / 1e6 * INPUT_PRICE_PER_M + n_videos * OUTPUT_TOKENS_PER_VIDEO / 1e6 * OUTPUT_PRICE_PER_M


queue_seconds = df_queue["duration_seconds"].sum() if len(df_queue) else 0
print(f"Eligible: {eligible} videos (<= {MAX_VIDEO_SECONDS / 60:.0f} min, top {MAX_VIDEOS_PER_CHANNEL} per channel, "
      f"{len(TAGGING_SKIP_CHANNELS)} channel(s) skipped); already tagged: {len(tagged_ids)}")
print(f"This run: {len(df_queue)} videos from {df_queue['channel_id'].nunique() if len(df_queue) else 0} channels, "
      f"{queue_seconds / 3600:.1f} h of video, {len(batches)} requests, "
      f"est ${estimate_cost(queue_seconds, len(df_queue), len(batches)):.2f} (cap ${MAX_SPEND_PER_RUN_USD} per run)")
if args.dry_run or not batches:
    sys.exit(0)

# Each request gets REQUEST_TIMEOUT_SECONDS; a hung call raises instead of blocking the run forever.
client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location=TAGGING_LOCATION,
                      http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_SECONDS * 1000))
run_started = time.time()


def minutes_left():
    return MAX_RUNTIME_MINUTES - (time.time() - run_started) / 60


RETRYABLE_ERROR_TYPES = ["RemoteProtocolError", "ConnectError", "ConnectTimeout", "ReadError", "ReadTimeout", "WriteError", "PoolTimeout"]


def is_retryable(error):
    """Capacity/rate errors (429, 500, 503, 504), timeouts, and dropped connections are worth retrying.
    The SDK's error classes vary by version, so the HTTP status is matched in the message text."""
    message = str(error).lower()
    return (type(error).__name__ in RETRYABLE_ERROR_TYPES or re.search(r"\b(429|500|503|504)\b", message) is not None
            or "timed out" in message or "disconnected" in message or "connection reset" in message)


def call_gemini(videos):
    """Score a list of videos in one request. Returns (scores_by_id, usage_metadata), or (None, None) on failure."""
    contents = []
    for video in videos:
        contents.append(types.Part.from_text(text=f"Video ID: {video['id']}"))
        contents.append(types.Part.from_uri(file_uri=f"https://www.youtube.com/watch?v={video['id']}", mime_type="video/mp4"))
    video_lines = "\n".join(
        f"- {video['id']}: \"{video['title']}\" - {video['description'][:300] if isinstance(video['description'], str) else ''}".replace("\n", " ")
        for video in videos
    )
    contents.append(types.Part.from_text(text=PROMPT.format(
        n=len(videos), linear_scale=LINEAR_SCALE, binary_scale=BINARY_SCALE, traits=trait_lines, videos=video_lines)))
    schema = {"type": "object", "properties": {video["id"]: trait_schema for video in videos},
              "required": [video["id"] for video in videos]}
    if minutes_left() < REQUEST_TIMEOUT_SECONDS / 60:
        return None, None
    for attempt in range(MAX_REQUEST_ATTEMPTS):
        try:
            response = client.models.generate_content(
                model=TAGGING_MODEL, contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema),
            )
            return json.loads(response.text), response.usage_metadata
        except Exception as error:
            message = str(error)
            # Jitter keeps the parallel workers from retrying in lockstep against the same capacity limit.
            wait_seconds = RETRY_BASE_SECONDS * 2 ** attempt * random.uniform(0.5, 1.5)
            if is_retryable(error) and attempt < MAX_REQUEST_ATTEMPTS - 1 and minutes_left() > wait_seconds / 60 + REQUEST_TIMEOUT_SECONDS / 60:
                print(f"  {videos[0]['id']}...: busy/rate-limited/timeout, retrying in {wait_seconds:.0f}s ({type(error).__name__}: {message[:70]})")
                time.sleep(wait_seconds)
                continue
            print(f"  {videos[0]['id']}...: request failed ({type(error).__name__}): {message[:200]}")
            return None, None


def tag_batch(batch):
    """Worker for one batch. Returns a list of (videos, scores_by_id, usage) for the requests that succeeded."""
    scores_by_id, usage = call_gemini(batch)
    if scores_by_id is not None:
        return [(batch, scores_by_id, usage)]
    requests = []
    if len(batch) > 1:
        # One unplayable video (removed, private, age-restricted) fails the whole request; isolate it.
        print(f"  Retrying a failed batch one video at a time ({', '.join(video['id'] for video in batch)})")
        for video in batch:
            single_scores, single_usage = call_gemini([video])
            if single_scores is not None:
                requests.append(([video], single_scores, single_usage))
    return requests


def save_rows(rows):
    """Append rows to BigQuery llm_tagged (and the local CSV backup)."""
    df_rows = pd.DataFrame(rows)
    df_rows[trait_columns] = df_rows[trait_columns].astype("Int64")
    write_table(bq_client, "llm_tagged", df_rows, "append")
    if args.env == "local":
        os.makedirs(os.path.dirname(LLM_TAGGED_PATH), exist_ok=True)
        df_rows.to_csv(LLM_TAGGED_PATH, mode="a", index=False, header=not os.path.exists(LLM_TAGGED_PATH))


buffer = {"rows": [], "last_save": time.time()}


def save_pending(force=False):
    """Write buffered rows once there are SAVE_EVERY_ROWS of them, SAVE_EVERY_SECONDS have passed, or force is set.
    A failed write keeps the rows buffered for the next attempt."""
    waited = time.time() - buffer["last_save"]
    if not buffer["rows"] or not (force or len(buffer["rows"]) >= SAVE_EVERY_ROWS or waited >= SAVE_EVERY_SECONDS):
        return
    for attempt in range(3):
        try:
            save_rows(buffer["rows"])
            buffer["rows"] = []
            break
        except Exception as error:
            print(f"  BigQuery save failed ({type(error).__name__}): {str(error)[:150]}; {len(buffer['rows'])} rows stay buffered")
            time.sleep(5 * (attempt + 1))
    buffer["last_save"] = time.time()


run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
spent = 0.0
tagged = 0
finished = 0
consecutive_failures = 0
stop_reason = None
next_batch = 0
# Up to PARALLEL_REQUESTS batches are in flight in worker threads; this main thread hands out batches,
# and buffers each one's results for BigQuery (all writes happen here, not in workers).
running = {}
with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as pool:
    try:
        while running or (stop_reason is None and next_batch < len(batches)):
            while stop_reason is None and next_batch < len(batches) and len(running) < PARALLEL_REQUESTS:
                batch = batches[next_batch]
                batch_seconds = sum(video["duration_seconds"] for video in batch)
                in_flight = sum(estimate_cost(seconds, len(videos), 1) for _, videos, seconds in running.values())
                if spent + in_flight + estimate_cost(batch_seconds, len(batch), 1) > MAX_SPEND_PER_RUN_USD:
                    stop_reason = f"the next request would pass the ${MAX_SPEND_PER_RUN_USD} per-run spend cap"
                    break
                if minutes_left() < REQUEST_TIMEOUT_SECONDS / 60:
                    stop_reason = f"near the {MAX_RUNTIME_MINUTES}-minute runtime limit"
                    break
                next_batch += 1
                running[pool.submit(tag_batch, batch)] = (next_batch, batch, batch_seconds)
                time.sleep(SECONDS_BETWEEN_REQUESTS)

            done, _ = wait(list(running), return_when=FIRST_COMPLETED)
            for future in done:
                batch_number, batch, batch_seconds = running.pop(future)
                tagged_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                batch_rows = []
                for request_number, (request_videos, scores, usage) in enumerate(future.result(), start=1):
                    input_tokens = usage.prompt_token_count or 0
                    output_tokens = (usage.candidates_token_count or 0) + (getattr(usage, "thoughts_token_count", None) or 0)
                    spent += input_tokens / 1e6 * INPUT_PRICE_PER_M + output_tokens / 1e6 * OUTPUT_PRICE_PER_M
                    for video in request_videos:
                        video_scores = scores.get(video["id"])
                        if not video_scores:
                            print(f"  No scores returned for {video['id']}; it stays in the queue for the next run")
                            continue
                        row = {"id": video["id"], "channel_id": video["channel_id"], "traits_hash": traits_hash,
                               "model": TAGGING_MODEL, "tagged_at": tagged_at, "video_seconds": video["duration_seconds"],
                               "request_id": f"{run_id}-{batch_number}-{request_number}", "request_videos": len(request_videos),
                               "request_input_tokens": input_tokens, "request_output_tokens": output_tokens}
                        for trait in traits:
                            value = video_scores.get(trait["column"])
                            top = 1 if trait["scale"] == "binary" else 4
                            row[trait["column"]] = value if isinstance(value, int) and 0 <= value <= top else None
                        batch_rows.append(row)
                if batch_rows:
                    buffer["rows"] += batch_rows
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                tagged += len(batch_rows)
                finished += 1
                print(f"Batch {batch_number}/{len(batches)} ({finished} done): {len(batch_rows)}/{len(batch)} tagged "
                      f"({batch_seconds / 60:.0f} min of video) | total {tagged} | spent ~${spent:.2f} | {minutes_left():.0f} min left")
                save_pending()
                if consecutive_failures >= MAX_CONSECUTIVE_FAILED_BATCHES and stop_reason is None:
                    stop_reason = f"{consecutive_failures} batches in a row tagged nothing (Gemini likely overloaded)"
    finally:
        # Also runs when the job is cancelled (Ctrl+C / GitHub's cancel signal), so finished work isn't lost.
        save_pending(force=True)

if buffer["rows"]:
    sys.exit(f"Could not write {len(buffer['rows'])} tagged rows to BigQuery; they are lost. Those videos stay in the queue.")
if stop_reason:
    print(f"Stopped early: {stop_reason}. The next run picks up the remaining queue.")
if tagged:
    set_column_descriptions(bq_client, "llm_tagged", {
        trait["column"]: f"{trait['name']} ({trait['category']}; {'0/1' if trait['scale'] == 'binary' else '0-4'}): {trait['definition']}"
        for trait in traits
    })
print(f"Done: tagged {tagged} videos in {(time.time() - run_started) / 60:.1f} min, est ${spent:.2f} "
      f"at list price -> {tagged_table}")

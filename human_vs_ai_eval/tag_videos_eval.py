"""
Model comparison on the human-tagged videos, using Leo's CURRENT tagger prompt verbatim
(Leotyang/DSO_585_project, branch leotyang/pipeline @ ea94b9b, src/tag_videos.py: LINEAR_SCALE,
BINARY_SCALE, PROMPT, "Video ID:" text part + YouTube URL part, JSON schema with 0/1 for binary traits).

Differences from production, on purpose (stated on the slide):
  * Gemini API key (AI Studio) instead of Vertex AI — same model names
  * one video per request (production also does this since 96c3f16, Oct 15)
  * Mark Rober (34 min) is tagged in full; production skips videos > 30 min entirely

Run:  python tag_videos_eval.py gemini-3.1-flash-lite 2
      python tag_videos_eval.py gemini-3.8-flash 1
Output: data/ai_tags_v2.csv (video_id, trait, score, run, model, ...)
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")  # put GEMINI_API_KEY=... in human_vs_ai_eval/.env (never commit it)
MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini-3.1-flash-lite"
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 1
VIDEOS = ["BWNOdHB8TKA", "_L1Rim7-IPo", "QX3txldu5h4", "u9KB8U9r_Wg", "bdK8Hckw3CI", "qdX3WEoo5x0",
          "oqYIu4rK_CY", "mhqzfgyzAw8", "j3YnR-yH7xU", "Jctn80QpQzM", "FYr8Pqg6npQ",
          "0Rqoe5quCJQ", "Knp90rLl3Ug", "YFe8LFCgT68", "mPakWr5s4k0", "zOeh3I4N9xk", "fyjdahqf884",
          "fkmS_QQwSL8", "ItbH0P9_0YQ", "9g-MljUBEpM", "pKC4xuem9S0"]
TITLES = {  # title + description[:300] as production passes them (description omitted: not stored locally)
    "BWNOdHB8TKA": "The Housing Market Is Completely F*d",
    "_L1Rim7-IPo": "Last Cheater Standing Wins $10,000",
    "QX3txldu5h4": "My Dogs Ordered 100 Buckets of Chicken!",
    "u9KB8U9r_Wg": "I Bought An Abandoned Church For $45K & Spent $194K Making It A Home",
    "bdK8Hckw3CI": "The Most Unexplored Places On Earth",
    "qdX3WEoo5x0": "Online Couples Meet for the First Time I Truth or Drink I Cut",
    "oqYIu4rK_CY": "facing my fear of flying alone",
    "mhqzfgyzAw8": "Let's Play ANIMAL HOSPITAL?",
    "j3YnR-yH7xU": "Conan Gray covers ADÉLA's 'Ain't In LA' for Like A Version",
    "Jctn80QpQzM": "Anne Hathaway Hosts Dakota Johnson vs. Josh Hartnett | Hot Ones Versus",
    "FYr8Pqg6npQ": "I Ranked EVERY Pizza in America",
    "0Rqoe5quCJQ": "24 Hours Inside Stripe: How They Build So Fast",
    "Knp90rLl3Ug": "DJI Osmo Pocket 4 (100 days later) | Watch Before You Buy",
    "YFe8LFCgT68": "Berlin Club Scene",
    "mPakWr5s4k0": "Dad Reacts to Steve Lacy - Oh yeah?",
    "zOeh3I4N9xk": "Javier Bardem Defends His 4 Most Controversial Takes",
    "fyjdahqf884": "Living with LA's Homeless Influencer Cult",
    "fkmS_QQwSL8": "Kevin Abstract covers Q Lazzarus' 'Goodbye Horses' for Like A Version",
    "ItbH0P9_0YQ": "Behind Malcolm Todd's cover of Audrey Hobert's 'Phoebe' for Like A Version (Interview)",
    "9g-MljUBEpM": "Jeff Teague & Rod Clark GO IN DEPTH ON about SCOUTING & RECRUITING at IU | College Basketball",
    "pKC4xuem9S0": "Their final photos will turn your stomach...",
}

# ---- verbatim from pipeline src/tag_videos.py @ ea94b9b ----
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
# ------------------------------------------------------------

traits = json.load(open(HERE / "data" / "traits_v2.json"))
for t in traits:
    t["column"] = re.sub(r"[^a-z0-9]+", "_", t["name"].lower()).strip("_")
by_col = {t["column"]: t["name"] for t in traits}
trait_lines = "\n".join(f"- {t['column']} [{'0/1' if t['scale'] == 'binary' else '0-4'}]: {t['definition']}" for t in traits)
trait_schema = {"type": "object",
                "properties": {t["column"]: {"type": "integer", "minimum": 0, "maximum": 1 if t["scale"] == "binary" else 4}
                               for t in traits},
                "required": list(by_col)}

out = HERE / "data" / "ai_tags_v2.csv"
done = set()
if out.exists():
    p = pd.read_csv(out)
    done = set(zip(p.model, p.video_id, p.run))

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
for run in range(1, RUNS + 1):
    for vid in VIDEOS:
        if (MODEL, vid, run) in done:
            print(f"skip {MODEL} {vid} run {run}"); continue
        contents = [types.Part.from_text(text=f"Video ID: {vid}"),
                    types.Part.from_uri(file_uri=f"https://www.youtube.com/watch?v={vid}", mime_type="video/mp4"),
                    types.Part.from_text(text=PROMPT.format(
                        n=1, linear_scale=LINEAR_SCALE, binary_scale=BINARY_SCALE, traits=trait_lines,
                        videos=f'- {vid}: "{TITLES[vid]}" - '))]
        schema = {"type": "object", "properties": {vid: trait_schema}, "required": [vid]}
        scores = None
        for attempt in range(4):
            try:
                r = client.models.generate_content(
                    model=MODEL, contents=contents,
                    config=types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema))
                scores = json.loads(r.text)[vid]
                break
            except Exception as e:
                msg = str(e)
                print(f"  {MODEL} {vid} run {run} attempt {attempt + 1}: {msg[:180]}")
                if not any(c in msg for c in ("429", "500", "503", "504", "timed out")):
                    break
                time.sleep(30 * 2 ** attempt)
        if scores is None:
            continue
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        pd.DataFrame([dict(model=MODEL, video_id=vid, run=run, trait=by_col[k], score=v, prompt="pipeline@ea94b9b",
                           tagged_at=now) for k, v in scores.items() if k in by_col]
                     ).to_csv(out, mode="a", index=False, header=not out.exists())
        print(f"{MODEL} {vid} run {run}: {len(scores)} traits saved")
        time.sleep(3)

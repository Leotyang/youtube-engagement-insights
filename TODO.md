# TODO.md — Task List, Trait Tagging Plan and Open Items

Working notes for the next stage after YouTube ingestion. See [README.md](README.md) for
the project overview and [CLAUDE.md](CLAUDE.md) for the status log.

Last updated: 2026-09-29 (tagging scaffold built)

---

## Task list

Kept in sync with actual project status (see [CLAUDE.md](CLAUDE.md)).

**Before meeting with Austin**
- [ ] Set up Jira board
- [ ] Choose a list of channels/videos for model training (add URLs to `CHANNEL_URLS` in `src/config.py`; MrBeast, MKBHD, Nick DiGiovanni pulled as a first test)
- [x] Set up YouTube API — key in `.env`, `python src/ingest.py` pulls channels → videos → engagement into `data/raw/*.csv` (2026-09-28)
- [ ] Black-box model: raw engagement metrics ~ views
- [ ] LLM video tagging — pipeline built (`src/tag_videos.py`, Gemini free tier, nightly GitHub Action); needs a Gemini key + the team's trait list to go live. See the sections below

**Next up (added 2026-10-13)**
- [ ] Add more traits / categorize traits
- [ ] Research & figure out a way to pressure test the 0-4 scale
- [x] Ingest writes channels/videos/engagement_snapshots to BigQuery from the Google Sheet creator list (code done 2026-10-14; first live local run + GitHub secrets pending)
- [ ] Start backfilling our BigQuery instance with tagged traits (migrate `tag_videos.py` to read/write BigQuery)
- [ ] Do some EDAs of our list of creators and their videos

**Phase I deliverables**
- [ ] Form team roles (business framing, data/context, methods, AI-assisted implementation, verification, stakeholder communication)
- [ ] Draft Feasibility & Problem Formulation Brief
- [ ] Draft Preliminary Business Dollar Value Assessment
- [ ] Draft Scope of Work and Execution Plan
- [ ] Week 3 executive buy-in presentation (first draft: `DSO_585_Brief_Deck.pptx`)

**Phase II pipeline**
- [ ] Identify and vet data sources (audience-demographics mitigation strategy)
- [ ] Define engagement and virality metrics precisely
- [ ] Build the trait taxonomy (content, format, hashtags, creator background, theme, industry)
- [ ] Run the trait-tagging pipeline on a sample and spot-check against human tags
- [ ] Build the engagement model (traits → views/likes/comments)
- [ ] Build the audience preference/segment model
- [ ] Build the optimization model (best trait combination per creator)
- [ ] Design the correlation-to-causal identification strategy
- [ ] Build the LLM-as-recommender benchmark and compare to the pipeline

## Where we are

- `python src/ingest.py` pulls every video from the past year for the channels in
  `CHANNEL_URLS` (`src/config.py`) and writes `data/raw/channels.csv`, `videos.csv`, and
  `engagement_snapshots.csv` with every API field. Working and tested on MrBeast, MKBHD,
  Nick DiGiovanni (315 videos).
- Next stage: score every video on a fixed list of traits, each on a universal 0–4 scale.

## Team TODO (in progress, owned by the team)

1. **Representative channel list.** 3–5 channels per genre, 5–8 genres (tech, food, gaming,
   finance, fitness, education, vlog/lifestyle, ...), mix of channel sizes. Deliverable:
   `youtube.com/@handle` URLs pasted into `CHANNEL_URLS`.
2. **Trait list.** 15–25 traits, each with a one-line definition. A trait is something a
   video can *be* to a degree (Tutorial, Humor, Challenge, Product Review, Storytelling,
   Reaction, ...). Attributes with categories or continuous values (length, upload day)
   are separate numeric features, not traits.
3. **Pressure-test the 0–4 scale** below. Does it need a level added or removed? Is the
   0-vs-1 line judgeable consistently, or should it collapse?
4. Hand-tag 5–10 videos each from the current test set to (a) surface traits and (b) serve
   as the human baseline for checking the model's agreement later.

## Universal trait scale (0–4)

Read "X" as the trait being scored. Two underlying dimensions: **intent** (did the creator
deliberately make X part of the video?) and **coverage** (how much of the video is X?).

| Score | Name | Definition |
|---|---|---|
| 0 | Absent | Nothing in the video is X. A viewer would not associate the video with X. |
| 1 | Incidental | The creator did not intend X, but part of the video has X value implicitly. |
| 2 | Explicit segment | The video as a whole is not X, but at least one part is deliberately X and signaled as such. |
| 3 | Featured | X is one of the video's stated purposes; a substantial dedicated portion is X, but the video also does other things. |
| 4 | Defining | The video is X and nothing else. Remove X and there is no video left. |

Tie-breakers: intent beats accident (explicit framing → at least 2); coverage moves you up
(segment 2, major portion 3, whole 4); when torn between two levels, pick the lower.

## Tagging pipeline plan (Claude to build once trait list lands; scaffold now with placeholders)

### Engine decision: Gemini API with direct YouTube URLs

An API is required for any pipeline over hundreds of videos. Chat UIs only handle one
video at a time by hand; local open models would require downloading videos (against
YouTube ToS) and are slow/weak on a laptop.

Gemini is the only major model API that accepts a **public YouTube URL as input and
watches the video itself** (frames + audio). Confirmed 2026-09-29 from the
[video understanding guide](https://ai.google.dev/gemini-api/docs/video-understanding) (YouTube
URL section). Per-project request limits are not printed in the
[rate limits page](https://ai.google.dev/gemini-api/docs/rate-limits); check them in
[AI Studio](https://aistudio.google.com/rate-limit) after creating a key.

| Fact | Value |
|---|---|
| Input | Public video URL passed as a file reference (unlisted/private not allowed) |
| Free tier | 8 hours of YouTube video per day, no card required. **Observed 2026-09-29: also capped at 20 requests/day for `gemini-3.8-flash`**, which is the binding limit |
| Paid tier | No video-length limit; ~$0.30 per 1M input tokens (Flash) |
| Token cost | ~100 tokens/sec of video at default resolution (~300 at high) |
| Controls | Frame sampling rate (`fps`), clipping via start/end offsets, up to 10 videos per request |

Cost math: a 20-minute video ≈ 120k tokens ≈ $0.04 on paid tier → **full 315-video baseline
≈ $10**. Free tier is capped at **20 requests/day**; the tagger therefore sends up to 10
videos per request (capped at 2h of video per request to stay inside the 1M-token context),
so the 8h-of-video/day rule is the binding limit again: **~25–40 videos/day, 315-video
baseline in ~2 weeks** of nightly runs. Live-tested 2026-09-29 with a 3-video batch.

Fallback (plan B, not built): Claude with thumbnail + transcript + sampled frames. No
audio, needs the content cache first, weaker on pacing/editing traits.

### Components

1. `src/traits.py` — trait name → definition dict, plus the scale text above. Placeholder
   traits until the team list lands; swapping is a copy-paste.
2. `src/tag_videos.py` — reads `videos.csv`, skips videos already scored under the current
   prompt version, sends YouTube URL + title + description + trait list + scale, requests
   JSON with one integer per trait enforced by a response schema. Clips videos >30 min to
   the first 30. Appends to `data/interim/video_traits.csv` with model, prompt version, and
   timestamp per row. Stops cleanly at the daily quota and resumes next run.
3. Config: `GEMINI_API_KEY` in `.env`, `TAGGING_MODEL` constant (current Flash model).
4. Test on 10 videos across the 3 channels, eyeball scores, report before full run.

### Content cache decision

- **Thumbnails: keep.** Official URLs already in `videos.csv`, one-line download, a few MB
  total. Useful for a human review sheet, thumbnail-trait analysis, and the Claude fallback.
- **Transcripts: defer.** Official captions endpoint is owner-only; the only route is an
  unofficial scraper (ToS grey area, breaks on page changes, rate-limited in bulk). Not
  needed for the Gemini path. Revisit if we switch to plan B or want text-only features.

### Running the free tier over ~2 weeks

No cloud compute needed. A day's batch (30–40 videos) takes ~20–30 min of wall time.

| Option | Notes |
|---|---|
| Run by hand daily | One command, walk away. Script resumes where it stopped. Enough for a 2-week baseline. |
| `launchd` on the Mac | Fires at a set time; fails silently if the laptop is asleep. |
| GitHub Actions cron | Free, cloud, no laptop. Key in repo secrets, results CSV committed back by the workflow (~30 lines YAML). Best free scheduler. |
| Cloud VM / Colab | Overkill. Colab can't schedule and times out. |

**Recommendation:** pay ~$10 for the paid tier, run the baseline once in one sitting, then
use the free tier for weekly increments by hand. If strictly free, add the GitHub Actions
workflow next to the tagger.

## Decisions made (2026-09-29)

- [x] Engine: Gemini via the `google-genai` SDK (`client.interactions.create`, model
  `gemini-3.8-flash`). Key goes in `.env` as `GEMINI_API_KEY` (still to be added).
- [x] Free tier + nightly GitHub Actions (`.github/workflows/tag_videos.yml`, 09:00 UTC).
  The run ingests, tags up to 7.5h of video, and commits the CSVs back.
- [x] Data CSVs (`data/raw/*`, `data/interim/video_traits.csv`) are now tracked in git so
  the Actions runner has persistent storage and results are reproducible.

## What's built (live-tested 2026-09-29: 4 videos scored, retries on 503/429 added)

- `src/traits.py` — placeholder TRAITS dict + SCALE text. Swap in the team's list, bump
  `TAGGING_PROMPT_VERSION` in `config.py`.
- `src/tag_videos.py` — resumable, batched tagger. `python src/tag_videos.py 10` for a spot check.
  Up to 10 videos / 2h of video per request, each video block named by ID and the JSON
  response keyed by ID. Videos >30 min are scored on their first 30 min. Retries 503/429
  with backoff, stops at the daily budget or when still rate-limited.
- Config knobs: `TAGGING_MODEL`, `TAGGING_PROMPT_VERSION`, `DAILY_VIDEO_SECONDS`,
  `MAX_VIDEO_SECONDS`, `MAX_VIDEOS_PER_REQUEST`, `MAX_SECONDS_PER_REQUEST`, `SECONDS_BETWEEN_REQUESTS`.

## To activate

1. Create a key at https://aistudio.google.com/apikey → `.env` `GEMINI_API_KEY=...`.
2. Spot check locally: `python src/tag_videos.py 10`, eyeball the scores.
3. GitHub → Settings → Secrets and variables → Actions: add `YOUTUBE_API_KEY` and
   `GEMINI_API_KEY`.
4. Merge to `main` (scheduled workflows only fire on the default branch), or trigger
   manually from the Actions tab with "Run workflow" on any branch.

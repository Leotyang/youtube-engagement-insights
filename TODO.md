# TODO.md — Task List, Trait Tagging Plan and Open Items

Working notes for the next stage after YouTube ingestion. See [README.md](README.md) for
the project overview and [CLAUDE.md](CLAUDE.md) for the status log.

Last updated: 2026-10-21 (daily snapshots; channel list synced with the sheet)

---

## Task list

Kept in sync with actual project status (see [CLAUDE.md](CLAUDE.md)).

**Before meeting with Austin**
- [ ] Set up Jira board
- [x] Choose a list of channels for model training (50 channels in the team Google Sheet, tab `Channel Selection`; ingest reads it directly)
- [x] Set up YouTube API — key in `.env`, `python src/ingest.py` pulls channels → videos → engagement into `data/raw/*.csv` (2026-09-28)
- [ ] Black-box model: raw engagement metrics ~ views
- [x] LLM video tagging — `src/tag_videos.py` on Vertex AI (`gemini-3.1-flash-lite`), 79 traits read from the sheet, results in BigQuery `youtube.llm_tagged`; nightly `tag_videos.yml` workflow (2026-10-15)

**Next up (added 2026-10-13)**
- [x] Add more traits / categorize traits (79 traits in 5 categories, `Scale` column Linear/Binary, in the sheet's `Content Traits` tab)
- [ ] Research & figure out a way to pressure test the 0-4 scale
- [x] Ingest writes channels/videos/engagement_snapshots to BigQuery from the Google Sheet creator list (one row per video, scraped once at 3+ days old, `age_days_at_pull` stored; local run done 2026-10-15; GitHub secrets + first Actions run pending)
- [ ] Backfill `llm_tagged` for the first sample: 50 most recent videos per channel, <= 30 min, CNBC skipped (~1,980 videos, ~$21); 3 tagged in the local test
- [ ] Add GitHub secret `GOOGLE_SERVICE_ACCOUNT_JSON` (+ `YOUTUBE_API_KEY`); check the first push-triggered Actions runs
- [x] Remove the TEMPORARY `push:` trigger in `tag_videos.yml` (2026-10-21)
- [ ] Merge the pipeline to `main` so the nightly schedules run (nothing has run on a schedule since 2026-10-15: `main` has no workflows); untrack `data/` first (`git rm -r --cached data`)
- [x] On The Radar Radio, CNBC, Apple, Bloomberg Originals removed from the sheet; ingest deleted their rows from every table (2026-10-21)
- [ ] Decide a brand vs independent-creator rule: triple j (ABC radio, 768 videos/yr, ~11K median views on 2.1M subs) looks like On The Radar Radio; Architectural Digest is Condé Nast like the removed Bon Appétit; Jubilee, First We Feast, Cut are media companies
- [ ] Wayne Hu (@nogatekeepers) has no uploads in the past year (contributes no videos); Stavvy's World still has a search link instead of a channel link
- [ ] Decide sampling for later batches: most recent X vs evenly spread over the year (prolific channels' 50 newest span only days)
- [x] AI vs manual comparison on the 5 hand-tagged videos in our data: `notebooks/03_ai_vs_manual.ipynb` (64% exact, 86% within 1, MAE 0.55, presence F1 0.76; worst: Production, Audience Hooks, Tone). The 3 manual videos outside the tagging queue were tagged as a one-off on 2026-10-15
- [ ] Re-run it as teammates add manual tags (the 6th manual video, the Abandoned Church one, is not in our scrape)
- [x] EDA of creators and videos: `notebooks/00_eda_charts.ipynb` reproduces the EDA slides (2026-10-15); training subset = videos tagged before `config.ANALYSIS_TAGGED_BEFORE` (3:30 PT Oct 15, 726 videos)

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
- [ ] Run the trait-tagging pipeline on a sample and spot-check against human tags (pilot on 5 videos done 2026-10-15: flash-lite 64% exact / 83% presence agreement vs 68% all-zeros baseline; Flash over-flags)
- [ ] Build the engagement model (traits → views/likes/comments)
  - [x] Baseline: plain OLS, no scaling/regularization/selection, `notebooks/01_baseline_linear_regression.ipynb` (2026-10-15). Random 20% test + 5-fold CV on the 80%: train R2 ~0.88, CV R2 negative for all targets (overfits)
  - [x] Tag dummies added to the baseline (57 YouTube tags used in >= 50 videos and >= 3 channels)
  - [ ] Handle sparse trait levels: compare one-hot vs ordinal 0-4 vs coarser levels (absent / minor / major) vs present-only; drop near-constant traits
  - [x] Lasso with scaling and a CV-chosen penalty: `notebooks/02_lasso.ipynb` (log views test R2 0.19 -> 0.66, CV 0.62; keeps 118 of 372 columns)
  - [ ] Ridge / elastic net for comparison; multicollinearity check (correlated trait pairs) deferred
  - [ ] Evaluate on held-out channels (grouped CV), not only random rows
  - [ ] Re-run when tagging finishes (~1,980 videos): move `ANALYSIS_TAGGED_BEFORE` in `config.py` and rerun notebooks 00-03. Note: `videos` counts are now refreshed nightly, so the Oct 15 results reproduce only from the 2026-10-15 snapshot partition
- [x] Daily snapshots: `video_daily_snapshots` and `channel_daily_snapshots` (one row per video / channel per day, date-partitioned, written by ingest; seeded with the 2026-10-15 pulls) (2026-10-21)
- [ ] Age normalization: after 3-4 weeks of snapshots, estimate growth curves (Shorts vs long-form) and normalize views to a reference age; meanwhile try a channel-relative, age-adjusted log-views target
- [ ] Build the audience preference/segment model
- [ ] Build the optimization model (best trait combination per creator)
- [ ] Design the correlation-to-causal identification strategy
- [ ] Build the LLM-as-recommender benchmark and compare to the pipeline

## Questions

Open questions to confirm with the professor. Add new ones here; move an item to the task list or
the decisions once answered.

- [ ] **Varying maturity of each video's metrics.** Views, likes and comments are lifetime counts
  taken once, when the video is scraped, so videos are measured at different ages (the backfill spans
  3-365 days; new videos are scraped at 3+ days old). Raw counts therefore mix "how well the video did"
  with "how long it has had to accumulate". What is the best way to account for this in the model?
  Options on the table: age at scrape (`age_days_at_pull`, e.g. log age) as a covariate; a
  per-channel age-adjusted target (views relative to that channel's videos of similar age); keeping
  only videos past a maturity cutoff; or re-snapshotting videos over time to estimate growth curves.

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

## Current tagging setup (2026-10-15; supersedes the 2026-09-29 free-tier plan above)

- Engine: Gemini on Vertex AI / Agent Platform, `gemini-3.1-flash-lite`, location `global`, authenticated
  with the pipeline service account (role Agent Platform User). No Gemini API key; `$300` GCP credit.
- Pilot (5 human-tagged videos): flash-lite was ~3x cheaper than `gemini-3.8-flash` and much closer to
  the human tags (Flash marked 76% of human-zero cells as present). ~91 tokens per video-second;
  3 videos per request works; one 97-min request was rejected.
- `src/traits.py` reads the trait list from the sheet; `src/tag_videos.py` reads its queue from
  BigQuery `videos` and appends to `llm_tagged` (one row per video; a sheet change to the trait list
  is blocked by a `traits_hash` check until the sheet is reverted or the table cleared).
- Knobs in `src/config.py`: `MAX_VIDEO_SECONDS` (longer videos never tagged), `MAX_VIDEOS_PER_CHANNEL`,
  `TAGGING_SKIP_CHANNELS`, `MAX_SPEND_PER_RUN_USD`, `MAX_RUNTIME_MINUTES`, request sizing, cost model.
- Commands: `python src/tag_videos.py --dry-run` (queue + cost, no calls), `--max-videos N`, no flag = whole
  queue up to the spend cap. Workflow `Tag videos` runs nightly at 10:00 UTC, one hour after ingest.

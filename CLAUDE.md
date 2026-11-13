# CLAUDE.md — Project Context for youtube-engagement-insights (DSO 585)

This file gives Claude (Claude Code) persistent context on this project, so it doesn't
need to be re-explained every session. **See [README.md](README.md) for the full
project description**, and [GIT_WORKFLOW.md](GIT_WORKFLOW.md) for how we collaborate
on Git/GitHub.

**Keep this file current as we work.** Whenever the project's scope, main question,
data sources, chosen methods, or key decisions change, update this file in the same
change/commit rather than letting it drift out of date. Treat it as the project's
living memory across sessions — future sessions (yours or a teammate's) should be
able to read this file and understand where the project actually stands, not where it
stood at the start.

**Always keep the [TODO.md](TODO.md) task list in sync with actual project
status.** Whenever a task in that list is started, finished, or a new task is
identified, update the TODO list in the same change — check off `[x]` completed
items, add new items as they come up, and remove/rewrite items that are no longer
relevant. Don't let it become a stale wishlist; if you're not sure whether an item is
done, ask rather than guessing.

## Course context

This is a team project for **DSO 585: Data-Driven Consulting** at USC. The course
operates in three phases:
- **Phase I (Weeks 1–3):** frame a vague business problem into a precise, feasible
  project plan (feasibility brief → dollar value assessment → scope of work →
  executive buy-in presentation).
- **Phase II (Weeks 4–13):** explore data, formulate and implement the analytical
  solution, verify results, interpret in business terms — presented weekly.
- **Phase III (Weeks 15–16):** final presentation + final report, framed around
  quantifiable business impact, adoption, and monitoring.

The course's repeated workflow is: **FRAME → DATA → FORMULATE → IMPLEMENT → VERIFY →
INTERPRET**. AI is meant to be an implementation partner, not an authority — the team
owns every assumption, result, and recommendation, and should be able to explain what
AI did, what the team decided, and how results were verified.

## Project summary (as of project kickoff)

**Main question:** How can independent creators (YouTubers) leverage audience
preference data to make videos that increase viewership and engagement?

**Planned pipeline:**
1. LLM-based trait tagging of a sample of videos across creators (content, format,
   hashtags, creator background, theme, industry, etc.)
2. ML model: traits → engagement metrics (views, likes, comments) to estimate trait
   parameters
3. Audience preference model: model how viewer demographics/segments interact with
   traits (not just population-average trait effects) — see README for the proposed
   approach (segment-level or interaction-term modeling, matrix-factorization-style
   framing)
4. Optimization model: given fitted parameters, find the trait combination that
   maximizes predicted engagement for a specific creator
5. Follow-on comparison: can an LLM directly recommend the same traits, and how does
   that compare to the formal pipeline?

**Open questions the team still needs to resolve** (see README for detail):
- Precise definitions of engagement and virality
- Drivers of the important KPIs
- Correlation vs. causal effects, and how to move from one to the other
- How to translate model output into an actionable intervention on a specific video
- LLM-as-recommender vs. ML+optimization pipeline comparison

## Personal goal (Leo): data-engineering practice

Leo is using this project to practice data engineering. When suggesting or designing anything, consider
where real data-engineering practice applies: data modeling (raw/staging/mart layers, table grain), dbt
transformations and tests, dev/prod separation, CI/CD for the pipeline, containerization, orchestration,
idempotent and backfillable jobs, data quality checks, and versioning of data, tags and models. Prefer
approaches that solve a real project need over tooling for its own sake, and keep GCP cost in mind
(the team runs on the $300 credit).

## Status log

Update this section (newest entry on top) as the project progresses — data sources
finalized, methods chosen/changed, key findings, blockers, pivots, etc. Keep entries
short; this is a running log, not a report.

- **2026-11-12 (evening, deck):** Sections 02 and 04 finished (teammates own the rest). Slide 24 = option 2 results with
  `age_option2_interactions.png` (only age x channel is interacted; all 79 traits are plain main effects). Options 1-3
  results slides share the same stats; new slide 28 compares every option and option-3 day window on the same metrics
  (`data/analysis/age_options_metrics.csv`, last two cells of notebook 07). Compare by real and shuffled gain
  separately: real minus shuffled makes option 3 look best only because shuffled traits overfit more on small samples.
  Speaker notes in both sections explain each chart and its implication for the age question.
- **2026-11-12:** Professor feedback (Nov 4): treat the project as explainability, with age as the main confounder;
  control it several ways and check the drivers agree; evaluate the LLM tags per trait against human tags with a
  rank-based loss. `notebooks/07_age_options.ipynb` (uses the Oct 15 pull + daily log, 296K day-to-day pairs) compares
  (1) one universal curve (breakpoint every day to day 30; smoothing penalty tested, not needed), (2) a curve per
  channel: universal curve x a channel factor k (0.44-1.72, shrunk toward 1; the interaction-term model fitted on the
  daily log, not one snapshot, which made the earlier version jagged), (3) views at exactly day 3/7/14/30/60/90 (190-890
  tagged per age). Metric 1 = projection from one snapshot 14 days ahead (held-out videos): typical error 7.4% no
  growth, 5.3% option 1, 4.5% option 2, 4.0% option 3 lookup (only where both ages are logged); from a 1-day-old
  snapshot 104% -> 26% / 23%. Both curves over-project videos 21+ days old (mean-based fit). Metric 2 = trait signal:
  +0.24 / +0.26 pps (options 1/2) vs -0.76 shuffled; option 3 negative at every age. Options 1 and 2 give the same
  trait effects (r = 1.00). Channel identity explains ~70% of log views at every age (3-90 days), no trend. Plan:
  option 2 to normalize/project. Human vs AI on 23 hand-tagged videos (10 tagged for this, $0.42): exact 63% = all-zeros
  baseline; rank agreement per video 0.69; triage 26 trust / 26 recalibrate / 25 drop-or-redefine, signal sits in the
  latter two. Progress deck lives in Google Slides (`DSO 585/Project`), edited via the service account (Slides API);
  chart PNGs from `docs/figures/` sync to the public `Project/deck_figures` folder (copy under a new name: overwriting
  loses the Drive ID). Nov 8 had no snapshot (missed run).
- **2026-11-04:** Analysis for the professor meeting (branch `leotyang/analysis-2026-11-04`; brief in
  `docs/2026-11-04_professor_meeting.md`, figures in `docs/figures/`). Age normalization (`05`): a per-format growth
  curve from 188K daily pairs (views x1.9 day 1-7, x1.2 day 7-30) cuts held-out-channel error ~45% under a week and
  21-28% at 7-30 days; size/genre-specific curves don't transfer to unseen channels, a channel-decay adjustment
  helps; past 30 days the curve can't be validated yet. 256 videos already have directly observed day-7 views
  (+~250/week). Tag validation (`06`, 2,788 videos, 51 channels): the random-split gain (+0.26 R2) is ~95% channel
  identity (within-channel shuffle control); real within-channel gain +0.014 (views) / +0.033 (likes); ordinal 0-4
  encoding best; Gemini re-tag of 100 videos ($0.50) agrees 88% exact with itself vs 64% with the human tagger.
  EDA (`04`): median channel 4.9M subs, 8 channels look like organisations (33% of videos), channel explains 68% of
  log-view variance; tagged subset is younger (median 47 vs 190 days) and has no videos over 30 min. Shorts are
  defined as <= 60 s in `05` but <= 180 s in `04`/`06`; standardize after the meeting.
- **2026-10-29:** Nightly pipeline verified Oct 22-27: one snapshot per video per day, no gaps, tagging keeps
  pace with uploads (~30/day after the 491-video backlog). Scheduled runs start 4-7 h late (GitHub cron delay).
  Added `apps_script/build_tagging_form.gs` so the class can hand-tag any YouTube video: a Google Form built from
  the Content Traits tab (one required question per trait; defaults of 0 via a pre-filled link, since Forms has
  no default answers; no email collected). Submissions land in the form's responses tab and, via an onFormSubmit
  trigger, as a new column in Manual Tagging (header = title from YouTube oEmbed, note = URL and time; a script
  lock keeps simultaneous submissions from colliding).
- **2026-10-22:** Repo made public (linked from Leo's resume). README rewritten as a manual (overview, status,
  Mermaid pipeline, the two workflows, data counts, early results, setup, structure); the original proposal moved
  to `docs/PROPOSAL.md`. GIT_WORKFLOW.md § 8 covers reading Actions logs, rerunning, and common failures.
  Secrets audit of all history: no keys or credential files ever committed; 10 early commits carry Leo's work email
  in their author metadata. `.env.example` removed (README lists the variables); the slide deck untracked and
  `*.csv` gitignored. Repo rename to `youtube-engagement-insights` planned (docs already use the new URL).
  The dashboard and sentiment features do not exist yet; the README marks them as planned.
- **2026-10-21:** Pipeline made production-shaped. Ingest pulls only the channels on the sheet and never
  deletes: it upserts `channels` and `videos` (latest metadata and counts; `pulled_at`/`age_days_at_pull` = this
  pull, `first_pulled_at` = first pull), adds new videos at any age (no 3-day wait), re-fetches every video of
  the sheet's channels (~265 videos.list calls for 13K videos), and overwrites today's partition of
  `video_daily_snapshots` (grain video x day, `is_available` flags deleted/private videos) and
  `channel_daily_snapshots` (grain channel x day). Kimball calls these periodic snapshot fact tables (SCD types
  are for changing dimension attributes). Partition overwrite makes reruns idempotent. Removing a channel's data
  is a manual one-off query, never pipeline logic; only `llm_tagged` history (paid for) must be kept. The tagger
  queue is scoped to the sheet's channels; the skip list is gone (the sheet decides). `config.py` holds only
  hand-maintained settings (sheet, BigQuery location, scope, model, budget, prices); calibrated tuning lives at
  the top of `tag_videos.py`. One dataset (`youtube`) for every run; `--env local` = BigQuery + CSV copies in
  `data/`, `--env github` = BigQuery only. Sheet changes: removed CNBC, On The Radar Radio, Apple, Bloomberg
  Originals; added Hasan Minhaj, Midwest Safety, Kelly Wakasa, SauccEats, Tom Scott, Wayne Hu (no videos in the
  past year). New-channel EDA in `00_eda_charts`: all fit inside the existing ranges. Temporary push trigger
  removed from `tag_videos.yml`; `data/` gitignored.
- **2026-10-15 (evening, deck):** Analysis frozen at `config.ANALYSIS_TAGGED_BEFORE` (3:30 PT, 726 tagged videos,
  48 channels); the tagger keeps running. Evaluation everywhere: random 20% test, 5-fold CV on the other 80%.
  Plain OLS (372 one-hot columns) overfits: log views train R2 0.89 vs test 0.19 (CV -0.25); adding feature groups
  raises train but not test. Lasso (standardized, alpha by CV) generalizes: log views test 0.66 / CV 0.62 with 118
  columns. Raw-count targets are unstable on any single split (Lasso keeps 2 columns). The OLS query had no ORDER BY,
  so the positional 80/20 split changed every run; fixed with ORDER BY id (earlier numbers were not reproducible).
  The "music performance = 4" coefficient is mostly On The Radar Radio (23 of 34 such videos), a clip channel with
  ~1.5K median views on 1.86M subs; whether to skip it like CNBC is open. Multicollinearity work deferred. AI vs manual
  tags (`03_ai_vs_manual`): 64% exact, 86% within 1, MAE 0.55, presence F1 0.76; AI scores higher on average.
  Notebooks 01-03 save results to `data/processed/`; the deck's model slides read from there.
- **2026-10-15 (end of day):** Added `notebooks/00_eda_charts.ipynb` (reproduces every EDA slide chart from
  BigQuery; genre = YouTube categoryId mapped via videoCategories.list, channel genre = its most common
  category). Baseline notebook now also has 57 YouTube-tag dummies (vocabulary = tags in >= 50 videos and >= 3
  channels across the whole dataset, so single-channel tags are excluded): 372 columns for ~410 train rows.
  Trait levels are sparse (of 300 dummies, 129 have < 20 videos), so the next step is to compare encodings
  (one-hot vs ordinal vs coarse vs present-only) with regularization and grouped-by-channel CV.
  Lesson: ask before assuming what an abbreviation means (V/C was views/comments, not views/channel).
- **2026-10-15 (late):** Baseline modeling notebook `notebooks/01_baseline_linear_regression.ipynb`: joins
  `llm_tagged` + `videos` + `channels`, one-hot encodes the 75 Linear (0-4) traits (level 0 = reference),
  keeps the 4 Binary traits as 0/1, adds 11 numeric metadata columns (duration, age at scrape, subscribers,
  publish hour/weekday, title/description length, tag count, HD, caption, paid placement) and fits plain
  OLS to views, log(1+views), likes, log(1+likes). On ~450 tagged videos it has ~315 columns for ~360 train
  rows, so it memorizes (train R2 0.96-0.98) and fails out of sample (test R2 -3 to -30): the expected
  starting point for regularization. Gotcha: sklearn's LinearRegression silently drops to rank 3 on this
  unscaled matrix (subscribers ~5e8 vs 0/1 dummies), so the notebook solves OLS with `np.linalg.lstsq`.
  EDA slides restructured into All Channels / All Videos / Training Subset: Channels / Training Subset:
  Videos (native Slides charts, numbers computed from BigQuery).
- **2026-10-15 (night):** The 8-parallel GitHub run still hit many 429s (Google's shared capacity, not our
  quota; synchronized 30-240 s backoffs idled the workers) and one unretried `RemoteProtocolError`.
  Fixes: retry connection errors, jittered 10-80 s backoff (5 attempts), 5 parallel requests, BigQuery
  writes buffered every 10 videos / 2 min (one write per video would hit the ~1,500 load jobs per table per
  day limit; a cancelled run flushes on exit), pandas-gbq warning silenced. Removed the temporary push
  trigger from `ingest_videos.yml`; the one in `tag_videos.yml` stays until the backfill finishes.
- **2026-10-15 (evening):** First full GitHub tagging run was slow: 294 videos in 4 h (74/h) because
  about half of the 3-video requests failed (Vertex 504 / 429) and fell back to one video at a time.
  Cancelled it (nothing lost: results save per request, and the queue skips anything already in
  `llm_tagged`). Switched to 1 video per request and 8 in parallel: local test tagged 16 videos in 3.2
  min (~300/h, a few 429s retried fine). ~376+ videos tagged so far of ~1,980. Open question for the
  professor logged in TODO.md: how to account for each video's different maturity (age at scrape).
- **2026-10-15 (later):** Tagger rebuilt and live on Vertex AI (Agent Platform) with
  `gemini-3.1-flash-lite` (location `global`, service-account auth; Gemini API key dropped after its
  prepaid credit hit $0). Pilot on the 5 human-tagged videos: flash-lite ~3x cheaper than
  gemini-3.8-flash and closer to human tags (64% exact / 83% presence vs Flash 29% / 48%; all-zeros
  baseline 68%), ~91 tokens per video-second, 3 videos per request OK. Traits (79, Linear 0-4 / Binary
  0/1) now come from the sheet via `src/traits.py`; results append to BigQuery `youtube.llm_tagged`
  (one row per video, trait columns described in the schema; no prompt versioning, a `traits_hash`
  check blocks tagging if the sheet's trait list changes). Queue: videos <= 30
  min, 50 most recent per channel, CNBC skipped (`TAGGING_SKIP_CHANNELS`): ~1,980 videos, ~$21. New
  workflow `tag_videos.yml` (nightly 10:00 UTC + temporary push trigger tagging 3 videos). Local test
  tagged 3 videos.
- **2026-10-15:** Ingest redesigned to scrape each video exactly once. Public YouTube Data API
  only has lifetime cumulative counts (windowed metrics need the Analytics API + channel-owner
  OAuth), so we approximate a fixed window: a video is pulled only once it is `MIN_VIDEO_AGE_DAYS`
  (=3, `config.py`) old and not already in BigQuery, and `age_days_at_pull` is stored. `videos` and
  `engagement_snapshots` are both one row per video, joined on `id` (no snapshot history). Existing
  backfill (pre-redesign) was scraped at ages 1-365 days: control for age in models. Tables and
  CSVs were dropped and rebuilt with the new logic on 2026-10-15.
- **2026-10-14:** Ingest now reads the creator list from the team Google Sheet (native Sheet,
  tab `Channel Selection`, via service account / ADC) and loads BigQuery (`dso-585-project-16336`,
  dataset `youtube`, tables `channels` replace, `videos` upsert on id, `engagement_snapshots`
  append). `python src/ingest.py --env local` also writes CSV backups; `--env github` is
  BigQuery-only. Dots in column names become underscores in BigQuery. Offline-tested only
  (mocked client); first live run pending. Tagger still reads CSVs, so it is next to migrate.
  Trait proposal (78 traits in 5 categories) in `trait_proposal.tsv`; modeling plan is to
  tag every video on every trait and let elastic-net regularization select.
- **2026-09-29 (night):** First live Gemini run succeeded: 4 videos scored on the placeholder
  traits, scores look sensible (MKBHD reviews → product_review 3, high_production 3). Found
  the real free-tier constraint: `gemini-3.8-flash` is capped at **20 requests/day**, far
  tighter than the 8h-of-video rule → ~16 nightly runs for the 315-video baseline. Options
  in TODO.md (check other models' limits in AI Studio, or ~$10 paid). Fix: tagger now batches up to 10 videos / 2h per request (API allows 10 YouTube URLs per
  request; video blocks named by ID, response schema keyed by ID), so the 8h/day video rule
  is binding again. Retries 503/429 with backoff. 7 videos tagged so far.
- **2026-09-29 (later):** Tagging pipeline scaffolded on the free tier: `src/traits.py`
  (placeholder traits + universal 0-4 scale), `src/tag_videos.py` (Gemini
  `interactions.create` with the YouTube URL as a video block and a JSON response schema;
  resumable, budget- and 429-aware), `.github/workflows/tag_videos.yml` (nightly ingest +
  tag + commit CSVs). Decision: data CSVs are now tracked in git so the Actions runner has
  storage. Untested against the live API — `GEMINI_API_KEY` not yet created. Setup steps in
  TODO.md → "To activate".
- **2026-09-29:** Ingestion branch `leotyang/youtube_ingestion` pushed. Next stage is trait
  tagging; plan, engine decision (Gemini API with direct YouTube URLs), universal 0–4 trait
  scale, content-cache decision (thumbnails yes, transcripts deferred), scheduling advice,
  and the team's open TODOs are written up in [TODO.md](TODO.md). Team is drafting the
  channel list and trait definitions; tagging pipeline not started.
- **2026-09-28 (night):** First real data pull succeeded. Channels are now given as URLs
  (`CHANNEL_URLS` in `src/config.py`); `youtube_api.py` resolves `@handle`, `/channel/UC…`,
  and `/user/…` URLs via `channels.list` filters (`forHandle`, `id`, `forUsername`; legacy
  `/c/` URLs are unsupported). Output keeps every API field an API key can access,
  flattened to dotted columns (57 video columns, 42 channel columns) plus
  `duration_seconds` and `pulled_at`. Scope per channel is a rolling window (`LOOKBACK_DAYS = 365`), not a fixed
  count. Test pull: MrBeast, MKBHD, Nick DiGiovanni, 315 videos from the past year → `data/raw/channels.csv`, `videos.csv`, `engagement_snapshots.csv`
  (gitignored). Decision: keep working in this repo for now; migrating to Colab + Drive
  only if teammates need to run the pull themselves.
- **2026-09-28 (evening):** Scope trimmed back to data collection only; modeling and LLM
  tagging are not started and their scaffolds were removed. Colab/Drive publishing dropped;
  the pipeline runs locally. `src/` is three plain scripts: `config.py` (`CHANNELS` dict
  name -> channel ID, `DATA_DIR`, key from .env), `youtube_api.py` (channels -> uploads
  playlist -> video IDs -> metadata/engagement; run it with an `@handle` to print a channel
  ID), `ingest.py` (writes `videos.csv` + appends `engagement_snapshots.csv`). Storage is
  CSV; `DATA_DIR` can be pointed at a Google Drive for Desktop folder to share with the team.
- **2026-09-28 (later):** Agreed a module layout: one script per pipeline stage in
  `src/`, modules exchange CSVs in `data/raw` → `interim` → `processed`. Scaffolded the
  first stage: `src/config.py` (channel list + paths + `.env` loading),
  `src/youtube_api.py` (channels → uploads playlist → video IDs → metadata/engagement
  via the Data API v3 REST endpoints with `requests`), and `src/ingest.py` (saves
  `videos.csv` master list and appends per-run `engagement_snapshots.csv` so engagement
  can be tracked over time). `.env.example` added; API key still pending. New near-term
  TODOs from the team (Jira board, channel selection, black-box engagement~views model,
  LLM tagging/embedding research) added to README.
- **2026-09-28:** Consolidated three separate Claude Code CLI sessions that had been
  running against this same repo folder into this one. Two of the three had drifted
  into session-management housekeeping (relocating a session transcript between
  project folders) rather than project work, so there was no divergent project
  content to merge — the repo's files already reflected the latest state. Committed
  the previously-untracked `DSO_585_Brief_Deck.pptx` (built 2026-09-10) so it isn't
  orphaned in a single session's local state. Going forward, do project work in this
  session/thread rather than opening parallel CLI sessions against the same folder,
  to avoid this fragmentation.
- **2026-09-10:** Project scoped. Main question and planned pipeline defined (see
  above). Wrote the full proposal-brief-style README (business problem, research
  questions, data/API strategy, methodology, timeline, contingency plan) modeled on
  classmates' sample scoping docs, and CLAUDE.md/GIT_WORKFLOW.md. Built a first-draft
  executive buy-in slide deck (`DSO_585_Brief_Deck.pptx`) using the USC Marshall
  template. Talked through the engagement model → audience preference model →
  optimization model methodology in depth (nested vs. fully-segmented modeling,
  confounding vs. effect modification) to sharpen the slide bullets; no data
  collection or modeling has started yet.

## Progress deck (Google Slides) and how to continue it

**Deck:** https://docs.google.com/presentation/d/1-wQADZx76ESW--hegJxXh0cmfvM0C9b7TkOz1WIRaqU/edit (team Drive,
`DSO 585/Project`; "anyone with the link can edit"). Teammates edit it live, so **never re-upload a rebuilt .pptx**:
change it element by element through the Slides API, which merges with their edits.

**Access (set up once per computer):** the service account `id-585-project-16336@dso-585-project-16336.iam.gserviceaccount.com`
edits the deck. Its key goes in `.env` as `GOOGLE_APPLICATION_CREDENTIALS` (same key the pipeline uses; never commit it).
The Slides API is enabled on the project. `deck/slides_api.py` holds the helpers (`slides`, `PID`, `rect`, `text`, `card`,
`stat`, `key_finding`, `source`, `new_content_slide`, `set_notes`, `run`); positions are in inches on a 10 x 5.625 slide.
Look a slide up first (`slides.get(presentationId=PID)`), then send one `batchUpdate`; check the result with
`slides.pages().getThumbnail(...)`.

**Charts are matplotlib PNGs** from `notebooks/07_age_options.ipynb` (and 04-06) in `docs/figures/`. Slides can only
insert an image from a public URL, so: copy the PNG into the public Drive folder `DSO 585/Project/deck_figures`
**under a new file name** (overwriting a synced file loses its Drive ID), get its file ID (Drive "Copy link", or on a Mac
with Drive for Desktop: `xattr -p 'com.google.drivefs.item-id#S' <file>`), then `createImage` / `replaceImage` with
`https://drive.google.com/uc?export=download&id=<ID>`. The charts on the slides are images, not editable charts.

**Slide map (object IDs, as of 2026-11-12, evening):** 1 `p1` cover · 2 `p2` overview (still lists the old four updates; to redo
as the six-section agenda) · 3 `sec01` cover "Our Dataset" · 4 `p3` class hand-tagging form · 5 `p4` EDA channels ·
6 `p5` EDA videos · 7 `eda_age_avail` data available at each age · 8 `p6` tagged subset · 9 `sec02` "New Data Pipeline" ·
10 `p7` daily log · 11 `p8` pipeline DAG · 12 `p9` BigQuery tables · 13 `p10` universal growth curve (speaker note has the
math) · 14 `sec03` "AI Tagging vs Manual Tagging" · 15-18 `p17`-`p20` (two yardsticks, exact match vs ranks, per-trait
triage, signal by triage group) · 19 `sec04` "Normalizing for Video Age" · 20-28 `age_a19`-`age_a28` (20 three options,
21-22 option 1 how/results, 23 option 2 per-channel curve, 24 option 2 results = interaction chart
`age_option2_interactions.png`, 25-26 option 3 design/results with a per-window metrics table, 27 comparison charts,
28 comparison table of every option on the same metrics; options 1-3 results slides share the same two stats) ·
29 `sec05` "Explainability vs Predictability" · 30 a teammate's slide "Explainability & Predictability" · 31 `sec06`
"Final Product and Next Steps" · 32 `p21` next steps and questions · 33 `p22` end. Section covers: `secNN` + `_label`,
`_title`, `_subtitle`, `_num` text boxes.

**Where the numbers come from:** section 01 EDA and slide 8 = BigQuery on the Nov 12 snapshot; section 02 = BigQuery
table metadata; section 03 = `analysis/human_vs_ai/human_vs_llm.py` (23 hand-tagged videos from the Manual Tagging tab;
`manual_cols.json` maps sheet columns to video IDs, `manual_llm_scores.json` holds the Gemini tags bought for the 10
videos that had none) plus `notebooks/06`; section 04 = `notebooks/07_age_options.ipynb` (writes CSVs to the gitignored
`data/analysis/`, so rerun it on a new computer before reusing those numbers).

**Open items for the deck:** section 05 content (beyond-coefficients explainability: permutation importance, SHAP,
partial dependence, causal methods), the overview slide, speaker notes outside sections 02 and 04 (those were
written 2026-11-12: what each chart shows, how to read it, what it means for the age question), and porting
`analysis/human_vs_ai/human_vs_llm.py` and the trait-group signal check into a notebook.

## Repo conventions

- See [GIT_WORKFLOW.md](GIT_WORKFLOW.md) for branching/PR conventions: work on a
  personal branch off `dev`, open a PR into `dev`, get a teammate's review before
  merging.
- If you're a teammate using Claude on this repo: point Claude at this file at the
  start of a session, and ask it to update the Status log section (and the rest of
  this file, if scope/methods changed) before you wrap up a session.

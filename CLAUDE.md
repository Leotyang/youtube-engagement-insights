# CLAUDE.md — Project Context for DSO_585_project

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

## Status log

Update this section (newest entry on top) as the project progresses — data sources
finalized, methods chosen/changed, key findings, blockers, pivots, etc. Keep entries
short; this is a running log, not a report.

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

## Repo conventions

- See [GIT_WORKFLOW.md](GIT_WORKFLOW.md) for branching/PR conventions: work on a
  personal branch off `dev`, open a PR into `dev`, get a teammate's review before
  merging.
- If you're a teammate using Claude on this repo: point Claude at this file at the
  start of a session, and ask it to update the Status log section (and the rest of
  this file, if scope/methods changed) before you wrap up a session.

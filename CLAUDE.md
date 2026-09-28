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

**Always keep the [README.md](README.md) TODO list in sync with actual project
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

- **2026-09-28 (evening):** Reconciled the Colab-prototyped pipeline into this repo as the
  single source of truth. `src/` is now a package (`from src import config`; run with
  `python -m src.<module>` from the repo root, or add the Drive Project folder to
  `sys.path` in Colab): `config.py` (secrets via .env or Colab userdata, channel list,
  trait taxonomy v1, tagging model), `youtube_api.py` (google-api-python-client wrappers,
  matching what Colab has preinstalled), `ingest.py` (`load_or_ingest()` + engagement
  snapshots), `tagging.py` (`load_or_tag()`, Claude tagging with model/prompt version
  stored per row, skips already-tagged videos), `model.py` (`fit_or_skip()` black-box
  RandomForest baseline on log views with a chronological split). Teammates don't use
  git and work in Colab against the shared Drive folder `DSO 585/Project`, so
  `scripts/publish_to_drive.sh` rsyncs the repo there (never touches the `.ipynb`).
  Workflow: commit here, then publish to Drive. No API keys yet; nothing has run on data.
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

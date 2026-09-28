# DSO_585_project

DSO 585 (Data-Driven Consulting) team project.

**New to this repo? Read [GIT_WORKFLOW.md](GIT_WORKFLOW.md) first** — it explains what Git/GitHub is, how to set up your SSH key, common commands, and how we use branches and pull requests (PRs) on this project. **If you're using Claude (Claude Code) to work on this project, also read [CLAUDE.md](CLAUDE.md)** — it holds the project context Claude needs, and we keep it updated as the project evolves.

---

# Project Proposal: Optimizing Content Traits for Independent Creator Engagement

## 1. Business Problem

YouTube's recommendation system decides which videos get surfaced to which viewers, but individual creators — especially independent ones without a data/analytics team — have no systematic way to know *which of their content traits* the algorithm and their audience actually reward. Creators mostly rely on intuition, trends, or trial-and-error to decide what to make next, which wastes production effort on videos with low expected engagement and makes it hard to grow a channel predictably.

The core challenge is translating audience preference (who watches, and what they respond to) into a concrete, actionable set of content traits a creator should incorporate in their next video. A reliable method to do this would give independent creators — who lack in-house data teams — an analytical edge similar to what large media companies already have internally.

**Main question:** How can independent creators (YouTubers) leverage audience preference data to make videos that increase viewership and engagement?

## 2. Research Questions

- How do we define **engagement** and **virality**, precisely (e.g., engagement rate vs. raw counts, a growth-rate or view-velocity threshold for "viral")?
- What are the drivers of the important KPIs (views, likes, comments) — which content traits (topic, format, hashtags, creator background, theme, industry/niche) matter most?
- What is merely **correlation** between a trait and engagement, and what is **causal**?
- How do we move from correlation to a causal estimate (e.g., creators who changed format over time, matching on channel/video characteristics, natural experiments around algorithm or platform changes)?
- How do content traits and **audience demographics/preferences** interact — does the same trait (e.g., video length, format) drive engagement differently depending on who is watching?
- Given fitted trait effects, how do we **intervene** on a particular upcoming video — i.e., turn model output into a specific, actionable change a creator could make?
- Can an **LLM directly recommend** the same traits to a creator (without the formal ML + optimization pipeline), and how does that compare in quality to our pipeline?

## 3. Data Description, Sources, and API Strategy

This project combines video metadata, engagement metrics, and (where available) audience demographic signals.

**a. Video metadata and engagement metrics**
- **Source:** YouTube Data API v3 (`videos.list`, `channels.list`, `search.list` endpoints), via the `google-api-python-client` library.
- **Description:** Public, per-video data — title, description, tags, duration, publish date, thumbnail, and the `statistics` object (view count, like count, comment count). This is available for any public video/channel without needing to own it.
- **API strategy:** Curate a list of creators/channels across a few industries/niches, pull their video lists via `search.list` (or `playlistItems.list` on the uploads playlist), then batch-call `videos.list` with `part=snippet,statistics,contentDetails` to get metadata + engagement counts per video. Respect API quota limits (default 10,000 units/day) by batching requests (up to 50 IDs per call).

**b. Audience demographics**
- **Constraint to flag early:** the YouTube **Analytics** API (which has real demographic breakdowns — age, gender, geography, subscriber status, traffic source) is only accessible for channels you own/have been granted access to via OAuth. We cannot pull true demographic data for arbitrary third-party creators.
- **Mitigating strategies (pick one or combine):**
  - Use our own (team members') YouTube channels, if any, as ground-truth demographic data via the Analytics API.
  - Use third-party estimated-audience-demographics tools (e.g., Social Blade, NoxInfluencer) as a proxy where available, clearly labeled as an estimate, not ground truth.
  - Infer audience-segment proxies from public signals — e.g., comment-section language/sentiment, video topic/niche as a demographic proxy (a well-documented correlation, e.g. gaming content skewing younger) — acknowledging this is a weaker substitute for real demographic data.
  - As a fallback/contingency, narrow scope to a "same-channel" audience-preference model: hold the audience roughly fixed (one channel/niche) and study how *that* audience's engagement responds to trait changes over time, sidestepping the need for cross-channel demographic data entirely.

**c. Trait labels (LLM-tagged)**
- **Source:** Generated by us — no external API. We will use an LLM (e.g., via the Anthropic or OpenAI API) to tag each sampled video against a fixed trait taxonomy (content/topic, video format, hashtags/tags, creator background, theme, industry/niche), producing a structured score/label per trait per video.
- **API strategy:** Batch video metadata (title, description, transcript/captions if available via `captions.list`) into a structured prompt per video, with a fixed output schema (e.g., JSON), and store results alongside the video's engagement metrics.

**d. Supplementary/backup data**
- Public Kaggle datasets (e.g., "Trending YouTube Video Statistics") as a fallback if live API collection is slow or rate-limited, to validate the pipeline end-to-end while live data collection continues in parallel.

## 4. Methodology

1. **Data ingestion & feature engineering.** Build an ETL pipeline to pull video metadata/engagement from the YouTube Data API across a curated set of creators, and construct the trait taxonomy.
2. **LLM-based trait tagging.** Tag each sampled video against the trait taxonomy using an LLM, producing structured, scored trait features per video.
3. **Engagement model.** Train a model (starting with an interpretable baseline — linear/regularized regression or gradient-boosted trees — over an LLM/deep-learning comparison later) using tagged traits as features against engagement metrics (views, likes, comments) to estimate each trait's contribution.
4. **Audience preference model.** Rather than fitting one global trait-effect model, model trait × audience-segment interactions (factorization-machine-style interaction terms, or a segment-stratified model) so a trait's estimated effect is conditioned on who the audience actually is, not a population average. See the data-strategy note above for how we'll approximate audience segments given API access constraints.
5. **Correlation → causal identification.** Explicitly separate the associational engagement model above from a causal-identification step — e.g., looking at within-channel changes over time (a channel that changes format/theme), matching on observable channel/video characteristics, or other quasi-experimental designs — to distinguish "this trait is merely correlated with engagement" from "this trait plausibly causes it."
6. **Optimization model.** Given the fitted (and where possible, causally-adjusted) trait parameters, use a linear or integer optimization model to find the trait combination that maximizes a specific creator's predicted engagement, subject to feasibility constraints (e.g., traits consistent with that creator's brand/resources).
7. **LLM-as-recommender benchmark.** As a comparison arm: prompt an LLM directly (given the same trait taxonomy and a creator's history) to recommend traits for a next video, and compare its recommendations — and the reasoning behind them — against the ML + optimization pipeline's output.
8. **Verification.** Backtest recommendations against held-out historical videos (chronological train/test split to avoid lookahead bias), and sanity-check trait-effect estimates against qualitative creator/domain knowledge.

## 5. Expected Outcomes

- A quantified estimate of which content traits drive engagement, and how that varies by audience segment.
- A working prototype that, given a creator's channel history, recommends a trait combination for their next video to maximize expected engagement.
- A documented comparison of the formal ML + optimization pipeline vs. a direct LLM recommendation, including where each is more/less reliable.
- A reusable trait-tagging and engagement-modeling pipeline that could extend to additional creators or platforms.

## 6. Timeline

| Week(s) | Focus | Tasks | Deliverables |
|---|---|---|---|
| 1 | Team formation | Form team, assign roles (business framing, data, methods, AI-assisted implementation, verification, communication), pick initial creator/niche scope. | Team roles; initial scope note. |
| 2 | Scoping | Draft working scoping document; test YouTube Data API access; confirm the audience-demographics constraint and chosen mitigation. | Working scoping doc draft. |
| 3 | Executive buy-in | Finalize scoping document; build the executive deck; present for 10–15 min. | Scoping doc; executive deck; presentation. |
| 4–5 | Data ingestion | Build ETL pipeline: pull video metadata/engagement across curated creators; assemble the trait taxonomy. | ETL pipeline; raw dataset; trait taxonomy v1. |
| 6–7 | Trait tagging | Build and validate the LLM trait-tagging pipeline; spot-check tags against human judgment. | Tagged dataset; tagging accuracy/consistency check. |
| 8–9 | Engagement model | Fit baseline engagement model(s); evaluate fit; identify top trait drivers. | Baseline model; feature-importance report. |
| 9–10 | Audience preference model | Build trait × audience-segment interaction model given available demographic/proxy data. | Segment-interaction model; findings memo. |
| 10 | *(Week 7 = holiday; adjust as needed)* | — | — |
| 11 | Correlation → causal | Design and run the causal identification analysis (within-channel changes, matching, or similar). | Causal-analysis writeup. |
| 12 | Optimization model | Build the trait-combination optimization model; test recommendations for sample creators. | Optimization model; sample recommendations. |
| 13 | LLM benchmark | Build the direct-LLM-recommendation benchmark; compare against the pipeline's output. | Comparison report. |
| 14 | *(Week 14 = holiday)* | — | — |
| 15 | Final polish | Refine analysis based on feedback; quantify business impact/value; polish visuals and narrative. | Draft final deck + report. |
| 16 | Final delivery | Final presentation (15–20 min); final report; reproducible code repository. | Final presentation; final report; repo. |

## 7. Contingency Plan

**Potential sticking points:**
1. **Audience demographic data access** — true per-video/per-channel demographics are only available for channels we own (YouTube Analytics API OAuth restriction).
2. **LLM trait-tagging consistency** — an LLM may tag traits inconsistently across videos/creators without a carefully specified taxonomy and prompt.
3. **Causal identification** — isolating a causal trait effect from confounders (channel size, algorithm changes over time, topic popularity trends) is inherently hard with observational data.
4. **API quota/rate limits** — the YouTube Data API has daily quota limits that could slow large-scale data collection.

**Pivot strategies:**
1. **If demographic data access fails:** narrow to a same-channel audience-preference model (see Data Description §b), or use publicly available Kaggle datasets with engagement metrics only (skip the audience-segment layer, and note it as a limitation).
2. **If LLM tagging proves inconsistent:** tighten the taxonomy/prompt with few-shot examples and a validation rubric; have a team member spot-check a sample of tags for agreement.
3. **If causal identification proves infeasible in the time available:** fall back to a clearly-labeled correlational analysis, explicitly stating that finding as a limitation rather than overclaiming causality.
4. **If API access is rate-limited or restricted:** fall back to publicly available datasets (e.g., Kaggle's YouTube trending-video datasets) to keep the pipeline moving while live collection continues in the background.

## TODO

> Kept up to date as the project progresses — see [CLAUDE.md](CLAUDE.md), which instructs Claude to always sync this list with actual project status.

**Before meeting with Austin**
- [ ] Set up Jira board
- [ ] Choose a list of channels/videos for model training (fill `CHANNEL_IDS` in `src/config.py`)
- [ ] Set up YouTube API — get an API key into `.env` / Colab secrets, then run `python -m src.ingest` (module and script done 2026-09-28)
- [ ] Black-box model: raw engagement metrics ~ views (baseline scaffold in `src/model.py`; needs ingested data to run)
- [ ] Explore LLM video tagging & embedding capabilities — research cheap LLM API tokens, decide on cloud data storage (tagging pipeline scaffold in `src/tagging.py`)

**Phase I deliverables**
- [ ] Form team roles (business framing, data/context, methods, AI-assisted implementation, verification, stakeholder communication)
- [ ] Draft Feasibility & Problem Formulation Brief
- [ ] Draft Preliminary Business Dollar Value Assessment
- [ ] Draft Scope of Work and Execution Plan
- [ ] Week 3 executive buy-in presentation (first draft: `DSO_585_Brief_Deck.pptx`)

**Phase II pipeline**
- [ ] Identify and vet data sources (audience-demographics mitigation strategy)
- [ ] Define engagement and virality metrics precisely
- [ ] Build the trait taxonomy (content, format, hashtags, creator background, theme, industry) — v1 definitions in `src/config.py`, needs team review
- [ ] Build LLM-based trait-tagging pipeline on a sample of videos
- [ ] Build the engagement model (traits → views/likes/comments)
- [ ] Build the audience preference/segment model
- [ ] Build the optimization model (best trait combination per creator)
- [ ] Design the correlation-to-causal identification strategy
- [ ] Build the LLM-as-recommender benchmark and compare to the pipeline

## Course framing (DSO 585)

This project follows the course's FRAME → DATA → FORMULATE → IMPLEMENT → VERIFY → INTERPRET workflow (per the DSO 585 course overview). Phase I deliverables are a Feasibility & Problem Formulation Brief, a Preliminary Business Dollar Value Assessment, and a Scope of Work — all of which should trace back to the business problem and research questions above.

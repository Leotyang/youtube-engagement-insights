# DSO_585_project

DSO 585 (Data-Driven Consulting) team project.

**New to this repo? Read [GIT_WORKFLOW.md](GIT_WORKFLOW.md) first** — it explains what Git/GitHub is, how to set up your SSH key, common commands, and how we use branches and pull requests (PRs) on this project. **If you're using Claude (Claude Code) to work on this project, also read [CLAUDE.md](CLAUDE.md)** — it holds the project context Claude needs, and we keep it updated as the project evolves.

## Project overview

### Business context

YouTube's recommendation system decides which videos get surfaced to which viewers, but individual creators — especially independent ones without a data/analytics team — have no systematic way to know *which of their content traits* the algorithm and audience actually reward. Creators mostly rely on intuition or trial-and-error to decide what to make next.

**Main question:** How can independent creators (YouTubers) leverage audience preference data to make videos that increase viewership and engagement?

### Precise problem statement

Given a set of content traits describing a video (content/topic, video format, hashtags/tags, creator background, theme, industry/niche, etc.), can we:
1. Quantify how much each trait drives engagement (views, likes, comments), separating correlation from causal effect where possible, and
2. Recommend the combination of traits a creator should incorporate in their next video to maximize expected engagement, conditional on their audience's preferences?

### Proposed analytical approach

1. **Trait tagging (feature construction).** Use an LLM to tag a sample of videos from *x* creators, scoring each video on a defined set of traits spanning: content/topic, video format (e.g., long-form, Shorts, tutorial, vlog, reaction), hashtags, creator background, video theme, and industry/niche.
2. **Engagement model.** Train an ML model using the tagged traits as features against engagement metrics (views, likes, comments) to estimate each trait's contribution (parameters).
3. **Audience preference model.** See below — models how viewer demographics interact with content traits and a given creator's existing audience.
4. **Optimization.** Given the fitted parameters, use a (linear or integer) optimization model to find the trait combination that maximizes predicted engagement for a specific creator, subject to constraints (e.g., traits that are actually feasible/consistent with that creator's brand).
5. **LLM-as-recommender benchmark.** As a follow-on question: can an LLM, given the same trait taxonomy and a creator's history, directly recommend traits to incorporate — and how does that recommendation compare to the ML + optimization pipeline above (better/worse, and why)?

### Audience preference model — approach

This needs to sit between the trait-tagging step and the engagement model, since the same trait (e.g., "9-minute tutorial") may drive very different engagement depending on who is watching. A reasonable way to build this:

- **Data:** Use YouTube Analytics API demographic breakdowns (age band, gender, geography, subscriber vs. non-subscriber, traffic source) per video/channel where available, rather than only aggregate engagement counts.
- **Segment the audience.** Cluster viewers/channels into a small number of audience segments based on demographic composition and watch behavior.
- **Model the interaction, not just the main effects.** Rather than one global regression of engagement on traits, include trait × audience-segment interaction terms (or fit a separate/hierarchical model per segment) so the model can learn that, e.g., a given format or theme performs differently for a Gen-Z-skewed audience vs. an older audience.
- **Treat it like a two-sided matching problem.** Conceptually similar to a recommender system: represent each audience segment as a preference vector over traits and each video as a trait vector; engagement is a function of the interaction between the two (e.g., via matrix factorization or a factorization-machine-style model), rather than assuming one fixed set of trait weights applies to every creator/audience.
- **Feed segment-specific parameters into the optimization step**, so the trait recommendation for a given creator is conditioned on *that creator's* actual audience composition, not a population-average audience.

### Open questions to resolve as part of this project

- How do we define **engagement** and **virality**, precisely (e.g., views/impression, engagement rate, a virality threshold or growth-rate cutoff)?
- What are the drivers of the important KPIs?
- What is merely **correlation**, and what is **causal**? What identification strategy (e.g., natural experiments, instrumental variables, matching, diff-in-diff on creators who change format) gets us from correlation to a causal estimate?
- How would we **intervene** on a particular video — i.e., translate the model's output into an actionable, specific change a creator could make to their next video?
- Would an **LLM directly recommending traits** (without the ML + optimization pipeline) perform better or worse than our formal pipeline, and why?

### Course framing (DSO 585)

This project follows the course's FRAME → DATA → FORMULATE → IMPLEMENT → VERIFY → INTERPRET workflow (per the DSO 585 course overview). Phase I deliverables are a Feasibility & Problem Formulation Brief, a Preliminary Business Dollar Value Assessment, and a Scope of Work — all of which should trace back to the business context and precise problem statement above.

## TODO

> Kept up to date as the project progresses — see [CLAUDE.md](CLAUDE.md), which instructs Claude to always sync this list with actual project status.

- [ ] Form team roles (business framing, data/context, methods, AI-assisted implementation, verification, stakeholder communication)
- [ ] Identify and vet data sources (YouTube Data API, YouTube Analytics API, creator/video sample)
- [ ] Define engagement and virality metrics precisely
- [ ] Build the trait taxonomy (content, format, hashtags, creator background, theme, industry)
- [ ] Build LLM-based trait-tagging pipeline on a sample of videos
- [ ] Build the engagement model (traits → views/likes/comments)
- [ ] Build the audience preference/segment model
- [ ] Build the optimization model (best trait combination per creator)
- [ ] Design the correlation-to-causal identification strategy
- [ ] Build the LLM-as-recommender benchmark and compare to the pipeline
- [ ] Draft Feasibility & Problem Formulation Brief (Phase I)
- [ ] Draft Preliminary Business Dollar Value Assessment (Phase I)
- [ ] Draft Scope of Work and Execution Plan (Phase I)
- [ ] Week 3 executive buy-in presentation

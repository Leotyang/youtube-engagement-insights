# Human vs AI trait tagging: evaluation

**Question:** can we trust the AI's trait tags enough to base creator recommendations on them, and what does their error do to the engagement model?
**Method:** compare AI tags with blind human tags on the same videos, using agreement measures that don't reward lucky guesses; then test, on the real BigQuery data, how much the measured AI error changes the model's conclusions.

Owner: Tiana Pinto. Last run: 2026-11-05 (21 human-tagged videos, 2,826 production-tagged videos).

## Results (2026-11-05)

| Question | Answer | Script |
|---|---|---|
| Are production tags (BigQuery `llm_tagged`) as good as our re-runs? | Yes: production vs human κ 0.69 = our re-run vs human κ 0.69 (13 videos in both); production vs re-run κ 0.92 | `production_vs_human.py` |
| How well does the AI agree with humans? | Current model (flash-lite) κ 0.68 (95% CI 0.63–0.74), 21 videos; gemini-3.8-flash κ 0.78 (13 videos so far), higher on 12 of 13 (sign test p = 0.003) | `evaluate.py` |
| Which traits can we trust? (Kendall's τ-b per trait) | Current model: 17 trust, 31 review, 15 drop/redefine, 16 too rare to judge. With 3.8-flash only Promotional and Face on Camera stay drop/redefine | `trait_triage.py` |
| Does AI error change the model's conclusions? (MC-SIMEX on 2,826 videos) | One extra dose of the measured AI error removes 56% of the tags' R² gain over controls and keeps 4 of the top-10 drivers. Corrected, top-10 effects are ~1.8× today's (linear, conservative: ~1.1×), 8 of 10 stay top 10, none flips sign | `real_downstream.py` |

## Reproduce

```bash
pip install -r requirements.txt
python evaluate.py              # headline agreement, CIs, consistency, categories
python trait_triage.py          # per-trait tau-b + verdicts  -> trait_triage.csv
python production_vs_human.py   # BigQuery tags vs human      -> production_vs_human.csv
python real_downstream.py       # MC-SIMEX downstream test (~40 s) -> real_downstream_*.csv
python make_charts.py           # slide 7 charts
python downstream_sim.py && python downstream_chart.py   # Oct 22 simulation (synthetic data, Leo-shaped)
```

No API key is needed for these: they read the saved tags in `data/`.

## Data (`data/`, not in git)

The repo ignores `data/` and `*.csv` (it is public), so the inputs live locally. To rebuild them:

| File | Where it comes from |
|---|---|
| `manual_tags.csv` | Team sheet, *Manual Tagging* tab → File → Download → CSV. 79 traits × one column per human-tagged video, scored blind |
| `video_map.csv` | Hand-made: `sheet_column, video_id, channel, rater, note`. Videos are joined **by ID, not title** |
| `traits_v2.json` | The 79 traits from the *Content Traits* tab: category, Linear (0–4) or Binary (0/1), definition |
| `ai_tags_v2.csv` | Output of `tag_videos_eval.py`: model, video_id, run, trait, score |
| `bq_llm_tagged_export.csv` | `bq_export.sql` run in the BigQuery console (one row per tagged video with views, age, duration, subscribers) |

## Files

| File | What it does |
|---|---|
| `tag_videos_eval.py` | Tags the human-tagged videos with the pipeline's prompt and scales **verbatim** (`src/tag_videos.py`); needs `GEMINI_API_KEY` in a local `.env` (never commit it) |
| `evaluate.py` | Quadratic-weighted κ, Krippendorff's α (ordinal), lazy-AI baseline, error rates, video-level bootstrap CIs, model comparison, test-retest, categories |
| `trait_triage.py` | Austin's per-trait, rank-based check: Kendall's τ-b (handles tied zeros; doesn't treat 0–4 as exact distances), bootstrap CI, MAE, bias, verdict |
| `production_vs_human.py` | Compares production tags from BigQuery with human tags and with our re-runs on the same videos |
| `real_downstream.py` | MC-SIMEX (Küchenhoff, Mwalili & Lesaffre 2006, *Biometrics* 62:85–96): adds 1–3 extra doses of the measured AI error to the real tags, refits, extrapolates back to zero error |
| `downstream_sim.py`, `downstream_chart.py` | Earlier simulation on synthetic data (Oct 22) |
| `make_charts.py` | Slide 7 charts, computed from `data/` |
| `bq_export.sql` | The BigQuery export query |

## Downstream test (`real_downstream.py`)

1. **Error pattern.** For each trait, P(AI score = j | human score = i) from the 21 human-tagged videos (current model, run 1), smoothed with 3 pseudo-counts toward the pooled pattern of its scale type.
2. **Model.** log(views + 1) on the 79 traits (per 1 SD) + log age, log age², log duration, log subscribers; SEs clustered by channel. Robustness: channel fixed effects. Leo-style check: LassoCV (5-fold, 40 alphas), 80/20 split.
3. **SIMEX.** Re-draw every tag from the error pattern 1, 2 and 3 times (5 replicates each), refit, fit a quadratic in the number of doses, evaluate at −1 (no error). The whole procedure is repeated on 30 bootstrap resamples of the 21 videos, so the interval includes the uncertainty in the error pattern itself.

## Judgment calls (change them at the top of each script)

- Triage verdicts: trust = τ-b ≥ 0.60 and MAE ≤ 0.5; drop/redefine = τ-b < 0.30 or MAE > 1; too rare = human > 0 on fewer than 3 videos; "uncertain" = bootstrap interval wider than 0.6.
- Downstream: smoothing k = 3; "driver" = top 10 by |effect|; quadratic extrapolation (standard), linear reported as the conservative bound.

## Limitations

- **One human per video:** no human-vs-human benchmark yet; the measured "AI error" includes human error, so the SIMEX correction may overstate it.
- **21 videos:** many per-trait intervals are wide (33 of 79 verdicts marked uncertain).
- **SIMEX adds error independently per trait;** real AI errors may be correlated across traits.
- **Associations, not causes:** cross-sectional, observational data.
- **Blind scores only:** the Tucker Budzyn column uses the tagger's original scores (two cells were edited in the sheet after the AI comparison existed).
- **Stavvy's World #121** is excluded (only a fan re-upload could be found).

## How this was built

The analysis was written with an AI coding assistant (Claude) as an implementation partner. Every decision (metrics, baselines, joining by video ID, video-level resampling, SIMEX setup, what to claim) was reviewed and can be explained by the owner, and every number can be regenerated with the commands above.

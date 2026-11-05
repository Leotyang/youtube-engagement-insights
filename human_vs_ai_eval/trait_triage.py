"""
Per-trait triage of LLM tags (Austin, Nov 4): a rank-based, per-trait comparison of LLM vs human scores,
then trust / redefine / drop. Traits are ordinal, so the main measure is Kendall's tau-b (rank agreement,
handles the many tied zeros), not RMSE.

For each trait, across all human-tagged videos the AI also tagged:
  tau_b      Kendall's tau-b between human and AI scores (1 = same ranking of videos, 0 = unrelated)
  tau_lo/hi  95% bootstrap interval for tau_b, resampling videos
  mae        mean |AI - human| in scale levels;  bias = mean(AI - human)
  present    videos where the human scored the trait > 0 (how much signal there is to rank)
  ai_retest  share of videos where the AI gave the same score on run 1 and run 2 (current model only)

Verdict rules (judgment calls, stated so they can be changed):
  too rare   human > 0 on fewer than 3 videos: not enough signal to rank; mostly agreement on "absent"
  trust      tau_b >= 0.60 and MAE <= 0.50
  drop/redefine  tau_b < 0.30 or MAE > 1.00
  review     everything in between (candidate for a sharper definition)
  "uncertain" is added when the bootstrap interval is wider than 0.6 (too few videos to be sure)

Run:  python trait_triage.py
Out:  trait_triage.csv  (one row per trait x model)
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

warnings.filterwarnings("ignore")
HERE = Path(__file__).parent
D = HERE / "data"
rng = np.random.default_rng(585)
MODELS = {"gemini-3.1-flash-lite": "current", "gemini-3.8-flash": "better"}

traits = {t["name"]: t for t in json.load(open(D / "traits_v2.json"))}
sheet = pd.read_csv(D / "manual_tags.csv")
vmap = pd.read_csv(D / "video_map.csv").set_index("sheet_column")
human = pd.concat(pd.DataFrame({"video_id": vmap.loc[c, "video_id"], "trait": sheet.Trait,
                                "human": pd.to_numeric(sheet[c], errors="coerce")}) for c in sheet.columns[1:])
human = human[human.human.isin([0, 1, 2, 3, 4])].copy()
binary = human.trait.map(lambda t: traits[t]["scale"]) == "binary"
human["human"] = np.where(binary, (human.human >= 1).astype(int), human.human).astype(int)
ai = pd.read_csv(D / "ai_tags_v2.csv")


def tau(x, y):
    if len(set(x)) < 2 or len(set(y)) < 2:
        return np.nan
    return kendalltau(x, y, variant="b").statistic


rows = []
for model, label in MODELS.items():
    p = human.merge(ai[(ai.model == model) & (ai.run == 1)][["video_id", "trait", "score"]], on=["video_id", "trait"])
    r2 = ai[(ai.model == model) & (ai.run == 2)][["video_id", "trait", "score"]].rename(columns={"score": "score2"})
    p = p.merge(r2, on=["video_id", "trait"], how="left")
    for t, g in p.groupby("trait"):
        h, a = g.human.values, g.score.values
        boots = []
        for _ in range(1000):
            i = rng.integers(0, len(g), len(g))
            boots.append(tau(h[i], a[i]))
        lo, hi = np.nanpercentile(boots, [2.5, 97.5]) if np.isfinite(boots).sum() > 50 else (np.nan, np.nan)
        rows.append({"model": label, "trait": t, "category": traits[t]["category"], "videos": len(g),
                     "present": int((h > 0).sum()), "ai_present": int((a > 0).sum()),
                     "tau_b": tau(h, a), "tau_lo": lo, "tau_hi": hi,
                     "mae": np.abs(a - h).mean(), "bias": (a - h).mean(),
                     "ai_retest": (g.score == g.score2).mean() if g.score2.notna().any() else np.nan})
res = pd.DataFrame(rows)


def verdict(r):
    if r.present < 3:
        return "too rare"
    if pd.notna(r.tau_b) and r.tau_b >= 0.60 and r.mae <= 0.50:
        v = "trust"
    elif pd.isna(r.tau_b) or r.tau_b < 0.30 or r.mae > 1.00:
        v = "drop/redefine"
    else:
        v = "review"
    if pd.notna(r.tau_lo) and r.tau_hi - r.tau_lo > 0.6:
        v += " (uncertain)"
    return v


res["verdict"] = res.apply(verdict, axis=1)
res.round(3).to_csv(HERE / "trait_triage.csv", index=False)

n_videos = res.videos.max()
print(f"Per-trait triage: {n_videos} videos, 79 traits, both models (Kendall tau-b, human vs AI run 1)\n")
for label in MODELS.values():
    r = res[res.model == label]
    base = r.verdict.str.replace(" (uncertain)", "", regex=False)
    print(f"[{label} AI] " + " | ".join(f"{k}: {v}" for k, v in base.value_counts().items())
          + f" | of which uncertain: {r.verdict.str.contains('uncertain').sum()}")
    print("  by category (median tau_b):", r.groupby("category").tau_b.median().round(2).to_dict())
b = res[res.model == "better"].set_index("trait")
c = res[res.model == "current"].set_index("trait")
judged = b[b.present >= 3].sort_values("tau_b")
print("\nWorst-ranked traits (better AI, enough signal):")
print(judged.head(10)[["category", "present", "tau_b", "tau_lo", "tau_hi", "mae", "bias", "verdict"]].round(2).to_string())
print("\nBest-ranked traits (better AI):")
print(judged.tail(10)[["category", "present", "tau_b", "mae", "verdict"]].round(2).to_string())
print(f"\nToo rare to judge (human > 0 on < 3 videos): {(b.present < 3).sum()} traits")
print(f"AI run-1 vs run-2 same score (current AI), median across traits: {c.ai_retest.median():.0%}; "
      f"lowest: {c.ai_retest.sort_values().head(5).round(2).to_dict()}")

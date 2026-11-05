"""
Human vs AI trait-tag agreement: produces every number on slides 7b, 7c and the backup slide.

Inputs (data/):
  manual_tags.csv  Manual Tagging sheet export: one row per trait, one column per human-tagged video
  video_map.csv    sheet column -> YouTube video_id (videos are joined by ID, never by title)
  traits_v2.json   the 79 traits: category, Linear (0-4) or Binary (0/1), definition
  ai_tags_v2.csv   AI scores from tag_videos_eval.py: model, video_id, run, trait, score

Run:  python evaluate.py
"""
import json
from pathlib import Path

import krippendorff as kd
import numpy as np
import pandas as pd
from scipy.stats import binomtest, ttest_1samp
from sklearn.metrics import cohen_kappa_score

D = Path(__file__).parent / "data"
rng = np.random.default_rng(585)
LEVELS = [0, 1, 2, 3, 4]
CURRENT, BETTER = "gemini-3.1-flash-lite", "gemini-3.8-flash"

# ---------- 1. Load and align ----------
traits = {t["name"]: t for t in json.load(open(D / "traits_v2.json"))}
sheet = pd.read_csv(D / "manual_tags.csv")
vmap = pd.read_csv(D / "video_map.csv").set_index("sheet_column")

human = pd.concat(
    pd.DataFrame({"video_id": vmap.loc[col, "video_id"], "trait": sheet.Trait,
                  "human": pd.to_numeric(sheet[col], errors="coerce")})
    for col in sheet.columns[1:])
human = human[human.human.isin(LEVELS)].copy()          # blanks and non-integers (e.g. "2/3") are dropped
is_binary = human.trait.map(lambda t: traits[t]["scale"]) == "binary"
human["human"] = np.where(is_binary, (human.human >= 1).astype(int), human.human).astype(int)  # same rule as the pipeline

ai = pd.read_csv(D / "ai_tags_v2.csv")


def pairs(model, run=1):
    """Human score and AI score side by side for every (video, trait) both sides scored."""
    a = ai[(ai.model == model) & (ai.run == run)][["video_id", "trait", "score"]]
    return human.merge(a, on=["video_id", "trait"])


# ---------- 2. Metrics ----------
def kappa(x, y):
    """Quadratic-weighted Cohen's kappa: agreement beyond chance; near-misses cost less than big misses."""
    return cohen_kappa_score(x, y, weights="quadratic", labels=LEVELS)


def alpha(x, y):
    """Krippendorff's alpha, ordinal: the content-analysis standard (0.667 tentative, 0.80 reliable)."""
    return kd.alpha(reliability_data=np.vstack([x, y]).astype(float),
                    level_of_measurement="ordinal", value_domain=LEVELS)


def summary(p):
    h, a = p.human, p.score
    err = a - h
    return {
        "videos": p.video_id.nunique(), "pairs": len(p),
        "kappa": kappa(h, a), "alpha": alpha(h, a),
        "exact_%": (err == 0).mean() * 100,
        "off_by_2plus_%": (err.abs() >= 2).mean() * 100,
        "missed_traits_%": ((a == 0) & (h > 0)).sum() / (h > 0).sum() * 100,   # false negatives
        "false_alarms_%": ((a > 0) & (h == 0)).sum() / (h == 0).sum() * 100,   # false positives
        "MAE": err.abs().mean(), "bias": err.mean(),
    }


def bootstrap_ci(p, n=2000):
    """95% CI for kappa, resampling whole VIDEOS (a video's 79 scores aren't independent)."""
    vids = p.video_id.unique()
    stats = [kappa(s.human, s.score) for s in
             (pd.concat([p[p.video_id == v] for v in rng.choice(vids, len(vids))]) for _ in range(n))]
    return np.percentile(stats, [2.5, 97.5])


pd.set_option("display.width", 160)
cur, bet = pairs(CURRENT), pairs(BETTER)
lazy = human.assign(score=0)                                # "lazy AI": says every trait is absent

print("=== Headline (slide 7b + backup table) ===")
table = pd.DataFrame({"current AI (flash-lite)": summary(cur), "better AI (3.8-flash)": summary(bet),
                      "lazy AI (all 0s)": summary(lazy)}).T
print(table.round(2).to_string())
for name, p in (("current", cur), ("better", bet)):
    lo, hi = bootstrap_ci(p)
    print(f"  {name} kappa 95% CI: {lo:.2f}-{hi:.2f}")
print(f"  share of human scores that are 0: {(human.human == 0).mean():.0%}")

print("\n=== Consistency: same video, same prompt, asked twice ===")
r1, r2 = pairs(CURRENT, 1), pairs(CURRENT, 2)
both = r1.merge(r2[["video_id", "trait", "score"]], on=["video_id", "trait"], suffixes=("_1", "_2"))
print(f"  current AI run 1 vs run 2: kappa {kappa(both.score_1, both.score_2):.2f}")
avg = np.floor((both.score_1 + both.score_2) / 2).astype(int)
print(f"  averaging the two runs (rounded down): kappa vs human {kappa(both.human, avg):.2f}")

print("\n=== Is the better AI really better? (per video) ===")
m = cur.merge(bet[["video_id", "trait", "score"]], on=["video_id", "trait"], suffixes=("_cur", "_bet"))
diffs = []
for v, g in m.groupby("video_id"):
    kc, kb = kappa(g.human, g.score_cur), kappa(g.human, g.score_bet)
    diffs.append(kb - kc)
    print(f"  {v}: current {kc:.2f} | better {kb:.2f}")
diffs = np.array(diffs)
wins = int((diffs > 0).sum())
print(f"  better AI higher on {wins}/{len(diffs)} videos; mean difference {diffs.mean():+.2f}; "
      f"sign test p = {binomtest(wins, len(diffs)).pvalue:.2f}; paired t-test p = {ttest_1samp(diffs, 0).pvalue:.2f}")

print("\n=== By trait category (slide 7c): Krippendorff's alpha ===")
rows = []
for name, p in (("current", cur), ("better", bet)):
    p = p.assign(category=p.trait.map(lambda t: traits[t]["category"]))
    for c, g in p.groupby("category"):
        rows.append({"model": name, "category": c, "alpha": alpha(g.human, g.score), "bias": (g.score - g.human).mean()})
cat = pd.DataFrame(rows).pivot(index="category", columns="model", values=["alpha", "bias"])
print(cat.round(2).to_string())
for name in ("current", "better"):
    ok = (cat[("alpha", name)] >= 0.667).sum()
    print(f"  {name}: {ok}/5 categories at or above 0.667")

print("\n=== What weak tags do to the engagement model (approximation) ===")
print("  Classical measurement error shrinks a trait's estimated effect to about (reliability x true effect).")
for c, a_ in cat[("alpha", "current")].sort_values().items():
    print(f"  {c:18s} alpha {a_:.2f} -> effect looks ~{1 - a_:.0%} weaker than it is")

"""
Downstream test (SIMULATION): how much do the AI's measured tagging errors hurt the engagement model?

Austin's suggestion (Oct 2026): judge LLM tagging by downstream model performance, not only by agreement.
Until we have the team's real model matrix, this simulates a dataset shaped like Leo's (notebook 02_lasso:
726 videos, 75 Linear 0-4 traits + 4 Binary, Lasso with alpha chosen by 5-fold CV, 80/20 split) where we
KNOW which traits drive engagement, then replaces the true trait scores with AI-like scores drawn from the
confusion matrices measured on our human-tagged videos (P(AI score | human score), per model).

Engagement here is SYNTHETIC. The point is the comparison between tag sources and encodings, not the numbers'
absolute level. Assumptions are stated at the top and can be changed.

Run:  python downstream_sim.py            (≈ a few minutes)
"""
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LassoCV
from sklearn.metrics import r2_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore", category=ConvergenceWarning)
D = Path(__file__).parent / "data"
rng = np.random.default_rng(585)

# ---------------- assumptions (change to test sensitivity) ----------------
N_VIDEOS = 726          # = Leo's analysis snapshot
N_DRIVERS = 10          # traits that truly affect engagement
TRUE_R2 = 0.40          # share of engagement variance the true traits explain
N_SIMS = 30
# "linear": effect grows evenly with the 0-4 score (what ordinal coding assumes)
# "threshold": effect only once a trait is featured (score >= 3), what one-hot can capture and ordinal cannot
import sys
SHAPES = sys.argv[1:] or ["linear", "threshold"]
MODELS = ["gemini-3.1-flash-lite", "gemini-3.8-flash"]

# ---------------- measured inputs ----------------
traits = json.load(open(D / "traits_v2.json"))
linear = [t["name"] for t in traits if t["scale"] == "linear"]
binary = [t["name"] for t in traits if t["scale"] == "binary"]
sheet = pd.read_csv(D / "manual_tags.csv")
vmap = pd.read_csv(D / "video_map.csv").set_index("sheet_column")
human = pd.concat(pd.DataFrame({"video_id": vmap.loc[c, "video_id"], "trait": sheet.Trait,
                                "human": pd.to_numeric(sheet[c], errors="coerce")}) for c in sheet.columns[1:])
human = human[human.human.isin([0, 1, 2, 3, 4])].copy()
is_bin = human.trait.isin(binary)
human.loc[is_bin, "human"] = (human.loc[is_bin, "human"] >= 1).astype(int)
human["human"] = human.human.astype(int)
ai = pd.read_csv(D / "ai_tags_v2.csv")
ai = ai[ai.run == 1]

# how often each human level occurs, per Linear trait (smoothed toward the pooled distribution: few videos per trait)
pooled = human[human.trait.isin(linear)].human.value_counts(normalize=True).reindex(range(5), fill_value=0).values
level_p = {}
for t in linear:
    counts = human[human.trait == t].human.value_counts().reindex(range(5), fill_value=0).values
    level_p[t] = (counts + 5 * pooled) / (counts.sum() + 5)          # 5 pseudo-videos of the pooled shape
bin_p = {t: (human[human.trait == t].human.sum() + 1) / (len(human[human.trait == t]) + 2) for t in binary}


def confusion(model):
    """P(AI level | human level), measured on the human-tagged videos; rows with few cases lean on overall error."""
    p = human.merge(ai[ai.model == model][["video_id", "trait", "score"]], on=["video_id", "trait"])
    lin = p[p.trait.isin(linear)]
    C = pd.crosstab(lin.human, lin.score).reindex(index=range(5), columns=range(5), fill_value=0).values + 0.5
    C = C / C.sum(1, keepdims=True)
    b = p[p.trait.isin(binary)]
    B = pd.crosstab(b.human, b.score).reindex(index=range(2), columns=range(2), fill_value=0).values + 0.5
    return C, B / B.sum(1, keepdims=True), p.video_id.nunique()


def draw_true(n):
    X = {t: rng.choice(5, n, p=level_p[t]) for t in linear}
    X.update({t: rng.binomial(1, bin_p[t], n) for t in binary})
    return pd.DataFrame(X)


def through_ai(X, C, B):
    """Replace each true score with an AI score drawn from P(AI | true level)."""
    Y = X.copy()
    for t in linear:
        u = rng.random(len(X)); cum = C[X[t].values].cumsum(1)
        Y[t] = (u[:, None] > cum).sum(1)
    for t in binary:
        u = rng.random(len(X)); Y[t] = (u > B[X[t].values, 0]).astype(int)
    return Y


def encode(X, how, enc=None):
    if how == "ordinal":
        return X.values.astype(float), None
    if enc is None:
        enc = OneHotEncoder(categories=[list(range(5))] * len(linear), drop="first", sparse_output=False).fit(X[linear])
    return np.c_[enc.transform(X[linear]), X[binary].values], enc


def trait_importance(coef, how):
    """One importance per trait: |coef| (ordinal) or summed |coef| over its 4 dummies (one-hot)."""
    if how == "ordinal":
        return pd.Series(np.abs(coef), index=linear + binary)
    lin = np.abs(coef[: 4 * len(linear)]).reshape(len(linear), 4).sum(1)
    return pd.Series(np.r_[lin, np.abs(coef[4 * len(linear):])], index=linear + binary)


rows = []
confs = {m: confusion(m) for m in MODELS}
for shape in SHAPES:
  for sim in range(N_SIMS):
      X = draw_true(N_VIDEOS)
      drivers = rng.choice(linear, N_DRIVERS, replace=False)
      beta = pd.Series(0.0, index=linear + binary)
      beta[drivers] = rng.choice([-1, 1], N_DRIVERS) * rng.uniform(0.15, 0.4, N_DRIVERS)
      Xs = X.values if shape == "linear" else np.where(X.values >= 3, 3, 0) * np.isin(np.arange(X.shape[1]), [list(X.columns).index(t) for t in linear])[None, :] + X.values * np.isin(np.arange(X.shape[1]), [list(X.columns).index(t) for t in binary])[None, :]
      signal = Xs @ beta.values
      noise_sd = np.sqrt(signal.var() * (1 - TRUE_R2) / TRUE_R2)
      y = signal + rng.normal(0, noise_sd, N_VIDEOS)
      test = rng.random(N_VIDEOS) < 0.2
      sources = {"human-quality tags (ceiling)": X}
      for m in MODELS:
          sources[m] = through_ai(X, *confs[m][:2])
      for src, Xo in sources.items():
          for how in ("ordinal", "one-hot"):
              Xtr, enc = encode(Xo[~test], how)
              Xte, _ = encode(Xo[test], how, enc)
              sc = StandardScaler().fit(Xtr)
              model = LassoCV(cv=5, alphas=40, max_iter=20000, random_state=sim).fit(sc.transform(Xtr), y[~test])
              imp = trait_importance(model.coef_, how)
              top = set(imp.sort_values(ascending=False).head(N_DRIVERS).index)
              rows.append({"shape": shape, "sim": sim, "tags": src, "encoding": how,
                           "test_R2": r2_score(y[test], model.predict(sc.transform(Xte))),
                           "true_drivers_found_of_10": len(top & set(drivers)),
                           "columns_kept": int((np.abs(model.coef_) > 1e-8).sum())})

res = pd.DataFrame(rows)
summary = res.groupby(["shape", "tags", "encoding"]).agg(
    test_R2=("test_R2", "mean"), test_R2_sd=("test_R2", "std"),
    drivers_found=("true_drivers_found_of_10", "mean"), columns_kept=("columns_kept", "mean")).round(3)
order = ["human-quality tags (ceiling)"] + MODELS
summary = summary.reindex([(sh, t, e) for sh in SHAPES for t in order for e in ("ordinal", "one-hot")])
print(f"SIMULATION — synthetic engagement; AI error rates measured on {confs[MODELS[0]][2]} human-tagged videos")
print(f"{N_SIMS} simulated datasets of {N_VIDEOS} videos; {N_DRIVERS} true driver traits; traits explain {TRUE_R2:.0%} of engagement")
print(summary.to_string())
res.to_csv(Path(__file__).parent / "downstream_sim_results.csv", index=False)

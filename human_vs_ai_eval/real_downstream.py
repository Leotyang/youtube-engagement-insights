"""
Downstream test on the REAL data (Austin, Nov 4: "test downstream model performance to find LLM tagging performance").

Question: the team's model explains views with AI tags. The AI's tags disagree with humans (kappa 0.69). Does that
error change WHICH traits come out as drivers, and by how much does it shrink their effects?

We cannot human-tag 2,826 videos, so we use MC-SIMEX (Kuchenhoff, Mwalili & Lesaffre 2006, Biometrics 62:85-96),
the standard correction for misclassified categorical variables:
  1. Measure the AI's error pattern per trait: Pi[i, j] = P(AI says j | human says i), from the 21 human-tagged videos
     (current model flash-lite, run 1; production tags match these re-runs at kappa 0.92, production_vs_human.py).
  2. Deliberately add MORE of that error to the real tags: lambda = 1 adds one extra dose (each tag re-drawn from
     Pi[its value]), lambda = 2 two doses, lambda = 3 three. Refit the model each time.
  3. Each coefficient drifts as error is added. Fit a quadratic in lambda and extrapolate back to lambda = -1,
     i.e. zero AI error ("what the model would say with human-quality tags").
  Uncertainty: steps 1-3 are repeated on 30 bootstrap resamples of the 21 human-tagged videos, so the interval
  includes the fact that the error pattern itself was measured on few videos.

Model (explainability, cross-sectional, Austin's Nov 4 framing). Outcome log(views + 1). Main spec controls for age,
the dominant confounder (log age + log age^2), plus log duration and log channel subscribers. Robustness: the same
with channel fixed effects (within-channel comparison). Standard errors clustered by channel (videos of one channel
are not independent). Traits are in SD units (1 SD of the observed tag), so coefficients are comparable.
Leo-style check: LassoCV (5-fold, 40 alphas) on an 80/20 split, test R^2 and selected traits as error is added.

Judgment calls (stated so they can be changed): smoothing k = 3 pseudo-counts toward the pooled error pattern of the
trait's scale type (linear / binary) because 21 videos cannot fill a 5x5 table per trait; "driver" = top 10 by
|coefficient| (effect size in SD units), used the same way before and after correction. Quadratic extrapolation is
the SIMEX standard; linear extrapolation is reported as the conservative (smaller) correction.

Run:  python real_downstream.py          (about 2 minutes)
Out:  real_downstream_coefs.csv, real_downstream_summary.csv
"""
import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LassoCV
from sklearn.model_selection import train_test_split

warnings.filterwarnings("ignore")
HERE = Path(__file__).parent
D = HERE / "data"
rng = np.random.default_rng(585)
LAMBDAS = [0, 1, 2, 3]
N_PI, N_REP, N_LASSO = 30, 5, 10        # bootstrap draws of Pi, SIMEX replicates per lambda, Lasso replicates
K_SMOOTH, TOP = 3, 10

# ---------- data ----------
traits = json.load(open(D / "traits_v2.json"))
names = [t["name"] for t in traits]
cols = [re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_") for n in names]
scale = np.array([t["scale"] for t in traits])
levels = np.where(scale == "binary", 2, 5)

bq = pd.read_csv(D / "bq_llm_tagged_export.csv").sort_values("tagged_at").drop_duplicates("id", keep="last")
bq = bq.reset_index(drop=True)
T0 = bq[cols].to_numpy(int)                                   # observed AI tags, videos x 79
y = np.log1p(bq.views.to_numpy(float))
la = np.log1p(bq.age_days_at_pull.to_numpy(float))
controls = np.column_stack([la, la ** 2, np.log1p(bq.duration_seconds), np.log1p(bq.channel_subscribers)])
groups = bq.channel_id.astype("category").cat.codes.to_numpy()
SD = T0.std(0)

# ---------- human vs AI pairs -> error pattern Pi ----------
sheet = pd.read_csv(D / "manual_tags.csv")
vmap = pd.read_csv(D / "video_map.csv").set_index("sheet_column")
human = pd.concat(pd.DataFrame({"video_id": vmap.loc[c, "video_id"], "trait": sheet.Trait,
                                "human": pd.to_numeric(sheet[c], errors="coerce")}) for c in sheet.columns[1:])
human = human[human.human.isin([0, 1, 2, 3, 4])].copy()
is_bin = human.trait.map({t["name"]: t["scale"] for t in traits}) == "binary"
human["human"] = np.where(is_bin, (human.human >= 1).astype(int), human.human).astype(int)
ai = pd.read_csv(D / "ai_tags_v2.csv")
pairs = human.merge(ai[(ai.model == "gemini-3.1-flash-lite") & (ai.run == 1)][["video_id", "trait", "score"]],
                    on=["video_id", "trait"])
pair_vids = pairs.video_id.unique()
tidx = {n: i for i, n in enumerate(names)}


def estimate_pi(p):
    """Per-trait P(AI = j | human = i), smoothed toward the pooled pattern of the same scale type."""
    counts = [np.zeros((L, L)) for L in levels]
    for t, h, a in zip(p.trait.map(tidx), p.human, p.score):
        counts[t][h, a] += 1
    pooled = {}
    for s, L in (("linear", 5), ("binary", 2)):
        c = sum(counts[i] for i in range(len(names)) if scale[i] == s) + 0.5
        pooled[s] = c / c.sum(1, keepdims=True)
    return [(counts[i] + K_SMOOTH * pooled[scale[i]]) / (counts[i].sum(1, keepdims=True) + K_SMOOTH)
            for i in range(len(names))]


def add_error(T, pis, times):
    """Re-draw every tag from Pi[its current value], `times` times (one extra dose of AI error each)."""
    T = T.copy()
    for _ in range(times):
        for j, pi in enumerate(pis):
            cum = pi.cumsum(1)[T[:, j]]
            T[:, j] = (rng.random(len(T))[:, None] > cum[:, :-1]).sum(1)
    return T


# ---------- models ----------
def demean(a, g):
    a = np.asarray(a, float)
    out = a.copy()
    for k in np.unique(g):
        m = g == k
        out[m] -= a[m].mean(0)
    return out


def ols(T, fe=False):
    """OLS of log views on traits (SD units) + controls; returns trait coefs, cluster-robust SEs, R^2."""
    Xt = T / SD
    if fe:   # channel fixed effects: compare videos within the same channel; subscribers is constant -> dropped
        X, yy = np.column_stack([demean(Xt, groups), demean(controls[:, :3], groups)]), demean(y, groups)
    else:
        X, yy = np.column_stack([np.ones(len(y)), Xt, controls]), y
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ X.T @ yy
    u = yy - X @ b
    meat = np.zeros((X.shape[1], X.shape[1]))
    for k in np.unique(groups):
        s = X[groups == k].T @ u[groups == k]
        meat += np.outer(s, s)
    G, n, p = len(np.unique(groups)), len(yy), X.shape[1]
    V = XtX_inv @ meat @ XtX_inv * G / (G - 1) * (n - 1) / (n - p)
    sl = slice(0, 79) if fe else slice(1, 80)
    return b[sl], np.sqrt(np.diag(V))[sl], 1 - (u ** 2).sum() / ((yy - yy.mean()) ** 2).sum()


def extrapolate(lams, vals, deg=2):
    """Polynomial in lambda through the SIMEX means, evaluated at lambda = -1 (no AI error)."""
    return np.polyval(np.polyfit(lams, vals, deg), -1)


def top(v, k=TOP):
    return set(np.argsort(-np.abs(v))[:k])


# ---------- 1. naive fits (what the team's model sees today) ----------
summary = {}
coefs = pd.DataFrame({"trait": names, "category": [t["category"] for t in traits], "scale": scale,
                      "ai_present_%": (T0 > 0).mean(0) * 100})
for spec, fe in (("main", False), ("channel_FE", True)):
    b, se, r2 = ols(T0, fe)
    coefs[f"{spec}_naive"], coefs[f"{spec}_t"] = b, b / se
    summary[f"{spec}: R2 with AI tags (in-sample)"] = r2
    summary[f"{spec}: traits significant at 5% (|t|>1.96, clustered)"] = int((np.abs(b / se) > 1.96).sum())

# ---------- 2. MC-SIMEX, with the error pattern re-estimated on bootstrap resamples of the human-tagged videos ----------
corrected = {"main": [], "channel_FE": []}
corrected_lin = {"main": [], "channel_FE": []}
curve = {"main": [], "channel_FE": []}
for d in range(N_PI):
    boot = rng.choice(pair_vids, len(pair_vids))
    pis = estimate_pi(pd.concat([pairs[pairs.video_id == v] for v in boot]))
    for spec, fe in (("main", False), ("channel_FE", True)):
        means = [coefs[f"{spec}_naive"].to_numpy()]
        for lam in LAMBDAS[1:]:
            means.append(np.mean([ols(add_error(T0, pis, lam), fe)[0] for _ in range(N_REP)], 0))
        means = np.array(means)
        curve[spec].append(means)
        corrected[spec].append(extrapolate(LAMBDAS, means))
        corrected_lin[spec].append(extrapolate(LAMBDAS, means, 1))
    print(f"  error-pattern draw {d + 1}/{N_PI} done", end="\r")
print()

for spec in corrected:
    C = np.array(corrected[spec])
    coefs[f"{spec}_corrected"] = np.median(C, 0)
    coefs[f"{spec}_corr_lo"], coefs[f"{spec}_corr_hi"] = np.percentile(C, [2.5, 97.5], 0)
    coefs[f"{spec}_corrected_linear"] = np.median(corrected_lin[spec], 0)
    naive = coefs[f"{spec}_naive"].to_numpy()
    mean_curve = np.mean(curve[spec], 0)
    for k, lam in enumerate(LAMBDAS[1:], 1):
        coefs[f"{spec}_lambda{lam}"] = mean_curve[k]
    nt = top(naive)
    keep = [len(nt & top(c)) for c in C]
    summary[f"{spec}: naive top-{TOP} drivers still top-{TOP} after correction (median, range)"] = \
        f"{int(np.median(keep))} ({min(keep)}-{max(keep)})"
    summary[f"{spec}: naive top-{TOP} still top-{TOP} after ONE extra dose of AI error"] = \
        len(nt & top(mean_curve[1]))
    summary[f"{spec}: top-{TOP} effects kept after ONE extra dose (median share of today's size)"] = \
        np.median(mean_curve[1][list(nt)] / naive[list(nt)])
    summary[f"{spec}: naive top-{TOP} still top-{TOP} with linear (conservative) correction"] = \
        len(nt & top(coefs[f"{spec}_corrected_linear"].to_numpy()))
    summary[f"{spec}: sign flips naive vs corrected, among naive top-{TOP}"] = \
        int(sum(np.sign(naive[i]) != np.sign(coefs[f"{spec}_corrected"][i]) for i in nt))
    ratio = np.median(np.abs(naive[list(nt)]) / np.abs(coefs[f"{spec}_corrected"].to_numpy()[list(nt)]))
    summary[f"{spec}: naive effect size as share of corrected, top-{TOP} median"] = ratio
    summary[f"{spec}: same, linear correction"] = np.median(
        np.abs(naive[list(nt)]) / np.abs(coefs[f"{spec}_corrected_linear"].to_numpy()[list(nt)]))
    coefs[f"{spec}_rank_naive"] = (-np.abs(coefs[f"{spec}_naive"])).rank().astype(int)
    coefs[f"{spec}_rank_corrected"] = (-np.abs(coefs[f"{spec}_corrected"])).rank().astype(int)

# ---------- 3. Leo-style Lasso as error is added ----------
pis = estimate_pi(pairs)
Xc = (controls - controls.mean(0)) / controls.std(0)
idx_tr, idx_te = train_test_split(np.arange(len(y)), test_size=0.2, random_state=585)


def lasso(T):
    X = np.column_stack([T / SD, Xc])
    m = LassoCV(cv=5, alphas=40, random_state=585, max_iter=5000).fit(X[idx_tr], y[idx_tr])
    return m.score(X[idx_te], y[idx_te]), m.coef_[:79]


r2_0, lc0 = lasso(T0)
sel0 = set(np.flatnonzero(lc0))
lasso_rows = [{"lambda": 0, "test_R2": r2_0, "traits_selected": len(sel0), "overlap_with_lambda0_%": 100.0}]
for lam in LAMBDAS[1:]:
    for _ in range(N_LASSO // 2 if lam > 1 else N_LASSO):
        r2, lc = lasso(add_error(T0, pis, lam))
        s = set(np.flatnonzero(lc))
        lasso_rows.append({"lambda": lam, "test_R2": r2, "traits_selected": len(s),
                           "overlap_with_lambda0_%": 100 * len(s & sel0) / max(len(sel0 | s), 1)})
lasso_df = pd.DataFrame(lasso_rows).groupby("lambda").mean()
r2_controls = LassoCV(cv=5, alphas=40, random_state=585).fit(Xc[idx_tr], y[idx_tr]).score(Xc[idx_te], y[idx_te])
summary["Lasso: test R2 controls only (age, duration, subscribers)"] = r2_controls
summary["Lasso: test R2 controls + AI tags (today)"] = r2_0
summary["Lasso: share of the tags' R2 gain over controls kept after ONE extra dose"] = \
    (lasso_df.test_R2[1] - r2_controls) / (r2_0 - r2_controls)
summary["Lasso: test R2 extrapolated to human-quality tags (quadratic, rough)"] = \
    extrapolate(lasso_df.index.to_numpy(float), lasso_df.test_R2.to_numpy())

# ---------- 4. does the error hit the traits the triage flags? ----------
tri = pd.read_csv(HERE / "trait_triage.csv")
tri = tri[tri.model == "current"].set_index("trait")
coefs["triage_tau_b"] = coefs.trait.map(tri.tau_b)
coefs["triage_verdict"] = coefs.trait.map(tri.verdict)
coefs["main_kept_share"] = coefs.main_lambda1 / coefs.main_naive   # after one extra dose: 1 = untouched, 0.5 = halved
ok = coefs.triage_tau_b.notna() & (coefs.triage_verdict != "too rare") & (coefs.main_naive.abs() > 0.1)
summary["Spearman(kept share, triage tau_b), judgeable traits with |effect| > 0.1 (positive = reliable shrink less)"] = \
    spearmanr(coefs.main_kept_share[ok], coefs.triage_tau_b[ok]).statistic
for v in ("trust", "review", "drop/redefine"):
    g = coefs[ok & coefs.triage_verdict.str.startswith(v)]
    summary[f"median kept share, triage '{v}' traits (n={len(g)})"] = g.main_kept_share.median()

# ---------- output ----------
coefs.round(4).to_csv(HERE / "real_downstream_coefs.csv", index=False)
pd.Series(summary, name="value").to_csv(HERE / "real_downstream_summary.csv")
pd.set_option("display.width", 200)
print(f"\nReal downstream test: {len(y)} videos, {len(np.unique(groups))} channels, 79 AI-tagged traits "
      f"(production flash-lite), error pattern from {len(pair_vids)} human-tagged videos\n")
for k, v in summary.items():
    print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")
print("\nLasso as AI error is added (lambda = extra doses):")
print(lasso_df.round(3).to_string())
show = ["trait", "main_naive", "main_t", "main_lambda1", "main_corrected", "main_corr_lo", "main_corr_hi",
        "main_corrected_linear", "main_rank_naive", "main_rank_corrected", "channel_FE_t", "triage_verdict"]
print(f"\nTop {TOP} drivers today (main spec, by |effect|), with corrected effects (log views per 1 SD of trait):")
print(coefs.sort_values("main_rank_naive").head(TOP)[show].round(3).to_string(index=False))
print(f"\nTop {TOP} after correction:")
print(coefs.sort_values("main_rank_corrected").head(TOP)[show].round(3).to_string(index=False))

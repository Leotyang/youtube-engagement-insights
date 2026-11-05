"""
Production tags vs human tags: are the tags the team's model actually uses (BigQuery llm_tagged) as good as
the re-runs we scored in evaluate.py?

Inputs:
  data/bq_llm_tagged_export.csv  BigQuery export (llm_tagged JOIN videos JOIN channels), Nov 5; one row per video
  data/manual_tags.csv, video_map.csv, traits_v2.json, ai_tags_v2.csv  as in evaluate.py

Compares, on the human-tagged videos that are also in BigQuery:
  production vs human            what the downstream model actually sees
  our flash-lite re-run vs human same model + Leo's prompt, tagged by us (the numbers on slide 7)
  production vs our re-run       does our re-run reproduce production? (if yes, slide-7 numbers carry over)

Run:  python production_vs_human.py
"""
import json
import re
from pathlib import Path

import krippendorff as kd
import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

HERE = Path(__file__).parent
D = HERE / "data"
LEVELS = [0, 1, 2, 3, 4]
rng = np.random.default_rng(585)

traits = {t["name"]: t for t in json.load(open(D / "traits_v2.json"))}
col_of = {t: re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_") for t in traits}   # same rule as the pipeline

sheet = pd.read_csv(D / "manual_tags.csv")
vmap = pd.read_csv(D / "video_map.csv").set_index("sheet_column")
human = pd.concat(pd.DataFrame({"video_id": vmap.loc[c, "video_id"], "trait": sheet.Trait,
                                "human": pd.to_numeric(sheet[c], errors="coerce")}) for c in sheet.columns[1:])
human = human[human.human.isin(LEVELS)].copy()
binary = human.trait.map(lambda t: traits[t]["scale"]) == "binary"
human["human"] = np.where(binary, (human.human >= 1).astype(int), human.human).astype(int)

bq = pd.read_csv(D / "bq_llm_tagged_export.csv").sort_values("tagged_at")
dupes = bq[bq.id.duplicated(keep=False)]
bq_latest = bq.drop_duplicates("id", keep="last")
prod = bq_latest[bq_latest.id.isin(human.video_id)].melt(
    id_vars="id", value_vars=list(col_of.values()), var_name="col", value_name="score")
prod["trait"] = prod.col.map({v: k for k, v in col_of.items()})
prod = prod.rename(columns={"id": "video_id"})[["video_id", "trait", "score"]]

ai = pd.read_csv(D / "ai_tags_v2.csv")
rerun = ai[(ai.model == "gemini-3.1-flash-lite") & (ai.run == 1)][["video_id", "trait", "score"]]


def kappa(x, y):
    return cohen_kappa_score(x, y, weights="quadratic", labels=LEVELS)


def alpha(x, y):
    return kd.alpha(reliability_data=np.vstack([x, y]).astype(float), level_of_measurement="ordinal",
                    value_domain=LEVELS)


def ci(p, a, b, n=2000):
    vids = p.video_id.unique()
    s = [kappa(q[a], q[b]) for q in (pd.concat([p[p.video_id == v] for v in rng.choice(vids, len(vids))])
                                      for _ in range(n))]
    return np.percentile(s, [2.5, 97.5])


def row(p, a, b):
    err = p[b] - p[a]
    lo, hi = ci(p, a, b)
    return {"videos": p.video_id.nunique(), "pairs": len(p), "kappa": kappa(p[a], p[b]), "kappa_lo": lo,
            "kappa_hi": hi, "alpha": alpha(p[a], p[b]), "exact_%": (err == 0).mean() * 100,
            "MAE": err.abs().mean(), "bias": err.mean()}


m = (human.merge(prod.rename(columns={"score": "production"}), on=["video_id", "trait"])
          .merge(rerun.rename(columns={"score": "rerun"}), on=["video_id", "trait"]))
vids = sorted(m.video_id.unique())
print(f"Human-tagged videos also in BigQuery: {len(vids)} of {human.video_id.nunique()}  ({', '.join(vids)})")
print(f"Not in BigQuery (excluded): {sorted(set(human.video_id) - set(vids))}\n")
res = pd.DataFrame({"production vs human": row(m, "human", "production"),
                    "our re-run vs human": row(m, "human", "rerun"),
                    "production vs our re-run": row(m, "rerun", "production")}).T
print(res.round(2).to_string())

per = pd.DataFrame([{"video_id": v, "prod_vs_human": kappa(g.human, g.production),
                     "rerun_vs_human": kappa(g.human, g.rerun), "prod_vs_rerun": kappa(g.rerun, g.production)}
                    for v, g in m.groupby("video_id")])
print("\nPer video (quadratic kappa):")
print(per.round(2).to_string(index=False))
print(f"\nProduction better than our re-run on {(per.prod_vs_human > per.rerun_vs_human).sum()} of {len(per)} videos")

if len(dupes):
    for v, g in dupes.groupby("id"):
        a, b = g.iloc[0][list(col_of.values())].astype(int), g.iloc[1][list(col_of.values())].astype(int)
        print(f"\nProduction tagged {v} twice ({g.tagged_at.iloc[0][:16]} and {g.tagged_at.iloc[1][:16]}): "
              f"same score on {(a.values == b.values).mean():.0%} of 79 traits, kappa {kappa(a, b):.2f}")

res.round(3).to_csv(HERE / "production_vs_human.csv")

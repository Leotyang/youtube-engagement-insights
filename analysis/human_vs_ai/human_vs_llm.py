import sys, json, re, os
import numpy as np, pandas as pd
from scipy.stats import spearmanr
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, REPO + "/src")
import config
from sheet import read_rows
from traits import get_traits
from google.cloud import bigquery
W = os.path.dirname(os.path.abspath(__file__))
traits = get_traits()
col_of = {re.sub(r"[^a-z0-9]+", "_", t["name"].lower()).strip("_"): t["column"] for t in traits}
category_of = {t["column"]: t["category"] for t in traits}
scale_of = {t["column"]: t["scale"] for t in traits}
cols = json.load(open(f"{W}/manual_cols.json"))
extra = {3: "BWNOdHB8TKA", 4: "_L1Rim7-IPo", 13: "0Rqoe5quCJQ", 15: "YFe8LFCgT68"}
rows = read_rows("Manual Tagging", "A:AA")
header_row = next(i for i, r in enumerate(rows) if r and r[0].strip() == "Trait")
human = {}
for r in rows[header_row + 1:]:
    if not r or not r[0].strip():
        continue
    key = re.sub(r"[^a-z0-9]+", "_", r[0].strip().lower()).strip("_")
    if key not in col_of:
        continue
    for o in cols:
        vid = o["ids"][0] if o["ids"] else extra[o["col"]]
        cell = r[o["col"]].strip() if len(r) > o["col"] else ""
        if cell != "":
            nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', cell)]
            if not nums:
                print('unparsed', vid, key, repr(cell)); continue
            if len(nums) > 1 or not re.fullmatch(r'\d+', cell):
                print('odd cell', vid, key, repr(cell))
            human.setdefault(vid, {})[col_of[key]] = float(np.mean(nums))
df_h = pd.DataFrame(human).T
print("human matrix", df_h.shape, "missing cells", int(df_h.isna().sum().sum()))
c = bigquery.Client(project=config.GCP_PROJECT_ID, location=config.BQ_LOCATION)
trait_cols = [t["column"] for t in traits]
df_l = c.query(f"""SELECT * EXCEPT(r) FROM (SELECT id, {', '.join(trait_cols)}, ROW_NUMBER() OVER (PARTITION BY id ORDER BY tagged_at) r
                   FROM youtube.llm_tagged WHERE id IN UNNEST(@ids)) WHERE r = 1""",
               job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("ids", "STRING", list(df_h.index))])).to_dataframe().set_index("id")
extra_scores = json.load(open(f"{W}/manual_llm_scores.json"))
df_l = pd.concat([df_l, pd.DataFrame(extra_scores).T[trait_cols]]).astype(float)
df_l = df_l[~df_l.index.duplicated()]
ids = [v for v in df_h.index if v in df_l.index]
df_h, df_l = df_h.loc[ids, trait_cols], df_l.loc[ids, trait_cols]
binary = [t for t in trait_cols if scale_of[t] == "binary"]
print("human values on binary traits:", {t: sorted(df_h[t].unique().tolist()) for t in binary})
df_h[binary] = (df_h[binary] > 0).astype(float)
print(len(ids), "videos with both")
meta = c.query("SELECT id, snippet_channelTitle ch FROM youtube.videos WHERE id IN UNNEST(@ids)",
               job_config=bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("ids", "STRING", ids)])).to_dataframe()
print("in dataset:", len(meta), "channels:", meta["ch"].nunique(), meta["ch"].value_counts().to_dict())
diff = df_l - df_h
lin = [t for t in trait_cols if scale_of[t] == "linear"]
print("overall exact", round((diff == 0).mean().mean(), 3), "within1", round((diff.abs() <= 1).mean().mean(), 3),
      "MAE", round(diff.abs().mean().mean(), 3), "mean LLM-human", round(diff.mean().mean(), 3))
print("all-zeros baseline exact vs human", round((df_h == 0).mean().mean(), 3))
# per-video rank agreement across traits
per_video = pd.Series({v: spearmanr(df_h.loc[v, lin], df_l.loc[v, lin])[0] for v in ids})
print("per-video Spearman across 75 linear traits: median", round(per_video.median(), 2), "range", round(per_video.min(), 2), round(per_video.max(), 2))
rows_out = []
retag = pd.read_csv(f"{REPO}/data/analysis/retag_consistency_by_trait.csv").set_index("trait")
for t in trait_cols:
    h, l = df_h[t], df_l[t]
    rho = spearmanr(h, l)[0] if h.nunique() > 1 and l.nunique() > 1 else np.nan
    rows_out.append({"trait": t, "category": category_of[t], "scale": scale_of[t], "human_nonzero": (h > 0).sum(), "llm_nonzero": (l > 0).sum(),
                     "spearman": rho, "bias": (l - h).mean(), "mae": (l - h).abs().mean(), "err_sd": (l - h).std(),
                     "exact": (l == h).mean(), "retag_kappa": retag.loc[t, "weighted_kappa"] if t in retag.index else np.nan})
df_t = pd.DataFrame(rows_out).set_index("trait")
def triage(r):
    if r["human_nonzero"] + r["llm_nonzero"] <= 2:
        return "too rare to judge"
    if r["err_sd"] <= 0.75 and abs(r["bias"]) < 0.5:
        return "trust"
    if r["err_sd"] <= 0.75:
        return "recalibrate"
    if not np.isnan(r["spearman"]) and r["spearman"] >= 0.5:
        return "recalibrate"
    return "drop or redefine"
df_t["triage"] = df_t.apply(triage, axis=1)
df_t.to_csv(f"{W}/human_vs_llm_by_trait.csv")
print(df_t["triage"].value_counts())
print(df_t.groupby("category")[["exact", "mae", "err_sd", "spearman", "bias"]].mean().round(2))
print(df_t.sort_values("err_sd", ascending=False).head(15).round(2).to_string())
print(df_t[df_t["triage"] == "recalibrate"].round(2).to_string())
per_video.to_csv(f"{W}/human_vs_llm_per_video.csv")

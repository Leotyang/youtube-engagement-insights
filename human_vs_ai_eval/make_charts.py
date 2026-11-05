"""Chart images for slides 7b/7c — labels baked in so Google Slides import can't drop them.
All numbers are computed from data/ (run 1 of each model, Leo's current prompt)."""
import json
from pathlib import Path
import numpy as np, pandas as pd, krippendorff as kd
from sklearn.metrics import cohen_kappa_score
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RED, GRAY, LIGHT, INK, MUTED, GRID = "#990000", "#8C8C8C", "#C9C8C3", "#1A1A1A", "#6B6B6B", "#E4E3DF"
plt.rcParams.update({"font.family": "Helvetica Neue", "font.size": 12, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": MUTED, "xtick.color": INK, "ytick.color": MUTED})

# ---- numbers computed from the data (run 1 of each model, Leo's current prompt) ----
D = Path(__file__).resolve().parent / "data"
TR = {t["name"]: t for t in json.load(open(D / "traits_v2.json"))}
man = pd.read_csv(D / "manual_tags.csv"); vm = pd.read_csv(D / "video_map.csv").set_index("sheet_column")
hum = pd.concat(pd.DataFrame({"video_id": vm.loc[c, "video_id"], "trait": man.Trait,
                              "h": pd.to_numeric(man[c], errors="coerce")}) for c in man.columns[1:])
hum = hum[hum.h.isin([0, 1, 2, 3, 4])].copy()
hum["h"] = np.where(hum.trait.map(lambda t: TR[t]["scale"]) == "binary", (hum.h >= 1).astype(int), hum.h).astype(int)
ai = pd.read_csv(D / "ai_tags_v2.csv"); ai = ai[ai.run == 1]
M = {m: hum.merge(ai[ai.model == m][["video_id", "trait", "score"]], on=["video_id", "trait"])
     for m in ("gemini-3.1-flash-lite", "gemini-3.8-flash")}
L, FL = M["gemini-3.1-flash-lite"], M["gemini-3.8-flash"]
assert L.video_id.nunique() == FL.video_id.nunique() == hum.video_id.nunique(), "a model is missing videos"
qwk = lambda d: cohen_kappa_score(d.h, d.score, weights="quadratic", labels=[0, 1, 2, 3, 4])
def alpha(d): return kd.alpha(reliability_data=np.vstack([d.h, d.score]).astype(float), level_of_measurement="ordinal", value_domain=[0, 1, 2, 3, 4])
EXACT = [round((L.h == L.score).mean() * 100), round((FL.h == FL.score).mean() * 100), round((hum.h == 0).mean() * 100)]
KAP = [round(qwk(L), 2), round(qwk(FL), 2), 0.0]
CATS = ["Subject Matter", "Tone and Emotion", "Audience Hooks", "Format", "Production"]
cat_a = lambda d: [round(alpha(d[d.trait.map(lambda t: TR[t]["category"]) == c]), 2) for c in CATS]
LITE_A, FLASH_A = cat_a(L), cat_a(FL)
NV = hum.video_id.nunique()
print("videos", NV, "exact", EXACT, "kappa", KAP, "lite α", LITE_A, "flash α", FLASH_A)

# ---- 7b: exact % vs κ ----
names = ["Current AI\n(flash-lite)", "Better AI\n(3.8-flash)", "Lazy AI\n(says 'absent'\nto everything)"]
cols = [GRAY, RED, LIGHT]
fig, axs = plt.subplots(1, 2, figsize=(7.2, 4.2), dpi=250)
panels = [
    (axs[0], EXACT, "Exact match with humans", "{:.0f}%", 100, ("Lazy AI scores higher than the current AI" if EXACT[2] > EXACT[0] else "Lazy AI looks as good as the real one")),
    (axs[1], KAP, "Agreement beyond luck (κ)", "{:.2f}", 1, "Lazy AI correctly scores zero"),
]
for ax, vals, title, fmt, top, note in panels:
    bars = ax.bar(range(3), vals, color=cols, width=0.62)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + top * 0.02, fmt.format(v), ha="center", va="bottom",
                fontsize=13, fontweight="bold", color=INK)
    ax.set_ylim(0, top * 1.12)
    ax.set_xticks(range(3), names, fontsize=9.5)
    ax.set_yticks([top * f for f in (0, .25, .5, .75, 1)])
    if top == 100:
        ax.set_yticklabels([f"{int(t)}%" for t in ax.get_yticks()], fontsize=9)
    else:
        ax.set_yticklabels([f"{t:.2f}" for t in ax.get_yticks()], fontsize=9)
    ax.grid(axis="y", color=GRID, lw=.8); ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=12.5, fontweight="bold", color=INK, pad=22)
    ax.text(0, 1.035, note, transform=ax.transAxes, fontsize=9.5, color=MUTED)
fig.tight_layout(w_pad=2.5)
fig.savefig(Path(__file__).parent / "charts" / "chart_7b.png", facecolor="white"); plt.close(fig)

# ---- 7c: α by category ----
cats = ["Subject\nMatter", "Tone &\nEmotion", "Audience\nHooks", "Format", "Production"]
lite = LITE_A
flash = FLASH_A
fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=250)
w = 0.38
x = range(len(cats))
b1 = ax.bar([i - w / 2 for i in x], lite, w * .95, color=LIGHT, label="Current AI (flash-lite)")
b2 = ax.bar([i + w / 2 for i in x], flash, w * .95, color=RED, label="Better AI (3.8-flash)")
for bars, tc in ((b1, INK), (b2, "white")):
    for bb in bars:
        ax.text(bb.get_x() + bb.get_width() / 2, bb.get_height() - .02, f"{bb.get_height():.2f}", ha="center",
                va="top", fontsize=9.5, color=tc, fontweight="bold")
ax.axhline(0.667, color=INK, ls="--", lw=1.3, label="Trust threshold (0.667)")
ax.set_ylim(0, 1.05); ax.set_yticks([0, .2, .4, .6, .8, 1.0]); ax.set_yticklabels([f"{t:.1f}" for t in ax.get_yticks()], fontsize=9)
ax.set_xticks(list(x), cats, fontsize=10.5)
ax.set_ylabel("Krippendorff's α (AI vs human)", fontsize=10, color=MUTED)
ax.grid(axis="y", color=GRID, lw=.8); ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=9.5, loc="upper right", ncol=3, bbox_to_anchor=(1.02, 1.13), handlelength=1.6, columnspacing=1.2)
ax.set_title("Agreement by trait category", loc="left", fontsize=12.5, fontweight="bold", color=INK, pad=28)
fig.tight_layout()
fig.savefig(Path(__file__).parent / "charts" / "chart_7c.png", facecolor="white"); plt.close(fig)
print("ok")

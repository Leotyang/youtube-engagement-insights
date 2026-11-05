"""Chart for the downstream simulation (reads downstream_sim_results.csv). Run after downstream_sim.py."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).parent
NAVY, AMBER, INK, MUTED, GRID = "#1F2A44", "#F2A900", "#1F2A44", "#5C6577", "#E3E6EC"
plt.rcParams.update({"font.family": "Arial", "font.size": 12, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": MUTED, "xtick.color": INK, "ytick.color": MUTED})

res = pd.read_csv(HERE / "downstream_sim_results.csv")
lin = res[res["shape"] == "linear"]
order = ["human-quality tags (ceiling)", "gemini-3.1-flash-lite", "gemini-3.8-flash"]
labels = ["Perfect tags\n(human quality)", "Current AI\n(flash-lite)", "Better AI\n(3.8-flash)"]
m = lin.groupby(["tags", "encoding"])[["test_R2", "true_drivers_found_of_10"]].mean()

fig, axes = plt.subplots(1, 2, figsize=(10, 4.3), dpi=220)
for ax, col, title, fmt, top in ((axes[0], "test_R2", "Model accuracy (test R²)", "{:.2f}", 0.45),
                                 (axes[1], "true_drivers_found_of_10", "True driver traits found (of 10)", "{:.1f}", 10.5)):
    for k, (enc, colr) in enumerate((("ordinal", NAVY), ("one-hot", AMBER))):
        vals = [m.loc[(t, enc), col] for t in order]
        xs = [i + (k - 0.5) * 0.36 for i in range(3)]
        bars = ax.bar(xs, vals, 0.34, color=colr, label=f"{enc} encoding")
        for x, v in zip(xs, vals):
            ax.text(x, v + top * 0.015, fmt.format(v), ha="center", va="bottom", fontsize=10.5, color=INK, fontweight="bold")
    ax.set_xticks(range(3), labels, fontsize=10.5)
    ax.set_ylim(0, top)
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=INK, pad=10)
axes[0].legend(frameon=False, fontsize=10, loc="upper right")
fig.tight_layout()
out = HERE / "charts" / "downstream_sim.png"
fig.savefig(out, facecolor="white")
print("wrote", out)

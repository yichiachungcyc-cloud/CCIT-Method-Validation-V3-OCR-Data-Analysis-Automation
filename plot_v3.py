from pathlib import Path
import os
import pandas as pd
import matplotlib.pyplot as plt

folder = Path(os.environ.get("CCIT_WORK_DIR", Path(__file__).resolve().parent)).resolve()
df = pd.read_csv(folder / "CCIT_v3_analysed.csv")

summary = pd.read_csv(folder / "CCIT_v3_summary.csv")

print(summary.to_string(index=False))

samples = df.loc[df["sample_category"] == "sample"]

fig, ax = plt.subplots(figsize=(10, 6))

status_styles = [
    ("未達接近區間", "steelblue", "Below Near-WL Range"),
    ("接近 WL", "orange", "Near WL"),
    ("超過 WL", "crimson", "Above WL"),
]

for status, color, label in status_styles:
    group = samples.loc[samples["wl_status"] == status]

    ax.scatter(
        group["test_id"],
        group["cycle2_pa"],
        color=color,
        label=label,
    )

ax.set_title(os.environ.get("CCIT_CHART_TITLE", "CCIT V3 - Sample Results"))
ax.set_xlabel("Test ID")
ax.set_ylabel("Cycle 2 Pa")


master_off = df.loc[df["sample_category"] == "master_off"]
master_on = df.loc[df["sample_category"] == "master_on"]

ax.scatter(
    master_off["test_id"],
    master_off["cycle2_pa"],
    color="seagreen",
    marker="s",
    label="Master MC-Off",
)

ax.scatter(
    master_on["test_id"],
    master_on["cycle2_pa"],
    color="purple",
    marker="^",
    label="Master MC-On",
)

positive = df.loc[df["sample_category"] == "positive"]

ax.scatter(
    positive["test_id"],
    positive["cycle2_pa"],
    color="darkorange",
    marker="D",  #菱形
    label="Positive SPL / STD",
)

summary_values = summary.set_index("parameter")["value"]

near_threshold = summary_values["near_threshold"]
warning_limit = summary_values["warning_limit"]
reject_limit = summary_values["reject_limit"]

ax.axhspan(
    near_threshold,
    warning_limit,
    color="gold",
    alpha=0.4,  #alpha 控制不透明度：0 完全透明，1 完全不透明
    label="Near WL Range",
)

ax.axhline(
    y=warning_limit,
    color="darkorange",
    linestyle="--",
    linewidth=1.5,
    label=f"WL: {warning_limit:.1f} Pa",
)

ax.axhline(
    y=reject_limit,
    color="firebrick",
    linestyle="-.",
    linewidth=1.5,
    label=f"Reject Limit: {reject_limit:.1f} Pa",
)

ax.grid(True, alpha=0.3)  #顯示格線，透明度設為 0.3(較淡)
ax.set_axisbelow(True)  #把格線放在資料點下方，避免蓋住點
ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1))


fig.tight_layout()

image_path = folder / "CCIT_v3_chart.png"
fig.savefig(image_path, dpi=300, bbox_inches="tight")

pdf_path = folder / "CCIT_v3_chart.pdf"
fig.savefig(pdf_path, bbox_inches="tight")


print("PDF 已儲存：", pdf_path)
print("繪製的一般 SPL 筆數：", len(samples))
print("圖片已儲存：", image_path)

if os.environ.get("CCIT_NO_SHOW") != "1":
    plt.show()
plt.close(fig)








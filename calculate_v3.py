from pathlib import Path
import os
import math
import pandas as pd

folder = Path(os.environ.get("CCIT_WORK_DIR", Path(__file__).resolve().parent)).resolve()
input_path = folder / "CCIT_v3_input.csv"

df = pd.read_csv(input_path, encoding="utf-8-sig")

product_type = os.environ.get("CCIT_PRODUCT_TYPE")
if product_type is None:
    product_type = input("請輸入樣品型態（liquid / solid）：")
product_type = product_type.strip().lower()
if product_type not in ("liquid", "solid"):
    raise ValueError("樣品型態只能輸入 liquid 或 solid")
for field in ("cycle1_mbar", "cycle1_pa", "cycle2_mbar", "cycle2_pa"):
    df[field] = pd.to_numeric(df[field], errors="raise")
    if not df[field].map(math.isfinite).all():
        raise ValueError(f"{field} 存在空值或無效數字")

print("讀入筆數：", len(df))
print(df[["test_no", "test_id", "sample_category"]].tail(3))

negative_mask = df["sample_category"] == "sample"
positive_mask = df["sample_category"] == "positive"

negative = df.loc[negative_mask, "cycle2_pa"]
positive = df.loc[positive_mask, "cycle2_pa"]

if len(negative) < 2 or positive.empty:
    raise ValueError("需要至少兩筆一般 SPL 及一筆陽性對照")

print("一般樣品筆數：", len(negative))
print("陽性對照筆數：", len(positive))

median_value = negative.median() 

absolute_deviations = (negative - median_value).abs()
mad_raw = absolute_deviations.median()

mad_scaled = mad_raw * 1.4826
initial_upper = median_value + 3 * mad_scaled

print("中位數：", median_value)
print("原始 MAD：", mad_raw)
print("校正後 MAD：", mad_scaled)
print("初步篩選上限：", initial_upper)

if mad_raw == 0:
    raise ValueError("MAD 為 0，請先人工確認資料分布")

df["initial_excluded"] = False

df.loc[negative_mask, "initial_excluded"] = (
    negative > initial_upper
)

excluded = df.loc[
    df["initial_excluded"],
    ["test_no", "comments", "cycle2_pa"]
]

print("初步排除筆數：", len(excluded))
print(excluded)

reference_mask = negative_mask & ~df["initial_excluded"]
reference = df.loc[reference_mask, "cycle2_pa"]

if len(reference) < 2:
    raise ValueError("參考資料不足 2 筆，無法計算樣本 SD")

reference_mean = reference.mean()
reference_sd = reference.std()

near_threshold = reference_mean + 2 * reference_sd
warning_limit = reference_mean + 3 * reference_sd

print("參考子集筆數：", len(reference))
print("參考平均值：", reference_mean)
print("參考 SD：", reference_sd)
print("接近 WL 區間下緣：", near_threshold)
print("Warning Limit（WL）：", warning_limit)

df["wl_status"] = "不適用" 

df.loc[negative_mask, "wl_status"] = "未達接近區間"

near_mask = (
    negative_mask
    & (df["cycle2_pa"] >= near_threshold)
    & (df["cycle2_pa"] <= warning_limit)
)

above_mask = (
    negative_mask
    & (df["cycle2_pa"] > warning_limit)
)

df.loc[near_mask, "wl_status"] = "接近 WL"
df.loc[above_mask, "wl_status"] = "超過 WL"

print(df.loc[
    near_mask | above_mask, #所以只印出「接近 WL」或「超過 WL」的資料
    ["test_no", "comments", "cycle2_pa", "wl_status"]
])


positive_mean = positive.mean()
reject_midpoint = (positive_mean + warning_limit) / 2

print("陽性對照平均值：", positive_mean)
print("Reject limit 調整前：", reject_midpoint)

rounded = int(round(reject_midpoint))  #將值轉成int
remainder = rounded % 10  #=餘數

if remainder <= 3:
    reject_limit = rounded - remainder
elif remainder <= 8:
    reject_limit = rounded - remainder + 5
else:
    reject_limit = rounded - remainder + 10

print("最終 Reject limit：", reject_limit)


analysed_path = folder / "CCIT_v3_analysed.csv"

df.to_csv(
    analysed_path,
    index=False,
    encoding="utf-8-sig"
)

print("分析資料已儲存：", analysed_path)

summary = pd.DataFrame([
    {"parameter": "median", "value": median_value},
    {"parameter": "mad_raw", "value": mad_raw},
    {"parameter": "mad_scaled", "value": mad_scaled},
    {"parameter": "initial_upper", "value": initial_upper},
    {"parameter": "reference_count", "value": len(reference)},
    {"parameter": "reference_mean", "value": reference_mean},
    {"parameter": "reference_sd", "value": reference_sd},
    {"parameter": "near_threshold", "value": near_threshold},
    {"parameter": "warning_limit", "value": warning_limit},
    {"parameter": "positive_mean", "value": positive_mean},
    {"parameter": "reject_midpoint", "value": reject_midpoint},
    {"parameter": "reject_limit", "value": reject_limit},
    {"parameter": "cycle2_pa_min", "value": -5}
])

summary_path = folder / "CCIT_v3_summary.csv"
summary.to_csv(
    summary_path, 
    index=False, 
    encoding="utf-8-sig"
)

print("統計摘要已儲存：", summary_path)

cycle1_reference_mean = df.loc[
    reference_mask, "cycle1_mbar"
].mean()

cycle1_mbar_min = cycle1_reference_mean - 50
cycle1_mbar_max = cycle1_reference_mean + 50

print("Cycle 1 mbar 參考平均值：", cycle1_reference_mean)
print("Cycle 1 mbar 最低值：", cycle1_mbar_min)
print("Cycle 1 mbar 最高值：", cycle1_mbar_max)


if product_type == "liquid":
    cycle2_mbar_min = 0
    cycle2_mbar_max = 10
    system_vacuum = 0
    disable_sys_vac = 0

elif product_type == "solid":
    cycle2_mbar_min = 490
    cycle2_mbar_max = 510
    system_vacuum = 1
    disable_sys_vac = 500

else:
    raise ValueError("樣品型態只能輸入 liquid 或 solid")

print("樣品型態：", product_type)
print("Cycle 2 mbar 最低值：", cycle2_mbar_min)
print("Cycle 2 mbar 最高值：", cycle2_mbar_max)
print("System Vacuum：", system_vacuum)
print("Disable Sys Vac：", disable_sys_vac)

settings = pd.DataFrame([
    {
        "product_type": product_type,
        "parameter": "Cycle 1 mbar min",
        "value": cycle1_mbar_min
    },
    {
        "product_type": product_type,
        "parameter": "Cycle 1 mbar max",
        "value": cycle1_mbar_max
    },
    {
        "product_type": product_type,
        "parameter": "Cycle 1 Pa min",
        "value": -5
    },
    {
        "product_type": product_type,
        "parameter": "Cycle 1 Pa max",
        "value": 50
    },
    {
        "product_type": product_type,
        "parameter": "Cycle 2 Pa min",
        "value": -5
    },
    {
        "product_type": product_type,
        "parameter": "Cycle 2 Pa max",
        "value": reject_limit
    },
    {
        "product_type": product_type,
        "parameter": "Cycle 2 mbar min",
        "value": cycle2_mbar_min
    },
    {
        "product_type": product_type,
        "parameter": "Cycle 2 mbar max",
        "value": cycle2_mbar_max
    },
    {
        "product_type": product_type,
        "parameter": "System Vacuum",
        "value": system_vacuum
    },
    {
        "product_type": product_type,
        "parameter": "Disable Sys Vac",
        "value": disable_sys_vac
    }
])

settings_path = folder / "CCIT_v3_system_settings.csv"
settings.to_csv(
    settings_path, 
    index=False, 
    encoding="utf-8-sig",
    float_format="%.1f"
)

print("系統設定已儲存：", settings_path)

"""將本次已核對的逐頁資料，轉成 V3 計算輸入。"""
from pathlib import Path
import os
import csv
import math
from pypdf import PdfReader

FOLDER = Path(os.environ.get("CCIT_WORK_DIR", Path(__file__).resolve().parent)).resolve()
MEASUREMENTS = ("cycle1_mbar", "cycle1_pa", "cycle2_mbar", "cycle2_pa")


def classify_comment(comment):
    text = comment.strip().casefold()
    if "master" in text:
        if "mc-off" in text or "mc_closed" in text:
            return "master_off"
        if "mc-on" in text or "mc@0.25cc/min" in text:
            return "master_on"
    elif "std" in text or "positive spl" in text:
        return "positive"
    elif "spl" in text:
        return "sample"
    raise ValueError(f"無法分類，請確認 Comments：{comment}")


def prepare_rows(rows):
    """先驗證整份資料，再按原始順序排除最後十筆及 QC Check。"""
    if len(rows) <= 10:
        raise ValueError("資料不足，排除最後十筆後沒有分析資料")
    seen = set()
    for row in rows:
        number = int(row["test_no"])
        if number <= 0 or number in seen:
            raise ValueError(f"Test No. 無效或重複：{number}")
        seen.add(number)
        if row["instrument_result"] not in ("Pass", "Fail"):
            raise ValueError(f"Test {number} 的 Result 尚未確認")
        for field in MEASUREMENTS:
            value = float(row[field])
            if not math.isfinite(value):
                raise ValueError(f"Test {number} 的 {field} 無效")

    suitability = rows[-10:]
    before_tail = rows[:-10]
    qc = [r for r in before_tail if "qc check" in r["comments"].casefold()]
    kept = [r for r in before_tail if "qc check" not in r["comments"].casefold()]
    categories = [classify_comment(r["comments"]) for r in kept]
    sample_count = categories.count("sample")
    if sample_count < 2 or "positive" not in categories:
        raise ValueError("需要至少兩筆一般 SPL 及一筆陽性對照")
    result = []
    sample_number = 0
    for row, category in zip(kept, categories):
        if category == "sample":
            sample_number += 1
            test_id = sample_number
        else:
            test_id = {"master_off": 0.1, "master_on": 0.5,
                       "positive": sample_count + 1}[category]
        result.append({
            "test_no": int(row["test_no"]), "test_id": test_id,
            **{field: float(row[field]) for field in MEASUREMENTS},
            "comments": row["comments"],
            "instrument_result": row["instrument_result"],
            "sample_category": category,
        })
    exclusions = [
        {"test_no": r["test_no"], "comments": r["comments"], "reason": reason}
        for group, reason in ((suitability, "Last 10 records: suitability"),
                              (qc, "QC Check")) for r in group
    ]
    return result, exclusions


def main():
    with (FOLDER / "CCIT.PDF").open("rb") as file:
        page_count = len(PdfReader(file).pages)
    rows = []
    for page in range(1, page_count + 1):
        path = FOLDER / "ocr_output" / f"page_{page}_paired_columns.csv"
        with path.open(newline="", encoding="utf-8-sig") as file:
            page_rows = list(csv.DictReader(file))
        if not page_rows:
            raise ValueError(f"第 {page} 頁沒有資料")
        rows.extend(page_rows)
    result, exclusions = prepare_rows(rows)
    for name, records in (("CCIT_v3_input.csv", result),
                          ("CCIT_v3_exclusions.csv", exclusions)):
        with (FOLDER / name).open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    print(f"原始資料：{len(rows)}；適用性：10；QC：{len(exclusions)-10}；保留：{len(result)}")


if __name__ == "__main__":
    main()

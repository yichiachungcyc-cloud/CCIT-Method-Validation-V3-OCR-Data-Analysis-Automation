"""Fictional fixture only. This demo never reads user reports or signs reviews."""
from pathlib import Path
import csv
import os
import subprocess
import sys
from prepare_v3_input import prepare_rows

ROOT = Path(__file__).resolve().parent


def synthetic_rows():
    rows = []

    def add(comment, pa, result="Pass"):
        rows.append({
            "test_no": str(len(rows) + 1),
            "cycle1_mbar": str(400 + (len(rows) % 7) / 10),
            "cycle1_pa": str(3 + len(rows) % 4),
            "cycle2_mbar": "0.2",
            "cycle2_pa": str(pa),
            "comments": comment,
            "instrument_result": result,
        })

    for i, value in enumerate((20, 21, 22), 1):
        add(f"DEMO Master MC-Off-{i}", value)
    for i, value in enumerate((85, 86, 87), 1):
        add(f"DEMO Master MC-On-{i}", value, "Fail")
    for i, value in enumerate((90, 92, 94), 1):
        add(f"DEMO Positive SPL_{i}", value, "Fail")
    sample_values = [12, 13, 14, 15, 16, 17, 18] * 4 + [22, 35]
    for i, value in enumerate(sample_values, 1):
        add(f"DEMO SPL_{i}", value)
        if i in (10, 20):
            add(f"DEMO QC Check_{i // 10}", 88, "Fail")
    for i in range(1, 6):
        add(f"DEMO Master MC-Off-END-{i}", 21)
    for i in range(1, 6):
        add(f"DEMO Master MC-On-END-{i}", 86, "Fail")
    return rows


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    folder = ROOT / "demo_output"
    folder.mkdir(exist_ok=True)
    rows = synthetic_rows()
    prepared, excluded = prepare_rows(rows)
    write_csv(folder / "synthetic_records.csv", rows)
    write_csv(folder / "CCIT_v3_input.csv", prepared)
    write_csv(folder / "CCIT_v3_exclusions.csv", excluded)
    env = dict(os.environ, CCIT_WORK_DIR=str(folder), CCIT_PRODUCT_TYPE="liquid",
               CCIT_NO_SHOW="1", MPLBACKEND="Agg", PYTHONIOENCODING="utf-8",
               CCIT_CHART_TITLE="CCIT V3 — Synthetic Demo / Not Instrument Data")
    print("SYNTHETIC DEMO: no OCR, no real reports, no human sign-off.", flush=True)
    for script in ("calculate_v3.py", "format_report.py", "plot_v3.py"):
        subprocess.run([sys.executable, str(ROOT / script)], env=env, cwd=folder, check=True)
    print(f"Fictional records: {len(rows)}; retained: {len(prepared)}; output: {folder}")


if __name__ == "__main__":
    main()

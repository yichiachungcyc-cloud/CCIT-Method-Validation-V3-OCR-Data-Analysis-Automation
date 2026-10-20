"""從 PDF 到圖表的入口。任何一步失敗，後續步驟停止。"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import re

FOLDER = Path(__file__).resolve().parent


def choose_pdf():
    """取消選檔就結束，不偷偷改讀舊 PDF。"""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    try:
        root.attributes("-topmost", True)
        return filedialog.askopenfilename(
            parent=root, title="選擇要分析的 CCIT PDF",
            filetypes=[("PDF files", "*.pdf")])
    finally:
        root.destroy()


def prepare_job(pdf, product_type):
    """同內容、同型態回到同資料夾；內容不同即使同名也分開。"""
    data = pdf.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    results = FOLDER / "results"
    results.mkdir(exist_ok=True)
    for existing in results.glob("*/job.json"):
        info = json.loads(existing.read_text(encoding="utf-8"))
        if info.get("pdf_sha256") == digest and info.get("product_type") == product_type:
            work = existing.parent
            if hashlib.sha256((work / "CCIT.PDF").read_bytes()).hexdigest() != digest:
                raise ValueError(f"工作資料夾的 PDF 已被修改：{work}")
            return work, digest
    name = re.sub(r'[^\w.-]+', '_', pdf.stem)[:45].strip('._') or 'PDF'
    work = results / f"{name}_{digest[:16]}_{product_type}"
    work.mkdir(exist_ok=False)
    (work / "CCIT.PDF").write_bytes(data)
    info = {"source_path": str(pdf), "source_name": pdf.name,
            "pdf_sha256": digest, "product_type": product_type}
    (work / "job.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return work, digest


def main():
    parser = argparse.ArgumentParser(description="CCIT V3: PDF → 人工核對 → Excel / 圖表")
    parser.add_argument("--product-type", choices=("liquid", "solid"))
    parser.add_argument("--pdf", type=Path, help="指定 PDF；省略時開啟選檔視窗")
    args = parser.parse_args()
    selected = args.pdf if args.pdf is not None else choose_pdf()
    if not selected:
        print("已取消選檔，沒有開始分析。")
        return
    pdf = Path(selected).expanduser().resolve()
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise SystemExit(f"請選擇現有 PDF：{pdf}")
    product_type = args.product_type
    if product_type is None:
        product_type = input("請輸入樣品型態（liquid / solid）：").strip().lower()
    if product_type not in ("liquid", "solid"):
        raise SystemExit("樣品型態只能輸入 liquid 或 solid")
    work, digest = prepare_job(pdf, product_type)
    print(f"\n本次結果資料夾：{work}", flush=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup = work / "backups" / f"before_pipeline_{run_id}"
    backup.mkdir(parents=True)
    for path in work.glob("CCIT_v3_*"):
        if path.is_file():
            shutil.copy2(path, backup / path.name)
    status = {"run_id": run_id, "status": "running", "product_type": product_type,
              "pdf_sha256": digest, "source_path": str(pdf), "work_dir": str(work),
              "backup": str(backup), "completed_steps": []}
    status_path = work / "pipeline_status.json"

    def save_status():
        status["updated_at"] = datetime.now(timezone.utc).isoformat()
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    environment = os.environ.copy()
    environment["CCIT_PRODUCT_TYPE"] = product_type
    environment["CCIT_WORK_DIR"] = str(work)
    environment["MPLBACKEND"] = "Agg"
    environment["CCIT_NO_SHOW"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    steps = ["extract_pdf.py", "column_ocr.py", "final_review.py", "prepare_v3_input.py",
             "calculate_v3.py", "format_report.py", "plot_v3.py"]
    save_status()
    try:
        for script in steps:
            status["current_step"] = script
            save_status()
            print(f"\n正在執行：{script}", flush=True)
            subprocess.run([sys.executable, str(FOLDER / script)], cwd=work,
                           env=environment, check=True)
            status["completed_steps"].append(script)
    except (subprocess.CalledProcessError, OSError, KeyboardInterrupt) as error:
        status["status"] = ("awaiting_final_review" if isinstance(error, subprocess.CalledProcessError)
                            and error.returncode == 2 and status["current_step"] == "final_review.py"
                            else "incomplete")
        status["error"] = str(error)
        save_status()
        print("\n本次尚未完成。請處理上方錯誤／核對表，再執行相同指令。")
        print("資料夾中的報表可能仍是舊版；請勿把它當成本次完成的結果。")
        print(f"核對表位於：{work / 'ocr_output'}")
        if status["status"] == "awaiting_final_review":
            print(f"最後核對與簽核：{work / 'CCIT_final_review.xlsx'}")
        print("填妥並關閉核對 CSV 後，重新執行入口，選同一份 PDF 與相同樣品型態。")
        raise SystemExit(1)
    status["status"] = "complete"
    status["outputs"] = ["CCIT_v3_report.xlsx", "CCIT_v3_chart.png", "CCIT_v3_chart.pdf"]
    save_status()
    print("\n本次完成：PDF、核對、計算、Excel 報表、PNG 與 PDF 圖表。")
    print(f"Excel 與圖表位於：{work}")


if __name__ == "__main__":
    main()

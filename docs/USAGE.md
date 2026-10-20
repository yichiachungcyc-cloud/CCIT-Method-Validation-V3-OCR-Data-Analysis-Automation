# Operation guide / 操作指南

## Input / 輸入

Run `python run_ccit_v3.py`, select a compatible PDF and enter `liquid` or `solid`. Alternatively pass `--pdf "path"` and `--product-type liquid`.

執行入口後選 PDF，再回終端機輸入型態。原檔不需改名；程式在 results 子資料夾保存副本與輸出。

## Resolve OCR exceptions / 修正 OCR 異常

Open the review CSV named in the message. Compare with `ocr_output/page_N.png`. Fill `corrected_value` and `correction_reason`; preserve identifiers, source fields and original OCR text. Save and close Excel before re-running.

依提示開啟核對 CSV，對照圖片後填修正值及原因。不要修改來源識別與原文。儲存、關閉 Excel，再選同一份 PDF 與型態執行。

## Final comparison and sign-off / 最後對照與簽核

Open `CCIT_final_review.xlsx` in the current work folder. Review all rows in **Data Review**, including grey exclusion rows. The **Source Image** hyperlink opens the original page image. Mark **Confirmed = Yes** only after comparing the row.

Open **Sign-off** and fill the yellow cells: reviewer name, date in `YYYY-MM-DD`, and `Approved`. Save, close, and rerun. Missing confirmations/sign-off stop downstream output. The record does not authenticate identity.

開啟本次結果資料夾的核對 Excel。點原圖連結逐列確認，包含灰色預計排除列。確認後填 Yes，再填 Sign-off 的姓名、日期與 Approved。這是人工紀錄，不是身分驗證。

If any value is wrong, leave that row unconfirmed and correct it upstream. Do not edit protected source cells. If the error is outside existing correction handlers, adapt the handler before continuing. Source changes archive the previous review and require a fresh sign-off.

發現錯誤先不要確認；回前段修正，必要時補對應的修正處理。來源改變會保留舊表並重新核對。

## Outputs / 輸出

| File | Purpose / 用途 |
|---|---|
| `CCIT_v3_report.xlsx` | Sample Analysis and System Settings / 樣品分析與系統設定 |
| `CCIT_v3_chart.png`, `.pdf` | Chart exports / 圖表 |
| `CCIT_v3_input.csv` | Filtered calculation input / 篩選後輸入 |
| `CCIT_v3_exclusions.csv` | Exclusion reasons / 排除原因 |
| `CCIT_v3_analysed.csv` | Measurements and statistical flags / 量測與統計標記 |
| `CCIT_v3_summary.csv` | Reference statistics and thresholds / 參考統計與門檻 |
| `final_signoff.json` | Manual reviewer record / 人工簽核紀錄 |
| `pipeline_status.json` | Status of the current attempt / 本次執行狀態 |

Use reports only after the current run says `complete`. `awaiting_final_review` is not completion. Old reports may still be present after a failed run.

本次狀態為 complete 才使用報表；待簽核或失敗時，資料夾可能仍有舊報表。

## Troubleshooting / 常見問題

- **PermissionError:** close the CSV/XLSX in Excel before writing again. / 先關閉 Excel 占用的檔案。
- **No file-picker window:** ensure Tkinter is available, or use `--pdf`. / 確認 Tkinter 或改用路徑參數。
- **Models unavailable:** first OCR use may require a model download. / 首次 OCR 可能需要網路下載模型。
- **Source mismatch:** do not force a correction from another report. / 不要套用其他報告的修正表。
- **Format unsupported:** inspect page images and adapt the template before trusting extraction. / 先檢查版面，不要忽略辨識問題。

## GitHub publishing checklist / 發布檢查

Publish this clean project folder, not the original working folder. Check staged files for PDFs, signatures, OCR text, real sample IDs and machine-specific paths. Only the generated fictional CSV and chart are allowlisted.

應上傳這個乾淨作品集資料夾，不是原工作資料夾。檢查來源 PDF、簽核、OCR 文字、真實樣品識別與私人路徑。僅模擬 CSV 與展示圖可公開。

Choose repository visibility and a reuse license before publication. No repository has been created by these files alone.

發布前決定公開／私人及授權；有這份專案不代表已建立遠端 GitHub repository。

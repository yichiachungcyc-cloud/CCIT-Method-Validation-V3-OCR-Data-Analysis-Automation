# Design notes / 設計說明

## Separation of responsibilities / 職責拆分

Whole-page OCR supplies headers and coordinates. Column OCR reduces merged cells. Matching uses page Y coordinates (`crop Y + crop top`) and a one-to-one time-row check. Neither method guarantees character correctness; final human comparison remains necessary.

整頁 OCR 提供表頭與位置；分欄 OCR 減少欄位黏在一起的問題。裁切內座標加回 top 後，才能與整頁時間列配對。一對一配對只代表位置符合條件，不保證字元正確。

The main runner executes seven scripts in order and stops on a nonzero exit. `final_review.py` is before `prepare_v3_input.py`, so final confirmation covers records that will later be excluded as well as retained samples. Individual scripts are not an access-control boundary.

主入口依序執行七個步驟；失敗就停止。最後人工確認放在篩選前，避免先移除資料後漏核對。個別程式不是存取控制邊界，操作時應使用入口。

## Source identity / 來源識別

The work folder is selected by PDF SHA-256 and product type. Review records bind to source data; altered final review values are rejected, and changed source data causes the previous workbook to be archived. Ordinary workbook protection prevents accidental edits; it is not cryptographic protection.

工作資料夾依 PDF 內容雜湊及型態區分。最終核對檢查來源與原值，來源改變後保留舊表並重新確認。Excel 保護是避免誤改，不是密碼學保護；姓名與日期也不驗證身分。

## Analysis specification / 分析規格

- **Reference filter:** ordinary samples only; exclude values strictly greater than `median + 3 × 1.4826 × median(abs(x − median))`. This is one upper-side pass, not iterative sigma clipping.
- **SD:** sample standard deviation (`ddof=1`). Zero MAD or fewer than two reference samples stops calculation.
- **Near WL:** `mean + 2 SD ≤ value ≤ mean + 3 SD`. **Above WL:** strictly greater than `mean + 3 SD`.
- **Reject midpoint:** `(positive_mean + WL) / 2`. First apply Python's integer `round` (ties-to-even). For the resulting integer's remainder modulo ten: 0–3 → lower ten; 4–8 → lower ten + 5; 9 → next ten.
- **Cycle 1 mbar:** reference-subset Cycle 1 mbar mean ± 50.
- **Cycle 1 Pa:** −5 to 50. **Cycle 2 Pa:** −5 to the adjusted reject limit.
- **Liquid:** Cycle 2 mbar 0–10; System Vacuum 0; Disable Sys Vac 0.
- **Solid:** Cycle 2 mbar 490–510; System Vacuum 1; Disable Sys Vac 500.

參考初篩只對一般樣品做一次上側篩選，並非反覆排除到沒有超限值。被排除者不參與參考平均與樣本 SD，但保留在表與圖上。WL 與儀器原始 Result 互不覆寫。以上皆為專案規則，不宣稱是 CCIT 通用標準。

## Display versus values / 顯示與數值

Analysis CSVs retain numerical precision. Reports/charts display one decimal. Final review cells use `0.0#######` to show at least one decimal without hiding additional measurement digits within that format.

計算保留精度，報表與圖表顯示一位小數。核對表至少顯示一位小數；396.0 顯示成 396 是格式問題，不一定是 OCR 少抓。

## Known constraints / 已知限制

- Expected table structure: Test, Time, Test#, mbar, Pa, mbar, Pa, Comments, Result.
- Pixel tolerances are tuned to the current rendering scale/template.
- Headers and time anchors can be confused by duplicated tables or audit trails.
- Pass/Fail are the only supported instrument results.
- Names must match the current category rules; unknown categories stop processing.
- The final ten-record exclusion is a configured workflow assumption, not an inferred suitability classification.
- Final review is a sign-off interface, not a general-purpose correction editor.
- Local files and hashes do not provide user authentication, immutable audit logs or comprehensive version-bound approval.
- Re-running can leave earlier outputs in place when a later step fails. Check the current `pipeline_status.json`.

不同掃描與版面仍需驗證；最後十筆是使用者指定的流程假設，不是程式判斷出的適用性分類。規則或程式變更後，應重新核對，不能沿用簽核就視為已驗證。

"""Template-based column OCR and position matching. Manual review is required."""
from pathlib import Path
import os
import csv
from PIL import Image
from pypdf import PdfReader
from rapidocr import RapidOCR

folder = Path(os.environ.get("CCIT_WORK_DIR", Path(__file__).resolve().parent)).resolve()
ocr_folder = folder / "ocr_output"

def normalize_review_time(value):
    """只供比對使用：9:55:42 與 09:55:42 相同，不改寫原始資料。"""
    import re
    text = str(value).strip()
    match = re.fullmatch(r"([0-9]{1,2}):([0-9]{2}):([0-9]{2})", text)
    if not match:
        raise ValueError(f"核對表時間格式無效：{text}")
    hour, minute, second = map(int, match.groups())
    if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
        raise ValueError(f"核對表時間超出範圍：{text}")
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def recognize_column(engine, image_path, top):
    result = engine(str(image_path))

    if not result.txts:
        raise ValueError(f"沒有辨識到文字：{image_path.name}")

    column_items = []

    for text, score, box in zip(
        result.txts, result.scores, result.boxes
    ):
        center_y = (
            min(point[1] for point in box)
            + max(point[1] for point in box)
        ) / 2

        column_items.append({
            "text": text,
            "score": float(score),
            "center_y": float(center_y),
            "page_center_y": float(center_y) + top,
        })

    column_items.sort(key=lambda item: item["page_center_y"])

    return column_items



def locate_table(page_number):
    """1. 讀取整頁 OCR，定位表頭、時間列與候選下緣。"""
    with (ocr_folder /  f"page_{page_number}_ocr.csv").open(
        "r", newline="", encoding="utf-8-sig"
    ) as file:
        items = list(csv.DictReader(file))

    pa_headers = [
        item for item in items
        if item["text"].strip().casefold() == "pa"
    ]

    pa_headers.sort(key=lambda item: float(item["left"]))

    if len(pa_headers) != 2:
        raise ValueError("沒有找到兩個 Pa 表頭，請先確認 OCR")

    pa_header = pa_headers[1]

    comments_headers = [
        item for item in items
        if item["text"].strip().casefold() == "comments"
        and abs(
            float(item["center_y"]) - float(pa_header["center_y"])
        ) <= 20
    ]

    if len(comments_headers) != 1:
        raise ValueError("無法確認 Comments 表頭位置")

    comments_header = comments_headers[0]

    left = int(float(pa_header["left"])) - 30 #(像素間距)

    right = int(
        (
            float(pa_header["right"])
            + float(comments_header["left"])
        ) / 2
    )

    top = int(float(pa_header["bottom"])) + 5 #(像素間距)，從 Pa 表頭底部再往下 5 像素開始裁切

    import re  ##Python 內建的文字格式比對工具


    time_headers = [
        item for item in items
        if item["text"].strip().casefold() == "time"
        and abs(
            float(item["center_y"]) - float(pa_header["center_y"])
        ) <= 20
    ]

    if len(time_headers) != 1:
        raise ValueError("無法確認 Time 表頭位置")

    time_header = time_headers[0]

    time_left = float(time_header["left"])

    time_items = [
        item for item in items
        if re.fullmatch(
            r"\d{1,2}:\d{2}:\d{2}", item["text"].strip()
        )
        and float(item["top"]) >= top
        and abs(float(item["left"]) - time_left) <= 40
    ]

    if not time_items:
        raise ValueError("Time 欄沒有找到時間，請核對定位")

    candidate_bottom = max(
        float(item["bottom"]) for item in time_items
    ) + 10

    print(
        f"第 {page_number} 頁，候選表格下緣："
        f"{candidate_bottom:.1f}"
    )

    last_time_item = max(
        time_items,
        key=lambda item: float(item["bottom"])
    )

    print(
        f"第 {page_number} 頁，最下方時間：",
        last_time_item["text"]
    )

    last_y = float(last_time_item["center_y"])

    last_row_items = [
        item for item in items
        if abs(float(item["center_y"]) - last_y) <= 20
    ]

    candidate_bottom = max(
        float(item["bottom"]) for item in last_row_items
    ) + 10

    print(
        f"第 {page_number} 頁，最後一列文字：",
        [item["text"] for item in last_row_items]
    )

    print(
        f"第 {page_number} 頁，整列候選下緣："
        f"{candidate_bottom:.1f}"
    )

    return items, time_items, left, right, top, candidate_bottom, comments_header


def recognize_pa(page_number, engine, time_items, left, right, top, candidate_bottom):
    """2. 裁出 Pa、辨識，並做雙向時間配對檢查。"""
    image_path = ocr_folder / f"page_{page_number}.png"
    crop_path = ocr_folder / f"page_{page_number}_cycle2_pa.png"

    with Image.open(image_path) as image:
        cropped = image.crop((
            max(0, left),
            top,
            min(image.width, right),
            min(image.height, int(candidate_bottom)),
        ))

        try:
            cropped.save(crop_path)
        finally:
            cropped.close()

    print("裁切圖片已儲存：", crop_path)


    print("正在辨識 Cycle 2 Pa 欄……")
    column_items = recognize_column(engine, crop_path, top)

    print("辨識出的文字框數量：", len(column_items))

    for number, item in enumerate(column_items, start=1):
        print(
            number,
            item["text"],
            "整頁 Y 座標：",
            round(item["page_center_y"], 1),
        )


    


    for pa_item in column_items:
        matches = [
            item for item in time_items
            if abs(
                float(item["center_y"]) - pa_item["page_center_y"]
            ) <= 20
        ]

        if len(matches) == 1:
            print(
                "Pa：", pa_item["text"],
                "對應時間：", matches[0]["text"],
            )
        else:
            print(
                "配對待確認，Pa：", pa_item["text"],
                "找到的時間數量：", len(matches),
            )

    problem_count = 0

    for time_item in time_items:
        matches = [
            pa_item for pa_item in column_items
            if abs(
                pa_item["page_center_y"]
                - float(time_item["center_y"])
            ) <= 20
        ]

        if len(matches) != 1:
            problem_count += 1

            print(
                "時間配對待確認：", time_item["text"],
                "找到的 Pa 數量：", len(matches),
            )

    print("時間文字框數量：", len(time_items))
    print("反向配對異常數：", problem_count)

    if problem_count != 0:
        raise ValueError("反向配對有異常，請先核對")

    paired_rows = []

    for pa_item in column_items:
        matches = [
            item for item in time_items
            if abs(
                float(item["center_y"]) - pa_item["page_center_y"]
            ) <= 20
        ]

        if len(matches) != 1:
            raise ValueError("Pa 無法唯一配對時間，請先核對")

        paired_rows.append({
            "time": matches[0]["text"],
            "cycle2_pa_text": pa_item["text"],
            "page_center_y": pa_item["page_center_y"],
        })

    paired_path = crop_path.with_name(
        crop_path.stem + "_paired.csv"
    )

    with paired_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["time", "cycle2_pa_text", "page_center_y"],
        )
        writer.writeheader()
        writer.writerows(paired_rows)

    print("配對結果已儲存：", paired_path)


    return image_path, column_items


def review_results(page_number, items, time_items, comments_header, top, candidate_bottom):
    """3. 找出 Result 疑點，讀回人工核對答案；不覆寫核對表。"""
    result_headers = [
        item for item in items
        if item["text"].strip().casefold() == "result"
        and abs(
            float(item["center_y"])
            - float(comments_header["center_y"])
        ) <= 20
    ]

    if len(result_headers) != 1:
        raise ValueError("無法確認 Result 表頭位置")

    result_header = result_headers[0]
    result_left = float(result_header["left"])
    result_right = float(result_header["right"])

    result_items = [
        item for item in items
        if top <= float(item["center_y"]) <= candidate_bottom
        and result_left - 30 <= (
            float(item["left"]) + float(item["right"])
        ) / 2 <= result_right + 30
    ]

    review_items = []

    for time_item in time_items:
        time_y = float(time_item["center_y"])

        matches = [
            item for item in result_items
            if abs(float(item["center_y"]) - time_y) <= 20
        ]

        if len(matches) != 1:
            reason = f"Result 文字框數量為 {len(matches)}，預期為 1"
        elif matches[0]["text"].strip() not in ["Pass", "Fail"]:
            reason = "Result 不是預期的 Pass／Fail"
        else:
            continue

        review_items.append({
            "page": page_number,
            "time": time_item["text"],
            "field": "Result",
            "ocr_text": " | ".join(item["text"] for item in matches),
            "reason": reason,
            "corrected_value": "",
            "correction_reason": "",
        })

    print(f"第 {page_number} 頁，Result 待確認筆數：{len(review_items)}")

    for item in review_items:
        print(item)

    review_path = ocr_folder / f"page_{page_number}_result_review.csv"

    if review_path.exists():
        print("核對表已存在，本次不覆寫：", review_path)
    else:
        with review_path.open(
            "x", newline="", encoding="utf-8-sig"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "page",
                    "time",
                    "field",
                    "ocr_text",
                    "reason",
                    "corrected_value",
                    "correction_reason",
                ],
            )

            writer.writeheader()
            writer.writerows(review_items)

        print("Result 核對表已儲存：", review_path)

    with review_path.open(
        "r", newline="", encoding="utf-8-sig"
    ) as file:
        saved_reviews = list(csv.DictReader(file))

    result_corrections = {}

    for review in review_items:
        matches = [
            saved for saved in saved_reviews
            if saved["page"] == str(review["page"])
            and normalize_review_time(saved["time"]) == normalize_review_time(review["time"])
            and saved["field"] == review["field"]
            and saved["ocr_text"] == review["ocr_text"]
        ]

        if len(matches) != 1:
            raise ValueError(
                f"核對記錄無法唯一對應：{review['time']}"
            )

        saved = matches[0]
        new_value = saved["corrected_value"].strip()
        reason = saved["correction_reason"].strip()

        if new_value not in ["Pass", "Fail"]:
            raise ValueError(
                f"{review['time']} 尚未填入有效修正值"
            )

        if not reason:
            raise ValueError(
                f"{review['time']} 尚未填寫修正原因"
            )

        if review["time"] in result_corrections:
            raise ValueError("同頁時間重複，不能只用時間定位修正")

        result_corrections[review["time"]] = new_value

        print(
            "已讀取人工修正：",
            review["time"],
            review["ocr_text"],
            "→",
            new_value,
        )



    return result_header, result_items, result_corrections


def recognize_comments(engine, image_path, result_header, right, top, candidate_bottom):
    """4. 裁出 Comments，使用同一個 OCR 工具辨識。"""
    comments_left = right

    comments_right = int(float(result_header["left"])) - 10

    comments_path = image_path.with_name(
        image_path.stem + "_comments.png"
    )

    with Image.open(image_path) as image:
        comments_image = image.crop((
            comments_left,
            top,
            comments_right,
            min(image.height, int(candidate_bottom)),
        ))

        try:
            comments_image.save(comments_path)
        finally:
            comments_image.close()

    print("Comments 裁圖已儲存：", comments_path)



    print("正在辨識 Comments 欄……")
    comments_items = recognize_column(engine, comments_path, top)

    print("Comments 文字框數量：", len(comments_items))

    for number, item in enumerate(comments_items, start=1):
        print(number, item["text"])

    return comments_items


def combine_columns(time_items, column_items, comments_items, result_items, result_corrections):
    """5. 依座標組合欄位，保留 Result 原文並套用核對值。"""
    for comment_item in comments_items:
        matches = [
            item for item in time_items
            if abs(
                float(item["center_y"])
                - comment_item["page_center_y"]
            ) <= 20
        ]

        if len(matches) != 1:
            raise ValueError(
                f"Comments 無法唯一配對時間：{comment_item['text']}"
            )

    combined_rows = []

    for time_item in time_items:
        time_y = float(time_item["center_y"])

        pa_matches = [
            item for item in column_items
            if abs(item["page_center_y"] - time_y) <= 20
        ]

        comment_matches = [
            item for item in comments_items
            if abs(item["page_center_y"] - time_y) <= 20
        ]

        if len(pa_matches) != 1 or len(comment_matches) != 1:
            raise ValueError(
                f"配對待確認，時間：{time_item['text']}，"
                f"Pa 數量：{len(pa_matches)}，"
                f"Comments 數量：{len(comment_matches)}"
            )

        combined_rows.append({
            "time": time_item["text"],
            "cycle2_pa_text": pa_matches[0]["text"],
            "comments": comment_matches[0]["text"],
            "page_center_y": time_y,
        })


    for row in combined_rows:
        matches = [
            item for item in result_items
            if abs(
                float(item["center_y"]) - row["page_center_y"]
            ) <= 20
        ]

        original_result = " | ".join(
            item["text"] for item in matches
        )

        if row["time"] in result_corrections:
            final_result = result_corrections[row["time"]]

        elif (
            len(matches) == 1
            and matches[0]["text"].strip() in ["Pass", "Fail"]
        ):
            final_result = matches[0]["text"].strip()

        else:
            raise ValueError(
                f"{row['time']} 的 Result 尚未完成核對"
            )

        row["result_ocr"] = original_result
        row["instrument_result"] = final_result

    combined_rows.sort(key=lambda item: item["page_center_y"])

    print("配對完成筆數：", len(combined_rows))

    for row in combined_rows:
        print(
            row["time"],
            row["cycle2_pa_text"],
            row["comments"],
        )


    return combined_rows


def save_page(image_path, combined_rows):
    """6. 儲存這一頁的配對結果。"""
    combined_path = image_path.with_name(
        image_path.stem + "_paired_columns.csv"
    )

    with combined_path.open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "time",
                "cycle2_pa_text",
                "comments",
                "page_center_y",
                "result_ocr",
                "instrument_result",
                "test_no_ocr",
                "test_no",
                "cycle1_mbar", "cycle1_pa", "cycle2_mbar", "cycle2_pa",
                "cycle1_mbar_ocr", "cycle1_mbar_score",
                "cycle1_pa_ocr", "cycle1_pa_score",
                "cycle2_mbar_ocr", "cycle2_mbar_score",
            ],
        )

        writer.writeheader()
        writer.writerows(combined_rows)

    print("分欄配對結果已儲存：", combined_path)




class ReviewRequired(ValueError):
    """需要人工核對時，停止本次正式輸出。"""


def extract_test_numbers(page_number):
    """先用整頁 OCR 的位置抓 Test#，不猜測或補寫編號。"""
    import re
    items, times, left, right, top, bottom, comments = locate_table(page_number)
    time_headers = [item for item in items
                    if item["text"].strip().casefold() == "time"
                    and abs(float(item["center_y"]) - float(comments["center_y"])) <= 20]
    if len(time_headers) != 1:
        raise ValueError(f"第 {page_number} 頁無法定位 Time 表頭")
    time_header = time_headers[0]
    headers = [item for item in items
               if item["text"].strip().casefold() in ("test", "test#")
               and float(item["left"]) > float(time_header["right"])
               and abs(float(item["center_y"]) - float(time_header["center_y"])) <= 20]
    if len(headers) != 1:
        raise ValueError(f"第 {page_number} 頁無法唯一定位 Test# 表頭")
    header = headers[0]
    candidates = [item for item in items
                  if top <= float(item["center_y"]) <= bottom
                  and float(header["left"]) - 30 <=
                  (float(item["left"]) + float(item["right"])) / 2
                  <= float(header["right"]) + 30]
    if len({normalize_review_time(item["text"]) for item in times}) != len(times):
        raise ValueError(f"第 {page_number} 頁時間重複，需另外核對定位")
    for item in candidates:
        matched_times = [t for t in times
                         if abs(float(t["center_y"]) - float(item["center_y"])) <= 20]
        if len(matched_times) != 1:
            raise ValueError(f"第 {page_number} 頁有 Test# 文字框無法唯一配對時間")
    records = []
    for time_item in times:
        matches = [item for item in candidates
                   if abs(float(item["center_y"]) - float(time_item["center_y"])) <= 20]
        raw = " | ".join(item["text"] for item in matches)
        number = None
        reason = ""
        if len(matches) != 1:
            reason = f"Test# 文字框數量為 {len(matches)}，預期為 1"
        elif not re.fullmatch(r"[0-9]+", raw.strip()) or int(raw.strip()) < 1:
            reason = "Test# 必須為正整數"
        else:
            number = int(raw.strip())
        records.append({"page": page_number, "time": time_item["text"],
                        "test_no_ocr": raw, "test_no": number, "reason": reason})
    return records


def prepare_test_numbers(page_count, pdf_path):
    """檢查所有頁的編號，產生核對表並驗證人工答案。"""
    import hashlib
    import re
    from collections import Counter

    fingerprint = hashlib.sha256(pdf_path.read_bytes())
    records = []
    for page_number in range(1, page_count + 1):
        fingerprint.update((ocr_folder / f"page_{page_number}_ocr.csv").read_bytes())
        records.extend(extract_test_numbers(page_number))
    source_id = fingerprint.hexdigest()
    counts = Counter(r["test_no"] for r in records if r["test_no"] is not None)
    for record in records:
        if record["test_no"] is not None and counts[record["test_no"]] > 1:
            record["reason"] = f"Test# {record['test_no']} 重複，請核對每個出現位置"
    issues = [record for record in records if record["reason"]]
    review_path = ocr_folder / "test_no_review.csv"
    fields = ["source_id", "page", "time", "field", "ocr_text", "reason",
              "corrected_value", "correction_reason"]
    if issues and not review_path.exists():
        with review_path.open("x", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for issue in issues:
                writer.writerow({"source_id": source_id, "page": issue["page"],
                                 "time": issue["time"], "field": "Test#",
                                 "ocr_text": issue["test_no_ocr"], "reason": issue["reason"],
                                 "corrected_value": "", "correction_reason": ""})
    print(f"Test# 共 {len(records)} 筆，待核對 {len(issues)} 筆")
    if issues:
        with review_path.open("r", newline="", encoding="utf-8-sig") as file:
            saved_rows = list(csv.DictReader(file))
        pending = []
        for issue in issues:
            matches = [saved for saved in saved_rows
                       if saved.get("source_id") == source_id
                       and saved.get("page") == str(issue["page"])
                       and normalize_review_time(saved.get("time", "")) == normalize_review_time(issue["time"])
                       and saved.get("field") == "Test#"
                       and saved.get("ocr_text") == issue["test_no_ocr"]]
            if len(matches) != 1:
                raise ReviewRequired(f"核對表與目前資料無法唯一對應，請檢查：{review_path}")
            saved = matches[0]
            value = saved.get("corrected_value", "").strip()
            reason = saved.get("correction_reason", "").strip()
            if not re.fullmatch(r"[0-9]+", value) or int(value) < 1 or not reason:
                pending.append(f"第 {issue['page']} 頁 {issue['time']}")
            else:
                issue["test_no"] = int(value)
        if pending:
            raise ReviewRequired("請完成 Test# 核對表：" + str(review_path)
                                 + "\n尚未完成：" + "、".join(pending))
    final_counts = Counter(record["test_no"] for record in records)
    if None in final_counts or any(count != 1 for count in final_counts.values()):
        raise ReviewRequired("核對後 Test# 仍有缺值或重複，請重新核對；不會自動補號。")
    return {(r["page"], r["time"]): r for r in records}



def parse_measurement(text):
    """只接受明確的有限數值，不自動刪除數字中間的空白。"""
    import re
    import math
    text = str(text).strip()
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)", text):
        raise ValueError(f"數值格式待核對：{text}")
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("數值必須為有限數")
    return value


def locate_measurement_columns(items, comments_header):
    """由表頭的左右順序決定三個量測欄，沿用目前報表版型。"""
    header_y = float(comments_header["center_y"])
    headers = [item for item in items
               if abs(float(item["center_y"]) - header_y) <= 20]
    numeric_headers = sorted(
        [item for item in headers if item["text"].strip().casefold() in ("mbar", "pa")],
        key=lambda item: float(item["left"]),
    )
    if [item["text"].strip().casefold() for item in numeric_headers] != ["mbar", "pa", "mbar", "pa"]:
        raise ValueError("量測表頭不是預期的 mbar、Pa、mbar、Pa，請核對版型")
    first = numeric_headers[0]
    preceding = [h for h in headers if float(h["right"]) < float(first["left"])]
    if not preceding:
        raise ValueError("找不到 Cycle 1 mbar 左側的表頭")
    previous = max(preceding, key=lambda h: float(h["right"]))
    columns = []
    for index, field in enumerate(("cycle1_mbar", "cycle1_pa", "cycle2_mbar")):
        current = numeric_headers[index]
        following = numeric_headers[index + 1]
        left = int((float(previous["right"]) + float(current["left"])) / 2)
        right = int((float(current["right"]) + float(following["left"])) / 2)
        columns.append((field, left, right))
        previous = current
    return columns


def read_measurements(page_number, engine, items, time_items, image_path,
                      comments_header, top, bottom):
    """三欄共用裁切、OCR 與雙向配對；疑點另外列入核對表。"""
    import hashlib
    columns = locate_measurement_columns(items, comments_header)
    values = {item["text"]: {} for item in time_items}
    issues = []
    digest = hashlib.sha256((folder / "CCIT.PDF").read_bytes())
    digest.update((ocr_folder / f"page_{page_number}_ocr.csv").read_bytes())
    digest.update(image_path.read_bytes())
    source_id = digest.hexdigest()

    for field, left, right in columns:
        crop_path = image_path.with_name(f"page_{page_number}_{field}.png")
        with Image.open(image_path) as image:
            crop_box = (max(0, left), top, min(image.width, right),
                        min(image.height, int(bottom)))
            if crop_box[0] >= crop_box[2] or crop_box[1] >= crop_box[3]:
                raise ValueError(f"{field} 裁切範圍無效")
            cropped = image.crop(crop_box)
            try:
                cropped.save(crop_path)
            finally:
                cropped.close()
        print(f"第 {page_number} 頁，正在辨識 {field}")
        detected = recognize_column(engine, crop_path, top)
        for item in detected:
            times = [t for t in time_items
                     if abs(float(t["center_y"]) - item["page_center_y"]) <= 20]
            if len(times) != 1:
                raise ReviewRequired(f"第 {page_number} 頁 {field} 有無法唯一配對的文字框，請查看裁圖")

        for time_item in time_items:
            time = time_item["text"]
            y = float(time_item["center_y"])
            matches = [item for item in detected if abs(item["page_center_y"] - y) <= 20]
            raw = " | ".join(item["text"] for item in matches)
            values[time][field + "_ocr"] = raw
            values[time][field + "_score"] = matches[0]["score"] if len(matches) == 1 else ""
            reason = ""
            if len(matches) != 1:
                reason = f"文字框數量為 {len(matches)}，預期為 1"
            else:
                try:
                    values[time][field] = parse_measurement(raw)
                except ValueError:
                    reason = "辨識文字不是明確數值"

            whole = [item for item in items
                     if abs(float(item["center_y"]) - y) <= 20
                     and left <= (float(item["left"]) + float(item["right"])) / 2 <= right]
            whole_raw = " | ".join(item["text"] for item in whole)
            if not reason:
                if len(whole) != 1:
                    reason = "整頁 OCR 無法提供唯一數值作比較"
                else:
                    try:
                        if parse_measurement(whole_raw) != values[time][field]:
                            reason = "分欄 OCR 與整頁 OCR 數值不同"
                    except ValueError:
                        reason = "整頁 OCR 數值格式待核對"
            if reason:
                issues.append({"source_id": source_id, "page": page_number,
                               "time": time, "field": field, "ocr_text": raw,
                               "whole_page_text": whole_raw, "reason": reason,
                               "corrected_value": "", "correction_reason": ""})

    review_path = ocr_folder / f"page_{page_number}_measurements_review.csv"
    if issues:
        if not review_path.exists():
            with review_path.open("x", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(file, fieldnames=list(issues[0]))
                writer.writeheader()
                writer.writerows(issues)
        with review_path.open("r", newline="", encoding="utf-8-sig") as file:
            saved_rows = list(csv.DictReader(file))
        pending = []
        for issue in issues:
            matches = [saved for saved in saved_rows
                       if saved.get("source_id") == source_id
                       and saved.get("page") == str(page_number)
                       and normalize_review_time(saved.get("time", "")) == normalize_review_time(issue["time"])
                       and saved.get("field") == issue["field"]
                       and saved.get("ocr_text") == issue["ocr_text"]
                       and saved.get("whole_page_text") == issue["whole_page_text"]]
            if len(matches) != 1:
                raise ReviewRequired(f"量測核對表與目前資料不符：{review_path}")
            saved = matches[0]
            try:
                value = parse_measurement(saved.get("corrected_value", ""))
                if not saved.get("correction_reason", "").strip():
                    raise ValueError("修正原因空白")
            except ValueError:
                pending.append(f"{issue['time']} {issue['field']}")
                continue
            values[issue["time"]][issue["field"]] = value
        if pending:
            raise ReviewRequired(f"請完成 {review_path}\n" + "、".join(pending))
    print(f"第 {page_number} 頁，三個量測欄完成：{len(values)} 列；核對項目：{len(issues)}")
    return values


def process_page(page_number, engine, test_numbers):
    """一頁的完整流程：先看這裡，不必一次理解所有細節。"""
    (items, time_items, left, right, top,
     candidate_bottom, comments_header) = locate_table(page_number)

    image_path, column_items = recognize_pa(
        page_number, engine, time_items, left, right, top, candidate_bottom
    )

    result_header, result_items, result_corrections = review_results(
        page_number, items, time_items, comments_header, top, candidate_bottom
    )

    comments_items = recognize_comments(
        engine, image_path, result_header, right, top, candidate_bottom
    )

    combined_rows = combine_columns(
        time_items, column_items, comments_items, result_items, result_corrections
    )

    for row in combined_rows:
        number_record = test_numbers[(page_number, row["time"])]
        row["test_no_ocr"] = number_record["test_no_ocr"]
        row["test_no"] = number_record["test_no"]

    measurements = read_measurements(
        page_number, engine, items, time_items, image_path,
        comments_header, top, candidate_bottom
    )
    for row in combined_rows:
        row.update(measurements[row["time"]])
        row["cycle2_pa"] = parse_measurement(row["cycle2_pa_text"])

    return combined_rows


def main():
    """整份 PDF 的入口：取得頁數、準備 OCR、逐頁處理。"""
    pdf_path = folder / "CCIT.PDF"
    with pdf_path.open("rb") as file:
        page_count = len(PdfReader(file).pages)

    print("PDF 總頁數：", page_count)
    test_numbers = prepare_test_numbers(page_count, pdf_path)
    print("正在準備 OCR……")
    engine = RapidOCR()

    completed_pages = []
    for page_number in range(1, page_count + 1):
        print(f"\n開始處理第 {page_number} 頁")
        rows = process_page(page_number, engine, test_numbers)
        completed_pages.append((page_number, rows))

    for page_number, rows in completed_pages:
        save_page(ocr_folder / f"page_{page_number}.png", rows)
    print("\n所有頁面的分欄辨識與配對已完成")


if __name__ == "__main__":
    try:
        main()
    except ReviewRequired as error:
        print(f"\n待人工核對：{error}")
        print("本次未更新配對結果；既有 CSV 是先前版本。")
        raise SystemExit(1)

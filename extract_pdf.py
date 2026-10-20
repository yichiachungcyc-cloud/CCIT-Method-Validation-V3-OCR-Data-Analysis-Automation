from pathlib import Path
import os
import pypdfium2 as pdfium
from rapidocr import RapidOCR
import csv

folder = Path(os.environ.get("CCIT_WORK_DIR", Path(__file__).resolve().parent)).resolve()
pdf_path = folder / "CCIT.PDF"

output_folder = folder / "ocr_output"
output_folder.mkdir(exist_ok=True)  #建立資料夾；已存在就繼續使用

print("正在準備 OCR……")
engine = RapidOCR()

pdf = pdfium.PdfDocument(str(pdf_path))

try:
    print("PDF 總頁數：", len(pdf))

    for page_index in range(len(pdf)):
        page_number = page_index + 1
        page = pdf[page_index]

        try:
            bitmap = page.render(scale=4)

            try:
                image = bitmap.to_pil()

                try:
                    image_path = (
                        output_folder / f"page_{page_number}.png"  #隨頁碼產生不同檔名
                    )
                    image.save(str(image_path))

                finally:
                    image.close()

            finally:
                bitmap.close()

        finally:
            page.close()

        print("圖片已儲存：", image_path)
        print(f"正在辨識第 {page_number} 頁……")
        result = engine(str(image_path))

        if not result.txts:
            raise ValueError(f"第 {page_number} 頁沒有辨識到文字，請確認圖片")

        print("文字框數量：", len(result.txts))
        print("前五個文字框：", list(result.txts[:5]))

        ocr_path = output_folder / f"page_{page_number}_ocr.csv"

        with ocr_path.open(
            "w", newline="", encoding="utf-8-sig"
        ) as file:
            writer = csv.writer(file)

            writer.writerow([
                "text", "score",
                "left", "top", "right", "bottom", "center_y"
            ])

            for text, score, box in zip(
                result.txts, result.scores, result.boxes
            ):
                left = float(min(point[0] for point in box))
                top = float(min(point[1] for point in box))
                right = float(max(point[0] for point in box))
                bottom = float(max(point[1] for point in box))
                center_y = (top + bottom) / 2

                writer.writerow([
                    text, float(score),
                    left, top, right, bottom, center_y
                ])

        print("OCR 明細已儲存：", ocr_path)

finally:
    pdf.close()

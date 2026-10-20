"""Synthetic-only tests: no confidential fixtures and no OCR model download."""
from pathlib import Path
from datetime import date
import tempfile
import unittest
from openpyxl import load_workbook
from demo import synthetic_rows
from prepare_v3_input import prepare_rows, classify_comment
from final_review import create_review, verify_review, PendingReview


class WorkflowTests(unittest.TestCase):
    def test_filter_order_and_x_positions(self):
        source = synthetic_rows()
        rows, excluded = prepare_rows(source)
        self.assertEqual((len(source), len(rows), len(excluded)), (51, 39, 12))
        self.assertEqual([int(r["test_no"]) for r in excluded[:10]], list(range(42, 52)))
        samples = [r for r in rows if r["sample_category"] == "sample"]
        self.assertEqual([r["test_id"] for r in samples], list(range(1, 31)))
        self.assertEqual({r["test_id"] for r in rows if r["sample_category"] == "positive"}, {31})

    def test_variable_sample_count(self):
        rows = synthetic_rows()
        rows = [r for r in rows if r["comments"] != "DEMO SPL_1"]
        prepared, _ = prepare_rows(rows)
        self.assertEqual({r["test_id"] for r in prepared if r["sample_category"] == "positive"}, {30})

    def test_positive_before_generic_spl(self):
        self.assertEqual(classify_comment("Positive SPL_example"), "positive")
        with self.assertRaises(ValueError):
            classify_comment("unclassified")

    def test_invalid_quantities_and_duplicate_ids(self):
        for value in ("NaN", "inf", "", "not-a-number"):
            with self.subTest(value=value):
                source = synthetic_rows()
                source[0]["cycle2_pa"] = value
                with self.assertRaises(ValueError):
                    prepare_rows(source)
        source = synthetic_rows()
        source[1]["test_no"] = source[0]["test_no"]
        with self.assertRaises(ValueError):
            prepare_rows(source)

    def test_review_gate(self):
        # Signature here is a disposable test fixture, never a user approval.
        rows = [[1, "08:00:00", 1, 400.0, 3.0, 0.2, 15.0,
                 "DEMO SPL_1", "Pass", "Keep", "ocr_output/page_1.png"]]
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as td:
            path = Path(td) / "review.xlsx"
            create_review(path, rows, "fixture-hash")
            with self.assertRaises(PendingReview):
                verify_review(path, rows, "fixture-hash")
            book = load_workbook(path)
            book["Data Review"]["L2"] = "Yes"
            book.save(path)
            with self.assertRaises(PendingReview):
                verify_review(path, rows, "fixture-hash")
            for cell, value in (("B7", "AUTOMATED TEST ONLY"),
                                ("B8", date(2026, 1, 1)), ("B9", "Approved")):
                book["Sign-off"][cell] = value
            book.save(path)
            self.assertEqual(verify_review(path, rows, "fixture-hash")["row_count"], 1)
            with self.assertRaises(PendingReview):
                verify_review(path, rows, "different-source")
            book["Data Review"]["G2"] = 999
            book.save(path)
            with self.assertRaises(PendingReview):
                verify_review(path, rows, "fixture-hash")


if __name__ == "__main__":
    unittest.main()

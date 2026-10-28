"""Invented regression fixtures. No real manuscript content is included."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit_translation.py"
SPEC = importlib.util.spec_from_file_location("audit_translation", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def fixture():
    return {"schema_version": 1, "title_zh": "方法比较", "title_en": "Method comparison",
            "sources": [{"id": "p1b1", "kind": "paragraph", "text": "With n=2, error is 0 and success is 95%."}],
            "omissions": [],
            "blocks": [{"id": "b1", "kind": "paragraph", "source_ids": ["p1b1"],
                        "zh": "当 n=2 时，误差为 0，成功率为 95%。"}]}


def codes(report):
    return {item["code"] for item in report["structural_errors"]}


class AuditTests(unittest.TestCase):
    def test_basic_pass_has_no_semantic_or_visual_attestation(self):
        report = AUDIT.audit_document(fixture())
        self.assertTrue(report["structural_pass"])
        self.assertFalse(report["numeric_review_required"])
        self.assertFalse(report["semantic_verified"])
        self.assertFalse(report["visually_verified"])
        self.assertIn("supplied source inventory", report["verification_scope"])

    def test_empty_english_title_allowed_only_if_unmapped(self):
        data = fixture()
        data["title_en"] = ""
        self.assertTrue(AUDIT.audit_document(data)["structural_pass"])
        data["front_matter_source_ids"] = {"title_en": ["p1b1"]}
        self.assertIn("front_matter_content", codes(AUDIT.audit_document(data)))
        data.pop("front_matter_source_ids")
        data.pop("title_en")
        self.assertIn("missing_title", codes(AUDIT.audit_document(data)))
        data["title_en"] = ""
        data["title_zh"] = ""
        self.assertIn("missing_title", codes(AUDIT.audit_document(data)))

    def test_reference_uses_text_and_other_prose_uses_zh(self):
        data = fixture()
        data["blocks"][0]["text"] = data["blocks"][0].pop("zh")
        self.assertIn("missing_translation", codes(AUDIT.audit_document(data)))
        data["blocks"][0]["kind"] = "reference"
        self.assertTrue(AUDIT.audit_document(data)["structural_pass"])
        data["blocks"][0]["zh"] = data["blocks"][0].pop("text")
        self.assertIn("missing_translation", codes(AUDIT.audit_document(data)))

    def test_small_numbers_are_not_ignored(self):
        data = fixture()
        data["blocks"][0]["zh"] = "当 n=1 时，误差为 0，成功率为 95%。"
        report = AUDIT.audit_document(data)
        self.assertTrue(report["structural_pass"])
        self.assertEqual(report["numeric_candidates"][0]["missing_tokens"], {"2": 1})
        self.assertEqual(report["numeric_candidates"][0]["added_tokens"], {"1": 1})

    def test_number_normalization_and_notation(self):
        self.assertEqual(AUDIT.numeric_tokens("1.00 × 10^-3; -5–-1; ≤2; 1/2; 95%"),
                         AUDIT.numeric_tokens("1e-3; -5 至 -1; <=2; 1/2; 95%"))
        self.assertNotEqual(AUDIT.numeric_tokens("≤2"), AUDIT.numeric_tokens("≥2"))
        self.assertNotEqual(AUDIT.numeric_tokens("95%"), AUDIT.numeric_tokens("95"))
        self.assertNotEqual(AUDIT.numeric_tokens("2^8"), AUDIT.numeric_tokens("28"))
        self.assertEqual(AUDIT.numeric_tokens("2,048"), AUDIT.numeric_tokens("2048"))
        self.assertEqual(AUDIT.numeric_tokens("共2次，值为0xAF"), AUDIT.numeric_tokens("2 repetitions, value 0xaf"))
        self.assertEqual(AUDIT.numeric_tokens(r"95\%"), AUDIT.numeric_tokens("95%"))
        self.assertEqual(AUDIT.numeric_tokens(r"\left(2\right)"), AUDIT.numeric_tokens("(2)"))
        self.assertEqual(AUDIT.numeric_tokens(r"x\leq 2"), AUDIT.numeric_tokens("x≤2"))

    def test_duplicate_source_block_and_unknown_ids(self):
        data = fixture()
        data["sources"].append(deepcopy(data["sources"][0]))
        data["blocks"].append(deepcopy(data["blocks"][0]))
        data["blocks"][1]["source_ids"] = ["unknown"]
        self.assertTrue({"duplicate_source_id", "duplicate_block_id", "unknown_source_id"} <= codes(AUDIT.audit_document(data)))

    def test_explicit_ids_are_not_implicit_ranges(self):
        data = fixture()
        data["sources"] += [{"id": "p1b2", "kind": "paragraph", "text": "Text."},
                            {"id": "p1b3", "kind": "paragraph", "text": "Text."}]
        data["blocks"][0]["source_ids"] = ["p1b1", "p1b3"]
        self.assertEqual(AUDIT.audit_document(data)["coverage"]["uncovered_source_ids"], ["p1b2"])
        data["blocks"][0]["source_ids"] = "p1b1-p1b3"
        self.assertIn("source_ids", codes(AUDIT.audit_document(data)))

    def test_shared_sources_require_explicit_declaration(self):
        data = fixture()
        second = deepcopy(data["blocks"][0])
        second["id"] = "b2"
        data["blocks"].append(second)
        self.assertIn("double_coverage", codes(AUDIT.audit_document(data)))
        data["shared_source_ids"] = ["p1b1"]
        self.assertTrue(AUDIT.audit_document(data)["structural_pass"])

    def test_omission_must_be_known_reasoned_and_not_translated(self):
        data = fixture()
        data["sources"].append({"id": "hdr", "kind": "running_header", "text": "Article"})
        self.assertIn("uncovered_source", codes(AUDIT.audit_document(data)))
        data["omissions"] = [{"source_id": "hdr", "reason": "Repeated running header; checked on page image."}]
        self.assertTrue(AUDIT.audit_document(data)["structural_pass"])
        self.assertTrue(AUDIT.audit_document(data)["review_required"])
        data["omissions"].append({"source_id": "p1b1", "reason": ""})
        self.assertTrue({"covered_and_omitted", "omission_reason"} <= codes(AUDIT.audit_document(data)))

    def test_table_cells_are_compared_at_same_coordinates(self):
        data = fixture()
        data["sources"] = [{"id": "t1", "kind": "table", "text": "Table 1. Error rates",
                            "headers": ["Method", "Error"], "rows": [["A", "0.1"], ["B", "0.2"]]}]
        data["blocks"] = [{"id": "b1", "kind": "table", "number": 1, "source_ids": ["t1"],
                           "zh": "误差率", "headers": ["方法", "误差"], "rows": [["A", "0.2"], ["B", "0.1"]]}]
        report = AUDIT.audit_document(data)
        self.assertTrue(report["structural_pass"])
        self.assertEqual(len(report["numeric_candidates"]), 2)
        self.assertEqual(report["numeric_candidates"][0]["location"], "blocks[0].rows[0][1]")
        data["blocks"][0]["rows"].pop()
        self.assertIn("table_dimensions", codes(AUDIT.audit_document(data)))
        data["blocks"][0]["rows"][0].append("extra")
        self.assertIn("table_rectangular", codes(AUDIT.audit_document(data)))

    def test_label_numbers_are_not_body_numbers(self):
        for kind, source_text, target_text in [("heading", "2.1 Results", "结果"),
                                                ("figure", "Figure 4. Results with n=2", "图 4  n=2 的结果")]:
            with self.subTest(kind=kind), TemporaryDirectory() as folder:
                image = Path(folder) / "image.png"
                image.write_bytes(b"exists")
                data = fixture()
                data["sources"] = [{"id": "s", "kind": kind, "text": source_text}]
                data["blocks"] = [{"id": "b", "kind": kind, "number": "2.1" if kind == "heading" else 4, "source_ids": ["s"],
                                   "zh": target_text, "image": "image.png"}]
                self.assertFalse(AUDIT.audit_document(data, folder)["numeric_review_required"])

    def test_missing_content_and_image_and_unknown_kind(self):
        data = fixture()
        data["blocks"][0].update(kind="figure", image="not-present.png", zh="")
        self.assertTrue({"missing_translation", "missing_image"} <= codes(AUDIT.audit_document(data)))
        data["blocks"][0]["kind"] = "invented"
        self.assertIn("block_kind", codes(AUDIT.audit_document(data)))
        data["blocks"][0]["kind"] = []
        self.assertIn("block_kind", codes(AUDIT.audit_document(data)))

    def test_heading_level_and_object_label_types(self):
        data = fixture()
        data["blocks"][0]["kind"] = "heading"
        for invalid in (0, 4, "2", True):
            data["blocks"][0]["level"] = invalid
            self.assertIn("heading_level", codes(AUDIT.audit_document(data)))
        data["blocks"][0]["level"] = 2
        self.assertTrue(AUDIT.audit_document(data)["structural_pass"])
        for invalid in ({}, [], True, " "):
            data["blocks"][0]["number"] = invalid
            self.assertIn("number_type", codes(AUDIT.audit_document(data)))
        data["blocks"][0]["number"] = "A.1"
        self.assertTrue(AUDIT.audit_document(data)["structural_pass"])
        data["blocks"][0].pop("number")
        for kind in ("figure", "table"):
            data["blocks"][0]["kind"] = kind
            self.assertIn("missing_number", codes(AUDIT.audit_document(data)))

    def test_nonfinite_table_numbers_are_rejected(self):
        data = fixture()
        source = {"id": "t1", "kind": "table", "text": "Values", "headers": ["A"], "rows": [[1.0]]}
        block = {"id": "b", "kind": "table", "number": 1, "source_ids": ["t1"],
                 "zh": "数值", "headers": ["A"], "rows": [[1.0]]}
        data["sources"], data["blocks"] = [source], [block]
        for invalid in (float("nan"), float("inf"), float("-inf")):
            block["rows"][0][0] = invalid
            self.assertIn("table_finite", codes(AUDIT.audit_document(data)))
        block["rows"][0][0] = "NaN"
        self.assertTrue(AUDIT.audit_document(data)["structural_pass"])
        source["rows"][0][0] = float("nan")
        self.assertIn("table_finite", codes(AUDIT.audit_document(data)))

    def test_absolute_and_drive_qualified_image_paths_rejected(self):
        with TemporaryDirectory() as folder:
            image = Path(folder) / "image.png"
            image.write_bytes(b"asset")
            data = fixture()
            data["blocks"][0].update(kind="figure", number=1, image=str(image.resolve()))
            self.assertIn("absolute_image", codes(AUDIT.audit_document(data, folder)))
            data["blocks"][0]["image"] = "image.png"
            self.assertTrue(AUDIT.audit_document(data, folder)["structural_pass"])
            if Path("C:chart.png").drive:
                data["blocks"][0]["image"] = "C:chart.png"
                self.assertIn("absolute_image", codes(AUDIT.audit_document(data, folder)))

    def test_front_matter_covers_bilingual_title_once(self):
        data = fixture()
        data["sources"].append({"id": "title", "kind": "heading", "text": "Comparison of 2 methods"})
        data["title_en"] = "Comparison of 2 methods"
        data["title_zh"] = "2 种方法的比较"
        data["front_matter_source_ids"] = {"title_zh": ["title"], "title_en": ["title"]}
        report = AUDIT.audit_document(data)
        self.assertTrue(report["structural_pass"])
        self.assertFalse(report["numeric_review_required"])
        self.assertEqual(report["coverage"]["front_matter_source_count"], 1)
        data["blocks"].append({"id": "titlebody", "kind": "heading", "source_ids": ["title"], "zh": "2 种方法的比较"})
        self.assertIn("double_coverage", codes(AUDIT.audit_document(data)))
        data["shared_source_ids"] = ["title"]
        self.assertTrue(AUDIT.audit_document(data)["structural_pass"])

    def test_front_matter_rejects_unknown_missing_and_numeric_change(self):
        data = fixture()
        data["front_matter_source_ids"] = {"metadata_line": ["unknown"]}
        self.assertTrue({"unknown_front_matter_source", "front_matter_content"} <= codes(AUDIT.audit_document(data)))
        data["sources"].append({"id": "title", "kind": "heading", "text": "Comparison of 2 methods"})
        data["title_zh"] = "3 种方法的比较"
        data["front_matter_source_ids"] = {"title_zh": ["title"]}
        report = AUDIT.audit_document(data)
        self.assertTrue(report["structural_pass"])
        self.assertEqual(report["numeric_candidates"][0]["location"], "title_zh")

    def test_placeholder_and_serialization_are_review_warnings(self):
        data = fixture()
        data["blocks"][0]["zh"] = "TODO 待翻译 {'zh': 'text'} turn1search2"
        report = AUDIT.audit_document(data)
        self.assertTrue(report["structural_pass"])
        self.assertEqual({w["code"] for w in report["review_warnings"]}, {"placeholder", "serialization_leak"})

    def test_warnings_scan_front_matter_and_figure_labels(self):
        with TemporaryDirectory() as folder:
            (Path(folder) / "image.png").write_bytes(b"asset")
            data = fixture()
            data["title_zh"] = "待补"
            data["title_en"] = "TBD"
            data["metadata_line"] = "{'zh': 'leak'}"
            data["blocks"][0].update(kind="figure", number=1, image="image.png", labels_zh={"Label": "TODO turn1search2"})
            report = AUDIT.audit_document(data, folder)
            self.assertTrue(report["structural_pass"])
            locations = {w["location"] for w in report["review_warnings"]}
            self.assertTrue({"title_zh", "title_en", "metadata_line", "blocks[0]"} <= locations)

    def test_equation_number_not_compared_as_expression(self):
        data = fixture()
        data["sources"] = [{"id": "eq", "kind": "equation", "text": "x=2 (7)"}]
        data["blocks"] = [{"id": "b", "kind": "equation", "number": 7, "source_ids": ["eq"], "latex": "x=2"}]
        self.assertFalse(AUDIT.audit_document(data)["numeric_review_required"])
        data["blocks"][0].pop("latex")
        self.assertIn("equation_content", codes(AUDIT.audit_document(data)))

    def test_equation_requires_exactly_one_representation_and_valid_escapes(self):
        with TemporaryDirectory() as folder:
            (Path(folder) / "image.png").write_bytes(b"asset")
            data = fixture()
            data["sources"] = [{"id": "eq", "kind": "equation", "text": "x=2"}]
            data["blocks"] = [{"id": "b", "kind": "equation", "source_ids": ["eq"],
                               "latex": "x=2", "image": "image.png"}]
            self.assertIn("equation_content", codes(AUDIT.audit_document(data, folder)))
            data["blocks"][0].pop("image")
            for char in ("\t", "\f", "\b"):
                data["blocks"][0]["latex"] = "x=" + char + "2"
                self.assertIn("latex_escape", codes(AUDIT.audit_document(data, folder)))
            data["blocks"][0]["latex"] = r"x=\frac{2}{1}"
            self.assertTrue(AUDIT.audit_document(data, folder)["structural_pass"])

    def test_cli_exit_codes_and_input_overwrite_guard(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "input.json"
            data = fixture()
            data["blocks"][0]["zh"] = "当 n=1 时，误差为 0，成功率为 95%。"
            source.write_text(json.dumps(data), encoding="utf-8")
            def run(*extra):
                return subprocess.run([sys.executable, str(SCRIPT), str(source), *extra], capture_output=True, text=True)
            self.assertEqual(run().returncode, 0)
            self.assertEqual(run("--strict-numbers").returncode, 2)
            self.assertNotEqual(run("--output", str(source)).returncode, 0)
            self.assertEqual(json.loads(source.read_text(encoding="utf-8")), data)
            data["blocks"][0]["source_ids"] = ["absent"]
            source.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(run().returncode, 1)

    def test_cli_report_cannot_overwrite_referenced_image(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / "input.json"
            asset = Path(folder) / "image.png"
            asset.write_bytes(b"original asset")
            data = fixture()
            data["blocks"][0].update(kind="figure", number=1, image="image.png")
            source.write_text(json.dumps(data), encoding="utf-8")
            run = subprocess.run([sys.executable, str(SCRIPT), str(source), "--output", str(asset)], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(asset.read_bytes(), b"original asset")


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from create_form import (
    AnswerPage,
    generate_apps_script,
    list_pdf_files,
    parse_answer_structure,
)


class ParseAnswerStructureTests(unittest.TestCase):
    def test_pdf_folder_scan_includes_nested_directories(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Đáp án 1.pdf").touch()
            (root / "Bộ đề").mkdir()
            (root / "Bộ đề" / "Đáp án 2.PDF").touch()
            (root / "ghi-chu.txt").touch()

            files = list_pdf_files(temp_dir)

        self.assertEqual(files, ["Bộ đề/Đáp án 2.PDF", "Đáp án 1.pdf"])

    def test_explicit_exam_keeps_page_range_and_answers(self):
        pages = [
            AnswerPage(
                pdf_page=10,
                printed_page=6,
                text=(
                    "ĐÁP ÁN TRẮC NGHIỆM CÁC CHỦ ĐỀ\n"
                    "ĐÁP ÁN TRẮC NGHIỆM BÀI 1\n"
                    "1. Đề số 1\n1. A 2. B"
                ),
            ),
            AnswerPage(
                pdf_page=11,
                printed_page=7,
                text="3. C 4. D",
            ),
        ]

        part = parse_answer_structure(pages)[1]["de-1"]

        self.assertEqual(part.label, "Đề số 1")
        self.assertEqual(part.answers, ["A", "B", "C", "D"])
        self.assertEqual(part.question_count, 4)
        self.assertEqual(part.page_description(), "trang 6-7 (trang PDF 10-11)")

    def test_sequential_question_numbers_are_one_part(self):
        pages = [
            AnswerPage(
                pdf_page=3,
                printed_page=None,
                text=(
                    "ĐÁP ÁN TRẮC NGHIỆM BÀI 2\n"
                    "1. A 2. B 3. C 4. D"
                ),
            )
        ]

        parts = parse_answer_structure(pages)[2]

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts["1"].answers, ["A", "B", "C", "D"])

    def test_source_question_range_is_preserved(self):
        pages = [
            AnswerPage(
                pdf_page=3,
                printed_page=None,
                text=(
                    "ĐÁP ÁN BÀI 2\n"
                    "11. A 12. B 13. C"
                ),
            )
        ]

        part = parse_answer_structure(pages)[2]["1"]

        self.assertEqual(part.question_start, 11)
        self.assertEqual(part.question_end, 13)

    def test_repeated_numeric_prefixes_create_parts(self):
        pages = [
            AnswerPage(
                pdf_page=20,
                printed_page=18,
                text=(
                    "ĐÁP ÁN TRẮC NGHIỆM BÀI 6\n"
                    "1. A 1. B 1. C 2. D 2. A"
                ),
            )
        ]

        parts = parse_answer_structure(pages)[6]

        self.assertEqual(list(parts), ["1", "2"])
        self.assertEqual(parts["1"].answers, ["A", "B", "C"])
        self.assertEqual(parts["2"].answers, ["D", "A"])


class GenerateAppsScriptTests(unittest.TestCase):
    def test_selected_range_keeps_original_question_numbers(self):
        script = generate_apps_script(
            'Bài "kiểm tra"',
            ["B", "D"],
            question_start=5,
            section_label="Phần 2 (Câu 5-6)",
        )

        self.assertIn('"question": "Câu 5"', script)
        self.assertIn('"question": "Câu 6"', script)
        self.assertNotIn('"question": "Câu 1"', script)
        self.assertIn('const FORM_TITLE = "Bài \\"kiểm tra\\"";', script)


if __name__ == "__main__":
    unittest.main()

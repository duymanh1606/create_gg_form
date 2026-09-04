#!/usr/bin/env python3
"""
create_form.py
──────────────
Đọc đáp án trắc nghiệm từ file PDF trong thư mục exam/,
sinh code Google Apps Script để tạo Google Form ABCD
(mỗi câu 1 điểm, quiz tự chấm).

CÁCH DÙNG:
    python create_form.py

    Chọn: bài, phần/đề, khoảng câu và tên Form trên terminal.
    → Script sinh file .gs, bạn paste vào script.google.com và chạy.

KHÔNG cần credentials.json, KHÔNG cần Google Cloud Console.
"""

import os
import sys
import re
import json
import subprocess
import base64
from bisect import bisect_right
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

import pdfplumber

# ── Paths ───────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXAM_DIR = os.path.join(SCRIPT_DIR, "exam")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
IMAGE_DIR = os.path.join(SCRIPT_DIR, "image")

# ── Regex patterns ──────────────────────────────────────

# Tiêu đề chương đáp án: "ĐÁP ÁN TRẮC NGHIỆM CÁC CHỦ ĐỀ"
ANSWER_CHAPTER_TITLE = re.compile(
    r"ĐÁP\s*ÁN\s*TRẮC\s*NGHIỆM\s*CÁC\s*CHỦ\s*ĐỀ",
    re.IGNORECASE,
)

# Header mỗi bài: "ĐÁP ÁN TRẮC NGHIỆM BÀI 1"
SECTION_HEADER = re.compile(
    r"ĐÁP\s*ÁN(?:\s*TRẮC\s*NGHIỆM)?(?:\s*CỦA)?\s*BÀI\s*(\d+)",
    re.IGNORECASE,
)

# Header đề tổng ôn: "ĐÁP ÁN CÁC ĐỀ TỔNG ÔN"
TONG_ON_HEADER = re.compile(
    r"ĐÁP\s*ÁN\s*CÁC\s*ĐỀ\s*TỔNG\s*ÔN",
    re.IGNORECASE,
)

# Header đề số: "1. Đề số 1" / "2. Đềsố2"
EXAM_HEADER = re.compile(
    r"(?m)^\s*(?:\d+\.\s*)?Đề\s*số\s*(\d+)\b[^\n]*$",
    re.IGNORECASE,
)

# Header phần: "Phần 1", "PHẦN II", "Phần A"
PART_HEADER = re.compile(
    r"(?m)^\s*(?:\d+\.\s*)?Phần(?:\s+thứ)?\s*"
    r"(\d+|[IVXLCDM]+|[A-Z])(?:\s*[:.\-–—].*)?\s*$",
    re.IGNORECASE,
)

# Mỗi entry đáp án: "1. C" / "C. A" / "2. B"
ANSWER_ENTRY = re.compile(
    r"(?:Câu\s*)?([A-Za-z\d]+)\s*[.):]\s*([A-D])\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AnswerPage:
    """Text và số trang của một trang thuộc khu vực đáp án."""

    pdf_page: int
    printed_page: Optional[int]
    text: str


@dataclass
class AnswerPart:
    """Một phần/đề có thể được người dùng chọn để tạo Form."""

    key: str
    label: str
    answers: list
    pdf_page_start: int
    pdf_page_end: int
    printed_page_start: Optional[int] = None
    printed_page_end: Optional[int] = None
    question_start: int = 1

    @property
    def question_count(self):
        return len(self.answers)

    @property
    def question_end(self):
        return self.question_start + self.question_count - 1

    def page_description(self):
        """Chuỗi số trang dễ đọc, ưu tiên số trang in trong tài liệu."""
        printed_range_available = (
            self.printed_page_start is not None
            and (
                self.printed_page_end is not None
                or self.pdf_page_start == self.pdf_page_end
            )
        )
        if printed_range_available:
            printed_end = self.printed_page_end or self.printed_page_start
            printed = _format_range(self.printed_page_start, printed_end)
            pdf = _format_range(self.pdf_page_start, self.pdf_page_end)
            if (
                self.printed_page_start != self.pdf_page_start
                or printed_end != self.pdf_page_end
            ):
                return f"trang {printed} (trang PDF {pdf})"
            return f"trang {printed}"
        return f"trang PDF {_format_range(self.pdf_page_start, self.pdf_page_end)}"


def _format_range(start, end):
    return str(start) if start == end else f"{start}-{end}"


# ═══════════════════════════════════════════════════════
#  PDF PARSING
# ═══════════════════════════════════════════════════════

def list_pdf_files(exam_dir=EXAM_DIR):
    """Quét đệ quy và trả về đường dẫn tương đối của các PDF trong exam/."""
    if not os.path.isdir(exam_dir):
        print(f"❌ Không tìm thấy thư mục: {exam_dir}")
        sys.exit(1)

    pdfs = []
    for current_dir, subdirs, filenames in os.walk(exam_dir):
        subdirs.sort(key=str.casefold)
        for filename in sorted(filenames, key=str.casefold):
            if filename.lower().endswith(".pdf"):
                full_path = os.path.join(current_dir, filename)
                pdfs.append(os.path.relpath(full_path, exam_dir))

    if not pdfs:
        print("❌ Không tìm thấy file PDF nào trong thư mục exam/")
        sys.exit(1)

    return sorted(pdfs, key=str.casefold)


def _extract_printed_page_number(text):
    """Đọc số trang được in trên tài liệu, nếu nhận diện được."""
    patterns = (
        r"(?i)(?:trang|page)\s*[-–—:]?\s*(\d{1,4})\b",
        r"(?i)HQMATHS\s*[-–—]\s*(\d{1,4})\b",
        r"(?m)^\s*[-–—]?\s*(\d{1,4})\s*[-–—]?\s*$",
    )
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            return int(matches[-1])
    return None


def extract_answer_pages(pdf_path):
    """
    Trích xuất các trang thuộc phần đáp án và giữ metadata số trang.

    Tìm lần xuất hiện cuối của tiêu đề đáp án để tránh mục lục ở đầu PDF.
    Nếu PDF không có tiêu đề tổng, lấy cụm tiêu đề bài gần cuối tài liệu.
    """
    with pdfplumber.open(pdf_path) as pdf:
        page_texts = [page.extract_text() or "" for page in pdf.pages]
        total_pages = len(page_texts)
        chapter_pages = [
            i for i, text in enumerate(page_texts)
            if ANSWER_CHAPTER_TITLE.search(text)
        ]

        if chapter_pages:
            start_page = chapter_pages[-1]
        else:
            section_pages = [
                i for i, text in enumerate(page_texts)
                if SECTION_HEADER.search(text) or TONG_ON_HEADER.search(text)
            ]
            if not section_pages:
                return []

            # Lấy cụm đáp án cuối, thay vì chỉ lấy đúng header cuối cùng.
            last_page = section_pages[-1]
            maximum_cluster_gap = max(10, total_pages // 5)
            candidates = [
                page for page in section_pages
                if last_page - page <= maximum_cluster_gap
            ]
            start_page = min(candidates)

        return [
            AnswerPage(
                pdf_page=i + 1,
                printed_page=_extract_printed_page_number(page_texts[i]),
                text=page_texts[i],
            )
            for i in range(start_page, total_pages)
        ]


def extract_answer_text(pdf_path):
    """API cũ: trả về text đáp án, không kèm metadata trang."""
    return "\n".join(page.text for page in extract_answer_pages(pdf_path))


def _combine_pages(pages):
    """Ghép text và trả về offset bắt đầu của từng trang."""
    chunks = []
    offsets = []
    cursor = 0
    for page in pages:
        offsets.append(cursor)
        chunks.append(page.text)
        cursor += len(page.text) + 1
    return "\n".join(chunks), offsets


def _page_at_position(pages, offsets, position):
    index = max(0, bisect_right(offsets, position) - 1)
    return pages[min(index, len(pages) - 1)]


def _part_from_matches(key, label, matches, pages, offsets):
    """Tạo AnswerPart từ danh sách regex match của các đáp án."""
    start_page = _page_at_position(pages, offsets, matches[0].start())
    end_page = _page_at_position(pages, offsets, matches[-1].start())
    prefixes = [match.group(1) for match in matches]
    question_start = 1
    if all(prefix.isdigit() for prefix in prefixes):
        numbers = [int(prefix) for prefix in prefixes]
        if numbers == list(range(numbers[0], numbers[0] + len(numbers))):
            question_start = numbers[0]

    return AnswerPart(
        key=str(key),
        label=label,
        answers=[match.group(2).upper() for match in matches],
        pdf_page_start=start_page.pdf_page,
        pdf_page_end=end_page.pdf_page,
        printed_page_start=start_page.printed_page,
        printed_page_end=end_page.printed_page,
        question_start=question_start,
    )


def _prefixes_form_contiguous_groups(prefixes):
    """True nếu mỗi prefix chỉ xuất hiện trong đúng một cụm liên tiếp."""
    completed = set()
    previous = None
    for prefix in prefixes:
        if prefix != previous:
            if prefix in completed:
                return False
            if previous is not None:
                completed.add(previous)
            previous = prefix
    return True


def _parse_implicit_parts(content, content_offset, pages, offsets):
    """Suy luận phần từ bảng đáp án khi PDF không ghi header phần."""
    matches = list(ANSWER_ENTRY.finditer(content))
    if not matches:
        return OrderedDict()

    # Chuyển match về hệ offset của toàn bộ text để tra cứu số trang.
    absolute_matches = []
    for match in matches:
        absolute_matches.append(_OffsetMatch(match, content_offset))

    prefixes = [match.group(1) for match in matches]
    unique_prefixes = list(OrderedDict.fromkeys(prefixes))

    # Dạng chuẩn "1.A 2.B 3.C" là số câu, toàn bộ thuộc một phần.
    # Một prefix chữ lặp lại (thường do ký hiệu trang trí trong PDF) cũng
    # được xem là một phần duy nhất.
    if (
        len(unique_prefixes) == len(prefixes)
        or len(unique_prefixes) == 1
        or not _prefixes_form_contiguous_groups(prefixes)
    ):
        return OrderedDict({
            "1": _part_from_matches(
                "1", "Phần 1", absolute_matches, pages, offsets
            )
        })

    # Prefix bị lặp theo nhóm (VD 1,1,...,2,2,...) chính là mã phần.
    grouped = OrderedDict()
    for match in absolute_matches:
        grouped.setdefault(match.group(1), []).append(match)

    parts = OrderedDict()
    for prefix, group_matches in grouped.items():
        parts[str(prefix)] = _part_from_matches(
            prefix,
            f"Phần {prefix}",
            group_matches,
            pages,
            offsets,
        )
    return parts


class _OffsetMatch:
    """Adapter nhỏ để cộng offset vào vị trí của một regex match."""

    def __init__(self, match, offset):
        self.match = match
        self.offset = offset

    def start(self):
        return self.match.start() + self.offset

    def group(self, index):
        return self.match.group(index)


def parse_answer_structure(pages):
    """
    Parse đáp án thành ``Bài -> Phần/Đề -> AnswerPart``.

    Mỗi phần chứa nhãn, khoảng trang, số câu và danh sách đáp án. Hàm hỗ
    trợ cả header ``Đề số``, ``Phần`` và bảng chỉ có prefix nhóm.
    """
    result = OrderedDict()
    if not pages:
        return result

    text, page_offsets = _combine_pages(pages)
    sections = []
    for match in SECTION_HEADER.finditer(text):
        sections.append((match.start(), match.end(), int(match.group(1))))
    next_lesson_number = (
        max((section[2] for section in sections), default=0) + 1
    )
    for match in TONG_ON_HEADER.finditer(text):
        # Đề tổng ôn đứng sau bài cuối, không giả định cố định là Bài 9.
        sections.append((match.start(), match.end(), next_lesson_number))
    sections.sort(key=lambda item: item[0])

    for index, (_, header_end, lesson_number) in enumerate(sections):
        section_end = (
            sections[index + 1][0] if index + 1 < len(sections) else len(text)
        )
        content = text[header_end:section_end]

        explicit_headers = []
        for match in EXAM_HEADER.finditer(content):
            value = match.group(1)
            explicit_headers.append(
                (match.start(), match.end(), f"de-{value}", f"Đề số {value}")
            )
        for match in PART_HEADER.finditer(content):
            value = match.group(1).upper()
            explicit_headers.append(
                (match.start(), match.end(), f"phan-{value}", f"Phần {value}")
            )
        explicit_headers.sort(key=lambda item: item[0])

        lesson_parts = OrderedDict()
        if explicit_headers:
            for header_index, (_, part_start, key, label) in enumerate(
                explicit_headers
            ):
                part_end = (
                    explicit_headers[header_index + 1][0]
                    if header_index + 1 < len(explicit_headers)
                    else len(content)
                )
                matches = [
                    _OffsetMatch(match, header_end + part_start)
                    for match in ANSWER_ENTRY.finditer(
                        content[part_start:part_end]
                    )
                ]
                if matches:
                    lesson_parts[key] = _part_from_matches(
                        key, label, matches, pages, page_offsets
                    )
        else:
            lesson_parts = _parse_implicit_parts(
                content, header_end, pages, page_offsets
            )

        if lesson_parts:
            result[lesson_number] = lesson_parts

    return result


def parse_all_answers(text):
    """API tương thích ngược với cấu trúc ``Bài -> phần -> đáp án`` cũ."""
    page = AnswerPage(pdf_page=1, printed_page=None, text=text)
    structure = parse_answer_structure([page])
    result = OrderedDict()
    for lesson, parts in structure.items():
        legacy_parts = OrderedDict()
        for index, part in enumerate(parts.values(), 1):
            numeric_key = re.search(r"(\d+)$", part.key)
            key = int(numeric_key.group(1)) if numeric_key else index
            legacy_parts[key] = part.answers
        result[lesson] = legacy_parts
    return result


# ═══════════════════════════════════════════════════════
#  APPS SCRIPT GENERATION
# ═══════════════════════════════════════════════════════

def get_local_logo_base64():
    """Tìm ảnh trong thư mục image/ và trả về (base64_str, mime_type)."""
    if not os.path.isdir(IMAGE_DIR):
        return "", ""
    for f in os.listdir(IMAGE_DIR):
        f_lower = f.lower()
        if f_lower.endswith((".png", ".jpg", ".jpeg", ".gif")):
            path = os.path.join(IMAGE_DIR, f)
            mime = "image/png"
            if f_lower.endswith(".jpg") or f_lower.endswith(".jpeg"):
                mime = "image/jpeg"
            elif f_lower.endswith(".gif"):
                mime = "image/gif"
            try:
                with open(path, "rb") as img_file:
                    b64 = base64.b64encode(img_file.read()).decode("utf-8")
                    return b64, mime
            except Exception:
                pass
    return "", ""


def generate_apps_script(
    title,
    answers,
    logo_b64="",
    logo_mime="",
    question_start=1,
    section_label="Trả lời",
):
    """
    Sinh code Google Apps Script hoàn chỉnh.

    Parameters
    ----------
    title     : str – Tên form
    answers   : list[str] – Danh sách đáp án đúng, VD: ['C', 'A', 'B', ...]
    logo_b64  : str – Base64 của ảnh logo
    logo_mime : str – Mime type của ảnh (vd: image/png)
    question_start : int – Số thứ tự của câu đầu tiên
    section_label  : str – Tên phần hiển thị ở trang trả lời

    Returns
    -------
    str – Nội dung file .gs
    """
    # Build JSON array for answers
    quiz_data = []
    for i, ans in enumerate(answers):
        quiz_data.append({
            "question": f"Câu {question_start + i}",
            "answer": ans,
        })

    quiz_json = json.dumps(quiz_data, ensure_ascii=False, indent=2)
    title_json = json.dumps(title, ensure_ascii=False)
    logo_json = json.dumps(logo_b64)
    logo_mime_json = json.dumps(logo_mime)
    section_label_json = json.dumps(section_label, ensure_ascii=False)

    gs_code = f'''/**
 * TẠO GOOGLE FORM TRẮC NGHIỆM ABCD
 * ──────────────────────────────────
 * Được sinh tự động bởi create_form.py
 *
 * CÁCH DÙNG:
 * 1. Vào https://script.google.com → New project
 * 2. Dán toàn bộ code này vào (xóa code cũ)
 * 3. Bấm Run ▶ → chọn hàm createQuizForm
 * 4. Lần đầu: cấp quyền (hoàn toàn miễn phí, không cần thanh toán)
 * 5. Xem log (Ctrl+Enter hoặc View → Logs) để lấy link Form
 */

const FORM_TITLE = {title_json};
const IS_QUIZ = true;           // true = bật chế độ Quiz (tự chấm điểm)
const POINTS_PER_QUESTION = 1;  // Mỗi câu 1 điểm
const LOGO_BASE64 = {logo_json}; // Ảnh mã hóa base64
const LOGO_MIME = {logo_mime_json};
const SECTION_LABEL = {section_label_json};

const QUIZ_DATA = {quiz_json};

function createQuizForm() {{
  const form = FormApp.create(FORM_TITLE);
  form.setDescription("Vui lòng điền thông tin và làm bài kiểm tra.");
  form.setIsQuiz(IS_QUIZ);

  // === TRANG 1 (TRANG ĐẦU): THÔNG TIN CHUNG ===
  
  // 1. Thêm Logo từ Base64 string
  if (LOGO_BASE64) {{
    try {{
      const decoded = Utilities.base64Decode(LOGO_BASE64);
      const blob = Utilities.newBlob(decoded, LOGO_MIME, "logo");
      form.addImageItem().setImage(blob).setAlignment(FormApp.Alignment.CENTER);
    }} catch (e) {{
      Logger.log("Lỗi tải ảnh logo: " + e.message);
    }}
  }}

  // 2. Thêm câu hỏi Họ và tên
  form.addTextItem()
      .setTitle("Họ và tên")
      .setRequired(true);

  // === TRANG 2: TRẢ LỜI CÂU HỎI ===
  
  // Hàm addPageBreakItem() chia trang từ vị trí hiện tại trở về sau
  // Nghĩa là mọi item add sau lệnh này sẽ nằm ở Trang 2
  form.addPageBreakItem().setTitle("Phần 2: " + SECTION_LABEL);

  // Vòng lặp thêm các câu hỏi trắc nghiệm vào Trang 2
  QUIZ_DATA.forEach(function(q) {{
    const item = form.addMultipleChoiceItem();
    item.setTitle(q.question);
    item.setRequired(true);

    if (IS_QUIZ && q.answer) {{
      // Tạo choices với đáp án đúng
      const letters = ["A", "B", "C", "D"];
      const choices = letters.map(function(letter) {{
        return item.createChoice(letter, letter === q.answer);
      }});
      item.setChoices(choices);
      item.setPoints(POINTS_PER_QUESTION);

      const feedback = FormApp.createFeedback()
        .setText("Đáp án đúng: " + q.answer)
        .build();
      item.setFeedbackForCorrect(feedback);
    }} else {{
      // Không có đáp án → chỉ tạo choices
      item.setChoices([
        item.createChoice("A"),
        item.createChoice("B"),
        item.createChoice("C"),
        item.createChoice("D")
      ]);
    }}
  }});

  Logger.log("══════════════════════════════════════");
  Logger.log("✅ Form đã tạo thành công!");
  Logger.log("📝 Link chỉnh sửa: " + form.getEditUrl());
  Logger.log("📎 Link cho học sinh: " + form.getPublishedUrl());
  Logger.log("══════════════════════════════════════");
}}
'''
    return gs_code


def copy_to_clipboard(text):
    """Thử copy text vào clipboard. Trả về True nếu thành công."""
    try:
        # Try xclip (Linux)
        proc = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE,
        )
        proc.communicate(text.encode("utf-8"))
        return proc.returncode == 0
    except FileNotFoundError:
        pass

    try:
        # Try xsel (Linux)
        proc = subprocess.Popen(
            ["xsel", "--clipboard", "--input"],
            stdin=subprocess.PIPE,
        )
        proc.communicate(text.encode("utf-8"))
        return proc.returncode == 0
    except FileNotFoundError:
        pass

    try:
        # Try wl-copy (Wayland)
        proc = subprocess.Popen(
            ["wl-copy"],
            stdin=subprocess.PIPE,
        )
        proc.communicate(text.encode("utf-8"))
        return proc.returncode == 0
    except FileNotFoundError:
        pass

    return False


def ask_number(prompt, minimum, maximum, default=None):
    """Hỏi một số nguyên trong khoảng, hỗ trợ giá trị mặc định."""
    while True:
        try:
            raw_value = input(prompt).strip()
            if not raw_value and default is not None:
                return default
            value = int(raw_value)
            if minimum <= value <= maximum:
                return value
        except (ValueError, EOFError):
            pass
        print(f"❌ Vui lòng nhập số từ {minimum} đến {maximum}!")


def choose_pdf_file(pdf_files):
    """Hiển thị kết quả quét và yêu cầu chọn trước khi đọc nội dung PDF."""
    print(f"📂 Tìm thấy {len(pdf_files)} file PDF đáp án trong exam/:")
    for index, relative_path in enumerate(pdf_files, 1):
        full_path = os.path.join(EXAM_DIR, relative_path)
        size_mb = os.path.getsize(full_path) / (1024 * 1024)
        print(f"  {index}. {relative_path} ({size_mb:.1f} MB)")

    print()
    choice = ask_number(
        f"📌 Chọn file để quét (1-{len(pdf_files)}) [1]: ",
        1,
        len(pdf_files),
        default=1,
    )
    return pdf_files[choice - 1]




# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════

def main():
    print()
    print("=" * 55)
    print("  📝  TẠO GOOGLE FORM TRẮC NGHIỆM TỪ ĐÁP ÁN PDF")
    print("=" * 55)
    print()

    # ── 1. Quét thư mục và chọn file PDF ─────────────
    print("🔎 Đang quét thư mục exam/...")
    pdfs = list_pdf_files()
    pdf_file = choose_pdf_file(pdfs)
    pdf_path = os.path.join(EXAM_DIR, pdf_file)
    print(f"✅ Đã chọn: {pdf_file}")
    print()

    # Chỉ bắt đầu mở và phân tích PDF sau khi người dùng đã chọn file.
    # ── 2. Parse đáp án ───────────────────────────────
    print("🔍 Đang đọc đáp án từ PDF...")
    answer_pages = extract_answer_pages(pdf_path)
    answer_structure = parse_answer_structure(answer_pages)

    if not answer_structure:
        print("❌ Không tìm thấy đáp án nào trong PDF!")
        sys.exit(1)

    # ── 3. Hiển thị cấu trúc bài/phần/trang/câu ──────
    print()
    print("📋 Cấu trúc đáp án tìm thấy:")
    lesson_list = list(answer_structure.keys())
    for lesson_number in lesson_list:
        print(f"  Bài {lesson_number}:")
        for part in answer_structure[lesson_number].values():
            print(
                f"    • {part.label}: {part.page_description()}, "
                f"{part.question_count} câu "
                f"(Câu {part.question_start}-{part.question_end})"
            )

    # ── 4. Nhập số bài ────────────────────────────────
    print()
    while True:
        try:
            lesson_input = int(input("📌 Chọn bài: ").strip())
            if lesson_input in answer_structure:
                break
        except (ValueError, EOFError):
            pass
        valid = ", ".join(str(lesson) for lesson in lesson_list)
        print(f"❌ Bài không hợp lệ! Chọn: {valid}")

    # ── 5. Chọn phần/đề ──────────────────────────────
    lesson_parts = list(answer_structure[lesson_input].values())
    if len(lesson_parts) == 1:
        selected_part = lesson_parts[0]
        print(f"📌 Phần: {selected_part.label} (chỉ có 1 phần)")
    else:
        print(f"📚 Các phần của Bài {lesson_input}:")
        for index, part in enumerate(lesson_parts, 1):
            print(
                f"  {index}. {part.label} — {part.page_description()} — "
                f"{part.question_count} câu "
                f"(Câu {part.question_start}-{part.question_end})"
            )
        part_choice = ask_number(
            f"📌 Chọn phần (1-{len(lesson_parts)}): ",
            1,
            len(lesson_parts),
        )
        selected_part = lesson_parts[part_choice - 1]

    # ── 6. Chọn khoảng câu ────────────────────────────
    total_questions = selected_part.question_count
    first_question = selected_part.question_start
    last_question = selected_part.question_end
    print(
        f"📄 {selected_part.label}: {selected_part.page_description()}, "
        f"có {total_questions} câu "
        f"(Câu {first_question}-{last_question})"
    )
    question_from = ask_number(
        f"📌 Từ câu [{first_question}]: ",
        first_question,
        last_question,
        default=first_question,
    )
    question_to = ask_number(
        f"📌 Đến câu [{last_question}]: ",
        question_from,
        last_question,
        default=last_question,
    )
    start_index = question_from - first_question
    end_index = question_to - first_question + 1
    answers = selected_part.answers[start_index:end_index]

    # ── 7. Nhập tên form ──────────────────────────────
    default_title = f"Bài {lesson_input} - {selected_part.label}"
    if question_from != first_question or question_to != last_question:
        default_title += f" - Câu {question_from}-{question_to}"
    title_input = input(f"📌 Nhập tên form [{default_title}]: ").strip()
    form_title = title_input if title_input else default_title

    # ── 8. Xác nhận ───────────────────────────────────
    print()
    print("─" * 55)
    print(f"  Bài:       {lesson_input}")
    print(f"  Phần:      {selected_part.label}")
    print(f"  Vị trí:    {selected_part.page_description()}")
    print(f"  Chọn câu:  {question_from}-{question_to} ({len(answers)} câu)")
    print(f"  Tên form:  {form_title}")
    print("─" * 55)
    print()

    # Hiển thị đáp án để kiểm tra
    print("📊 Đáp án:")
    for i in range(0, len(answers), 10):
        chunk = answers[i : i + 10]
        row = "  ".join(
            f"{question_from + i + j:>2}.{a}"
            for j, a in enumerate(chunk)
        )
        print(f"   {row}")
    print()

    # ── 9. Sinh Apps Script ───────────────────────────
    logo_b64, logo_mime = get_local_logo_base64()
    section_label = (
        f"Bài {lesson_input} - {selected_part.label} "
        f"(Câu {question_from}-{question_to})"
    )
    gs_code = generate_apps_script(
        form_title,
        answers,
        logo_b64,
        logo_mime,
        question_start=question_from,
        section_label=section_label,
    )

    # Lưu file .gs
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = re.sub(r"[^\w\-]", "_", form_title)
    gs_filename = f"{safe_name}.gs"
    gs_path = os.path.join(OUTPUT_DIR, gs_filename)

    with open(gs_path, "w", encoding="utf-8") as f:
        f.write(gs_code)

    # Thử copy vào clipboard
    copied = copy_to_clipboard(gs_code)

    print("✅ Đã sinh code Apps Script!")
    print(f"   📄 File: output/{gs_filename}")
    if copied:
        print("   📋 Đã copy vào clipboard!")
    print()

    # ── 10. Hướng dẫn ─────────────────────────────────
    print("╔══════════════════════════════════════════════════╗")
    print("║  📌 HƯỚNG DẪN TẠO GOOGLE FORM                  ║")
    print("╠══════════════════════════════════════════════════╣")
    print("║  1. Vào https://script.google.com               ║")
    print("║  2. Bấm '+ New project'                         ║")
    print("║  3. Xóa code cũ, dán code từ clipboard/file     ║")
    print("║  4. Bấm Run ▶ → chọn hàm createQuizForm        ║")
    print("║  5. Cấp quyền (miễn phí, không cần thanh toán)  ║")
    print("║  6. Xem Execution Log để lấy link Form          ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    if not copied:
        print(f"💡 Mở file để copy code: {gs_path}")
        print()

    print()
    print("✅ Hoàn tất!")
    print()


if __name__ == "__main__":
    main()

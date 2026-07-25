#!/usr/bin/env python3
"""
create_form.py
──────────────
Đọc đáp án trắc nghiệm từ file PDF trong thư mục exam/,
sinh code Google Apps Script để tạo Google Form ABCD
(mỗi câu 1 điểm, quiz tự chấm).

CÁCH DÙNG:
    python create_form.py

    Nhập: đề số, tên bài trên terminal.
    → Script sinh file .gs, bạn paste vào script.google.com và chạy.

KHÔNG cần credentials.json, KHÔNG cần Google Cloud Console.
"""

import os
import sys
import re
import json
import subprocess
import base64
from collections import OrderedDict

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
    r"ĐÁP\s*ÁN\s*TRẮC\s*NGHIỆM\s*BÀI\s*(\d+)",
    re.IGNORECASE,
)

# Header đề tổng ôn: "ĐÁP ÁN CÁC ĐỀ TỔNG ÔN"
TONG_ON_HEADER = re.compile(
    r"ĐÁP\s*ÁN\s*CÁC\s*ĐỀ\s*TỔNG\s*ÔN",
    re.IGNORECASE,
)

# Header đề số: "1. Đề số 1" / "2. Đềsố2"
EXAM_HEADER = re.compile(
    r"(\d+)\.\s*Đề\s*số\s*(\d+)",
    re.IGNORECASE,
)

# Mỗi entry đáp án: "1. C" / "C. A" / "2. B"
ANSWER_ENTRY = re.compile(
    r"([A-Za-z\d]+)\.\s*([A-D])\b",
)


# ═══════════════════════════════════════════════════════
#  PDF PARSING
# ═══════════════════════════════════════════════════════

def list_pdf_files():
    """Liệt kê các file PDF trong thư mục exam/."""
    if not os.path.isdir(EXAM_DIR):
        print(f"❌ Không tìm thấy thư mục: {EXAM_DIR}")
        sys.exit(1)

    pdfs = sorted(
        f for f in os.listdir(EXAM_DIR) if f.lower().endswith(".pdf")
    )

    if not pdfs:
        print("❌ Không có file PDF nào trong thư mục exam/")
        sys.exit(1)

    return pdfs


def extract_answer_text(pdf_path):
    """
    Trích xuất text từ phần đáp án cuối PDF.

    Tìm trang cuối cùng chứa tiêu đề chương đáp án
    (để bỏ qua mục lục ở đầu sách) rồi đọc từ đó đến hết.
    """
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        start_page = None

        # Tìm trang CUỐI CÙNG chứa tiêu đề "ĐÁP ÁN TRẮC NGHIỆM CÁC CHỦ ĐỀ"
        # (trang đầu là mục lục, trang cuối là nội dung thật)
        for i in range(total_pages - 1, -1, -1):
            text = pdf.pages[i].extract_text() or ""
            if ANSWER_CHAPTER_TITLE.search(text):
                start_page = i
                break

        # Fallback: tìm trang cuối có SECTION_HEADER
        if start_page is None:
            for i in range(total_pages - 1, -1, -1):
                text = pdf.pages[i].extract_text() or ""
                if SECTION_HEADER.search(text):
                    start_page = i
                    break

        if start_page is None:
            print("❌ Không tìm thấy phần đáp án trong PDF!")
            sys.exit(1)

        # Đọc từ trang tìm được đến cuối
        texts = []
        for i in range(start_page, total_pages):
            text = pdf.pages[i].extract_text() or ""
            texts.append(text)

        return "\n".join(texts)


def parse_all_answers(text):
    """
    Parse toàn bộ text đáp án thành cấu trúc:
    {
        bai_number: {
            de_number: [list of answer letters],
            ...
        },
        ...
    }
    """
    result = OrderedDict()

    # ── Tìm các section ──────────────────────────────
    sections = []

    for m in SECTION_HEADER.finditer(text):
        bai_num = int(m.group(1))
        sections.append((m.start(), bai_num))

    for m in TONG_ON_HEADER.finditer(text):
        # "Đề tổng ôn" = phần cuối cùng, thường là Bài 9
        sections.append((m.start(), 9))

    sections.sort(key=lambda x: x[0])

    if not sections:
        return result

    # ── Parse từng section ────────────────────────────
    for idx, (start_pos, bai_num) in enumerate(sections):
        end_pos = (
            sections[idx + 1][0] if idx + 1 < len(sections) else len(text)
        )
        section_text = text[start_pos:end_pos]

        # Tìm header nội dung (SECTION_HEADER hoặc TONG_ON_HEADER)
        header_match = SECTION_HEADER.search(section_text)
        if not header_match:
            header_match = TONG_ON_HEADER.search(section_text)
        if not header_match:
            continue

        content_after_header = section_text[header_match.end() :]

        # Kiểm tra có "Đề số N" không
        exam_headers = list(EXAM_HEADER.finditer(content_after_header))

        if exam_headers:
            # ── Có phân đề ────────────────────────────
            bai_answers = OrderedDict()
            for ei, eh in enumerate(exam_headers):
                de_num = int(eh.group(2))
                eh_start = eh.end()
                eh_end = (
                    exam_headers[ei + 1].start()
                    if ei + 1 < len(exam_headers)
                    else len(content_after_header)
                )
                exam_text = content_after_header[eh_start:eh_end]

                answers = [
                    m.group(2).upper()
                    for m in ANSWER_ENTRY.finditer(exam_text)
                ]
                if answers:
                    bai_answers[de_num] = answers

            if bai_answers:
                result[bai_num] = bai_answers
        else:
            # ── Không có "Đề số" → kiểm tra prefix ───
            entries = [
                (m.group(1), m.group(2).upper())
                for m in ANSWER_ENTRY.finditer(content_after_header)
            ]

            if not entries:
                continue

            # Tất cả cùng prefix chữ (VD: "C") → 1 đề duy nhất
            unique_prefixes = set(p for p, _ in entries)
            all_same_nonnumeric = (
                len(unique_prefixes) == 1
                and not list(unique_prefixes)[0].isdigit()
            )

            if all_same_nonnumeric:
                result[bai_num] = OrderedDict(
                    {1: [letter for _, letter in entries]}
                )
            else:
                # Prefix khác nhau (VD: 1, 2, 3, 4) → nhóm theo prefix
                bai_answers = OrderedDict()
                for prefix, letter in entries:
                    key = int(prefix) if prefix.isdigit() else 1
                    bai_answers.setdefault(key, []).append(letter)
                if bai_answers:
                    result[bai_num] = bai_answers

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


def generate_apps_script(title, answers, logo_b64="", logo_mime=""):
    """
    Sinh code Google Apps Script hoàn chỉnh.

    Parameters
    ----------
    title     : str – Tên form
    answers   : list[str] – Danh sách đáp án đúng, VD: ['C', 'A', 'B', ...]
    logo_b64  : str – Base64 của ảnh logo
    logo_mime : str – Mime type của ảnh (vd: image/png)

    Returns
    -------
    str – Nội dung file .gs
    """
    # Build JSON array for answers
    quiz_data = []
    for i, ans in enumerate(answers):
        quiz_data.append({
            "question": f"Câu {i + 1}",
            "answer": ans,
        })

    quiz_json = json.dumps(quiz_data, ensure_ascii=False, indent=2)

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

const FORM_TITLE = "{title}";
const IS_QUIZ = true;           // true = bật chế độ Quiz (tự chấm điểm)
const POINTS_PER_QUESTION = 1;  // Mỗi câu 1 điểm
const LOGO_BASE64 = "{logo_b64}"; // Ảnh mã hóa base64
const LOGO_MIME = "{logo_mime}";

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
  form.addPageBreakItem().setTitle("Phần 2: Trả lời");

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




# ═══════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════

def main():
    print()
    print("=" * 55)
    print("  📝  TẠO GOOGLE FORM TRẮC NGHIỆM TỪ ĐÁP ÁN PDF")
    print("=" * 55)
    print()

    # ── 1. Chọn file PDF ──────────────────────────────
    pdfs = list_pdf_files()

    if len(pdfs) == 1:
        pdf_file = pdfs[0]
        print(f"📄 File PDF: {pdf_file}")
    else:
        print("📂 Chọn file PDF:")
        for i, f in enumerate(pdfs, 1):
            name = os.path.splitext(f)[0]
            print(f"  {i}. {name}")
        while True:
            try:
                choice = int(input("\nNhập số: ").strip())
                if 1 <= choice <= len(pdfs):
                    pdf_file = pdfs[choice - 1]
                    break
            except (ValueError, EOFError):
                pass
            print("❌ Lựa chọn không hợp lệ!")

    pdf_path = os.path.join(EXAM_DIR, pdf_file)
    print()

    # ── 2. Parse đáp án ───────────────────────────────
    print("🔍 Đang đọc đáp án từ PDF...")
    answer_text = extract_answer_text(pdf_path)
    all_answers = parse_all_answers(answer_text)

    if not all_answers:
        print("❌ Không tìm thấy đáp án nào trong PDF!")
        sys.exit(1)

    # ── 3. Hiển thị danh sách bài ─────────────────────
    print()
    print("📋 Các bài có đáp án:")
    bai_list = list(all_answers.keys())
    for bai_num in bai_list:
        de_dict = all_answers[bai_num]
        de_info = ", ".join(
            f"Đề {d} ({len(a)} câu)" for d, a in de_dict.items()
        )
        print(f"  Bài {bai_num}: {de_info}")

    # ── 4. Nhập số bài ────────────────────────────────
    print()
    while True:
        try:
            bai_input = int(input("📌 Nhập số bài: ").strip())
            if bai_input in all_answers:
                break
        except (ValueError, EOFError):
            pass
        valid = ", ".join(str(b) for b in bai_list)
        print(f"❌ Bài không hợp lệ! Chọn: {valid}")

    # ── 5. Nhập đề số ────────────────────────────────
    de_dict = all_answers[bai_input]
    de_list = list(de_dict.keys())

    if len(de_list) == 1:
        de_input = de_list[0]
        print(f"📌 Đề số: {de_input} (chỉ có 1 đề)")
    else:
        de_options = "/".join(str(d) for d in de_list)
        while True:
            try:
                de_input = int(
                    input(f"📌 Nhập đề số ({de_options}): ").strip()
                )
                if de_input in de_dict:
                    break
            except (ValueError, EOFError):
                pass
            print(f"❌ Đề không hợp lệ! Chọn: {de_options}")

    answers = de_dict[de_input]

    # ── 6. Nhập tên form ──────────────────────────────
    default_title = f"Bài {bai_input} - Đề {de_input}"
    title_input = input(f"📌 Nhập tên form [{default_title}]: ").strip()
    form_title = title_input if title_input else default_title

    # ── 7. Xác nhận ───────────────────────────────────
    print()
    print("┌─────────────────────────────────────┐")
    print(f"│  Bài:      {bai_input:<25}│")
    print(f"│  Đề:       {de_input:<25}│")
    print(f"│  Số câu:   {len(answers):<25}│")
    print(f"│  Tên form: {form_title:<25}│")
    print("└─────────────────────────────────────┘")
    print()

    # Hiển thị đáp án để kiểm tra
    print("📊 Đáp án:")
    for i in range(0, len(answers), 10):
        chunk = answers[i : i + 10]
        row = "  ".join(
            f"{i + j + 1:>2}.{a}" for j, a in enumerate(chunk)
        )
        print(f"   {row}")
    print()

    # ── 8. Sinh Apps Script ───────────────────────────
    logo_b64, logo_mime = get_local_logo_base64()
    gs_code = generate_apps_script(form_title, answers, logo_b64, logo_mime)

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

    # ── 9. Hướng dẫn ──────────────────────────────────
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

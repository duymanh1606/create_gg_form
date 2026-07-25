/**
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

const FORM_TITLE = "HSA TEST ĐỀ 2 BÀI 1";
const IS_QUIZ = true;           // true = bật chế độ Quiz (tự chấm điểm)
const POINTS_PER_QUESTION = 1;  // Mỗi câu 1 điểm
const LOGO_FILE_ID = "";        // ID ảnh logo trên Google Drive (để trống nếu không có)

const QUIZ_DATA = [
  {
    "question": "Câu 1",
    "answer": "A"
  },
  {
    "question": "Câu 2",
    "answer": "A"
  },
  {
    "question": "Câu 3",
    "answer": "C"
  },
  {
    "question": "Câu 4",
    "answer": "A"
  },
  {
    "question": "Câu 5",
    "answer": "A"
  },
  {
    "question": "Câu 6",
    "answer": "D"
  },
  {
    "question": "Câu 7",
    "answer": "D"
  },
  {
    "question": "Câu 8",
    "answer": "B"
  },
  {
    "question": "Câu 9",
    "answer": "C"
  },
  {
    "question": "Câu 10",
    "answer": "B"
  },
  {
    "question": "Câu 11",
    "answer": "D"
  },
  {
    "question": "Câu 12",
    "answer": "B"
  },
  {
    "question": "Câu 13",
    "answer": "D"
  },
  {
    "question": "Câu 14",
    "answer": "D"
  },
  {
    "question": "Câu 15",
    "answer": "C"
  },
  {
    "question": "Câu 16",
    "answer": "B"
  },
  {
    "question": "Câu 17",
    "answer": "A"
  },
  {
    "question": "Câu 18",
    "answer": "A"
  },
  {
    "question": "Câu 19",
    "answer": "D"
  },
  {
    "question": "Câu 20",
    "answer": "A"
  },
  {
    "question": "Câu 21",
    "answer": "B"
  },
  {
    "question": "Câu 22",
    "answer": "B"
  },
  {
    "question": "Câu 23",
    "answer": "B"
  },
  {
    "question": "Câu 24",
    "answer": "C"
  },
  {
    "question": "Câu 25",
    "answer": "B"
  },
  {
    "question": "Câu 26",
    "answer": "A"
  },
  {
    "question": "Câu 27",
    "answer": "C"
  },
  {
    "question": "Câu 28",
    "answer": "B"
  },
  {
    "question": "Câu 29",
    "answer": "A"
  },
  {
    "question": "Câu 30",
    "answer": "C"
  }
];

function createQuizForm() {
  const form = FormApp.create(FORM_TITLE);
  form.setDescription("Vui lòng điền thông tin và làm bài kiểm tra.");
  form.setIsQuiz(IS_QUIZ);

  // === TRANG 1 (TRANG ĐẦU): THÔNG TIN CHUNG ===
  
  // 1. Thêm Logo từ Google Drive bằng ID
  if (LOGO_FILE_ID) {
    try {
      const img = DriveApp.getFileById(LOGO_FILE_ID).getBlob();
      form.addImageItem().setImage(img).setAlignment(FormApp.Alignment.CENTER);
    } catch (e) {
      Logger.log("Lỗi tải ảnh logo: " + e.message);
    }
  }

  // 2. Thêm câu hỏi Họ và tên
  form.addTextItem()
      .setTitle("Họ và tên")
      .setRequired(true);

  // === TRANG 2: TRẢ LỜI CÂU HỎI ===
  
  // Hàm addPageBreakItem() chia trang từ vị trí hiện tại trở về sau
  // Nghĩa là mọi item add sau lệnh này sẽ nằm ở Trang 2
  form.addPageBreakItem().setTitle("Phần 2: Trả lời");

  // Vòng lặp thêm các câu hỏi trắc nghiệm vào Trang 2
  QUIZ_DATA.forEach(function(q) {
    const item = form.addMultipleChoiceItem();
    item.setTitle(q.question);
    item.setRequired(true);

    if (IS_QUIZ && q.answer) {
      // Tạo choices với đáp án đúng
      const letters = ["A", "B", "C", "D"];
      const choices = letters.map(function(letter) {
        return item.createChoice(letter, letter === q.answer);
      });
      item.setChoices(choices);
      item.setPoints(POINTS_PER_QUESTION);

      const feedback = FormApp.createFeedback()
        .setText("Đáp án đúng: " + q.answer)
        .build();
      item.setFeedbackForCorrect(feedback);
    } else {
      // Không có đáp án → chỉ tạo choices
      item.setChoices([
        item.createChoice("A"),
        item.createChoice("B"),
        item.createChoice("C"),
        item.createChoice("D")
      ]);
    }
  });

  Logger.log("══════════════════════════════════════");
  Logger.log("✅ Form đã tạo thành công!");
  Logger.log("📝 Link chỉnh sửa: " + form.getEditUrl());
  Logger.log("📎 Link cho học sinh: " + form.getPublishedUrl());
  Logger.log("══════════════════════════════════════");
}

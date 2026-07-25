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

const FORM_TITLE = "TEST Đề 1 bài 1";
const IS_QUIZ = true;           // true = bật chế độ Quiz (tự chấm điểm)
const POINTS_PER_QUESTION = 1;  // Mỗi câu 1 điểm

const QUIZ_DATA = [
  {
    "question": "Câu 1",
    "answer": "C"
  },
  {
    "question": "Câu 2",
    "answer": "C"
  },
  {
    "question": "Câu 3",
    "answer": "C"
  },
  {
    "question": "Câu 4",
    "answer": "B"
  },
  {
    "question": "Câu 5",
    "answer": "A"
  },
  {
    "question": "Câu 6",
    "answer": "A"
  },
  {
    "question": "Câu 7",
    "answer": "A"
  },
  {
    "question": "Câu 8",
    "answer": "C"
  },
  {
    "question": "Câu 9",
    "answer": "C"
  },
  {
    "question": "Câu 10",
    "answer": "D"
  },
  {
    "question": "Câu 11",
    "answer": "D"
  },
  {
    "question": "Câu 12",
    "answer": "C"
  },
  {
    "question": "Câu 13",
    "answer": "D"
  },
  {
    "question": "Câu 14",
    "answer": "A"
  },
  {
    "question": "Câu 15",
    "answer": "A"
  },
  {
    "question": "Câu 16",
    "answer": "C"
  },
  {
    "question": "Câu 17",
    "answer": "C"
  },
  {
    "question": "Câu 18",
    "answer": "D"
  },
  {
    "question": "Câu 19",
    "answer": "D"
  },
  {
    "question": "Câu 20",
    "answer": "C"
  },
  {
    "question": "Câu 21",
    "answer": "B"
  },
  {
    "question": "Câu 22",
    "answer": "C"
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
    "answer": "A"
  },
  {
    "question": "Câu 26",
    "answer": "D"
  },
  {
    "question": "Câu 27",
    "answer": "C"
  },
  {
    "question": "Câu 28",
    "answer": "C"
  },
  {
    "question": "Câu 29",
    "answer": "D"
  },
  {
    "question": "Câu 30",
    "answer": "A"
  }
];

function createQuizForm() {
  const form = FormApp.create(FORM_TITLE);
  form.setDescription("Chọn 1 đáp án đúng cho mỗi câu hỏi. Mỗi câu " + POINTS_PER_QUESTION + " điểm.");
  form.setIsQuiz(IS_QUIZ);

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

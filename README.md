# 📝 PDF to Google Form Converter

Công cụ tự động trích xuất đáp án trắc nghiệm (A, B, C, D) từ file PDF và sinh ra mã code Google Apps Script để tạo Google Form. 

**Đặc biệt:** KHÔNG cần cài đặt Google API phức tạp, KHÔNG cần Google Cloud Console. Hoàn toàn miễn phí và cực kỳ dễ sử dụng cho giáo viên / người ra đề!

---

## 🚀 Tính năng nổi bật
- **Bóc tách thông minh**: Tự động dò tìm và bóc tách bảng đáp án từ cuối sách PDF.
- **Form 2 trang chuyên nghiệp**: Tự động chia form làm 2 phần: Trang 1 (Logo & Họ tên học sinh), Trang 2 (Bài kiểm tra).
- **Nhúng Logo tự động**: Chỉ cần bỏ file ảnh vào thư mục, tool sẽ tự mã hoá và chèn ảnh thẳng vào đầu form mà không cần qua Google Drive.
- **Tự động chấm điểm**: Bật sẵn chế độ Quiz (bài kiểm tra), set 1 điểm/câu và cài sẵn đáp án đúng.

---

## 📂 Cấu trúc thư mục cần biết
- `create_form.py`: File chạy chính.
- `exam/`: Nơi bạn bỏ các file PDF có chứa bảng đáp án vào đây.
- `image/`: Nơi chứa ảnh logo của bạn (ví dụ: `hq_image.png`). Nếu có ảnh, tool sẽ tự gắn vào Form.
- `output/`: Thư mục chứa các file mã code (`.gs`) được tạo ra.

---

## ⚙️ Cài đặt (Chỉ làm 1 lần đầu tiên)

1. Cài đặt **Python 3** trên máy tính của bạn.
2. Mở Terminal / Command Prompt tại thư mục dự án và chạy lệnh cài thư viện đọc PDF:
   ```bash
   pip install -r requirements.txt
   ```
*(Nếu bạn đang dùng môi trường ảo (venv), hãy chạy `.venv/bin/python -m pip install -r requirements.txt`)*

---

## 🛠 Hướng dẫn sử dụng chi tiết

### BƯỚC 1: Sinh mã code từ PDF
1. Chắc chắn bạn đã bỏ file PDF đề thi vào thư mục `exam/`.
2. Mở Terminal và chạy lệnh:
   ```bash
   python create_form.py
   ```
3. Script sẽ hỏi bạn một số thông tin, hãy làm theo hướng dẫn:
   - Chọn bài / Chọn đề.
   - Nhập tên Form muốn tạo (VD: *Kiểm tra 15 phút Toán*).
4. Tool báo thành công và sinh ra một file code ở thư mục `output/` (ví dụ: `output/Kiem_tra_Toan.gs`). Code này cũng đã được **tự động copy vào bộ nhớ đệm (clipboard)** của máy tính.

### BƯỚC 2: Tạo Google Form bằng 1 cú click
1. Mở trình duyệt web và truy cập vào: [https://script.google.com](https://script.google.com)
2. Bấm nút **New project** (Dự án mới) ở góc trái.
3. Xóa hết toàn bộ code cũ trên màn hình đi và **Dán (Paste)** đoạn code bạn vừa tạo vào.
4. Bấm nút **Run ▶** (Chạy) ở thanh công cụ phía trên. (Đảm bảo chữ bên cạnh nút Run đang là `createQuizForm`).

### BƯỚC 3: Cấp quyền (Chỉ bị hỏi ở lần đầu tiên)
(CHÚ Ý: Nên tạo 1 tài khoản gg clone để không bị ảnh hưởng tới quyển truy cập dữ )

Vì script sẽ tạo Form bằng tài khoản của chính bạn, Google sẽ yêu cầu xác nhận bảo mật (Hoàn toàn miễn phí, không tốn tiền):
1. Bấm **Review permissions** (Xem lại quyền).
2. Chọn tài khoản Google của bạn.
3. Nếu Google hiện cảnh báo *"Google hasn't verified this app" (Google chưa xác minh ứng dụng này)*:
   - Bấm vào chữ **Advanced (Nâng cao)** ở góc dưới bên trái.
   - Kéo xuống và chọn dòng chữ **Go to Untitled project (unsafe)**.
4. Bấm **Allow (Cho phép)**.

### BƯỚC 4: Lấy link gửi cho học sinh
1. Sau khi chạy xong, hãy nhìn xuống bảng **Execution Log (Nhật ký thực thi)** ở nửa dưới màn hình.
2. Bạn sẽ thấy thông báo:
   ```
   ✅ Form đã tạo thành công!
   📝 Link chỉnh sửa: https://docs.google.com/forms/d/.../edit
   📎 Link cho học sinh: https://docs.google.com/forms/d/.../viewform
   ```
3. Lấy dòng **"Link cho học sinh"** và gửi cho các bạn học sinh làm bài thôi! 🎉

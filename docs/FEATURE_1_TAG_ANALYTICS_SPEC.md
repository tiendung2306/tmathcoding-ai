# ĐẶC TẢ TÍNH NĂNG 1: THỐNG KÊ HOÀN THÀNH BÀI TẬP THEO TAG & NHẬN XẾT AI CÁ NHÂN HÓA
## (Feature 1 Specification: Tag Completion Analytics & AI Diagnostic Engine)

* **Tên tính năng:** Tag Completion Analytics & AI Learning Advisor
* **Mã tính năng:** `FEAT-01`
* **Phiên bản:** 1.0.0
* **Ngày cập nhật:** 21/08/2026
* **Trạng thái:** Approved Specification

---

## 1. TỔNG QUAN & MỤC TIÊU (OVERVIEW & GOALS)

Tính năng **Thống kê Hoàn thành Bài tập theo Tag & Nhận xét AI** cung cấp cho học sinh cái nhìn trực quan, minh bạch về tiến độ học tập và hiệu suất nộp bài trên từng chủ đề bài tập (`judge_problemtype`).

### Mục tiêu chính:
1. **Đo lường Tiến độ Độc lập:** Tính phần trăm bài tập đã AC trên tổng số bài tập của từng Tag chủ đề.
2. **Thống kê Lỗi Nộp bài (Thông tin phụ):** Phân tích tỷ lệ phần trăm các kết quả nộp bài (AC, WA, TLE, RTE, CE) trên tổng số lần nộp bài của từng Tag.
3. **AI Learning Advisor (Nhận xét Cá nhân hóa Daily):** Mỗi ngày hệ thống tự động tạo **1 lời nhận xét duy nhất** dựa trên dữ liệu 7 ngày qua của học sinh. Nhận xét nhẹ nhàng, vui vẻ, chỉ ra hoạt động 7 ngày qua và gợi ý dí dỏm nên luyện thêm bài nào tiếp theo.

---

## 2. YÊU CẦU CHỨC NĂNG CHI TIẾT (FUNCTIONAL REQUIREMENTS)

### 2.1. Tần Suất & Khung Thời Gian (Daily 7-Day Window)
* **Khung thời gian cố định:** Phân tích dữ liệu trong **7 ngày vừa qua**.
* **Tần suất cập nhật:** Sinh 1 lời nhận xét/ngày (Cache theo ngày). Lời nhận xét sẽ đồng hành cùng học sinh suốt cả ngày.

---

### 2.2. Thống Kê Theo Tag (Tag-Level Metrics Computation)

Đối với mỗi Tag chủ đề ($i \in [1, 99]$ từ bảng `judge_problemtype`):

#### A. Chỉ số Tiến độ Hoàn thành Bài tập (Completion Metrics)
* `total_problems`: Tổng số bài tập thuộc Tag $i$ hiện có trong hệ thống tmath.
* `ac_problems`: Số lượng bài tập **duy nhất** thuộc Tag $i$ mà học sinh đã đạt trạng thái AC (Accepted).
* `completion_rate`: Tỷ lệ phần trăm hoàn thành:
  $$\text{completion\_rate} = \left( \frac{\text{ac\_problems}}{\text{total\_problems}} \right) \times 100\%$$
* `tag_weight`: Phân loại quy mô Tag dựa trên `total_problems`:
  * **Tag nhỏ:** `total_problems` $\le 3$ bài.
  * **Tag trung bình:** $4 \le$ `total_problems` $\le 9$ bài.
  * **Tag lớn:** `total_problems` $\ge 10$ bài.

#### B. Chỉ số Thống kê Nộp bài (Submission Verdict Rates - Độc lập)
Tính trên tổng số lượt bấm "Nộp bài" của học sinh thuộc Tag $i$ trong 7 ngày qua:
* `total_submissions`: Tổng số lượt nộp bài.
* `ac_count`: Số lượt chấm đúng (AC).
* `wa_count`: Số lượt sai kết quả (WA - Wrong Answer).
* `tle_count`: Số lượt quá giới hạn thời gian (TLE - Time Limit Exceeded).
* `other_count`: Số lượt lỗi khác (RTE, CE, MLE...).
* **Tỷ lệ từng loại verdict (%):**
  $$\text{wa\_rate} = \left( \frac{\text{wa\_count}}{\text{total\_submissions}} \right) \times 100\%$$
  $$\text{tle\_rate} = \left( \frac{\text{tle\_count}}{\text{total\_submissions}} \right) \times 100\%$$

---

### 2.3. Động Cơ AI Nhận Xét (Daily 7-Day AI Advisor)

Động cơ AI đóng vai trò làm Mentor thân thiện, mỗi ngày sinh 1 câu nhận xét nhẹ nhàng gồm 2 ý chính:

1. **Ý 1: Nhận xét 7 ngày vừa qua & Cảnh báo lỗi nộp bài:**
   * *Nếu có nộp bài:* Nêu rõ số lượt nộp và các Tag đã làm. **Đặc biệt:** Nếu học sinh bị nộp sai (WA - Wrong Answer) hoặc quá giới hạn thời gian (TLE - Time Limit Exceeded) ở Tag nào, AI sẽ nhẹ nhàng chỉ rõ loại lỗi và số lần vướng phải (ví dụ: *"Bạn đã nộp 5 bài tuần qua, đáng chú ý có 1 lần TLE ở Tag 'Toán: Số học'. Hãy chú ý tối ưu thuật toán nhé! 😉"*).
   * *Nếu không nộp bài:* "7 ngày qua bạn chưa nộp bài mới nào cả, tranh thủ nghỉ ngơi hay đang bí thuật toán thế?"
2. **Ý 2: Gợi ý vui vẻ (Friendly Recommendation):**
   * Đưa ra lời khuyên vui vẻ, kích thích động lực: "Hôm nay thử khởi động lại bằng 1 bài thuộc dạng [Tag C] xem thế nào nhé! 😉"

---

## 3. THIẾT KẾ GIAO DIỆN NGƯỜI DÙNG (UI/UX SPECIFICATION)

Giao diện gồm **2 Khối chính**:

### 1. Thẻ Nhận Xét AI Hằng Ngày (Daily AI Insight Card)
* Đặt ở vị trí nổi bật trên cùng của trang Dashboard.
* Nội dung: Lời nhận xét vui vẻ, thân thiện cho 7 ngày qua + Gợi ý bài tập trong ngày.

### 2. Bảng Thống Kê Chi Tiết Theo Tag (Tag Completion List / Cards)
* **Thanh công cụ:**
  * Bộ lọc nhanh theo trạng thái: `Tất cả` | `🟢 Điểm mạnh` | `🔴 Yếu/Sai nhiều` | `⚪ Chưa làm`.
  * Ô tìm kiếm tên Tag (`judge_problemtype`).
* **Chi tiết mỗi Card Tag:**
  * **Tên Tag & Nhãn quy mô:** Ví dụ *Quy hoạch động (15 bài)*.
  * **Thanh tiến trình Hoàn thành bài tập:** Progress Bar hiển thị `% completion_rate` ($AC\_problems / Total\_problems$).
  * **Thanh phân bố Lỗi nộp bài (Badge Info):** Hiển thị % AC, % WA, % TLE. Cảnh báo đỏ nếu % WA hoặc TLE vượt mốc $50\%$.

---

## 4. ĐẶC TẢ API (API SPECIFICATION)

### API 1: Lấy dữ liệu thống kê theo Tag của Học sinh
* **Endpoint:** `GET /api/v1/student/analytics/tags`
* **Query Parameters:**
  * `user_id`: `int` (Mặc định `1` khi test độc lập)
* **Lưu ý Tích hợp:** Khi đưa vào Monolith chính, thay thế `user_id` query bằng Session/JWT Auth Dependency.
* **Response Output (JSON):**
```json
{
  "user_id": 1,
  "student_name": "Nguyễn Văn A",
  "summary": {
    "total_problems_in_system": 1250,
    "total_solved_unique": 45,
    "total_submissions_7d": 120
  },
  "tags": [
    {
      "tag_id": 12,
      "key": "dp",
      "name": "Dynamic Programming",
      "total_problems": 15,
      "ac_problems": 5,
      "completion_rate": 33.33,
      "tag_weight": "large",
      "submissions_stat": {
        "total_submissions": 20,
        "ac_count": 5,
        "wa_count": 2,
        "tle_count": 13,
        "ac_rate": 25.0,
        "wa_rate": 10.0,
        "tle_rate": 65.0,
        "primary_error": "TLE"
      },
      "status": "NEEDS_IMPROVEMENT"
    }
  ]
}
```

### API 2: Lấy nhận xét hằng ngày từ AI Advisor cho Học sinh
* **Endpoint:** `GET /api/v1/student/analytics/ai-commentary`
* **Query Parameters:**
  * `user_id`: `int` (Mặc định `1` khi test độc lập)
  * `force_refresh`: `boolean` (Mặc định `false`)
* **Lưu ý Tích hợp:** Khi đưa vào Monolith chính, thay thế `user_id` query bằng Session/JWT Auth Dependency.
* **Response Output (JSON):**
```json
{
  "commentary": "Trong 7 ngày vừa qua, bạn đã nộp 15 lượt bài tập và làm rất tốt ở mảng Quy hoạch động (5 bài AC)! Hôm nay thử đổi gió với 1 bài toán Sắp xếp nhẹ nhàng để tích điểm nhé! 😉",
  "recent_7days_summary": {
    "submissions_count": 15,
    "active_tags": ["Dynamic Programming"]
  },
  "recommended_tags": ["Sắp xếp", "Mảng 1D"],
  "generated_at": "2026-08-23T08:00:00Z"
}
```

---

## 5. KẾ HOẠCH TRIỂN KHAI (IMPLEMENTATION STEPS)

1. **Tạo Cấu Trúc Thư Mục `docs/`:** Di chuyển và tổ chức lại các file tài liệu đặc tả vào thư mục `docs/`.
2. **Backend Implementation:**
   * Xây dựng SQL Aggregation Service để tính toán các thông số theo Tag và Khung thời gian.
   * Xây dựng Prompt Engineering & Service kết nối với LLM Adapter (Ollama / Gemini) qua Instructor Framework.
3. **Frontend Implementation:**
   * Xây dựng Component `AIAdvisorCard` hiển thị lời nhận xét.
   * Xây dựng Component `TagCompletionGrid` hiển thị danh sách 99 tag kèm thanh phần trăm hoàn thành và tỷ lệ nộp đúng/sai.

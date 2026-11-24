# Code Doctor v2

Code Doctor viết nhận xét cho **giảng viên** về một bài nộp, cả bài AC lẫn bài
lỗi (WA, TLE, RTE, IR, CE, MLE, OLE). Mỗi nhận xét về mã phải chỉ ra dòng cụ
thể; nhận xét lỗi không có dòng thật bị loại trước khi hiển thị.

Cách làm dựa trên Clara ([Gulwani, Radiček, Zuleger, PLDI 2018](https://www.microsoft.com/en-us/research/publication/automated-clustering-program-repair-introductory-programming-assignments/)):
dùng các bài đúng sẵn có để đánh giá bài mới, gom bài đúng thành cụm (hướng
giải), và so bài mới với cụm có chi phí sửa nhỏ nhất.

## Luồng xử lý

1. Đọc bài nộp, đề và kết quả từng test qua Source API (quyền kiểm tra mỗi lần).
2. Dựng mô hình chương trình (`app/services/code_doctor/program_model.py`):
   - như Clara, chỉ giữ cấu trúc vòng lặp làm luồng điều khiển; đoạn không có
     vòng lặp được gộp lại. Ví dụ `E[L()L(L())]` là main có một vòng lặp đơn và
     một vòng lặp lồng hai tầng;
   - chuỗi token đã thay tên biến bằng `ID` để đổi tên biến không làm thay đổi
     khoảng cách;
   - đặc trưng kỹ thuật (mảng cộng dồn, sắp xếp, tìm kiếm nhị phân, set/map...).
3. Phân tích tĩnh (`static_facts.py`): ràng buộc n từ đề, ước lượng độ phức tạp,
   rủi ro tràn số, nhập xuất chậm, đệ quy sâu, mảng nhỏ hơn n.
4. Ngân hàng lời giải (`solution_bank.py`, `matching.py`):
   - lần đầu lấy tối đa 3 bài AC mẫu qua `GET /problems/{id}/accepted-samples`;
   - hai bài đúng cùng ngôn ngữ, cùng cấu trúc vòng lặp và cùng tập kỹ thuật
     thuộc một hướng giải; bài đầu tiên là đại diện;
   - mỗi bài AC được Code Doctor xem cũng được thêm vào ngân hàng, nên số hướng
     giải tăng dần mà không cần mở rộng Source API;
   - chi phí sửa = khoảng cách token (0 đến 100) + 40 nếu khác cấu trúc vòng lặp
     + tối đa 30 nếu khác kỹ thuật. Hướng gần nhất là hướng có chi phí nhỏ nhất;
     hướng tốt nhất là hướng giảng viên chọn làm chuẩn, nếu chưa có thì là hướng
     có độ phức tạp ước lượng thấp nhất.
5. Model nhận đề, ràng buộc, kết quả chấm, phân tích tĩnh, thẻ hướng giải và mã
   AC tham chiếu, rồi trả JSON theo `DoctorLLMOutput`.
   Với bài AC, mã tham chiếu là hướng tốt nhất nếu nó nhanh hơn bài nộp.
6. `validator.py` loại dòng không tồn tại, giới hạn số mục, hạ độ tin cậy khi
   thiếu bằng chứng; với bài AC, "lỗi logic" được chuyển thành rủi ro chưa bị
   test phát hiện.
7. Báo cáo lưu vào `doctor_report` và Redis. Khi model lỗi hoặc quá giờ, báo cáo
   vẫn có phần phân tích tĩnh và so khớp, kèm `fallback_reason`, cache 5 phút.

Khác biệt so với Clara: chưa chạy chương trình nên chưa so khớp biến bằng
trace và chưa có phản ví dụ. Đây là giai đoạn 3 của kế hoạch (`doctor-runner`
chạy mã học sinh và mã AC trên input sinh tự động trong sandbox).

## Cấu hình model

Code Doctor đọc cả mã học sinh và mã tham chiếu nên cần model mạnh hơn và cửa
sổ ngữ cảnh lớn hơn auto-tag. Các biến `DOCTOR_LLM_*` để trống sẽ dùng giá trị
`LLM_*` tương ứng.

| Biến | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `DOCTOR_LLM_PROVIDER` | `LLM_PROVIDER` | `openai_compatible`, `ollama` hoặc provider của litellm |
| `DOCTOR_LLM_BASE_URL` | `LLM_BASE_URL` | Endpoint tương thích OpenAI |
| `DOCTOR_LLM_API_KEY` | `LLM_API_KEY` | Khóa API |
| `DOCTOR_LLM_MODEL` | `LLM_MODEL` | Tên model |
| `DOCTOR_LLM_CONTEXT_WINDOW` | `LLM_CONTEXT_WINDOW` | Token ngữ cảnh; nên từ 16384 trở lên |
| `DOCTOR_LLM_MAX_TOKENS` | 1800 | Token tối đa cho câu trả lời JSON |
| `DOCTOR_LLM_TIMEOUT_SECONDS` | 150 | Thời hạn một lần gọi model; job có thêm 90 giây |

Model chạy cục bộ qua Ollama được gửi `reasoning_effort: none`; nếu model vẫn
trả khối `<think>`, adapter bỏ khối đó trước khi đọc JSON. Ollama trong Docker
trên macOS chỉ chạy CPU, nên model 4B thường quá chậm cho Code Doctor.

## API

| Phương thức | Đường dẫn | Mục đích |
| --- | --- | --- |
| `POST` | `/api/v1/student/code-doctor/diagnose` | Tạo hoặc lấy báo cáo; kết quả có `diagnosis` (tương thích cũ) và `report` |
| `GET` | `/api/v1/student/code-doctor/problems/{problem_id}/approaches` | Danh sách hướng giải của bài |
| `PATCH` | `/api/v1/student/code-doctor/approaches/{approach_id}` | Đặt tên, mô tả, `status` (`auto`, `approved`, `rejected`), `is_canonical` |
| `POST` | `/api/v1/student/code-doctor/submissions/{submission_id}/feedback` | Giảng viên chấm báo cáo: `correct`, `partial`, `wrong` |

Hướng giải bị `rejected` không được dùng để so sánh. Chọn `is_canonical` sẽ bỏ
cờ này ở các hướng khác của cùng bài và duyệt hướng đó.

## Dữ liệu (`tmath_dashboard`, revision `20261125_0001`)

| Bảng | Nội dung |
| --- | --- |
| `doctor_solution_approach` | Hướng giải: cấu trúc vòng lặp, kỹ thuật, độ phức tạp, bài đại diện, trạng thái duyệt |
| `doctor_solution_member` | Bài AC thuộc hướng giải: ID bài nộp, hash mã nguồn, chi phí sửa so với đại diện |
| `doctor_report` | Báo cáo mới nhất của mỗi bài nộp, kèm fingerprint đầu vào |
| `doctor_feedback` | Đánh giá của giảng viên về báo cáo |

Không lưu mã nguồn trong dashboard DB. Mã đại diện được đọc lại qua Source API
với quyền của người đang dùng.

## Kiểm thử

```sh
cd backend && python -m pytest tests/test_code_doctor.py
cd frontend && npm test
```

`SqlStoreTests` chỉ chạy khi có `aiosqlite`; các test khác dùng `MemoryDoctorStore`.

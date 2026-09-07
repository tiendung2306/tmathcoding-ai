# KẾ HOẠCH PHÂN CÔNG PHÁT TRIỂN (WORK SPLIT PLAN)
## tmath AI Diagnostic & Admin Dashboard Service

* **Phiên bản:** 1.1.0
* **Trạng thái:** Đã duyệt phân công — 2 dev fullstack: **Dũng** (Dev A), **Khải** (Dev B)
* **Bản trình bày PDF:** `bao-cao-du-an.pdf` (cùng thư mục `docs/`)

---

## 1. ĐÁNH GIÁ TIẾN ĐỘ HIỆN TẠI (BASELINE ASSESSMENT)

Mã nguồn hiện tại **đi xa hơn mức "base"**: các tính năng phía Học sinh và Giáo viên đã có logic thật ở cả backend lẫn frontend. Vấn đề "chưa chạy được" đến từ 3 nhóm nguyên nhân: môi trường chưa dựng, một số điểm dữ liệu đang gắn cứng (mock), và 2 tính năng trong SDD chưa triển khai.

### 1.1. Đã làm xong (chỉ cần kiểm chứng lại khi chạy thật)

| Thành phần | Trạng thái | Ghi chú |
|---|---|---|
| Backend core (config, async MySQL, LLM Adapter Instructor + LiteLLM) | Xong | `backend/app/core/` |
| 11 model ánh xạ DB thật tmath (DMOJ) | Xong | `backend/app/models/dmoj.py` |
| FEAT-01: Tag Analytics + AI Advisor hằng ngày | Xong logic | `tag_analytics_service.py`, `tag_ai_service.py`, có fallback khi LLM lỗi |
| F1.1 Cây kỹ năng 99 node | Xong logic | `skill_tree_service.py` — riêng Bloom Radar đang là số cứng |
| F1.2 Code Doctor (Socratic) | Xong logic | `code_doctor_service.py`, có fallback theo loại lỗi |
| F2.1 Heatmap 2D + cảnh báo STUCK/GAP/INACTIVE | Xong logic | `heatmap_service.py`, dữ liệu Bloom thật |
| F2.2 Tìm kiếm + chi tiết học sinh | Xong logic | `teacher.py`, `StudentDetailModal.tsx` |
| Frontend: shell, sidebar, tìm kiếm toàn cục, 2 dashboard | Xong | TypeScript biên dịch sạch (`tsc --noEmit` không lỗi) |
| Infra: docker-compose, script seed DB / nạp model | Xong | `scripts/`, backup 200 file SQL |

### 1.2. Chưa xong hoặc đang gắn cứng (lý do "chưa hoạt động được")

1. **Môi trường chưa dựng:** Python deps chưa cài trên máy, Docker stack chưa chạy, DB chưa seed, model Ollama chưa nạp. Backend hiện chỉ chạy được trong Docker.
2. **Dữ liệu gắn cứng:**
   - Bloom Radar của Skill Tree trả về điểm mô phỏng theo số chủ đề (`skill_tree_service.py` dòng 59–67), không phải điểm Bloom thật.
   - Nút "Chẩn đoán bài nộp" gọi cứng `submission_id = 3447100` (`StudentDashboard.tsx` dòng 78), không có cách chọn bài nộp lỗi thật.
   - `admin.py` trả về số liệu auto-tag cứng (16491/4520/27.4%), chưa có pipeline thật.
3. **Tính năng còn thiếu theo SDD:**
   - **F3.1 Pipeline Auto-Tagging** (Code-Informed Classifier) — mới có schema `AutoTagResult`, chưa có worker, chưa lưu kết quả.
   - **F1.3 Chế độ tự học** — chưa có code nào.
4. **Nợ kỹ thuật:** Redis/Celery khai báo trong requirements và compose nhưng chưa dùng (cache AI commentary đang in-memory, mất khi restart); các endpoint giáo viên chưa kiểm tra quyền (bất kỳ `org_id`/`teacher_id` nào cũng đọc được); chưa có test tự động.

---

## 2. NGUYÊN TẮC CHIA VIỆC

Chia theo **domain dọc (vertical slice)**, mỗi dev chịu trách nhiệm toàn bộ backend + frontend + kiểm thử của domain mình để tránh xung đột merge:

- **Dũng (Dev A) — Domain Học sinh:** F1.1, F1.2, F1.3, FEAT-01, cache/queue AI.
- **Khải (Dev B) — Domain Giáo viên + Admin:** F2.1, F2.2, F3.1, phân quyền, hạ tầng kiểm thử.

---

## 3. MILESTONE 0 — DỰNG MÔI TRƯỜNG & CHẠY THẬT (Cả 2 làm chung, 1–2 ngày)

Mục tiêu: hệ thống chạy end-to-end thật với dữ liệu thật.

| # | Việc | Owner |
|---|---|---|
| M0.1 | `docker compose up -d --build`, seed 10.1 GB backup, nạp model Ollama theo README | Cả 2 (mỗi người 1 bộ env độc lập) |
| M0.2 | Rà soát và sửa `docker-compose.yml`, `scripts/seed_mysql.py`, `scripts/pull_model.py` nếu seed/nạp lỗi; ghi lại mọi bước vào README | **Khải chính**, Dũng review |
| M0.3 | Hướng dẫn chạy dev nhẹ không cần full Docker: chỉ container `db` + `redis` + `ollama`, backend chạy `uvicorn` local, frontend `npm run dev` | **Dũng chính**, Khải review |
| M0.4 | Smoke test checklist: `/health`, 4 API student, 5 API teacher, 2 dashboard render đủ dữ liệu | Cả 2 |

Đầu ra: hệ thống chạy thật, danh sách bug thực tế ghi vào issue để xếp vào A/B bên dưới.

---

## 4. DŨNG — HỌC SINH & AI CÁ NHÂN HÓA (fullstack)

### A1. Bloom Radar thật cho Cây Kỹ năng (sửa dữ liệu gắn cứng)
- Backend: tính điểm Bloom thật từ `judge_problem.group_id` theo cách của `heatmap_service.py` (đã có `BLOOM_GROUP_MAP`: 4→A, 5→B, 6→C, 7→D, 8→E, 13→F). Sửa `skill_tree_service.py` + `schemas/student.py`.
- Frontend: cập nhật `types/index.ts`, `BloomRadar.tsx` để nhận điểm thật thay vì 6 trường cứng.

### A2. Code Doctor dùng bài nộp thật (bỏ mock 3447100)
- Backend: thêm `GET /api/v1/student/submissions/failed?user_id=` — danh sách bài nộp lỗi gần đây (WA/TLE/RTE) kèm tên bài, verdict, thời gian (join `judge_submissionsource` để chỉ trả bài có mã nguồn).
- Frontend: thay nút mock bằng danh sách/chọn bài nộp lỗi rồi mới mở `CodeDoctorModal`; có trạng thái rỗng ("Không có bài nộp lỗi trong 7 ngày qua").

### A3. Cache AI commentary bằng Redis (thay in-memory dict)
- Sửa `tag_ai_service.py`: đọc/ghi key `ai_commentary:{user_id}:{YYYY-MM-DD}` qua Redis (`REDIS_HOST` đã có trong config). `force_refresh` vẫn xóa cache.
- Tùy chọn nâng cao (nếu còn thời gian): Celery beat sinh nhận xét sáng mỗi ngày.

### A4. F1.3 Chế độ tự học (tính năng mới — cần chốt phạm vi với chủ dự án trước khi code)
- Đề xuất phạm vi: gợi ý lộ trình tự học dựa trên tag yếu nhất từ FEAT-01 (tag `NEEDS_IMPROVEMENT` / `UNATTEMPTED` có `total_problems` lớn) + danh sách bài đề xuất trong tag đó.
- Backend: 1 endpoint mới + service; Frontend: 1 section mới trong `StudentDashboard` theo `DESIGN.md`.

### A5. Chất lượng
- pytest cho `tag_analytics_service`, `skill_tree_service`, `code_doctor_service` (dùng SQLite/fixture hoặc DB đã seed).
- Audit anti-slop toàn bộ UI phía Học sinh theo `ANTISLOP.md`.

---

## 5. KHẢI — GIÁO VIÊN, ADMIN & PIPELINE AI (fullstack)

### B1. F3.1 Pipeline Auto-Tagging thật (ưu tiên cao nhất của Khải)
- Tạo bảng mới (ví dụ `judge_problem_ai_tag`) + model SQLAlchemy: `problem_id`, `primary_tag_id`, `secondary_tag_ids`, `bloom_group_id`, `reasoning`, `model`, `created_at`. Có script CREATE TABLE đi kèm.
- Feature extractor: quét mã nguồn AC (`judge_submissionsource`) nhận đặc trưng — `dfs/bfs/queue`, `dp[][]`, `segment_tree`, `gcd/sàng`, kèm giới hạn N từ đề — đúng theo SDD §4.3 và prompt mẫu SDD §6.
- Service gọi `llm_adapter.generate_structured` với schema `AutoTagResult` (đã có sẵn trong `schemas/ai.py`).
- Sửa `POST /admin/auto-tag/run-batch`: chạy batch thật bằng FastAPI BackgroundTasks (lấy N bài chưa tag, tag lần lượt, ghi DB, có giới hạn tốc độ). `GET /admin/auto-tag/status` đọc số liệu thật từ DB.
- Frontend: trang **Admin** mới (thêm tab trong `AppSidebar`): thanh tiến độ, nút chạy batch, bảng 10 bài tag gần nhất. Giữ tối giản theo `DESIGN.md`.

### B2. Phân quyền phía Giáo viên
- Kiểm tra `teacher_id` thuộc `judge_organization_admins` (hoặc super_admin) trước khi trả heatmap/chi tiết học sinh; không thì trả 403.
- Gom logic vào một dependency (ví dụ `get_current_teacher`) để sau này cắm JWT thật theo SDD §7 mà không sửa từng endpoint.

### B3. Chất lượng & hạ tầng
- pytest cho `heatmap_service` (điểm Bloom, 3 loại cảnh báo) và các endpoint teacher.
- Healthcheck cho service `backend` trong docker-compose; dọn biến Redis/Celery trong requirements nếu không dùng (phối hợp với Dũng khi A3 dùng Redis).
- Audit anti-slop toàn bộ UI phía Giáo viên/Admin theo `ANTISLOP.md`.

### B4. Tùy chọn (nếu còn thời gian, cần chủ dự án duyệt)
- Migration frontend sang cấu trúc tham chiếu `shadcn-admin` (theo `flow-agent/step-1..3.md`). Khuyến nghị: **hoãn** đến khi A1–A4, B1–B3 ổn định, vì rủi ro đụng chéo toàn bộ frontend. Nếu làm thì Dũng nhận phần trang Học sinh, Khải nhận phần Giáo viên/Admin.

---

## 6. QUY TẮC PHỐI HỢP

1. **Hợp đồng API:** backend `app/schemas/*.py` (Pydantic) và frontend `src/types/index.ts` phải luôn đồng bộ. Ai đổi một trong hai phải đổi cả hai trong cùng commit và báo trong PR.
2. **Ranh giới file:** Dũng sở hữu `student.py`, `schemas/student.py`, `schemas/analytics.py`, service phía student, trang Student; Khải sở hữu `teacher.py`, `admin.py`, `schemas/teacher.py`, heatmap/auto-tag service, trang Teacher/Admin. File chung (`router.py`, `App.tsx`, `AppSidebar.tsx`, `types/index.ts`): chỉ được thêm, không sửa phần của người kia; xung đột merge thì người không phải chủ sở hữu ưu tiên nhường.
3. **Nhánh:** `feat/student-*` (Dũng), `feat/teacher-admin-*` (Khải), `infra/*` (Khải ở M0), PR vào `main` phải có ít nhất 1 review của dev còn lại.
4. **Thiết kế:** mọi thay đổi UI phải theo `DESIGN.md`, qua audit `ANTISLOP.md`. Copy tiếng Việt ngắn gọn, không thêm dịch tiếng Anh tự động.
5. **Demo hàng tuần:** mỗi dev demo domain của mình trên dữ liệu thật; bug phát hiện nằm ngoài domain ghi issue cho đúng owner.

---

## 7. THỨ TỰ ƯU TIÊN TÓM TẮT

| Tuần | Dũng | Khải |
|---|---|---|
| 1 | M0 + A1 (Bloom Radar thật) | M0 + B1 (Auto-Tagging pipeline thật) |
| 2 | A2 (Code Doctor thật) | B1 tiếp + B2 (trang Admin + phân quyền) |
| 3 | A3 (Redis cache) + A4 (Chế độ tự học) | B3 (pytest, healthcheck) |
| 4 | A4 tiếp + A5 (test + audit) | B4 tùy chọn / xử lý nợ kỹ thuật |

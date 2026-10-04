# tmath AI Diagnostic & Admin Dashboard Service

Hệ thống Microservice AI Phân Tích Học Lực, Trợ Lý AI Code Doctor, Auto-Tagging & Màn Hình Admin Dashboard cho Nền tảng tmath Online Judge (DMOJ).

Dashboard dùng hai kết nối database độc lập: DB gốc chỉ đọc và `tmath_dashboard`
do dashboard quản lý bằng migration Alembic có phiên bản. Đọc
[hướng dẫn database và migration](backend/DB_ARCHITECTURE.md) trước khi cấu hình
kết nối hoặc sửa schema. Profile `local-source` bên dưới dùng DB gốc local làm fixture;
khi kết nối DB gốc bên ngoài, bỏ profile và cấu hình `SOURCE_DB_*`.

---

## Điều hướng frontend

Frontend dùng React 18, TypeScript, Vite và React Router 6 với browser history.
Mỗi màn hình chính có địa chỉ riêng; Back/Forward, tải lại, bookmark và mở link
trong tab mới hoạt động theo URL.

| Địa chỉ | Màn hình |
| --- | --- |
| `/` | Chọn khu vực làm việc |
| `/student/classes` | Danh sách lớp |
| `/student/classes/:classId/students` | Học sinh trong lớp |
| `/student/students/:studentId` | Thống kê học sinh |
| `/teacher/classes` | Danh sách lớp giáo viên |
| `/teacher/classes/:classId/sessions` | Phiên học của lớp |
| `/teacher/sessions/:sessionId` | Theo dõi hoặc xem lại phiên học |
| `/admin` | Quản trị dashboard |
| `/admin/skills` | Cấu hình cây kỹ năng và phân loại tag |

Tìm kiếm lớp/học sinh, bộ lọc danh sách lớp, sắp xếp, phân trang lớp và khoảng thời gian dùng query string.
Link từ lớp sang học sinh giữ ngữ cảnh danh sách để breadcrumb đưa người dùng
về đúng bộ lọc trước đó. Link tìm học sinh toàn cục mở hồ sơ độc lập.

Khi deploy bản build, cấu hình web server trả `index.html` cho các đường dẫn
frontend chưa khớp file. Các đường dẫn `/api/` phải proxy đến backend; tài nguyên
tĩnh phải được phục vụ như file, không trả HTML thay cho file bị thiếu. Vite dev
server hiện hỗ trợ tải lại các địa chỉ frontend trực tiếp.

Kiểm tra frontend trong thư mục `frontend`: `npm ci`, `npm test`, `npm run build`.
Các route tiếp tục dùng quy ước truy cập backend hiện tại của dự án; lựa chọn
khu vực ở trang đầu không thay thế xác thực tài khoản.

TanStack Query quản lý các read của dashboard và ngữ cảnh lớp: cache 30 giây,
nhận xét AI 5 phút, giữ cache không sử dụng tối đa 5 phút. Request cùng query key
được dùng chung, kể cả lúc StrictMode remount; kết quả đến muộn chỉ cập nhật cache
của đúng học sinh/khoảng thời gian. Shared read được cho phép hoàn tất thay vì hủy
ngay khi một consumer rời trang; request thống kê có timeout 30 giây, AI 250 giây.
Retry thực hiện qua từng phần UI, không tự gửi lại request lỗi hoặc sinh AI.
Khi tích hợp đăng nhập/đăng xuất, xóa query cache khi đổi tài khoản và thêm phạm vi
tài khoản vào query key. Cache frontend không thay thế kiểm tra quyền backend.

Vite polling trên Docker/Windows dùng chu kỳ 1 giây và bỏ qua cache npm, build,
tests. Tránh đặt cache công cụ mới trong cây thư mục được watcher theo dõi.

[Báo cáo kiểm tra điều hướng và UI](anti-slop/audit-001-2026-10-04.md).

Cây kỹ năng dùng 10 gốc cố định và Khác, mở theo luồng gốc → tag → bài toán.
Mỗi tag có kho bài tìm kiếm/lọc/phân trang; mở bài để xem đề, công thức toán và
lịch sử nộp. Số AC đếm bài riêng biệt trong khoảng chọn, không chấm điểm 0–100.
Bộ lọc và trang trong cây giữ khi đóng modal, hiện chưa lưu vào URL.

Màn quản trị `/admin/skills` cho kéo thả hoặc chọn nhóm để lưu ngay. AI phân loại
tag chưa gắn và lưu danh sách đề xuất vào DB; quản trị duyệt/từ chối trong modal.
Frontend không yêu cầu chọn tài khoản quản trị. Backend dùng
`DASHBOARD_ADMIN_PROFILE_ID` và kiểm tra `super_admin` theo quy ước standalone.

Đọc [hướng dẫn cấu hình và thống kê bài AC](docs/SKILL_TREE_CONFIGURATION.md)
và [bảng phân loại 99 tag](docs/SKILL_TAG_TAXONOMY_2026-10-04.md).
Cấu hình nằm trong database dashboard. Triển khai toàn bộ chuỗi migration đến
head `20261004_0003` trước khi chạy backend mới:

```sh
docker compose run --rm dashboard-migrate python -m app.db.migrate deploy
```

Migration giữ bản sao cấu hình trước khi chuyển sang gốc cố định và giữ gán tay
ở gốc nhận biết. Nếu gốc custom có tag nhưng chưa có ánh xạ rõ, migration dừng
trước DDL để operator bổ sung kế hoạch ánh xạ; không tự ép tag vào Khác.
Frontend thêm thư viện kéo thả, modal/menu và hiển thị Markdown/công thức.
Chạy `npm ci` hoặc rebuild container frontend khi lấy phiên bản mới.

## 🏗️ CẤU TRÚC DỰ ÁN (PROJECT STRUCTURE)

```text
tmathcoding/
├── .env.example                  # Mẫu biến môi trường dự án
├── .env                          # File cấu hình môi trường local chính
├── docker-compose.yml            # Docker Compose Base Stack (DB, Redis, Ollama, Open WebUI, Backend, Frontend)
├── docker-compose.gpu.yml        # NVIDIA CUDA GPU Extension Override (Siêu gọn - 10 dòng)
├── docker-compose.rocm.yml       # AMD ROCm GPU Extension Override (Siêu gọn - 8 dòng)
├── docs/                         # Thư mục chứa tài liệu đặc tả & thiết kế dự án
│   ├── SOFTWARE_DESIGN_DOCUMENT.md   # Tài liệu Thiết kế SDD v3.1.0 chuẩn hóa
│   └── FEATURE_1_TAG_ANALYTICS_SPEC.md # Đặc tả chi tiết Tính năng 1 (Tag Analytics & AI Diagnostic)
├── backup/                       # Thư mục chứa 202 file SQL backup (10.1 GB)
├── scripts/
│   ├── pull_model.py             # Script nạp Model AI từ .env vào Docker Persistent Volume
│   ├── seed_mysql.py             # Script tự động import 10.1 GB backup vào MySQL DB
│   └── test_llm.py               # Script Chat CLI Interactive thử nghiệm kết nối LLM Engine
├── backend/                      # Service FastAPI Backend AI API
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py         # Nạp biến môi trường động & LLM Hyperparameters từ .env
│   │   │   └── llm_adapter.py    # AsyncOpenAI/HTTPX cho Ollama, Instructor JSON; LiteLLM cho provider khác
│   │   ├── services/
│   │   └── main.py
│   └── Dockerfile
└── frontend/                     # React 18 + TypeScript + Vite Dashboard App
```

---

## ⚙️ CẤU HÌNH SIÊU THAM SỐ LLM ENGINE (`.env`)

Bạn có thể tinh chỉnh các thông số siêu tham số mô hình AI dễ dàng tại file `.env` gốc dự án:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=hf.co/empero-ai/Qwen3.8-4B-GGUF:Q4_K_M
LLM_API_KEY=ollama

# Tinh chỉnh Siêu tham số LLM (Hyperparameters)
LLM_TEMPERATURE=0.2          # Độ sáng tạo (0.0: Chính xác/Phân tích code, 1.0: Văn bản)
LLM_MAX_TOKENS=2048          # Số lượng token tối đa trong 1 câu trả lời
LLM_TOP_P=0.95               # Nucleus sampling probability
LLM_CONTEXT_WINDOW=8192      # Kích thước cửa sổ ngữ cảnh (Context Window / num_ctx)
LLM_REQUEST_TIMEOUT_SECONDS=240 # Deadline mặc định, bao gồm retry; Code Doctor dùng 90s, auto-tag 240s
```

---

## ⚡ HƯỚNG DẪN KHỞI CHẠY 100% QUA DOCKER (FULL CONTAINERIZED MODE)

### Bước 1: Khởi chạy Docker Compose (Tùy chọn theo Phần cứng)

* **Chạy CPU Mode (Mặc định):**
  ```bash
  docker compose --profile local-source up -d --build
  ```

* **Chạy NVIDIA CUDA GPU Acceleration:**
  ```bash
  docker compose --profile local-source -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
  ```

* **Chạy AMD ROCm GPU Acceleration:**
  ```bash
  docker compose --profile local-source -f docker-compose.yml -f docker-compose.rocm.yml up -d --build
  ```

---

### Bước 2: Nạp Model AI Trong `.env` Vào Container Ollama (Chạy 1 lần đầu)

```bash
docker exec -it tmath-backend python /scripts/pull_model.py
```

---

### Bước 3: Seed 10.1 GB Dữ Liệu Backup Vào MySQL (Chạy 1 lần đầu)

```bash
  docker compose --profile local-source run --rm source-seed
```

---

### 🧪 Bước 4: Kiểm Tra & Trải Nghiệm AI

Lệnh seed ở bước 3 chỉ dành cho fixture local, không chạy với DB gốc bên ngoài.
Backend dùng tài khoản chỉ đọc nên không thực hiện import/schema của DB gốc.

* **Cách 1: Giao diện Giao tiếp Web UI (ChatGPT-like UI):** `http://localhost:3000` (Open WebUI)
* **Cách 2: Trải nghiệm Interactive AI Chat CLI:**
  ```bash
  docker exec -it tmath-backend python /scripts/test_llm.py
  ```

---

## 🌐 ĐƯỜNG DẪN TRUY CẬP HỆ THỐNG

* **Open WebUI (ChatGPT UI cho Ollama):** `http://localhost:3000`
* **tmath React Frontend Dashboard:** `http://localhost:5173`
* **FastAPI OpenAPI Swagger Docs:** `http://localhost:8000/docs`
* **Health Check Endpoint:** `http://localhost:8000/health`

## Phân tích nguồn và vòng đời LLM

Code Doctor, auto-tag và phân tích năng lực dùng bản nguồn đã làm sạch; mã gốc trong DB và giao diện không bị sửa. C/C++ dùng Tree-sitter, Python 3 dùng AST/tokenize, Python 2/Pascal dùng Pygments. Java/C#/Rust/Text, nguồn quá 1 MiB hoặc cú pháp không chắc chắn được giữ nguyên. Prompt có ánh xạ dòng gốc; nếu vượt ngân sách, chọn đơn vị cú pháp nguyên vẹn và báo thiếu ngữ cảnh. Chưa có tokenizer chính xác hoặc chọn hàm theo call graph cho model GGUF tùy biến.

Thinking giữ mặc định của model. Với cấu hình Ollama/OpenAI-compatible, mỗi request sở hữu kết nối HTTP bất đồng bộ; khi coroutine hết deadline hoặc bị hủy, socket được đóng để Ollama ngừng xử lý. Deadline bao gồm retry kiểm tra JSON. Đóng modal/ngừng polling không hủy job nền. Chẩn đoán thành công được cache 7 ngày; lời khuyên dự phòng chỉ cache 5 phút và không giữ trong cache RAM. Reasoning chưa có final answer hoặc câu trả lời bị cắt do hết token không được coi là chẩn đoán hoàn tất.

Kiểm thử backend trong stack Docker đang chạy:

```powershell
docker cp backend/tests/. tmath-backend:/tmp/tmath-tests
docker exec tmath-backend env PYTHONPATH=/app python -m unittest discover -s /tmp/tmath-tests -v
docker exec tmath-backend env PYTHONPATH=/app python /scripts/test_auto_tagging.py
```

`scripts/verify_llm_cancellation.py` kiểm tra hủy/timeout và phản hồi sau đó trên Ollama thật, không ghi dữ liệu ứng dụng. `scripts/benchmark_llm_latency.py` đo CPU, thinking và cache prompt; đây là probe chẩn đoán, không phải cấu hình production. Dependencies mới cần được cài qua rebuild backend khi triển khai sang máy khác.

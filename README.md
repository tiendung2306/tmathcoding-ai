# tmath AI Diagnostic & Admin Dashboard Service

Hệ thống Microservice AI Phân Tích Học Lực, Trợ Lý AI Code Doctor, Auto-Tagging & Màn Hình Admin Dashboard cho Nền tảng tmath Online Judge (DMOJ).

---

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
  docker compose up -d --build
  ```

* **Chạy NVIDIA CUDA GPU Acceleration:**
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
  ```

* **Chạy AMD ROCm GPU Acceleration:**
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.rocm.yml up -d --build
  ```

---

### Bước 2: Nạp Model AI Trong `.env` Vào Container Ollama (Chạy 1 lần đầu)

```bash
docker exec -it tmath-backend python /scripts/pull_model.py
```

---

### Bước 3: Seed 10.1 GB Dữ Liệu Backup Vào MySQL (Chạy 1 lần đầu)

```bash
docker exec -it tmath-backend python /scripts/seed_mysql.py
```

---

### 🧪 Bước 4: Kiểm Tra & Trải Nghiệm AI

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

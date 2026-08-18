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
├── SOFTWARE_DESIGN_DOCUMENT.md   # Tài liệu Thiết kế SDD v3.1.0 chuẩn hóa
├── backup/                       # Thư mục chứa 202 file SQL backup (10.1 GB)
├── scripts/
│   ├── pull_model.py             # Script nạp Model AI từ .env vào Docker Persistent Volume
│   ├── seed_mysql.py             # Script tự động import 10.1 GB backup vào MySQL DB
│   └── test_llm.py               # Script Chat CLI Interactive thử nghiệm kết nối LLM Engine
├── backend/                      # Service FastAPI Backend AI API
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py         # Nạp biến môi trường động & LLM Hyperparameters từ .env
│   │   │   └── llm_adapter.py    # LLM Adapter chuẩn (Instructor + LiteLLM Async, MD_JSON mode)
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
* **Health Check Endpoint:** `http://localhost:8000/api/v1/health`

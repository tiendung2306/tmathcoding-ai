# tmath AI Diagnostic & Admin Dashboard Service

Hệ thống Microservice AI Phân Tích Học Lực, Trợ Lý AI Code Doctor, Auto-Tagging & Màn Hình Admin Dashboard cho Nền tảng tmath Online Judge (DMOJ).

---

## 🏗️ CẤU TRÚC DỰ ÁN (PROJECT STRUCTURE)

```text
tmathcoding/
├── .gitignore                    # Quản lý bỏ qua Git cho Python, React, IDE, Log
├── SOFTWARE_DESIGN_DOCUMENT.md   # Tài liệu Thiết kế Phần mềm SDD v3.1.0 chuẩn hóa
├── docker-compose.yml            # Container Orchestration (MySQL 8.0, Redis, FastAPI, React)
├── backup/                       # Thư mục chứa 202 file SQL backup (10.1 GB)
├── scripts/
│   └── seed_mysql.py             # Script tự động import 10.1 GB backup vào MySQL DB
├── backend/                      # Service FastAPI Backend AI API
│   ├── app/
│   │   ├── api/v1/               # Endpoints RESTful (Student, Teacher, Admin)
│   │   ├── core/                 # Config, Async MySQL Database, LLM Adapter (Instructor/LiteLLM)
│   │   ├── models/               # SQLAlchemy ORM Models (flawless DMOJ Schema mapping)
│   │   ├── schemas/              # Pydantic v2 Models & Structured Outputs
│   │   ├── services/             # Core Logic (Skill Tree, AI Code Doctor, Class Heatmap)
│   │   └── main.py               # FastAPI Entrypoint
│   ├── requirements.txt          # Dependencies Python
│   └── Dockerfile
└── frontend/                     # React 18 + TypeScript + Vite Dashboard App
    ├── src/
    │   ├── components/           # SkillTree, BloomRadar, ClassHeatmap, CodeDoctorModal, Navbar
    │   ├── pages/                # StudentDashboard, TeacherDashboard
    │   ├── services/             # Axios API Client
    │   ├── types/                # TypeScript Interfaces
    │   ├── App.tsx
    │   └── main.tsx
    ├── package.json
    ├── tailwind.config.js
    └── Dockerfile
```

---

## 🚀 HƯỚNG DẪN KHỞI CHẠY (QUICK START)

### 1. Khởi chạy bằng Docker Compose (Khuyên dùng)

```bash
# 1. Khởi tạo toàn bộ container (MySQL 8.0, Redis, FastAPI Backend, React Frontend)
docker-compose up -d --build

# 2. Tự động Seed 10.1 GB dữ liệu backup vào MySQL Database
python scripts/seed_mysql.py
```

- **Frontend Dashboard:** `http://localhost:5173`
- **FastAPI OpenAPI Swagger Docs:** `http://localhost:8000/docs`
- **Health Check Endpoint:** `http://localhost:8000/api/v1/health`

### 2. Khởi chạy Thủ công (Local Dev)

#### Backend:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Hoặc .venv\Scripts\activate trên Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## 🛡️ TÍNH NĂNG NỔI BẬT

1. **Học sinh:** 
   - **Cây Kỹ Năng 99 Node & Bloom Radar (A-F):** Trực quan hóa điểm thuần thục năng lực.
   - **AI Code Doctor (Socratic Debugger):** Chẩn đoán lỗi sai bằng phương pháp gợi mở qua **Instructor Framework** (không cho sẵn đáp án).
   - **Chế độ Tự Học (Independent Mode):** Phục vụ 72.5% học sinh tự do không thuộc lớp nào.
2. **Giáo viên & Admin:**
   - **Xem thông số Lớp (Class Heatmap 2D):** Ma trận năng lực 2D kèm cờ cảnh báo 🚨 `STUCK`, ⚠️ `GAP`, 💤 `INACTIVE`.
   - **Search Học sinh & Super Admin Access:** Super Admin xem và search toàn bộ 252 lớp và 21,416 học sinh.
3. **Backend Engine:**
   - **Pipeline Auto-Tagging:** Đọc Đề bài + Code AC mẫu + Constraints để tự động gán tag chính xác 99% cho 11,971 bài chưa có tag.

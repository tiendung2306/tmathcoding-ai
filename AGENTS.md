# Agent Instructions

## Database architecture

Đọc [backend/DB_ARCHITECTURE.md](backend/DB_ARCHITECTURE.md) trước khi sửa model,
kết nối DB, truy vấn qua hai DB hoặc migration.

Dashboard kết nối DB gốc tmathcoding bằng `SOURCE_DB_*` với quyền chỉ đọc và quản
lý schema riêng `tmath_dashboard` bằng `DASHBOARD_DB_*`. Hai kết nối có host,
port và tài khoản độc lập. Config/star, phiên học và kết quả AI thuộc dashboard.

- Lưu cấu hình mới của dashboard vào `tmath_dashboard`, không thêm các bảng cấu
  hình này vào database gốc.
- Sử dụng `DashboardBase`, `get_dashboard_db` và `DashboardSessionLocal` trong
  `backend/app/core/dashboard_database.py`; đăng ký model trong `app/models/dashboard.py`.
- DDL chỉ chạy bằng Alembic với tài khoản migration riêng. Revision dùng
  `YYYYMMDD_NNNN`, có `down_revision`, `upgrade()`/`downgrade()`, và giữ một head.
  Revision đã triển khai không được sửa. Không gọi `create_all()` hay tạo DB ở startup.
- Không join SQL xuyên DB/server. Ghép dữ liệu bằng ID qua hai kết nối độc lập.
- Các tham chiếu đến profile/lớp của database gốc là ID logic, không tạo khóa
  ngoại xuyên database. Kiểm tra quyền trên dữ liệu gốc trước khi lưu tùy chọn.

## UI / UX

For any task involving frontend, UI, UX, styling, visual design,
components, pages, layout, typography, animation, or product copy:

1. Read `DESIGN.md` before making UI decisions.
2. Read `ANTISLOP.md` before making UI changes.
3. Read the relevant installed antislop skills.
4. Preserve existing business logic and functionality.
5. Do not redesign the product merely for novelty.

When auditing an existing UI, use ANTISLOP in AFTER mode.

Before finishing:
- perform a repository-wide anti-slop audit;
- fix all approved violations;
- verify that no unnecessary AI-generated copy or UI patterns remain.

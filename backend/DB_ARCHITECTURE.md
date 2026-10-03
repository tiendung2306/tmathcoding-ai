# Hai database và migration của dashboard

Dashboard là service độc lập. Database gốc thuộc tmathcoding; dashboard chỉ đọc
dữ liệu từ đó. Dashboard sở hữu schema và DDL của `tmath_dashboard`.

## Kết nối và quyền

| Database | Biến môi trường | Quyền của ứng dụng | Dữ liệu |
| --- | --- | --- | --- |
| Gốc tmathcoding | `SOURCE_DB_HOST`, `SOURCE_DB_PORT`, `SOURCE_DB_USER`, `SOURCE_DB_PASSWORD`, `SOURCE_DB_NAME` | `SELECT` | Profile, lớp, năm học, bài toán, bài nộp, danh mục tag |
| Dashboard | `DASHBOARD_DB_HOST`, `DASHBOARD_DB_PORT`, `DASHBOARD_DB_USER`, `DASHBOARD_DB_PASSWORD`, `DASHBOARD_DB_NAME` | `SELECT`, `INSERT`, `UPDATE`, `DELETE` | Star, phiên học, kết quả AI và các cấu hình mới của dashboard |
| Migration dashboard | Cùng host/port/database dashboard, tài khoản `DASHBOARD_MIGRATION_USER` và `DASHBOARD_MIGRATION_PASSWORD` | DDL/DML chỉ trên `tmath_dashboard` | Thay đổi schema và cập nhật `alembic_version` |

Hai kết nối có host, port, tài khoản và mật khẩu độc lập. Không suy ra cấu hình
dashboard từ DB gốc. Hai server có thể cùng dùng port nội bộ `3306`.
Trong Docker local, DB gốc là fixture ở `db:3306`, mở ra host `3306`;
dashboard ở `dashboard-db:3306`, mở ra host `3307`, có volume `dashboard_mysql`
riêng. DB gốc local chỉ chạy khi bật profile `local-source`.
Trong môi trường tích hợp, đặt `SOURCE_DB_HOST`/`SOURCE_DB_PORT` tới DB bên ngoài
và dùng tài khoản chỉ đọc do bên sở hữu DB cấp. Không cần bật `local-source`.
Import backup vào fixture local dùng tác vụ operator `source-seed`, không dùng
tài khoản backend: `docker compose --profile local-source run --rm source-seed`.
Profile `source-seed` không chạy theo `up` thông thường và không dùng cho DB ngoài.

Runtime backend được che các biến mật khẩu root và tài khoản migration trong
Docker Compose. Không đưa tài khoản migration vào backend ở môi trường triển khai.
Script `docker/mysql/init-users.sh` khởi tạo tài khoản cho volume MySQL mới;
đổi mật khẩu trên volume đã tồn tại cần thao tác quản trị riêng, không chỉ sửa `.env`.

`MYSQL_*` và `CONFIG_MYSQL_DB` vẫn được đọc như alias tương thích cho cấu hình cũ.
Code và cấu hình mới phải dùng `SOURCE_DB_*` và `DASHBOARD_DB_*`.

## Convention cho code mới

- Dùng `Database` trong `app/core/db_resources.py` để tạo engine/session pool.
- Model đọc dữ liệu gốc dùng `Base` trong `app/core/database.py`; API dùng `get_db`.
  Không tạo migration hay gọi `create_all()` cho metadata này.
- Model do dashboard sở hữu dùng `DashboardBase` trong
  `app/core/dashboard_database.py`; API dùng `get_dashboard_db`, worker dùng
  `DashboardSessionLocal`. Đăng ký model mới trong `app/models/dashboard.py`.
- Không tạo foreign key xuyên hai DB, không viết SQL join/subquery giữa hai
  server. Lưu ID logic, kiểm tra ID/quyền bằng kết nối gốc, rồi ghi dữ liệu vào
  dashboard. Lấy metadata theo nhóm ID để tránh một truy vấn cho từng bản ghi.
- Phiên học (`tmath_virtual_class_session`) và kết quả AI (`judge_problem_ai_tag`)
  thuộc dashboard. Đừng chuyển các model này trở lại metadata DB gốc.
- Constraint/index dùng naming convention của `DashboardBase`: `pk_<table>`,
  `uq_<table>_<column>`, `ix_<table>_<column>`. Tên đặc biệt phải ghi rõ trong model
  và revision. Timestamp được lưu theo UTC.
- Cấu hình/star có metadata riêng không đồng nghĩa với việc tạo DB lúc startup.
  Backend chỉ kiểm tra phiên bản schema, không thực thi DDL.

## Migration có phiên bản

Dùng Alembic, cấu hình tại `backend/alembic.ini`, revision trong
`backend/migrations/versions/`. Chỉ metadata của dashboard được đưa vào Alembic.
Baseline là `20261003_0001`, tạo ba bảng dashboard và bảng `alembic_version`.
Baseline cũng hỗ trợ bảng `class_star` cũ đã có sẵn nếu schema khớp; khác schema
thì dừng để kiểm tra, không tự sửa hoặc đánh dấu đã migrate.

Convention:

1. Revision ID dùng `YYYYMMDD_NNNN`, ví dụ `20261004_0001`; số thứ tự tăng trong
   cùng ngày. Tên file là `<revision>_<mo_ta_snake_case>.py`.
2. Mỗi revision có `revision`, `down_revision`, `upgrade()` và `downgrade()`.
   `down_revision` trỏ tới head trước đó; giữ một head cho chuỗi migration.
3. Revision đã triển khai là bất biến. Thay đổi tiếp theo phải có revision mới.
   Không import model hiện tại vào revision; ghi snapshot kiểu cột/constraint/index.
4. Autogenerate là bản nháp phải review: rename, backfill, nullability, default,
   index và nguy cơ mất dữ liệu cần được kiểm tra thủ công.
5. Dùng tài khoản migration và CLI có khóa MySQL; không chạy migration ở mỗi
   worker/startup. CLI dùng `GET_LOCK` để tránh hai tiến trình đổi schema cùng lúc.
6. MySQL DDL không có rollback giao dịch đầy đủ. Backup trước thay đổi phá hủy;
   ưu tiên thêm cột, backfill, chuyển code rồi mới xóa cột ở revision sau.
7. Downgrade chỉ chạy trên bản sao khi kiểm thử, hoặc sau khi đã xác nhận kế hoạch
   khôi phục. Downgrade baseline sẽ xóa toàn bộ bảng dashboard.
8. Không dùng `stamp head` để bỏ qua schema khác biệt. Startup từ chối schema chưa
   ở đúng head; triển khai phải chạy upgrade trước khi phục vụ request.

Các lệnh chạy từ thư mục gốc dự án, sử dụng môi trường migration:

```sh
docker compose run --rm dashboard-migrate python -m app.db.migrate heads
docker compose run --rm dashboard-migrate python -m app.db.migrate current
docker compose run --rm dashboard-migrate python -m app.db.migrate upgrade head
docker compose run --rm dashboard-migrate python -m app.db.migrate check
docker compose run --rm dashboard-migrate python -m app.db.migrate deploy
docker compose run --rm dashboard-migrate python -m app.db.migrate revision --autogenerate --rev-id 20261004_0001 -m "add_dashboard_preferences"
```

`revision` ghi ra folder migration đã bind mount về repository. Sau khi review,
thử upgrade trên DB trống và trên bản sao DB hiện có; chạy `check` để đối chiếu
schema với model, kiểm tra head và kiểm thử tính năng bị ảnh hưởng. Không downgrade
DB đang phục vụ chỉ để thử revision. Chạy `python -m app.db.migrate ...` trực tiếp
từ folder `backend` nếu không dùng Docker, với các biến môi trường tương ứng.

Khởi chạy local có fixture DB gốc:

```sh
docker compose --profile local-source up -d --build
```

`deploy` chạy `upgrade head` và `check` trong cùng khóa migration. Vì vậy model
đã đổi nhưng chưa có revision tương ứng cũng làm deployment dừng.

Compose đợi MySQL dashboard sẵn sàng, chạy `dashboard-migrate` một lần, rồi mới
khởi động backend. Production nên dùng migration như một deployment job riêng.

## Chuyển dữ liệu từ kiến trúc cũ

1. Backup, dừng backend/worker cũ để dữ liệu không thay đổi trong lúc sao chép.
2. Khởi tạo server/database dashboard và tài khoản, chạy `upgrade head`.
3. Chạy preview rồi copy với công cụ `app.db.import_legacy`:

```sh
docker compose run --rm dashboard-migrate python -m app.db.import_legacy --legacy-config-db tmath_dashboard
docker compose run --rm dashboard-migrate python -m app.db.import_legacy --legacy-config-db tmath_dashboard --apply
```

Nếu bảng star cũ trên source server nằm ngoài `SOURCE_DB_NAME`, dùng tài khoản
operator có quyền đọc schema đó cho tác vụ import; không mở rộng quyền của tài
khoản runtime. Không truyền mật khẩu trực tiếp trong command line.

Công cụ giữ nguyên ID, timestamp và dữ liệu JSON, kiểm tra từng batch sau khi
copy, cho phép chạy lại với bản ghi giống hệt, và dừng nếu có ID trùng nhưng dữ
liệu khác. Hàm `copy_table` trong `app/db/data_transfer.py` có thể tái sử dụng
cho các tác vụ chuyển dữ liệu khác. Công cụ không tự xóa hay sửa bảng nguồn.

4. Chạy lại import để kiểm tra tính lặp lại, chạy `check`, xác nhận chức năng đọc
   lớp, star, start/stop phiên và auto-tag; sau đó bật backend mới.
5. Bảng legacy trong DB gốc có thể giữ để rollback nhưng backend mới không dùng
   nữa. Việc xóa chúng thuộc kế hoạch cleanup của bên quản lý DB gốc, sau backup
   và xác nhận cutover. Database config cũ do dashboard tạo có thể gỡ sau khi đã
   copy và đối chiếu, không xóa database gốc.

Tham khảo: [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html),
[autogenerate và check](https://alembic.sqlalchemy.org/en/latest/autogenerate.html).

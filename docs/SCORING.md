# Cách tính điểm thành tích và hướng dẫn manual test

## Quy tắc

Điểm thành tích được tính trong dashboard, không sửa điểm ở hệ thống tmath gốc.

- Mỗi học sinh–bài chỉ có một kết quả. Có ít nhất một AC hợp lệ là 1; đã nộp kết quả hoàn tất nhưng chưa AC là 0. Chưa làm thì không đưa vào mô hình.
- Không giới hạn 7 ngày. Một bài WA rồi AC sau nhiều tháng vẫn chuyển từ 0 sang 1 ở snapshot tiếp theo.
- Nộp 100 lần WA vẫn chỉ là một quan sát 0. AC rồi WA vẫn là 1 nếu còn một AC hợp lệ. Chấm lại mất AC cuối cùng thì trở về 0.
- Bài nào cũng có điểm. Bài chưa có bậc nguồn nhận mặc định 100 điểm; bậc vẫn để trống, không giả thành A. Không có trạng thái chờ admin chấm điểm.
- QU/P/G, lỗi nội bộ IE và kết quả chưa xác định không được coi là thất bại. Verdict hoàn tất được mock nhận: AC, WA, TLE, MLE, RTE, OLE, IR, CE, AB, SC. CE là một lần thử hoàn tất.
- Mỗi bài AC chỉ cộng điểm một lần. Không trừ điểm vì số lần WA/TLE.
- Cùng một bảng điểm, cùng một bài luôn có cùng điểm cho mọi học sinh, bất kể ngày AC. Không có mùa hay học kỳ.

## Điểm của từng bài

Mặc định để manual test:

| Bậc | Khoảng điểm | Điểm khởi tạo |
| --- | ---: | ---: |
| A | 100–450 | 300 |
| B | 500–850 | 700 |
| C | 900–1.250 | 1.100 |
| D | 1.300–1.650 | 1.500 |
| E | 1.700–2.050 | 1.900 |
| F | 2.100–2.450 | 2.300 |

Khoảng điểm cố định trong `backend/app/scoring/policy.py`. Quản trị viên không có giao diện hoặc API để đổi khoảng, ngưỡng dữ liệu hay gán bậc. Thay quy tắc điểm là thay đổi code có kiểm thử và triển khai lại.

Bậc nguồn dùng ID 4/5/6/7/8/13 tương ứng A/B/C/D/E/F. Dashboard lấy trực tiếp `group_id` từ Source API, không có override. Bài thiếu bậc dùng 100 điểm mặc định cố định trong code. Khi nguồn bổ sung bậc, lần cập nhật sau dùng khoảng và điểm của bậc nguồn tương ứng; không cần admin thao tác trên dashboard.

Bayesian Rasch ước lượng đồng thời năng lực học sinh R và độ khó bài D:

`P(AC) = 1 / (1 + 10^((D - R) / 400))`

Năng lực có prior Normal(1300, 500²); độ khó có prior Normal(điểm khởi tạo của bậc, 200²), giới hạn ngay trong bộ tối ưu theo khoảng bậc. Đây là thang nội bộ tmath, không quy đổi ngang Codeforces.

Worker dùng MAP, NumPy/SciPy L-BFGS-B và gradient giải tích. Cặp quan sát chỉ xuất hiện một lần; ô chưa làm không biến thành 0. Bài được giải bởi học sinh có năng lực khác nhau có mức bằng chứng khác nhau, nên không chỉ dựa vào số AC thô.

Điểm đề xuất là độ khó ước lượng làm tròn tới 50 gần nhất, nửa bước làm tròn lên, vẫn nằm trong khoảng bậc. Có ít nhất 30 người thử và ít nhất 5 người ở mỗi nhóm AC/chưa AC mới dùng điểm từ mô hình. Ngưỡng này cố định trong code, là quy tắc ổn định cho V1, không phải chứng nhận thống kê.

- Đủ dữ liệu: “Theo dữ liệu”.
- Thiếu dữ liệu: giữ điểm công bố cũ cùng bậc nếu hợp lệ; nếu chưa có thì dùng “Điểm khởi tạo”.
- Chưa có A–F: 100 điểm mặc định. Không tự gán A hoặc coi là 0 điểm.

Tổng điểm học sinh là tổng các giá trị điểm của tất cả bài AC riêng biệt trong snapshot, bao gồm bài dùng điểm mặc định. Không hiển thị “bài chờ điểm” hoặc yêu cầu admin xác nhận bảng thiếu điểm. Backend không cho công bố bảng còn giá trị điểm NULL.

## Dữ liệu và tính nhất quán của V1

V1 dùng full snapshot, chưa dùng feed thay đổi tăng dần. Source API mock gom bài nộp bằng SQL, xuất các trang file 1.000 dòng và checksum. Snapshot MySQL dùng REPEATABLE READ; các trang đã xuất không đổi khi nguồn có AC/rejudge mới. Snapshot mock hết hạn sau một giờ và không dùng lại được sau khi provider restart.

Worker chạy riêng với job/lease trong dashboard DB. Một lần chỉ chạy một tác vụ điểm. Snapshot hỏng, thiếu trang, trùng khóa, checksum sai hoặc mô hình không hội tụ thì lượt tính thất bại, bảng đang dùng được giữ nguyên. Có thể tạo lượt mới để chạy lại. V1 không resume một snapshot hết hạn; dữ liệu staging của lượt lỗi không được công bố.

Tổng được tính sẵn và đối chiếu độc lập trong DB trước khi sẵn sàng. Công bố đổi một active pointer trong giao dịch, nên không có trường hợp ghép tổng cũ với điểm bài mới. AC mới hơn snapshot được đưa vào lần tác vụ `refresh` tiếp theo. V1 chưa tự đặt lịch cập nhật; việc bỏ màn quản trị không tự biến worker thành bộ đồng bộ thời gian thực.

V1 chỉ mở ở khu vực admin có quyền super admin nguồn, vì snapshot bao gồm toàn kho, kể cả bài riêng tư và profile chưa thuộc lớp. Không dùng endpoint này cho giáo viên có quyền hẹp.

`submission.points`, `problem.points`, `profile.points` và performance points nguồn giữ nguyên. Điểm chấm test 100/100 khác điểm thành tích. Sau công bố, danh sách học sinh chính xếp theo tổng thành tích mới; thứ hạng được tính trước phân trang/tìm kiếm, đồng điểm cùng hạng. Hồ sơ có bảng các bài đóng góp điểm. Các điểm nguồn còn lại phải được hiểu theo nguồn, không phải rating mới.

## Khởi chạy

Từ thư mục gốc, dùng cấu hình `.env` hiện có:

```powershell
docker compose --profile local-source up -d --build backend source-api-mock scoring-worker frontend
```

Compose chạy migration dashboard trước backend/worker. Revision thêm bảng điểm là `20261027_0001`, nối sau `20261011_0002`. Không chạy downgrade trên dữ liệu đang dùng để thử.

Nếu cần chạy migration riêng:

```powershell
docker compose run --rm dashboard-migrate python -m app.db.migrate deploy
```

Provider ngoài cần hỗ trợ `POST /integration/v1/scoring/snapshots` và GET các trang snapshot như mock. Nếu chưa hỗ trợ, worker báo lỗi rõ ràng; dashboard không chuyển sang đọc SQL nguồn.

## Manual test cần thiết

1. Đăng nhập và mở `http://localhost:5173/student/students`. Không còn mục menu hoặc màn quản trị điểm; địa chỉ cũ `/admin/scoring` chuyển về danh sách học sinh.
2. Mở một học sinh, xem điểm thành tích và các bài đóng góp. Tổng phải bằng tất cả bài AC riêng biệt, không có nhãn chờ điểm.
3. Bậc bài phải khớp Source API; không có control thay bậc hoặc khoảng điểm. Bài nguồn chưa phân bậc được 100 điểm nhưng không tự được gán A.
4. Khi kỹ thuật viên chạy `refresh` sau AC mới, tổng được cập nhật theo snapshot mới; nộp lại AC cùng bài không được tăng tổng.

## Lệnh bảo trì dành cho triển khai

Không có màn quản trị riêng. Kỹ thuật viên tạo tác vụ và xem trạng thái bằng các lệnh sau, worker sẽ xử lý ở nền:

```powershell
docker compose exec -T backend python -m app.scoring.maintenance calibrate
docker compose exec -T backend python -m app.scoring.maintenance status
```

Khi lượt tính READY, công bố bằng ID trả về từ `status`:

```powershell
docker compose exec -T backend python -m app.scoring.maintenance publish --run-id ID_CUA_LUOT_TINH
```

Cập nhật AC mà giữ điểm bài đã công bố:

```powershell
docker compose exec -T backend python -m app.scoring.maintenance refresh
```

Khi nâng từ bản cũ có bài NULL điểm, lệnh sau dựng tổng mới từ snapshot AC sẵn có và công bố đồng loạt; không tải lại toàn bộ Source API hay sửa bảng lịch sử đã công bố:

```powershell
docker compose exec -T backend python -m app.scoring.maintenance reprice
```

Nếu nguồn đổi bậc, refresh dùng bậc nguồn mới và điểm khởi tạo tương ứng khi không giữ được điểm cũ hợp lệ. Hiệu chỉnh tiếp bằng `calibrate` khi cần đánh giá lại độ khó. Không khôi phục bậc dashboard cũ đè lên bậc nguồn.

Không cần thử spam vào DB nguồn để kiểm tra cơ chế này; dùng fixture/tests để kiểm tra lặp, pending và rejudge. Không sửa trực tiếp bảng điểm nguồn.

Kiểm tra tiến trình nếu job chưa chạy:

```powershell
docker compose logs --tail 60 scoring-worker
docker compose ps
```

## Giới hạn cần biết

- Có trần bậc và khử trùng không đồng nghĩa chống được nhiều tài khoản cố tình nộp sai. Quản trị vẫn cần kiểm tra đề xuất đáng ngờ.
- Đây là ước lượng mức hoàn thành luyện tập theo lịch sử, chịu ảnh hưởng việc tự chọn bài, học thêm, xem lời giải và thời gian sử dụng. MAP không cung cấp khoảng tin cậy posterior đầy đủ.
- Mức 100 cho bài chưa có bậc là quy ước mặc định, chưa phản ánh độ khó thực nghiệm của bài đó. Admin vẫn xem tổng đầy đủ; nếu cần phân loại chính xác hơn thì dữ liệu bậc được bổ sung ở nguồn.
- Chạy full snapshot là lựa chọn V1 để manual test với provider local. Tối ưu incremental, retention dataset tự động và kiểm định mô hình nâng cao nằm trong kế hoạch mở rộng; không gọi V1 là đã hoàn thành mọi hạng mục production trong `SCORING_IMPLEMENTATION_PLAN.md`.

## Kiểm chứng local ngày 28/10/2026

- Đã pull `main`, remote báo đã cập nhật đầy đủ; migration deploy/check đạt.
- 30 kiểm thử liên quan scoring, migration, danh sách/lớp và một contract test snapshot đạt. Frontend production build đạt.
- Run local `34e9725a862441cea01b197e6f61aaf2`: 4.541 bài, 20.326 profile, 1.327.765 cặp. Có 2.411 bài dùng điểm mô hình, 317 bài chưa phân bậc. Đã công bố bản thử có xác nhận thiếu điểm.
- Đối soát SQL theo từng profile: 0 tổng sai; kiểm tra toàn bảng: 0 bài sai khoảng/bước điểm.
- Lượt kiểm chứng ban đầu có màn quản trị; màn đó đã được gỡ theo yêu cầu sau đó. Giao diện hiện chỉ giữ điểm trong danh sách/hồ sơ học sinh.
- Lượt chạy bộ test rộng trước đó còn test cũ chưa khớp hợp đồng hiện tại: `frontend/tests/navigation.test.mjs` (range mặc định 7d), `frontend/tests/query.test.mjs` (mock navigation), `source_api_mock/tests/test_api.py` (visibility contest), `backend/tests/test_gateway_analytics_services.py` (EmptyClassGateway thiếu aggregate_students). Không thay hành vi navigation/contest để làm các test ngoài phạm vi này đạt. Chỉ báo các kiểm thử liên quan ở trên là đã đạt, không tuyên bố toàn bộ test repository đạt.

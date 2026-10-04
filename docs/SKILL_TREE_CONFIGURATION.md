# Cây kỹ năng cố định

Dashboard dùng 10 nhóm chuyên môn và Khác, theo bảng 99 tag trong [báo cáo phân loại](SKILL_TAG_TAXONOMY_2026-10-04.md). Thứ tự, tên và phạm vi gốc được cố định ở backend. Quản trị chỉ gắn tag, không tạo/sửa/xóa gốc. Việc phân nhóm không suy ra rằng mọi bài của một tag chỉ dùng kỹ thuật đó.

## Luồng học sinh

Ban đầu tất cả gốc thu gọn. Mỗi gốc hiển thị số dạng có bài, số bài trong kho và số bài AC riêng biệt. Chọn một gốc mở vùng tag toàn chiều rộng; không tự mở tag. Mỗi lần mở một tag để xem toàn kho bài, gồm cả bài chưa làm.

Danh sách bài tìm theo tên/mã và lọc Tất cả/Có AC/Đã thử chưa AC/Chưa làm trước khi phân trang, 20 bài/trang. Bấm bài mở modal đề Markdown, công thức toán và lịch sử nộp 10 lượt/trang. Bấm lượt nộp mở trình xem mã/test/Code Doctor hiện có. Đóng modal giữ nguyên gốc, tag, bộ lọc và trang; focus về bài vừa mở.

Số AC đếm bài riêng biệt có ít nhất một AC trong khoảng chọn, kể cả nộp WA sau đó. Bài đã thử bao gồm bài AC. Kho bài vẫn đầy đủ khi đổi khoảng thời gian; trạng thái/counts/lịch sử chỉ xét lượt nộp trong khoảng. Mốc tham chiếu dùng bài nộp mới nhất trong nguồn, giống thống kê dashboard hiện có.

Một bài thuộc nhiều tag trong cùng gốc chỉ tính một lần ở gốc. Bài thuộc nhiều gốc có thể đóng góp từng gốc; tổng học sinh không cộng các gốc. Không dùng điểm 0–100, mục tiêu AC hoặc ngưỡng thành thạo. Phần phân tích tag thu gọn vẫn giữ số bài và phân bố verdict theo lượt nộp, bỏ nhãn suy luận Điểm mạnh/Cần luyện trong dashboard mới.

Nhóm không có bài bị ẩn trên dashboard; nhóm có bài nhưng học sinh chưa nộp vẫn hiện. Tag mới chưa gắn được gom vào Khác. Tag rỗng vẫn có trong danh mục quản trị, nhưng không xuất hiện như nhánh bài trống.

## Luồng quản trị

`/admin/skills` hiển thị 10 gốc và Khác với phạm vi cố định. Chọn nhóm trong từng tag hoặc kéo thả để lưu và áp dụng ngay. Mỗi tag thuộc một gốc. Gỡ về Chưa phân loại vẫn hiện dưới Khác trên dashboard.

AI xử lý các tag chưa gắn theo từng lượt nhỏ, lưu đề xuất vào DB trước khi trả về. Modal hiển thị tiến độ và danh sách chờ; có tick chọn, duyệt/từ chối từng hàng, đã chọn hoặc tất cả. Cột cuối Hành động có submenu Chọn nhóm hỗ trợ hover/click/bàn phím. Chọn nhóm thủ công chốt ngay; AI cần duyệt. Chỉ ẩn hàng sau khi DB commit. Hàng từ chối được ẩn nhưng quyết định còn lưu để phản hồi AI muộn không hồi sinh hàng cùng scope.

## DB và chuyển đổi

Cấu hình/proposals nằm trong `tmath_dashboard`; nguồn chỉ đọc. Không join SQL xuyên DB. Revision tránh ghi đè từ trang cũ hoặc người khác, trả 409 để tải lại.

Migration `20261004_0003` thêm `taxonomy_version` và `taxonomy_backup`, nối sau `20261004_0002`. Snapshot giữ draft/published/proposals/revision cũ trước khi áp dụng bảng mới. Đây là bản sao phục vụ vận hành, không đưa lịch sử phiên bản hoặc nút khôi phục trở lại UI. Migration không sửa bài/tag/submission nguồn.

Gán trước đó ở gốc nhận biết được giữ, gồm tag ở nhóm con (làm phẳng về gốc). Gốc custom có tag nhưng chưa có ánh xạ rõ làm migration dừng trước DDL. Downgrade được kiểm thử trên bản sao độc lập, không chạy trên DB người dùng.

Local ngày 04/10/2026: trước chuyển revision3, bốn gốc Khác/DP/Đồ thị/Số học, assignments rỗng. Sau chuyển revision4: 11 gốc, 99 tag gắn, 95 ở nhóm chuyên môn và 4 ở Khác. Snapshot revision3 và 15 từ chối theo scope cũ giữ nguyên. Mapping mới là bảng đã thống nhất, không phải duyệt lại đề xuất AI cũ.

## Kiểm chứng

104 kiểm thử backend, 19 frontend và build production đạt. Có ca phân trang toàn kho, lọc trước phân trang, AC rồi WA, phân biệt học sinh, khoảng thời gian, tag trùng bài, khóa gốc, snapshot và downgrade/upgrade độc lập.

Browser kiểm tra gốc/tag, bộ lọc AC, đề có công thức, lịch sử và đóng modal giữ lọc. Đã xem bố cục desktop 1280px và tổng quan trong khung 390px; khung hẹp dùng iframe để kiểm tra reflow, không thay cho kiểm thử trên thiết bị thật. Các thao tác browser trong lượt này không ghi cấu hình người dùng.

Probe đọc lại DB/API: `scripts/verify_fixed_skill_tree.py` chạy trong backend local với `PYTHONPATH=/app`. Probe ngày này xác nhận baseline và số AC/kho của tag4 ở user20586, không ghi dữ liệu. Triển khai theo [DB_ARCHITECTURE.md](../backend/DB_ARCHITECTURE.md).

Tài khoản quản trị standalone dùng `DASHBOARD_ADMIN_PROFILE_ID` để kiểm tra super_admin; frontend không yêu cầu chọn ID. Khi tích hợp hệ thống đăng nhập, thay fallback bằng danh tính từ phiên/JWT.
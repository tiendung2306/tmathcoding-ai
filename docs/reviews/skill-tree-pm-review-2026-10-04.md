# Review PM: bỏ mục tiêu và điểm 0–100

Reviewer: subagent GPT-6.1 Sol, reasoning medium, vai PM. Theo yêu cầu người dùng, chỉ review mô tả thiết kế và luồng do agent chính gửi; không xem browser, không đọc code và không sửa file. Đây là review sản phẩm, không thay thế kiểm thử kỹ thuật.

## Quyết định người dùng

“Hiện số bài AC và minh chứng, chưa chấm điểm 0–100”. Bỏ mục tiêu khỏi tạo/sửa nhóm. Gốc có tên và mô tả; vị trí cha là thao tác tổ chức nhóm.

## Trao đổi và điều chỉnh

1. PM bác bỏ việc chỉ giấu mục tiêu 10 nhưng giữ công thức ngầm. Agent bỏ score/target khỏi chỉ số cây mới; không tự chuyển sang tỷ lệ AC/tổng kho.
2. PM duyệt số AC, số đã thử, số bài trong kho và minh chứng; yêu cầu đếm bài riêng biệt, hợp cả tag trực tiếp và hậu duệ tại cha. Agent giữ loại trùng bài/lượt nộp và phạm vi bài hiện có, thêm kiểm thử 131 bài AC không bị giới hạn 100.
3. PM đề nghị không gọi 1 bài AC là hoàn thành chuyên đề. Agent chỉ hiện N bài AC; 0 AC phân biệt Chưa làm và Đã thử, chưa có AC. Không dùng ngưỡng màu điểm hay phần trăm.
4. PM duyệt danh sách số bài thay radar cho cấu hình mới. Ma trận lớp/hồ sơ dùng số AC và metadata metric=ac_count; tên field scores cũ chỉ giữ tương thích vận chuyển. Trung bình lớp ghi rõ bài AC/học sinh, một chữ số thập phân, gồm học sinh chưa làm và dấu trống cho lớp rỗng.
5. PM phát hiện preview chưa chọn học sinh không nên dùng 0 thay cho chưa có dữ liệu. Agent chỉ hiện cây + số bài trong kho; chọn học sinh mới hiện kết quả/minh chứng, thay ID xóa dữ liệu preview cũ, lỗi ID không biến thành 0.
6. PM yêu cầu giải thích số liệu theo kho và phân loại hiện tại, vì đổi phân loại có thể thay đổi số AC. Agent thêm giải thích trên cây và tài liệu. Minh chứng theo bài đủ phạm vi đã chốt; liên kết từng submission là mở rộng chưa yêu cầu.

PM đã duyệt ba nhóm thay đổi theo mô tả. Agent chính tự kiểm tra browser và kỹ thuật; không gửi browser cho PM. Cấu hình thử trên UI chưa được lưu/áp dụng vào dữ liệu dùng chung.

## Yêu cầu tiếp theo: bỏ xem trước/lịch sử, sửa AI

Người dùng yêu cầu bỏ lịch sử phiên bản và xem trước, đồng thời sửa AI đứng ở 0/99 và báo lỗi. Quyết định này thay thế luồng nháp/xem trước/khôi phục trước đây.

- PM duyệt Lưu và áp dụng nguyên tử, giữ chỉnh sửa khi lưu lỗi và không tự nhận đề xuất AI chưa duyệt. Agent bỏ các phần UI/endpoint liên quan, không tạo snapshot mới; bảng cũ được giữ nguyên.
- Log thực tế cho thấy lô 20 tag hết thời gian và JSON mảng bị từ chối bởi bộ đọc wrapper. Agent dùng lô 3, giảm suy luận dài riêng cho phân loại local, nhận cả mảng/wrapper nhưng giữ kiểm tra đầy đủ ID, số lượng và trùng lặp. Lượt thử thật Set/Map vào Cấu trúc dữ liệu, DP chữ số vào Quy hoạch động đã HTTP 200.
- PM yêu cầu không giả tiến độ, giữ kết quả tốt/checkbox, retry phần còn thiếu và vô hiệu hóa đề xuất cũ khi cây thay đổi. Agent thêm bộ xử lý có kiểm thử; browser quan sát 0 → 3 → 9/99, Dừng giữ 12 đề xuất, chạy tiếp từ 12/99 cùng phạm vi tag.
- PM yêu cầu Dừng phải giải phóng model. Agent phát hiện proxy giữ kết nối và thêm hủy trực tiếp theo ID lượt. Log thực tế xác nhận DELETE 200, request AI 499, model cancel task và all slots are idle. Mỗi lần thử lại dùng ID mới; lỗi hủy được báo trung thực.
- PM phản biện chất lượng khi chỉ có một gốc DS mà model cố gán các dạng ngoài phạm vi vào đó. Agent siết prompt yêu cầu khớp trực tiếp mô tả và chọn Khác nếu không phù hợp; đề xuất vẫn cần admin duyệt. Kiểm tra hình thức hợp lệ không chứng minh nội dung phân loại đúng.

PM duyệt các luồng theo mô tả; agent chính kiểm tra thực tế. 84 test backend, 12 test frontend và build đạt. Ảnh tiến độ: skill-config-ai-progress.png.

Kiểm tra AI thật cuối cùng trả HTTP 200: với chỉ gốc Cấu trúc dữ liệu và Khác, Set/Map vào Cấu trúc dữ liệu, digit DP vào Khác. Cấu hình không bị ghi trong lượt kiểm tra. Log model xác nhận nút Dừng hủy tác vụ và giải phóng lượt chạy. PM duyệt cuối theo mô tả, không còn blocker trong phạm vi yêu cầu; bước quản trị viên duyệt đề xuất vẫn được giữ vì một lượt kiểm tra không bảo đảm mọi phân loại AI đều đúng.

## Yêu cầu chuyển danh sách đề xuất vào modal

- Bấm AI mở modal ngay; từng lô lưu DB dashboard trước khi trả kết quả. Nút Danh sách đề xuất mở lại; đóng modal không dừng AI.
- Bảng có tick cột đầu, tag, nhóm đích, lý do và trạng thái. Duyệt/từ chối đã chọn hoặc tất cả chỉ xử lý hàng chờ hợp lệ hiện có; hàng đã gắn/từ chối vẫn giữ, khóa checkbox. Khi AI chạy, dừng hoặc chờ trước khi duyệt.
- PM phát hiện rủi ro trạng thái đã gắn trước lưu bị sai sau reload. Đã giải quyết: trạng thái chưa lưu suy từ cây đang chỉnh; chỉ commit đã gắn cùng giao dịch áp dụng. Reload bỏ chỉnh sửa trở lại chờ nếu nhóm khớp, hoặc báo cấu hình thay đổi nếu gốc chưa lưu không còn.
- Context dùng ID/tên/mô tả/cha, bỏ thứ tự và assignments. Duyệt một tag không làm các hàng khác mất hiệu lực. Từ chối được lưu, không tự mở lại qua retry, không bị kết quả AI đến muộn ghi đè cùng context.
- Sửa đích ghi rõ Đích do bạn chọn và giữ tên nhóm AI ban đầu cạnh lý do. Lỗi chỉnh/từ chối có Thử lại thao tác; lỗi AI có Thử lại AI.
- Agent chính thử AI thật nhận 3 tag, Dừng, duyệt một hàng, từ chối một hàng, sửa đích còn lại, duyệt tất cả và đóng/mở lại. Sau tải lại, danh sách vẫn còn và hàng từ chối vẫn giữ trạng thái. Không áp dụng cây thử vào dashboard dùng chung.

PM duyệt thiết kế và các bổ sung qua mô tả, không browser/code. 89 test backend, 16 test frontend và build đạt; migration upgrade/check/downgrade/reupgrade đạt, head duy nhất 20261004_0002.

## Yêu cầu chốt nhóm của tag ngay

- Người dùng thay quyết định trước: chọn nhóm/kéo tag lưu và áp dụng ngay; chọn nhóm trong modal là quyết định thủ công và tag rời danh sách. Đề xuất giữ nguyên của AI vẫn cần duyệt. Bỏ Save toàn trang; tạo/sửa nhóm chốt bằng nút của form, đổi thứ tự lưu ngay, xóa nhánh qua xác nhận.
- PM yêu cầu không vô tình áp dụng form đang nhập, không ghi đè người khác, duyệt hàng loạt nguyên tử, 409 có cách tải cấu hình mới và giữ nội dung form. Đã thực hiện: mọi write kiểm tra revision; duyệt lấy tài liệu server và chỉ gắn tag đã chọn. Lỗi giữ dữ liệu, chỉ ẩn hàng sau success.
- Modal có placeholder Chọn nhóm để gắn ngay và hiển thị đích đề xuất riêng. Chọn cùng nhóm AI cũng chốt ngay; hàng từ chối/stale có thể gắn thủ công theo nhóm hiện hành. Hàng đã gắn không còn trong API danh sách hoặc sau reload; AI muộn không đưa nó trở lại.
- Xóa toàn nhánh nhóm đưa tag về chưa phân loại/Khác, không xóa tag/bài/submission. Giữ một gốc thật, muốn xóa gốc cuối cần tạo gốc thay thế; lý do hiện trên UI.
- Browser dùng fixture rõ nhãn: tạo gốc, gắn/gỡ Map ngoài modal, chọn Map trong modal rồi reload chỉ còn Set, duyệt Set và modal rỗng. Đối chiếu DB xác nhận 5 commit. Ghi cạnh tranh mô phỏng làm save form trả 409; reload giữ nguyên text đang nhập. Khôi phục toàn bộ cấu hình/list gốc bằng kiểm tra revision và tài liệu đầy đủ.

PM duyệt cuối theo mô tả, không browser/code. 93 backend tests, 17 frontend tests và build đạt. Screenshot fixture: skill-config-instant-tag.png. Head migration giữ nguyên 20261004_0002, không đổi schema cho lượt này.

## Modal: ưu tiên nhóm AI đề xuất và xử lý khi AI chạy

PM đã review qua mô tả, không xem browser/code. Các điều kiện được áp dụng: chỉ ẩn sau commit; phản hồi AI muộn không đưa hàng đã xử lý trở lại; hành động tất cả dùng tập ID hiện có lúc bấm; tiến độ xử lý độc lập số hàng chờ; cảnh báo phạm vi cũ nằm cạnh kết quả. Bảng bỏ trạng thái và hàng từ chối. Nhóm AI đề xuất hiển thị lớn, đậm; thao tác đổi nhóm phía dưới. Toolbar responsive. 19 test frontend và production build đạt. Browser kiểm tra dữ liệu hiện tại chỉ đọc, không tạo/dọn fixture trong cấu hình người dùng.

## Cột Hành động và submenu chọn nhóm

PM review qua mô tả, không xem browser/code: đồng ý chuyển thao tác ra cột cuối; ghi nhận menu Hành động thêm một bước mở trước Duyệt/Từ chối. Submenu Chọn nhóm hỗ trợ hover/click/bàn phím. Nhóm con dùng đường dẫn cha, menu cuộn và né mép màn hình. Sau chọn thao tác, focus quay về vùng danh sách. Browser kiểm tra mở ba mục, click mở submenu Khác/DP, Escape đóng; không chọn đích hoặc thay đổi tag. 19 test frontend và build đạt.

## 10 gốc cố định và duyệt kho bài

User đồng ý triển khai 10 nhóm chuyên môn và Khác theo báo cáo 99 tag. PM review chỉ qua mô tả, không xem code/browser: duyệt một gốc/một tag mở, không tự mở tag, toàn kho tìm/lọc trước phân trang, modal đề và lịch sử giữ ngữ cảnh; ghi rõ khoảng thời gian, không chấm điểm 0–100.

DB trước đổi revision 3 có 4 gốc và 0 gán, 15 từ chối. Migration 20261004_0003 giữ snapshot trước đổi, không ghi đè gán tay, giữ đề xuất cũ. Sau đọc lại revision 4 có 11 gốc/99 gán/Khác 4; snapshot revision 3 và 15 từ chối không đổi. Gán vào bảng mới không đồng nghĩa duyệt AI cũ. Nếu root custom có tag mà thiếu ánh xạ rõ, migration dừng trước DDL; nhóm con ở gốc nhận biết được làm phẳng về gốc và giữ override. PM duyệt qua mô tả hiện trạng/chênh lệch này.

PM duyệt hợp nhất panel root trùng và thu gọn phân tích 99 tag. Theo cảnh báo PM, nhãn suy luận cũ được thay ở chế độ forest bằng Có AC/Đã thử chưa AC/Chưa làm; tỷ lệ verdict vẫn nói rõ mẫu số là lượt nộp. Fallback cũ chỉ dùng khi thật sự chưa có forest, lỗi tải hiện ErrorPanel.

104 kiểm thử backend/19 frontend và build đạt. Migration upgrade/check/downgrade/reupgrade trên SQLite riêng đạt. Probe đọc DB/API xác nhận 99 gán, backup và số AC/kho/cutoff khớp tag 4 của học sinh 20586. Browser kiểm tra nhóm/tag/bộ lọc AC/đề có công thức/lịch sử. Đóng modal giữ filter và trả focus đúng về bài vừa mở. Đã xem desktop 1280px và tổng quan khung 390px qua iframe, không ghi cấu hình người dùng. Màu chữ phụ 7.24:1 và AC 5.48:1 đạt tương phản AA.
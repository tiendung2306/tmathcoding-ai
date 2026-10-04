# Phân loại toàn bộ 99 tag

Ngày đối chiếu: 04/10/2026. Phân tích bên dưới dựa trên danh mục đọc từ API kết nối
DB nguồn. Người dùng đã chấp nhận bảng này; migration `20261004_0003` dùng nó làm
phân loại khởi tạo cho 10 gốc cố định và Khác. Quản trị vẫn có thể chuyển tag vào
gốc khác; bảng này không tự ghi đè gán tay khi ứng dụng khởi động. Đọc
[hướng dẫn hiện hành](SKILL_TREE_CONFIGURATION.md) để xem luồng và kết quả chuyển đổi.

**Khuyến nghị: 10 gốc chuyên môn cố định + Khác.** Đây là phương án thiết kế cho kho hiện tại, không phải phân loại chuẩn duy nhất hay cam kết bao phủ mọi tag tương lai.

## Cách đánh giá

Đọc toàn bộ tên/key của 99 tag. Đọc thêm tối đa ba bài mẫu mỗi tag ở 17, 26, 36, 42, 43, 65, 88, 90, 94, 103, 106, 110. Chưa kiểm toán mọi bài của mỗi tag. Đối chiếu tự động: đủ 99 ID, mỗi ID đúng một vị trí, không trùng hoặc bỏ sót.

## Các gốc đề xuất

| Gốc | Số tag | Phạm vi |
|---|---:|---|
| Nền tảng lập trình | 10 | Cú pháp, điều khiển, hàm, dữ liệu cơ bản và cài đặt; không gom kỹ thuật thuật toán nâng cao. |
| Sắp xếp, tìm kiếm và xử lý dãy | 11 | Sắp xếp, tìm kiếm, hai con trỏ, thống kê, đánh dấu, tiền tố, nén dữ liệu và nhảy trên chuỗi trạng thái. Không phải mọi bài có mảng đều thuộc nhóm này. |
| Duyệt, quay lui và chia để trị | 7 | Duyệt không gian nghiệm, sinh cấu hình, đệ quy, quay lui, nhánh cận, chia để trị và Meet in the Middle. DFS/BFS trên đồ thị thuộc nhóm Đồ thị. |
| Cấu trúc dữ liệu | 13 | Container, cấu trúc lưu trữ và truy vấn/cập nhật dữ liệu: STL, DSU, Trie, Segment Tree, Fenwick, Sparse Table, chia căn. |
| Xử lý xâu | 4 | Thao tác, duyệt và so khớp xâu, hashing xâu. DP trên xâu vẫn thuộc DP; Trie thuộc Cấu trúc dữ liệu. |
| Quy hoạch động | 16 | Các dạng DP theo trạng thái/chuyển trạng thái, kể cả DP cây, xâu, bitmask, chữ số và tối ưu chia để trị. |
| Đồ thị và cây | 12 | Biểu diễn/duyệt đồ thị, đường đi, cây khung, DAG, ghép cặp, liên thông, LCA và các kỹ thuật cấu trúc cây. |
| Toán học và số học | 20 | Số học, đại số, xác suất, tổ hợp, xử lý bit và các phép biến đổi/tính toán toán học. |
| Hình học | 1 | Các bài hình học và kỹ thuật tính toán hình học. Một tag đang chứa 44 bài, không phải phạm vi chỉ có một kỹ năng. |
| Tham lam | 1 | Chiến lược lựa chọn cục bộ để tìm nghiệm tối ưu. Một tag đang chứa 57 bài; giữ riêng vì là một phương pháp giải. |
| Khác / chưa xác định kỹ năng | 4 | Tag tổng hợp, nguồn/hình thức bài hoặc chưa xác định; không suy ra một kỹ năng đồng nhất từ cả tag. |

## Điểm cần hiểu đúng

- Duyệt nhị phân #17 là sinh/liệt kê cấu hình nhị phân, có bài liệt kê dãy nhị phân và tam phân. Không phải tìm kiếm nhị phân.
- Hash #26 có bài kiểm tra xâu đối xứng và đếm xâu con khác nhau; đề xuất vào Xử lý xâu theo mẫu đã đọc.
- Prefix #106 có cả bài tổng tiền tố và DP hình chữ nhật. Đề xuất vị trí chính là xử lý dãy/bảng theo kỹ thuật tiền tố; đây là tag hỗn hợp, không chứng minh mọi bài cùng kỹ thuật.
- Ma trận hai chiều nâng cao #90 có bài DP và đếm ô màu; xếp tạm vào xử lý dãy/bảng vì phạm vi tag rộng, tránh xem tên ma trận là bằng chứng mọi bài thuộc DP.
- Binary Lifting #103 hiện có một bài Lửa thiêng: chọn ca làm việc theo khoảng thời gian. Không nên tự động xem tag này chỉ là kỹ năng cây. Đề xuất nhảy/tìm kiếm trong nhóm xử lý dãy; các bài LCA có tag riêng #99.
- Chia căn #110 có truy vấn/cập nhật trên dãy và bài truy vấn cây. Đề xuất vào Cấu trúc dữ liệu theo kỹ thuật tổ chức truy vấn, dù có bài dùng cây.
- DSU #58 và Trie #96 vào Cấu trúc dữ liệu. DP trên cây #61, xâu #79, palindrome #82 vào DP. Đây là quy ước vị trí chính để admin/AI áp dụng nhất quán.
- Kì thi #65 có bài số học, dãy và xâu. EnglishCoding #43 có bài viết tiếng Anh nhưng dùng kỹ thuật khác nhau. Tổng hợp #42 cũng trộn bài; Chưa xác định #36 là nhãn chưa phân loại. Không dùng chúng như bốn kỹ năng.
- Không loại các bài trong Khác khỏi kho hoặc số AC tổng. Một bài có tag kỹ thuật khác vẫn có thể xuất hiện trong gốc chuyên môn tương ứng.
- Số tag không đo độ quan trọng hoặc số bài độc lập. Không cộng số bài của các tag để tính tổng vì một bài có nhiều tag.

## Ánh xạ đủ 99 tag

Cột căn cứ phân biệt đánh giá theo tên tag với việc đã đọc bài mẫu. Các tag hỗn hợp là vị trí đề xuất để quản trị, không phải xác nhận kỹ thuật của toàn bộ bài.

### Nền tảng lập trình (10 tag)

| ID | Tên tag nguồn | Căn cứ |
|---:|---|---|
| 4 | A01 - Nhập môn: Biến, hằng và phép toán | Tên và key của tag |
| 5 | A02 - Nhập môn: Cấu trúc rẽ nhánh | Tên và key của tag |
| 6 | A03 - Nhập môn: Cấu trúc lặp | Tên và key của tag |
| 7 | A05 - Nhập môn: Mảng một chiều | Tên và key của tag |
| 8 | A06 - Nhập môn : Mảng hai chiều | Tên và key của tag |
| 10 | A04 - Nhập môn : Hàm (function) | Tên và key của tag |
| 22 | Phương pháp: Kỹ năng cài đặt | Tên và key của tag |
| 33 | B04 - Thuật toán cơ bản : Cấu trúc bản ghi pair và struct | Tên và key của tag |
| 47 | A09 - Nhập môn : Kỹ thuật cài đặt cơ bản | Tên và key của tag |
| 59 | A10 - Nhập môn : Xử lý file văn bản | Tên và key của tag |

### Sắp xếp, tìm kiếm và xử lý dãy (11 tag)

| ID | Tên tag nguồn | Căn cứ |
|---:|---|---|
| 24 | B02 - Thuật toán cơ bản : Sắp xếp | Tên và key của tag |
| 25 | Phương pháp: Tìm kiếm nhị phân cơ bản | Tên và key của tag |
| 45 | Kỹ thuật: Two Pointer | Tên và key của tag |
| 74 | Phương pháp: Tìm kiếm nhị phân kết quả | Tên và key của tag |
| 87 | B03 - Thuật toán cơ bản : Tìm kiếm | Tên và key của tag |
| 88 | B05 - Thuật toán cơ bản : Mảng thống kê, đánh dấu | Đã đọc bài mẫu |
| 90 | B10 - Thuật toán cơ bản : Ma trận và mảng hai chiều | Đã đọc bài mẫu; tag hỗn hợp/không xác định một kỹ năng |
| 94 | Kỹ thuật: Rời rạc hoá | Đã đọc bài mẫu |
| 103 | Kỹ thuật: Binary Lifting | Đã đọc bài mẫu |
| 105 | Kĩ thuật: Tìm kiếm nhị phân song song | Tên và key của tag |
| 106 | B09 - Thuật toán cơ bản : Quy hoạch động mảng cộng dồn | Đã đọc bài mẫu; tag hỗn hợp/không xác định một kỹ năng |

### Duyệt, quay lui và chia để trị (7 tag)

| ID | Tên tag nguồn | Căn cứ |
|---:|---|---|
| 13 | Phương pháp: Đệ quy | Tên và key của tag |
| 16 | Phương pháp: Duyệt cơ bản | Tên và key của tag |
| 17 | Phương pháp: Duyệt nhị phân | Đã đọc bài mẫu |
| 18 | Phương pháp: Duyệt hoán vị | Tên và key của tag |
| 20 | Phương pháp: Chia để trị | Tên và key của tag |
| 54 | Phương pháp: Duyệt nhánh cận | Tên và key của tag |
| 91 | Kỹ thuật: Meet in the Middle | Tên và key của tag |

### Cấu trúc dữ liệu (13 tag)

| ID | Tên tag nguồn | Căn cứ |
|---:|---|---|
| 23 | CTDL: Segment Tree | Tên và key của tag |
| 27 | C - Cấu trúc dữ liệu nâng cao: 02 - Stack | Tên và key của tag |
| 28 | C - Cấu trúc dữ liệu nâng cao: 03 - Queue_deque | Tên và key của tag |
| 37 | CTDL: Priority Queue | Tên và key của tag |
| 38 | C - Cấu trúc dữ liệu nâng cao: 05 - Set | Tên và key của tag |
| 39 | C - Cấu trúc dữ liệu nâng cao: 04 - Map | Tên và key của tag |
| 44 | CTDL: Fenwick Tree | Tên và key của tag |
| 56 | C - Cấu trúc dữ liệu nâng cao: 01 - Vector | Tên và key của tag |
| 58 | Đồ thị: Disjoint Set | Tên và key của tag |
| 92 | CTDL: Sparse Table | Tên và key của tag |
| 96 | CTDL: Trie | Tên và key của tag |
| 108 | B06 - Thuật toán cơ bản : Map, Set | Tên và key của tag |
| 110 | Kỹ thuật: Duyệt chia căn | Đã đọc bài mẫu |

### Xử lý xâu (4 tag)

| ID | Tên tag nguồn | Căn cứ |
|---:|---|---|
| 9 | A07 - Nhập môn : Xâu ký tự | Tên và key của tag |
| 26 | Kỹ thuật: Hash | Đã đọc bài mẫu |
| 62 | Nâng cao - Xâu kí tự | Tên và key của tag |
| 75 | B07 - Thuật toán cơ bản : Duyệt xâu | Tên và key của tag |

### Quy hoạch động (16 tag)

| ID | Tên tag nguồn | Căn cứ |
|---:|---|---|
| 14 | Phương pháp: Quy hoạch động | Tên và key của tag |
| 31 | Quy hoạch động: Nhân ma trận | Tên và key của tag |
| 61 | Quy hoạch động: Tree | Tên và key của tag |
| 63 | Quy hoạch động: SOS | Tên và key của tag |
| 76 | Quy hoạch động: Dãy số | Tên và key của tag |
| 77 | Quy hoạch động: Bảng hai chiều | Tên và key của tag |
| 78 | Quy hoạch động: Cái túi | Tên và key của tag |
| 79 | Quy hoạch động: Xâu con | Tên và key của tag |
| 80 | Quy hoạch động: Bitmask | Tên và key của tag |
| 81 | Quy hoạch động: Cấu hình | Tên và key của tag |
| 82 | Quy hoạch động: Palindrome | Tên và key của tag |
| 83 | Quy hoạch động: Chia để trị | Tên và key của tag |
| 84 | Quy hoạch động: Khác | Tên và key của tag |
| 85 | Quy hoạch động: Chữ số | Tên và key của tag |
| 86 | Quy hoạch động: Thành phần liên thông | Tên và key của tag |
| 89 | B08 - Thuật toán cơ bản : Quy hoạch động cơ bản | Tên và key của tag |

### Đồ thị và cây (12 tag)

| ID | Tên tag nguồn | Căn cứ |
|---:|---|---|
| 15 | Đồ thị: DFS và BFS | Tên và key của tag |
| 29 | Đồ thị: Floyd | Tên và key của tag |
| 30 | Đồ thị: Dijkstra | Tên và key của tag |
| 35 | Đồ thị: Mở đầu về đồ thị | Tên và key của tag |
| 40 | Đồ thị: Cây khung | Tên và key của tag |
| 55 | Đồ thị: DAG | Tên và key của tag |
| 57 | Đồ thị: Cặp ghép | Tên và key của tag |
| 64 | Đồ thị: Tarjan | Tên và key của tag |
| 93 | Đồ thị: Topo | Tên và key của tag |
| 98 | Centroid Decomposition | Tên và key của tag |
| 99 | Đồ thị: LCA | Tên và key của tag |
| 104 | Đồ thị: Cây nâng cao | Tên và key của tag |

### Toán học và số học (20 tag)

| ID | Tên tag nguồn | Căn cứ |
|---:|---|---|
| 11 | Toán: Số học | Tên và key của tag |
| 19 | Toán: Đại số | Tên và key của tag |
| 32 | Toán: Xác suất | Tên và key của tag |
| 49 | Toán: Tổ hợp | Tên và key của tag |
| 52 | A08 - Nhập môn : Số học cơ bản 1 | Tên và key của tag |
| 60 | Toán học: Xử lý bit | Tên và key của tag |
| 66 | Số học: Ước, bội | Tên và key của tag |
| 67 | Số học: Số nguyên tố cơ bản | Tên và key của tag |
| 68 | Số học: Phân tích thừa số nguyên tố | Tên và key của tag |
| 69 | Số học: Sàng nguyên tố | Tên và key của tag |
| 70 | Số học: Sàng ước | Tên và key của tag |
| 71 | Số học: Nhân ấn độ | Tên và key của tag |
| 72 | Số học: Legendre | Tên và key của tag |
| 73 | Số học: Tổ hợp | Tên và key của tag |
| 95 | Số học: Bao hàm - Loại trừ | Tên và key của tag |
| 97 | Số học: Khử gauss | Tên và key của tag |
| 100 | Số học: Chia kẹo Euler | Tên và key của tag |
| 101 | Số học: Euler's totient function | Tên và key của tag |
| 102 | Số học: Chung | Tên và key của tag |
| 107 | B01 - Thuật toán cơ bản : Số học 2 | Tên và key của tag |

### Hình học (1 tag)

| ID | Tên tag nguồn | Căn cứ |
|---:|---|---|
| 12 | Toán: Hình học | Tên và key của tag |

### Tham lam (1 tag)

| ID | Tên tag nguồn | Căn cứ |
|---:|---|---|
| 21 | Phương pháp: Tham lam | Tên và key của tag |

### Khác / chưa xác định kỹ năng (4 tag)

| ID | Tên tag nguồn | Căn cứ |
|---:|---|---|
| 36 | Chưa xác định | Đã đọc bài mẫu; tag hỗn hợp/không xác định một kỹ năng |
| 42 | Tổng hợp | Đã đọc bài mẫu; tag hỗn hợp/không xác định một kỹ năng |
| 43 | EnglishCoding | Đã đọc bài mẫu; tag hỗn hợp/không xác định một kỹ năng |
| 65 | Kì thi | Đã đọc bài mẫu; tag hỗn hợp/không xác định một kỹ năng |

## Vì sao chọn 10

Chọn 10 để tách kiến thức lập trình cơ bản, kỹ thuật xử lý/tìm kiếm trên dãy và phương pháp duyệt không gian nghiệm. Có thể dùng 9 bằng cách gộp Hình học vào Toán học, nhưng với cây kỹ năng tôi ưu tiên để học sinh nhìn thấy hình học riêng. Nhiều hơn 10 có thể tách số học/đại số/tổ hợp hoặc container/cấu trúc truy vấn, nhưng chúng phù hợp làm nhánh con hơn là thêm gốc ở mức tổng quan. Bộ 10 không nhằm cân bằng số tag giữa các nhóm và không phải số nhóm duy nhất có thể dùng.

Giữ tag là lá trong gốc. Nếu muốn cây nhiều cấp, nhóm con có thể là Số học, Tổ hợp, Container STL, Cấu trúc truy vấn, Sinh cấu hình hoặc Tìm kiếm nhị phân. Root cố định không có nghĩa phải bỏ nhóm con.

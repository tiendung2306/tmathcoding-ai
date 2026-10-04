# Đánh giá yêu cầu 8 cây kỹ năng

Tài liệu này ghi nhận phương án ban đầu, trước khi chốt và triển khai. Quyết định
hiện hành là 10 gốc cố định và Khác, số bài AC/minh chứng, không có điểm 0–100 hay
mục tiêu AC. Xem [hướng dẫn hiện hành](SKILL_TREE_CONFIGURATION.md) và
[bảng phân loại 99 tag](SKILL_TAG_TAXONOMY_2026-10-04.md). Các nhận xét hiện trạng
và đề xuất chấm điểm bên dưới được giữ làm lịch sử phân tích, không phải đặc tả
của phiên bản đang chạy.

Ngày: 04/10/2026. Phạm vi: đọc mã nguồn, đặc tả, kiến trúc hai DB và dữ liệu backup trong repository. Chưa đối chiếu DB production, chưa đo hiệu năng cây mới. Không sửa ứng dụng hoặc dữ liệu.

## Kết luận

Yêu cầu khả thi trên kiến trúc hiện tại. Có thể giữ 8 danh mục của bản đồ năng lực làm 8 gốc, thêm các cấp kỹ năng con và tính điểm từ lịch sử submission. Không cần AI để dựng cây hoặc tính điểm cơ bản.

Đây là thay đổi cả mô hình phân loại, API, chấm điểm và giao diện. Chỉ thay cách vẽ frontend sẽ chưa đáp ứng được yêu cầu. Điều kiện để kết quả đáng tin là duyệt cấu trúc cây, xác định ý nghĩa điểm và kiểm tra mức phủ tag của bài toán.

## Hiện trạng đã xác nhận

- `backend/app/services/algorithm_competency_service.py`: `ALGORITHM_PILLARS` định nghĩa 8 danh mục và ánh xạ tag ID sang danh mục. Tên gốc gồm Quy hoạch động; Cấu trúc dữ liệu; Xử lý xâu; Hàm và Đệ quy; Toán học và Số học; Hình học tính toán; Lý thuyết đồ thị; Thuật toán tham lam.
- `backend/app/services/skill_tree_service.py`: lấy tất cả tag, đếm bài AC riêng biệt theo tag và trả danh sách phẳng. Mọi node có category là “Chủ đề”. Điểm bằng `min(100, số bài AC / chỉ tiêu × 100)`; chỉ tiêu toàn bộ lịch sử là 10, 7 ngày là 2, 30 ngày là 4, 1 năm là 8. Trường hợp 1 ngày đang rơi vào mặc định 10.
- `frontend/src/components/SkillTree.tsx`: dùng lưới thẻ, không có cạnh nối, cha–con hoặc mở rộng nhánh. PM có cơ sở khi nhận xét nó chưa giống một cây kỹ năng.
- `backend/app/schemas/student.py`: node chưa có `parent_id`, `children`, độ sâu, số bài làm hoặc bằng chứng tính điểm.
- `backend/app/models/dmoj.py` và schema backup: tag có ID, tên, tên đầy đủ, priority; không có quan hệ cha–con. Submission có kết quả, thời gian, bộ nhớ, điểm, ngày, bài toán và ngôn ngữ; mã nguồn nằm trong bảng riêng.
- Radar dùng `CompetencyEvaluator`: bài AC có trọng số theo mức Bloom, cộng/trừ hành vi nộp, thời gian thực thi và heuristic chất lượng mã. Đây là công thức khác với điểm cây hiện tại.
- Auto-tag lưu kết quả ở dashboard. Radar và cây hiện tại chỉ dùng tag gốc trong `judge_problem_types`; chưa sử dụng kết quả AI này.
- Các tài liệu cũ vẫn mô tả cây 99 node/Bloom, có đoạn không còn khớp implementation hiện tại. Đánh giá này ưu tiên mã đang có và schema backup.

## Mức đáp ứng của dữ liệu hiện có

Đếm trực tiếp hai file `backup/dmoj.judge_problemtype.00000.sql` và `backup/dmoj.judge_problem_types.00000.sql`: 99 tag, 5.080 liên kết bài–tag. Số bài dưới đây là số ID bài riêng biệt gắn tag trong backup, không phải số bài đã kiểm tra chất lượng hoặc số bài học sinh đã giải.

| Nhánh PM yêu cầu | Tag hiện có | Số bài | Nhận xét |
| --- | --- | ---: | --- |
| DP một chiều | 76: `dp_day_so` | 99 | “DP dãy số”; cần giáo viên duyệt, không tự đồng nhất với mọi DP một chiều |
| DP hai chiều | 77: `dp_2darr` | 39 | “DP bảng hai chiều”; cần chốt tên và phạm vi |
| DP chữ số | 85: `dpdigit` | 24 | Có thể làm nhánh trực tiếp |
| Segment Tree | 23: `segtree` | 78 | Có thể làm nhánh trực tiếp |
| BIT/Fenwick Tree | 44: `fenwick` | 14 | Có thể làm nhánh trực tiếp |
| STL | Chưa có tag riêng | Không áp dụng | Tạo node nhóm của dashboard |
| STL → Map | 39: `map` | 43 | Có thể làm nhánh con |
| STL → Set | 38: `set` | 15 | Có thể làm nhánh con |
| STL → Vector | 56: `vector` | 5 | Có dữ liệu nhưng mỏng hơn Map/Set |

DP còn có nhánh Tree, SOS, Knapsack, Bitmask, Palindrome, tối ưu chia để trị và các tag khác. Đồ thị có DFS/BFS, Dijkstra, Floyd, cây khung, DSU, LCA... Tuy nhiên Hình học và Tham lam hiện mỗi danh mục chỉ ánh xạ một tag tổng. Muốn hai cây này phân nhánh sâu hơn cần bổ sung phân loại bài toán trong dashboard, hoặc duyệt kết quả phân loại đề xuất.

Một số kỹ năng chỉ có 0–2 bài gắn tag trong backup. Không áp chỉ tiêu 10 bài giống nhau cho mọi nhánh. Bốn tag `unknown`, `doituyen`, `e123`, `exam` chưa thuộc 8 danh mục; cần giữ ở danh sách chuyên đề hoặc vùng chưa phân loại, không ép vào cây không phù hợp.

## Cách dựng cây đề xuất

Giữ một định nghĩa phân loại dùng chung cho radar và cây. Mỗi node có ID ổn định, tên, cha, thứ tự và các tag ánh xạ. Cho phép node nhóm không có tag trực tiếp, như STL. Với node vừa có bài gắn trực tiếp vừa có nhánh con, tính trên hợp các bài trực tiếp và bài của các nhánh con.

Ví dụ cấu trúc để thảo luận, chưa phải taxonomy đã được giáo viên duyệt:

```text
Quy hoạch động
  Cơ bản / dãy số
  Bảng hai chiều
  Chữ số
  Cái túi
  Bitmask
  Trên cây

Cấu trúc dữ liệu
  Segment Tree
  Fenwick Tree / BIT
  STL
    Vector
    Map
    Set
    Stack
    Queue / Deque
    Priority Queue
```

Một kỹ năng có thể liên quan nhiều danh mục, ví dụ Trie và DP trên cây. Để giao diện vẫn là 8 cây dễ đọc, chọn một vị trí chính cho mỗi kỹ năng; quan hệ liên quan hoặc tiên quyết là metadata riêng. Quan hệ cha–con chỉ thể hiện phân loại, không tự suy ra điều kiện mở khóa.

Phân loại bài thành DP một chiều/hai chiều cũng có thể chồng với Knapsack hoặc DP chữ số. Không ép mọi nhóm này thành một chuỗi quan hệ cha–con nếu không đúng chuyên môn; bài có thể là bằng chứng cho nhiều kỹ năng, nhưng phải khử trùng trong từng node và khi tổng hợp lên cha.

## Điểm nên thể hiện điều gì?

Khuyến nghị MVP thể hiện mức tích lũy bằng chứng giải bài theo kỹ năng, thang 0–100; không quảng bá là phép đo chính xác tuyệt đối năng lực. PM/giáo viên duyệt chỉ tiêu cho từng kỹ năng và ý nghĩa các mức.

Một công thức khởi đầu có thể là `100 × min(1, tổng trọng số bài AC riêng biệt / chỉ tiêu của kỹ năng)`, với trọng số theo mức bài đã được duyệt. Đây là đề xuất mới, chưa có trong ứng dụng. Chỉ tiêu phải phù hợp kho bài và mục tiêu học, không tự coi điểm bài toán là độ khó chuẩn.

- Nộp lại cùng bài không làm tăng số bài đã giải.
- Bài nhiều tag có thể đóng góp cho nhiều kỹ năng liên quan; tại một node chỉ tính một lần.
- Node cha tổng hợp từ tập bài đã khử trùng. Không cộng điểm con hoặc lấy trung bình không trọng số.
- Điểm gốc trên cây phải dùng cùng định nghĩa với điểm radar. Nếu thay công thức, chuyển cả hai và ghi phiên bản công thức.
- Hiển thị số bài đã thử, số bài AC, chỉ tiêu, cách tính và danh sách bài làm minh chứng. Có thể có trạng thái “Chưa đủ dữ liệu”.
- “Chưa có bài AC” khác “Chưa thử”: học sinh chỉ có WA/TLE vẫn đã thử. Không gọi là “Chưa mở” nếu sản phẩm không có cơ chế khóa.
- Năng lực tích lũy nên mặc định dùng toàn bộ lịch sử; hoạt động 7/30 ngày có thể hiển thị riêng. Nếu cho điểm theo kỳ, phải ghi rõ đó là điểm trong kỳ và không so sánh trực tiếp với điểm tích lũy có chỉ tiêu khác.
- Gắn tag bài toán cho biết học sinh giải được bài thuộc chủ đề, chưa chứng minh họ đã dùng đúng kỹ thuật đó. Muốn khẳng định học sinh thành thạo Map hoặc DP chữ số qua cách giải cần phân tích chính submission của học sinh, không chỉ một code AC của người khác.

## Các vấn đề cần sửa nếu tái sử dụng bộ chấm hiện tại

1. **Đếm lặp submission trong radar.** Truy vấn join một submission với nhiều tag rồi append từng dòng vào danh mục. Khi nhiều tag cùng danh mục, tổng lượt nộp và `fail_before_ac` bị tăng; TLE/MLE và các chỉ số hành vi có thể bị sai. Backup có 496 bài nhiều tag, trong đó 174 cặp bài–danh mục có nhiều tag thuộc cùng danh mục. Đây là nguy cơ có bằng chứng dữ liệu, chưa định lượng số học sinh bị ảnh hưởng.
2. **Thang 100 nhưng mức tối đa thực tế là 80.** Công thức hiện cộng tối đa 50 nền tảng + 10 hành vi + 12 hiệu năng + 8 heuristic mã nguồn. Clamp 100 không chuẩn hóa tổng thành 100. Chỉ tiêu và nhãn phải được hiệu chỉnh trước khi áp xuống các nhánh nhỏ.
3. **Heuristic chưa đủ làm bằng chứng sử dụng kỹ thuật.** Tìm thấy container hoặc pragma không chứng minh cấu trúc dữ liệu tối ưu; runtime nhỏ so với time limit không tự chứng minh độ phức tạp tối ưu. Không dùng các nhận xét này như kết luận chắc chắn về kỹ năng cụ thể.
4. **Khoảng thời gian chưa đồng nhất.** Cây không có chỉ tiêu riêng 1 ngày; ngày tham chiếu được neo theo submission mới nhất toàn DB, không nhất thiết ngày thực tế. Cần giữ hoặc đổi có chủ đích, ghi rõ ý nghĩa bộ lọc.
5. **AI chưa lấp được mọi khoảng thiếu.** Auto-tag dùng danh mục tag hiện có; thêm nhánh hoàn toàn mới cần mở rộng danh mục dashboard và quy trình duyệt. Prompt còn mô tả ID 1–99 dù backup có ID lớn hơn 99. Không dùng nhãn AI để backfill toàn bộ mà thiếu kiểm chứng.

## Thay đổi kỹ thuật cần thiết

| Phần | Công việc |
| --- | --- |
| Định nghĩa cây | Duyệt 8 gốc, các cấp con, tên hiển thị, ánh xạ tag và nhánh chưa có dữ liệu |
| Dashboard DB | Nếu quản lý cấu trúc bằng DB: thêm node, mapping tag/bài, chỉ tiêu và phiên bản; Alembic revision mới, giữ một head |
| Backend | Đọc metadata dashboard và submissions nguồn qua hai kết nối; ghép bằng ID trong ứng dụng; gom truy vấn theo tập ID, khử trùng, tính điểm bottom-up |
| API | Trả 8 cây có parent/children, điểm, bằng chứng và trạng thái; cập nhật schema/types đồng bộ |
| Frontend | Chọn danh mục, mở/thu nhánh, cạnh thể hiện quan hệ, xem điểm và bài minh chứng; dùng được bằng bàn phím và trên điện thoại |
| Kiểm thử | Nhiều tag cùng nhánh, nộp lại, chỉ có WA/TLE, node nhóm, tag tổng, thiếu dữ liệu, điểm gốc khớp radar, bộ lọc thời gian |
| Tài liệu | Cập nhật SDD và đặc tả điểm; tránh tiếp tục gọi danh sách phẳng là cây |

DB gốc giữ quyền chỉ đọc. Cấu trúc cây, mapping và chỉ tiêu mới do dashboard sở hữu phải ở `tmath_dashboard`, dùng `DashboardBase` và migration Alembic. Không thêm parent vào tag của DB gốc, không có foreign key hoặc SQL join xuyên DB/server.

MVP có thể dùng cấu hình cây được version trong repository nếu chưa cần chỉnh từ admin; cần chọn rõ cách quản trị. Nếu lưu DB thì áp đúng quy ước trên. Không cần lưu snapshot điểm ngay ở MVP; cân nhắc cache có phiên bản và invalidation khi có submission/tag mới. Chưa có phép đo để quyết định cần precompute.

## Phạm vi triển khai đề xuất

1. Duyệt taxonomy và điểm bằng vài học sinh/bài mẫu trước khi xây UI hoàn chỉnh.
2. MVP: đúng 8 gốc; nhiều cấp từ tag hiện có; thêm node nhóm STL; điểm có minh chứng; gốc khớp radar; trạng thái thiếu dữ liệu trung thực. Không yêu cầu AI thời gian thực.
3. Giai đoạn sau: phân nhánh các danh mục đang thiếu tag, admin duyệt mapping, xác nhận kỹ thuật từ code của chính học sinh và theo dõi tiến bộ theo thời gian.

Không cần hiển thị toàn bộ 8 cây bung hết cùng lúc. Nên có tổng quan 8 danh mục và mở cây từng danh mục; khi PM yêu cầu thấy cả 8 thì giữ 8 vùng gốc có thể thu gọn. Bố cục cuối cần kiểm chứng với dữ liệu thật, tên dài và màn hình nhỏ.

Chưa chốt thời gian triển khai vì chưa có cây được duyệt, chưa biết cần admin chỉnh cây hay chỉ cấu hình cố định, và chưa xác minh mức phủ dữ liệu đang chạy. Phần triển khai phần mềm có phạm vi rõ; công việc phân loại và duyệt dữ liệu có thể lớn hơn phần vẽ cây.

## Điều kiện nghiệm thu

- Đúng 8 gốc, nhánh con đúng phân loại được duyệt, hỗ trợ ít nhất ba cấp với STL → Map/Set.
- Điểm tái lập được từ submission; cùng bài/nhiều tag không nhân số lượt tại một node.
- Điểm gốc cây và radar khớp khi cùng học sinh, thời điểm, khoảng thời gian và phiên bản.
- Kỹ năng chưa đủ bằng chứng được thể hiện rõ; không lấy tag cha để tự gán điểm cho mọi kỹ năng con.
- Có mở/thu, xem bằng chứng, loading/error/empty, keyboard/focus và bố cục mobile.
- Không ghi hoặc đổi schema DB gốc; migration dashboard theo đúng kiến trúc.

Rà soát antislop tĩnh toàn repository được ghi riêng tại `anti-slop/audit-003-2026-10-04.md`. Không có hạng mục sửa ứng dụng được phê duyệt trong yêu cầu đánh giá này.

# Kế hoạch triển khai điểm bài và điểm tích lũy tmath

Ngày lập: 27/10/2026. Trạng thái: kế hoạch kỹ thuật để review, chưa triển khai tính điểm.

**Điều chỉnh yêu cầu ngày 28/10/2026:** không có màn quản trị điểm, không cho quản trị viên cấu hình khoảng điểm/ngưỡng hoặc gán bậc. Khoảng điểm cố định trong code, A–F chỉ lấy từ Source API. Các đoạn về cấu hình/override và UI công bố trong kế hoạch cũ bên dưới đã bị thay thế bởi yêu cầu này. V1 vận hành tác vụ bằng CLI kỹ thuật; xem `SCORING.md` để biết hành vi đã triển khai.

**Điều chỉnh tiếp:** mọi bài đều có điểm. Bài chưa có A–F từ nguồn dùng mặc định 100 điểm, không có trạng thái chờ điểm/xác nhận partial ở giao diện. Các đoạn xử lý NULL/chờ phân bậc trong kế hoạch cũ không còn là hành vi hiện hành.

## 1. Phạm vi và các quyết định đã thống nhất

- Mỗi bài có giá trị điểm riêng; hai bài cùng C có thể khác điểm.
- Mỗi bậc A–F có khoảng điểm cố định. Kết quả mô hình không được vượt khoảng của bậc.
- Một cặp học sinh–bài chỉ tạo một quan sát: có AC là 1; đã thử nhưng chưa có AC là 0. Chưa từng làm là thiếu quan sát, không phải 0.
- Dùng toàn bộ lịch sử hợp lệ tại mốc đồng bộ; không áp dụng cửa sổ 7 ngày từng được đề xuất.
- AC nhiều lần chỉ tính điểm một lần. WA/TLE không trực tiếp trừ điểm thành tích.
- Điểm tích lũy là tổng điểm hiện hành của các bài AC riêng biệt. Mọi học sinh dùng cùng bảng điểm, không khóa điểm theo ngày AC.
- Mô hình đề xuất điểm; quản trị duyệt bảng điểm trước khi công bố. Khi công bố phải cập nhật đồng loạt điểm học sinh.
- Không thêm mùa/học kỳ. Phiên bản kỹ thuật chỉ phục vụ tính nhất quán, truy vết và khôi phục.
- Nguồn được đọc qua Source API. Các bảng và kết quả mới thuộc `tmath_dashboard`.

Mục tiêu của mô hình V1 là ước lượng độ khó thực nghiệm trong môi trường luyện tập tmath. Với nhãn “từng AC”, kết quả phản ánh khả năng hoàn thành sau quá trình luyện tập; không gọi đây là năng lực thi độc lập hoặc rating tương đương Codeforces.

## 2. Hiện trạng đã kiểm tra và hệ quả kỹ thuật

| Hiện trạng | Hệ quả khi triển khai |
| --- | --- |
| Probe Source API local trong cuộc trao đổi ngày 27/10/2026 ghi nhận 4.541 bài; 4.224 có A–F, 295 Uncategorized, 22 NULL | Đây là số liệu fixture local, không đại diện mặc nhiên cho production; phải đo lại trước backfill |
| `SourceProblem.group_id` và `/problem-groups` cung cấp bậc; ID A–F là 4,5,6,7,8,13 | Ánh xạ theo ID được kiểm tra, không suy từ thứ tự danh mục hoặc `group_id - 4` |
| `SourceProblemFact` có `ac_count`, `attempt_count`, `first_ac_at`, `verdict_counts` | Có thể tạo nhãn nhị phân mà không tải source code, testcase, mô tả đề |
| `student_catalog_service.py` yêu cầu Source API sắp `points_desc` và nhận `rank` nguồn | Thay điểm sau khi phân trang sẽ sai cả trang lẫn thứ hạng; phải có đường xếp hạng mới |
| `heatmap_service.py`, `class_student_service.py` và API tìm kiếm vẫn đọc `points` nguồn | Cần kiểm kê mọi nơi hiển thị điểm, không chỉ sửa một màn hình |
| `_catalog_version()` ở mock đọc lại danh mục và liên kết để băm | Không gọi lại hàm này cho từng học sinh trong backfill lớn |
| Endpoint problem-facts hiện gom toàn lịch sử học sinh rồi mới cắt trang | Phân trang response hiện chưa bảo đảm chi phí xử lý theo kích thước trang |
| Aggregate hiện tối đa 100 profile, facts nhúng tối đa 1.000 cặp; aggregate super admin vẫn có điều kiện ghi danh lớp | Không mặc nhiên coi endpoint này bao phủ mọi profile, đặc biệt học sinh chưa thuộc lớp |
| Feed submission-changes hiện theo lớp, journal mock nằm trong RAM | Không đủ làm nguồn đồng bộ toàn cục bền vững; mất cursor khi restart, một học sinh có thể nằm nhiều lớp |
| `LLMJobManager` lưu trạng thái Redis/RAM và chạy bằng `asyncio.create_task` | Không dùng làm bộ thực thi bền vững cho hiệu chỉnh điểm và công bố bảng điểm |
| Celery có trong requirements nhưng Compose chưa có scoring worker/beat | Không coi hạ tầng hàng đợi đã sẵn sàng |
| Alembic head trong repository là `20261011_0002` | Thêm revision nối head tại lúc triển khai, không sửa revision đã triển khai |

Tham chiếu code: `backend/app/services/source_gateway.py`, `student_catalog_service.py`, `class_student_service.py`, `heatmap_service.py`, `source_api_mock/main.py`, `backend/app/core/job_manager.py`.

## 3. Chính sách điểm cần đóng thành cấu hình có phiên bản

### 3.1. Khoảng A–F

Bảng dưới là bộ giá trị đề xuất để chạy thử, chưa phải chính sách được người dùng duyệt. Các bậc không chồng lấn, điểm công bố là số nguyên theo bước 50:

| Bậc | Thấp nhất | Cao nhất | Điểm khởi tạo |
| --- | ---: | ---: | ---: |
| A | 100 | 450 | 300 |
| B | 500 | 850 | 700 |
| C | 900 | 1.250 | 1.100 |
| D | 1.300 | 1.650 | 1.500 |
| E | 1.700 | 2.050 | 1.900 |
| F | 2.100 | 2.450 | 2.300 |

Mục đích của bộ này: mỗi bậc có tám mức điểm và thứ tự A < B < C < D < E < F luôn được giữ. Đây là quy ước thưởng của tmath, không phải các mốc Codeforces hoặc bằng chứng bài F khó gấp một số cố định lần bài A.

Trước lần công bố đầu tiên phải so sánh các bộ khoảng trên hồ sơ thật: tỷ trọng điểm từ mỗi bậc, thứ hạng thay đổi, ảnh hưởng của việc giải nhiều bài dễ. Chốt cả khoảng, điểm đầu, bước làm tròn và quy tắc làm tròn nửa bước; không để phụ thuộc `round()` khác nhau giữa Python và JavaScript.

Khoảng là ràng buộc ngay trong bộ tối ưu, đồng thời được kiểm tra lại khi lưu và công bố. Không chỉ cắt điểm ở UI. Khi thay khoảng phải tạo chính sách mới và chạy lại toàn bộ chuỗi kiểm chứng.

### 3.2. Bài chưa có bậc và bài đổi bậc

- Lưu `source_group_id` và `effective_grade` riêng. Mặc định dùng bậc nguồn; dashboard chỉ override khi quản trị phân bậc có lý do và lịch sử duyệt.
- 317 bài chưa có bậc trong fixture được xuất thành danh sách xử lý, giữ đầy đủ các bài mà học sinh đã AC.
- Trong chạy thử, bài chưa phân bậc có `point_value=null`, và hồ sơ có `unscored_solved_count`. Không biến “chưa biết” thành 0 điểm hoặc tự gán A.
- Để thay thế bảng điểm toàn kho chính thức, phải hoàn thành phân bậc các bài trong phạm vi tính điểm. Nếu chỉ triển khai cho một tập bài, tập đó phải được công bố rõ và áp dụng chung cho mọi học sinh.
- Thay bậc từ nguồn hoặc override làm hết hiệu lực đề xuất cũ của bài; tạo đề xuất mới và cập nhật tổng qua quy trình công bố.
- Bài không đủ dữ liệu vẫn nhận điểm khởi tạo trong bậc, trạng thái `PROVISIONAL`. Đây khác trạng thái không có bậc.

### 3.3. Phạm vi dữ liệu và quyền

Định nghĩa một tập bài tính điểm và một tập profile rõ ràng trong chính sách. Bao gồm học sinh không thuộc lớp nếu mục tiêu là toàn nền tảng; không suy tập profile bằng hợp danh sách lớp một cách im lặng.

Điểm bài là chung, nhưng việc xem lịch sử giải và tổng điểm từ bài riêng tư vẫn phải theo quyền nguồn. V1 có thể tính toàn kho cho khu vực quản trị được cấp quyền toàn cục. Chưa phục vụ tổng toàn kho đó cho tài khoản chỉ có quyền xem một phần dữ liệu.

Trước khi mở cho giáo viên có quyền hẹp, chọn một phạm vi bài công khai dùng chung hoặc xây tổng theo phạm vi được cấp quyền. Không để tổng điểm/chi tiết đóng góp làm lộ việc học sinh đã giải bài riêng tư. Nhu cầu này phải xuất hiện trong contract và kiểm thử, không giải quyết bằng việc giấu tên bài ở frontend.

## 4. Kiến trúc được đề xuất

```text
Source API được cấp quyền
  -> scoring sync worker: lấy metadata, kết quả học sinh–bài, thay đổi
  -> dashboard DB: facts đã khử trùng + checkpoint
       -> scoring calibration worker: snapshot bất biến -> Rasch có giới hạn
       -> đề xuất điểm + kiểm định + quản trị duyệt
       -> dựng bảng điểm và tổng điểm ứng viên
       -> công bố nguyên tử một thế hệ dữ liệu
       -> API đọc tổng/chi tiết/xếp hạng tính sẵn -> frontend
```

Chọn một service `scoring-worker` riêng, có thể chạy lệnh `sync`, `calibrate`, `build`, `publish`, `reconcile`. V1 dùng bảng job bền vững trong MySQL dashboard và một tiến trình worker có lease/heartbeat. Redis chỉ là cache tùy chọn, không quyết định đúng/sai điểm.

Một worker xử lý tuần tự các job nặng lúc đầu; tăng worker đồng bộ chỉ khi benchmark cho thấy cần thiết. Mỗi job xử lý theo chunk, checkpoint để tránh một job dài chiếm worker vô hạn. Có thể bổ sung Celery làm cơ chế đánh thức sau này, nhưng dữ liệu job, checkpoint và trạng thái công bố vẫn ở dashboard DB.

Tách container worker khỏi FastAPI, giới hạn CPU/RAM và số luồng BLAS. Không chạy mô hình trong request HTTP hoặc dùng chung semaphore với LLM/Ollama. Không cần GPU hoặc LLM cho tính điểm.

## 5. Source API: hợp đồng cần bổ sung trước khi tối ưu quy mô lớn

### 5.1. Đường tương thích để làm pilot

Dùng catalog và problem-facts hiện có cho một mẫu nhỏ có giới hạn; chạy trong worker. Không gọi cho mọi học sinh mỗi khi giáo viên mở trang. Phải đo số request, thời gian và số lượt nguồn quét lại lịch sử.

### 5.2. Bulk snapshot cho backfill

Đề xuất namespace mới `/integration/v1/scoring/`, tên endpoint có thể đổi khi thống nhất với provider:

- Khởi tạo hoặc yêu cầu một snapshot chỉ đọc cho scope đã được cấp quyền; provider trả `snapshot_id`, `catalog_version`, `facts_revision`, `roster_revision`, thời điểm và watermark của changes.
- Đọc catalog, roster/membership và các cặp học sinh–bài qua các page của cùng snapshot. Facts tối thiểu gồm `profile_id`, `problem_id`, `observed`, `has_ac`, `pair_revision`, `first_ac_at` và các cờ dữ liệu hợp lệ.
- Bắt đầu với page 1.000 cặp, có giới hạn byte, điều chỉnh qua benchmark. Không tải code, testcase hay description.
- Cặp chưa từng nộp không cần xuất. Snapshot có manifest tổng số cặp, tổng AC, số profile và checksum theo partition để đối soát.
- Provider phải bảo đảm snapshot bất biến xuyên page hoặc xuất một artifact nhất quán; chỉ gắn cùng timestamp không đủ. Cùng `catalog_version` cũng không chứng minh cùng trạng thái verdict.
- Cursor gắn với snapshot, scope và phiên bản schema. Resume từ checkpoint; snapshot hết hạn thì bỏ staging chưa hoàn tất và tạo lần sync mới, không ghép page từ hai snapshot.

Ở Source API mock, gom dữ liệu bằng SQL phía provider với tài khoản chỉ đọc, xử lý theo tập ID/partition, không kéo mọi submission vào Python mỗi page. Một snapshot tính fingerprint/manifest một lần. Đo query plan trước khi quyết định cần index nguồn nào; dashboard không tự chạy DDL nguồn.

### 5.3. Feed thay đổi bền vững

Đề xuất feed toàn cục của các cặp thay đổi, có cursor bền vững, revision có thứ tự commit, hỗ trợ:

- Bài nộp mới, verdict đổi sau chấm, rejudge bài cũ, xóa/invalidate lượt nộp.
- Catalog đổi bậc, bài mới, thay quyền hiển thị; profile/membership thay đổi có revision riêng.
- Mỗi event chứa trạng thái cặp đã gom đầy đủ hoặc cho phép fetch lại trạng thái cặp chính thức. Không suy `has_ac=false` chỉ từ một lượt AC bị đổi thành WA vì có thể còn AC khác.
- Giao ít nhất một lần được chấp nhận; consumer phải chịu được lặp, đảo thứ tự, restart, hết retention.
- Watermark phản ánh thứ tự commit hoặc bảo đảm tương đương. Không dùng `MAX(submission.id)`, ngày nộp hoặc auto-increment được cấp trước commit làm bằng chứng đã đọc đủ mọi thay đổi.

Provider production có thể cung cấp CDC/outbox/change log phù hợp, nhưng đây là việc phối hợp với bên sở hữu nguồn. Không thêm bảng nguồn từ dashboard. Journal RAM hiện tại của mock không đáp ứng cam kết này.

Nếu provider chưa có feed bền vững: dùng bulk snapshot định kỳ và đối soát toàn bộ, công khai độ trễ; chưa cam kết cập nhật gần thời gian thực. Feed theo lớp chỉ được dùng hỗ trợ và phải khử trùng, không thay thế reconciliation toàn scope.

### 5.4. Quyền truy cập

Worker dùng actor/service identity được provider cấp rõ phạm vi, không giả mạo quyền bằng ID query. Bổ sung batch permission/roster lookup để API không cần một cuộc gọi quyền cho mỗi học sinh. Runtime chỉ giữ `SOURCE_API_*`; `SOURCE_DB_*` vẫn chỉ thuộc mock/operator.

## 6. Lưu trữ trong dashboard DB

Các tên dưới là đề xuất; có thể gộp bảng nhỏ nhưng phải giữ các bất biến và index.

| Nhóm bảng | Nội dung và khóa quan trọng |
| --- | --- |
| `scoring_policy`, `scoring_grade_band` | Chính sách bất biến, grade, min/max/initial/step, prior, quy tắc verdict và eligibility; UNIQUE(policy_id, grade) |
| `scoring_problem` | ID bài nguồn, source/effective grade, override đã duyệt, metadata revision, trạng thái; PK(problem_id) |
| `scoring_profile`, `scoring_membership` | Metadata tối thiểu và scope/membership để phân trang/xếp hạng; ID logic, roster revision |
| `scoring_pair_fact` | Một dòng/profile–problem: observed, has_ac, first_ac_at, pair_revision, ingestion offset; PK(profile_id, problem_id) |
| `scoring_sync_run`, `scoring_job` | Snapshot, manifest, cursor/checkpoint, lease, attempt, heartbeat, fencing token, lỗi; claim job bằng cập nhật có điều kiện |
| `scoring_calibration_run`, `scoring_item_estimate` | Policy, input snapshot/hash, phiên bản code/dependency, chẩn đoán, difficulty đề xuất, support và bất định |
| `scoring_release`, `scoring_release_item` | Bảng điểm đã duyệt; UNIQUE(release_id, problem_id); integer point_value, trạng thái/calibration run tham chiếu |
| `scoring_generation`, `scoring_active` | Gắn release với thế hệ tổng điểm, facts watermark và scope; một active pointer cho mỗi scope |
| `scoring_student_total` | PK(generation_id, profile_id), tổng BIGINT, solved/unscored counts; index(generation_id, total_points DESC, profile_id) |
| `scoring_audit` | Người duyệt, thay đổi, lý do, manifest/diff hash, idempotency key; ghi cùng giao dịch thay đổi trạng thái |

Index bổ sung cho pair facts: `(problem_id, has_ac, profile_id)` để tìm các học sinh chịu ảnh hưởng khi điểm bài đổi. Thêm index cho membership theo `(scope_id/class_id, profile_id)`, lease/job status và cursor stream theo query thực tế.

Điểm công bố và tổng dùng số nguyên, không dùng FLOAT. Giá trị mô hình dùng float64 trong worker, không dùng trực tiếp để cộng điểm ở API. Constraint kiểm tra khoảng/step trước công bố phải chạy phía server; DB constraint áp dụng khi phù hợp.

Không có FK xuyên nguồn. FK giữa các bảng dashboard được phép. Đăng ký model ở `app/models/dashboard.py`; migration Alembic revision mới `YYYYMMDD_NNNN` nối head, có upgrade/downgrade, thử trên DB trống và bản sao. Không `create_all()` hoặc DDL ở startup.

Dataset hiệu chỉnh cần bất biến: tạo bản xuất compact chỉ gồm ID/index/nhãn, metadata và checksum từ một snapshot facts xác định; lưu ở volume bền vững được quản lý hoặc bản snapshot DB. Đọc vài chunk từ bảng facts đang thay đổi mà không có snapshot không được coi là dataset tái lập được. Không giữ nguồn code/test trong dataset.

## 7. Đồng bộ đúng và không cộng trùng

### 7.1. Backfill lần đầu

1. Kiểm tra quyền và scope; lấy catalog, mapping bậc và roster cùng manifest.
2. Đọc bulk pair facts vào staging theo chunk; checkpoint sau khi commit từng chunk.
3. Kiểm tra khóa trùng, tính hợp lệ ID/revision, đếm và checksum.
4. Kết thúc snapshot, chuyển staging sang facts hoàn chỉnh bằng một thao tác kích hoạt có kiểm tra revision.
5. Tiếp nhận feed changes sau watermark của snapshot để không bỏ AC xảy ra trong lúc backfill.

Học sinh nằm nhiều lớp hoặc bài có nhiều tag vẫn chỉ có một dòng pair facts. Học sinh chưa có bài nào phải có tổng 0 khi scope đã đồng bộ đầy đủ; học sinh chưa được đồng bộ phải có trạng thái chưa sẵn sàng, không giả làm 0.

### 7.2. Cập nhật tăng dần

Trong một giao dịch ngắn: kiểm tra event/revision đã áp dụng, upsert trạng thái cặp, cập nhật tổng active theo chuyển trạng thái, ghi checkpoint. Commit trước khi acknowledge event.

- WA thêm cho cặp đang 0: tổng không đổi; mô hình vẫn chỉ nhận một quan sát 0.
- Có AC đầu tiên: chuyển 0 thành 1, cộng đúng một lần giá trị bài của release active.
- AC tiếp hoặc WA sau AC: không cộng/trừ thêm.
- Rejudge mất AC cuối cùng: chuyển 1 thành 0 và điều chỉnh tổng; nếu còn AC khác thì giữ 1.
- Không còn lượt nộp hợp lệ: chuyển sang không quan sát, khác nhãn 0.
- Event cũ đến sau event mới: bỏ qua theo pair_revision.

Ở đây “có AC” là có AC trong lịch sử hợp lệ theo trạng thái nguồn hiện tại. Nếu nguồn chính thức hủy một verdict AC thì kết quả cần phản ánh việc đó; không giữ một cờ từng-AC vĩnh viễn bằng phép OR không thể đảo.

Tất cả phần thay đổi tổng có record idempotency hoặc revision-guarded transition; không thực hiện `total += value` chỉ vì nhận một event. Nếu dùng nhiều worker phải có khóa hàng theo thứ tự cố định, retry deadlock hữu hạn.

Deletion/tombstone và 404 cần phân biệt: không coi timeout, thu hồi quyền hoặc bản ghi tạm không đọc được là bằng chứng xóa. Chính sách giữ/loại điểm bài bị ngừng phục vụ phải được ghi rõ; giữ metadata lịch sử đã công bố để không mất dấu phần đóng góp.

### 7.3. Đối soát

Chạy reconciliation từ snapshot chính thức để tìm pair bị thiếu/sai, rejudge cũ và delta bị mất. So sánh tổng tính lại từ tập AC với tổng đã materialize. Không dựa riêng vào ngày submission vì rejudge bài cũ không đổi ngày nộp.

Giai đoạn đầu đối soát toàn scope theo ngày nếu benchmark cho phép; khi lớn, partition có checksum và một vòng quét đầy đủ định kỳ. Sai lệch được sửa từ dữ liệu gốc, có audit và không tự sửa nhãn vì mô hình thấy bất thường.

## 8. Bộ hiệu chỉnh độ khó

### 8.1. Công nghệ và tài nguyên

- V1: Bayesian Rasch, discrimination cố định, ước lượng MAP với prior có phiên bản và giới hạn difficulty theo grade.
- Dùng NumPy + SciPy `L-BFGS-B`, gradient giải tích, phép tính log ổn định; pin dependency sau khi kiểm tra tương thích image Python hiện tại. L-BFGS-B hỗ trợ box bounds và không cần lưu full Hessian.
- Tối ưu trên thang đã chuẩn hóa, chuyển lại sang điểm khi xuất; áp cả quy tắc làm tròn và kiểm tra giới hạn lần cuối.
- Dữ liệu là mảng chỉ chứa các cặp quan sát, không tạo ma trận đặc học sinh × bài, không tạo quan sát giả cho ô trống.
- Chi phí mỗi lượt đánh giá objective/gradient theo số cặp P; bộ nhớ mục tiêu O(P + số học sinh + số bài), thêm bộ nhớ limited-memory của optimizer. Vector hóa hoặc chunk cố định, không vòng lặp ORM từng cặp.
- Chạy chung toàn kho để dùng cùng thang năng lực; không fit độc lập từng grade rồi ghép điểm.
- Không dùng tổng điểm tích lũy cũ làm năng lực đầu vào. R được ước lượng cùng difficulty, có prior/anchor cố định để tránh trôi thang giữa các lần chạy.
- Có warm start từ lần trước cùng policy; chạy cold start kiểm chứng trên cùng input và so sánh sai khác trước khi tin warm start.

### 8.2. Chất lượng dữ liệu và độ tin cậy

- Cặp có lượt chấm hoàn tất và kết quả hợp lệ mới được xuất thành nhãn. Danh sách verdict hợp lệ phải xác minh từ nguồn; trạng thái pending/lỗi hạ tầng không tự thành 0. CE chỉ có thể là 0 nếu đây là verdict hoàn tất thuộc policy, không tự loại vì công thức cũ từng đề xuất loại.
- Một người chỉ đóng góp một nhãn cho mỗi bài. Không tăng trọng số vì nộp nhiều, không phạt trực tiếp WA/TLE.
- Ghi số người thử, số AC, số chưa AC, mức phủ nhóm học sinh/lớp và connected components của đồ thị học sinh–bài. Component tách rời hoặc nhóm rất ít dữ liệu được đánh dấu phụ thuộc prior, không trình bày như có so sánh thực nghiệm chắc chắn.
- Chưa có đủ dữ liệu thì giữ điểm khởi tạo; những lần sau giữ điểm công bố trước nếu estimate mới chưa đủ tin cậy.
- Mốc pilot có thể dùng ít nhất 30 người và ít nhất 5 nhãn mỗi phía để xem xét điểm theo dữ liệu. Đây là heuristic thử nghiệm, không phải bảo đảm thống kê; phải điều chỉnh dựa vào độ ổn định và mô phỏng.
- Bài toàn 1/toàn 0 vẫn có estimate hữu hạn nhờ prior/bounds, nhưng không tự công bố ở sát trần/sàn chỉ vì optimizer hội tụ.
- Ghi projected gradient, trạng thái hội tụ, số vòng, thời gian, lượng bài chạm biên, mục tiêu trước/sau; NaN/Inf, thiếu dữ liệu hay hết budget thì run không đủ điều kiện công bố.
- MAP không phải toàn bộ posterior. Nếu xuất độ bất định, dùng phương pháp xấp xỉ được kiểm chứng hoặc bootstrap theo học sinh, ghi tên phương pháp. Không lấy riêng đường chéo Hessian hoặc `hess_inv` optimizer rồi gọi là khoảng tin cậy chính xác.
- Dùng tập nhỏ với suy luận tham chiếu đầy đủ để kiểm tra MAP/uncertainty trong pilot; không chạy MCMC toàn kho định kỳ khi chưa chứng minh cần thiết.

### 8.3. Chống tác động bất thường và giới hạn của mô hình

Trần/sàn chặn việc bài A vượt bậc, khử trùng chặn spam WA cùng tài khoản. Chúng không chặn được nhiều tài khoản cố tình tạo thất bại ở nhiều cặp. Tác vụ chẩn đoán phải báo các đợt nhãn 0 tăng mạnh theo cụm và ảnh hưởng tới điểm; tạm không công bố thay đổi đáng ngờ để quản trị kiểm tra.

Không tự quy kết gian lận hoặc bỏ điểm AC hợp lệ. Quy tắc loại tài khoản khỏi tập hiệu chỉnh chỉ dựa trên chính sách có phiên bản và tín hiệu được nguồn/quản trị xác nhận; dữ liệu dùng học mô hình và quyền nhận điểm là hai quyết định riêng.

Không dùng chia ngẫu nhiên submissions để đánh giá vì cùng học sinh–bài sẽ rò dữ liệu giữa train/test. Benchmark theo cặp và snapshot thời gian, chỉ dùng thông tin có ở thời điểm train. Lưu ý nhãn lifetime 0 có thể thành 1 về sau, đó là cập nhật dữ liệu theo quy tắc đã chọn, không phải bài tự nhiên dễ đi.

V1 không hứa loại được thiên lệch tự chọn bài, xem lời giải hoặc tiến bộ nhiều năm. Đánh giá độ nhạy theo lớp, thời điểm và prior. Nếu không cải thiện so với baseline, giữ điểm khởi tạo thay vì công bố một phân biệt độ khó không có bằng chứng.

## 9. Công bố điểm không tạo trạng thái nửa cũ nửa mới

### 9.1. Các phiên bản cần tách

- `policy_version`: khoảng bậc, prior, eligibility và quy tắc điểm.
- `release_id`: bảng giá trị điểm đã được duyệt, bất biến sau công bố.
- `generation_id`: bộ tổng điểm được dựng cho một release và scope.
- `facts_revision/offset`: kết quả AC đã cập nhật đến đâu.
- `roster_revision`: tập học sinh/quyền/phạm vi để xếp hạng.

Release đứng yên thì điểm từng bài đứng yên. Tổng học sinh vẫn tăng khi có AC mới; vì vậy chỉ có release_id chưa đủ để mô tả một snapshot tổng điểm.

### 9.2. Quy trình

1. Calibration tạo đề xuất và diff, không đụng bảng active.
2. Quản trị duyệt đúng hash của policy + đề xuất + catalog + phạm vi; sửa nội dung phải duyệt lại. Catalog thay đổi liên quan đến grade/scope làm đề xuất cũ không đủ điều kiện công bố.
3. Worker dựng release và generation ứng viên từ một facts snapshot nhất quán, gồm mọi học sinh trong scope, kể cả tổng 0.
4. Trong khi build, luồng active vẫn nhận AC mới; lưu delta bền vững và replay chúng sang ứng viên theo cùng bảng giá ứng viên.
5. Bắt kịp một barrier watermark. Tạm serialize phần commit facts/publish trong khoảng ngắn có giới hạn, kiểm tra candidate hoàn chỉnh; không giữ transaction suốt thời gian fit/build.
6. Trong giao dịch ngắn, khóa active row, kiểm tra expected active revision, policy, catalog, facts offset và lease fencing token; đổi pointer sang generation mới và ghi audit. Nếu delta chưa bắt kịp hoặc khóa quá lâu thì hoãn publish, tiếp tục dùng bản cũ.
7. Tiếp tục áp dụng delta sau barrier vào generation mới. Cache theo generation/revision, không chờ xóa cache hàng loạt để đạt tính đúng.

Mọi API lấy active pointer và dữ liệu liên quan trong cùng một read snapshot, trả metadata phiên bản. Không đọc release mới rồi ghép với tổng cũ ở một request khác mà không phát hiện.

Job publish có idempotency key, trạng thái `APPROVED -> BUILDING -> READY -> PUBLISHED/FAILED`; retry không tạo hai lần công bố. Lease hết hạn thì worker cũ không được tiếp tục commit, kể cả process đó sống lại.

### 9.3. Khôi phục

- Chưa switch pointer: hủy generation lỗi, bản active không bị ảnh hưởng.
- Đã switch: khôi phục bảng điểm cũ bằng cách dựng generation với facts mới nhất rồi switch theo cùng quy trình. Không trỏ thẳng vào tổng cũ đã bỏ lỡ AC mới.
- Báo cáo lịch sử cần tái lập thì giữ release, facts snapshot/manifest và dữ liệu báo cáo tương ứng. Không gọi bảng tổng active đang thay đổi là snapshot lịch sử.
- Có khả năng tắt hiển thị điểm mới và quay về chế độ hiển thị cũ qua feature flag; điểm cũ phải có nguồn/nhãn rõ, không trộn hai thang.

## 10. API đọc và xếp hạng

### 10.1. Hợp đồng dashboard mới

Đề xuất các chức năng API, tên URL chốt khi làm integration:

- Read điểm bài theo lô ID và phân trang; read tổng/đóng góp từng bài của học sinh.
- Read leaderboard theo scope/lớp, tìm kiếm và phân trang server-side.
- Admin đọc/cập nhật policy draft, overrides bậc; chạy sync/calibration; xem diff, duyệt, công bố, khôi phục; đọc job/status.
- Response điểm có `release_id`, `generation_id`, `facts_as_of`, `facts_revision`, `roster_revision`, readiness/coverage và `unscored_solved_count`.
- Ghi policy dùng optimistic concurrency/expected revision. Các thao tác công bố có `expected_active_revision`, idempotency key và quyền admin đã xác minh.

Giữ `source_points`, `submission.points` và điểm tính mới là các trường có ý nghĩa riêng trong quá trình chuyển đổi. `100/100` của một lượt chấm vẫn là kết quả chấm test, không được đổi thành `1.200/1.200` vì bài có giá trị 1.200 điểm thành tích. Không ghi đè các cột gốc qua API đọc.

### 10.2. Xếp hạng và phân trang

- Đọc điểm từ bảng tổng dashboard, sắp xếp theo tổng mới trước khi phân trang.
- Đồng điểm cùng hạng; dùng profile_id để thứ tự trang ổn định. Tính rank trên toàn scope trước bộ lọc tìm kiếm; phân biệt hạng lớp và hạng toàn scope.
- Không lấy một trang `points_desc` từ nguồn rồi đổi điểm/sort lại trong trang đó.
- Đồng bộ roster/membership và metadata tìm kiếm tối thiểu để truy vấn theo lô trong dashboard. Kiểm tra scope/permission hiện tại qua Source API; không dùng cache membership cũ để cấp quyền đã bị thu hồi.
- Cho phép join SQL giữa các bảng dashboard. Metadata thiếu có thể lấy nguồn theo một batch ID của trang; không gọi riêng từng học sinh. Nếu provider chưa có batch/permission revision, phải bổ sung hoặc giới hạn rollout, không tải toàn bộ roster trong mỗi request.
- Với vài chục nghìn profile, thử rank bằng window function/aggregate trên index trong DB; đo `EXPLAIN` và p95 trước khi thêm rank materialization riêng.
- Dùng pagination token gắn scope + release/generation + facts/roster revision. Nếu dữ liệu đổi giữa hai trang thì trả stale/restart hoặc phục vụ snapshot đã giữ, không âm thầm trùng/bỏ hàng.

### 10.3. Các điểm tích hợp cần sửa

`student_catalog_service.py`, `class_student_service.py`, `heatmap_service.py`, API teacher/search/detail; frontend types/API client, trang Students, roster lớp, hồ sơ học sinh và dialog bài.

Không thay AC-count ở cây kỹ năng bằng điểm một cách ngầm định. Nếu thêm chỉ số điểm theo nhóm, hợp tập bài trước khi cộng để nhiều tag cùng nhóm không nhân điểm. Tổng toàn học sinh không bằng phép cộng các nhóm có bài giao nhau.

Tổng tích lũy mặc định all-time. Bộ lọc hoạt động 7/30 ngày hiện hữu không tự đổi tổng này. Điểm trong khoảng thời gian, nếu triển khai, phải là chỉ số riêng theo `first_ac_at`, không tính AC lặp của bài đã giải từ trước thành điểm mới.

Phần giao diện triển khai sau khi backend ổn định; giữ cấu trúc hiện tại theo `DESIGN.md`, không thiết kế lại toàn dashboard. Khi thực hiện UI phải đọc các antislop skill liên quan, audit AFTER toàn repository và chỉ sửa các mục đã được duyệt theo AGENTS.md.

## 11. Hiệu năng và lịch chạy

### 11.1. Quy tắc bắt buộc

- Không fit mô hình, quét submission hoặc backfill trong request đọc.
- Không quét mọi pair khi có một AC. Chỉ cập nhật cặp và học sinh liên quan.
- Worker có client/pool riêng, bắt đầu tối đa 2 request Source API đồng thời, retry có backoff/jitter và `Retry-After`, giảm tốc khi 429/5xx; không nâng semaphore mặc định 20 để tăng tải một cách mù quáng.
- Bulk upsert theo chunk 1.000–5.000 hàng để thử nghiệm; giữ giao dịch ngắn và keyset pagination. Đo packet size, lock waits và query plan trước khi tăng chunk.
- Dataset/fit có budget CPU/RAM/runtime, checkpoint job và cancel ở ranh giới chunk. Vượt budget thì FAILED/RETRY, không công bố dữ liệu một phần.
- Dựng tổng một lần cho mỗi release, sau đó cập nhật delta. Dùng INSERT-SELECT/GROUP BY theo partition trong DB dashboard khi phù hợp, không ORM từng học sinh.
- Redis chứa cache có phiên bản và TTL; Redis hỏng thì đọc DB đúng phiên bản. Job/checkpoint/active pointer không phụ thuộc Redis.
- Chỉ một calibration/publish cùng scope/policy tại một thời điểm. Fit xong giải phóng tài nguyên trước khi xử lý job tiếp.
- Chạy lại không có thay đổi input hash thì bỏ qua fit; nhiều AC mới có thể gom vào một lượt hiệu chỉnh.

### 11.2. Lịch khởi đầu để benchmark

| Tác vụ | Lịch đề xuất |
| --- | --- |
| Đồng bộ facts có feed bền vững | Poll khoảng 1–5 phút, có giới hạn ngân sách |
| Cập nhật tổng active | Cùng giao dịch áp dụng delta, không chờ calibration |
| Đề xuất difficulty | Ban đêm, tối đa một lần/ngày nếu có thay đổi dữ liệu |
| Công bố điểm bài | Theo lượt quản trị duyệt, không tự đổi hàng ngày |
| Đối soát | Hàng ngày khi quy mô cho phép; tăng dần partition nếu cần |

Nếu chỉ có snapshot định kỳ, độ trễ AC phụ thuộc lịch snapshot và thời gian xử lý. Lịch này không phải cam kết near-real-time khi provider chưa có năng lực tương ứng.

### 11.3. Chỉ tiêu đo, chưa phải kết quả đạt

Đo trên cấu hình ghi rõ CPU/RAM, cùng workload, cả cache nóng/lạnh và khi fit đang chạy:

| Chỉ tiêu | Mục tiêu khởi đầu |
| --- | --- |
| Truy vấn tổng/leaderboard trong dashboard DB | p95 dưới 100 ms cho trang thông thường |
| API điểm end-to-end khi upstream quyền khỏe | p95 dưới 500 ms, p99 dưới 1 giây |
| Hồi quy p95 API đọc khi worker fit | Không quá 20% so với baseline cùng tải |
| Tổng điểm đối chiếu | Khớp tuyệt đối integer, không chấp nhận sai số |
| Điểm từng bài | 100% trong band/step, không NaN/Inf hoặc point_value âm |
| Độ trễ sync | Đo từ commit nguồn đến facts active; báo watermark, không chỉ thời điểm worker chạy |
| Fit/build/backfill | Ghi thời gian, peak RSS, request/byte và số hàng quét; đặt SLO sau pilot |

Thử dataset fixture thật và synthetic tăng số pair 5x/10x, kèm nhiều người AC cùng bài, nhiều profile 0 điểm, nhiều tag, nhiều lớp trùng học sinh. Số bài 4.541 không đủ để dự đoán tải; P là số cặp học sinh–bài quan sát và S là số submission nguồn mới quyết định chi phí đồng bộ.

## 12. Kiểm thử và tiêu chí nghiệm thu

### 12.1. Tính đúng nghiệp vụ/dữ liệu

- Cặp chưa làm/WA-only/AC-only/WA rồi AC/AC rồi WA; một và rất nhiều lượt nộp cho cùng cặp.
- Đến muộn 0 -> 1, rejudge mất AC cuối/không mất AC cuối, xóa lượt nộp, tất cả lượt còn pending, tombstone.
- Một học sinh nhiều lớp, bài nhiều tag, tên/profile trùng, chưa ghi danh lớp; không đếm đôi.
- Grade NULL/Uncategorized/ID lạ; override; đổi bậc trong lúc fit/build; dữ liệu catalog thay đổi giữa page.
- Chạy lại cùng batch/event hai lần không đổi tổng; event cũ đến sau event mới không làm lùi trạng thái.
- Cùng release/facts, tổng batch bằng tổng delta và bằng phép tính trực tiếp trên tập AC. Mọi học sinh giải cùng bài có cùng đóng góp.
- Học sinh chưa đồng bộ không bị gán tổng 0; bài thiếu grade không bị biến thành 0 điểm đã xác nhận.
- Không có mùa và không khóa điểm theo ngày AC; thay bảng giá cập nhật đồng loạt.

### 12.2. Mô hình

- Kiểm tra gradient giải tích bằng finite difference trên fixture nhỏ; bound, prior/anchor, chuẩn hóa và làm tròn.
- Dataset mô phỏng có độ khó biết trước: thu hồi đúng thứ tự trong điều kiện đủ dữ liệu; điều kiện thiếu dữ liệu được đánh dấu.
- Cold/warm start trên input giống nhau cho kết quả tương đương trong tolerance đã định.
- Bài không có người thử, toàn AC, toàn chưa AC, học sinh một quan sát, component tách rời: hữu hạn và đúng trạng thái.
- So sánh với điểm đầu theo grade và baseline tỷ lệ AC có làm trơn. Đánh giá log loss/Brier và calibration theo bậc/lớp; không chỉ dùng độ khớp trên tập train.
- Chia theo snapshot thời gian, tránh rò tương lai và cùng cặp. Kiểm tra độ nhạy prior và ổn định qua các mẫu học sinh.
- Mô phỏng spam WA cùng tài khoản không thay input nhị phân; tấn công nhiều tài khoản vẫn bị band và cảnh báo chẩn đoán.

### 12.3. Giao dịch, lỗi và quyền

- Worker bị kill ở trước/sau commit và trước/sau acknowledge, lease hết hạn, job bị nhận hai lần, hai admin publish cùng lúc.
- Có AC mới trong lúc build và đúng thời điểm switch; không mất/cộng đôi điểm.
- Redis down, provider 429/timeout/5xx, cursor hết hạn, feed hết retention, DB deadlock/disk-full; active cũ vẫn đọc đúng hoặc báo trạng thái không sẵn sàng rõ ràng.
- Rollback điểm bài nhưng vẫn giữ AC mới; retry rollback/publish không tạo bản công bố trùng.
- Teacher không đọc được student/private problem ngoài quyền qua leaderboard, tổng, details, cache, job hoặc export. Cache có account/scope/version, xóa account cache khi đổi đăng nhập.
- Xếp hạng đúng toàn scope trước search, đúng tie và ranh giới page; không sắp xếp lại riêng từng page nguồn.
- Migration một head, upgrade/check trên DB trống và bản sao; downgrade/reupgrade chỉ trên fixture độc lập.

Không tuyên bố “mô hình chính xác” chỉ vì optimizer hội tụ hoặc tổng cộng đúng. Tách nghiệm thu tính đúng hệ thống với nghiệm thu mức phù hợp của ước lượng độ khó.

## 13. Thứ tự triển khai và đầu ra từng giai đoạn

| Giai đoạn | Công việc | Đầu ra/điều kiện chuyển tiếp |
| --- | --- | --- |
| 0. Audit và policy | Đo P/S/profile, eligible catalog, phân bố grade, verdict; kiểm tra provider capabilities và quyền; thử các band | Báo cáo dữ liệu, policy draft, phương án 317 bài, benchmark baseline; chốt scope và band trước công bố |
| 1. Contract và schema | Spec bulk snapshot/changes/roster; mock và contract tests; bảng dashboard/migration/job | Backfill pilot có manifest đúng, không source SQL ở runtime, migration một head |
| 2. Đồng bộ facts | Backfill, checkpoint, delta, rejudge, reconciliation, chống trùng | Full snapshot/delta cho cùng kết quả; kill/resume/replay không sai lệch |
| 3. Hiệu chỉnh offline | Bounded Rasch MAP, kiểm tra gradient, quality report và band | Đề xuất tái lập được, benchmark và chẩn đoán; chưa thay điểm người dùng |
| 4. Tổng điểm và công bố | Baseline release để test, generation build/replay/barrier, publish/rollback, read API | AC tới trong lúc publish không mất; tổng integer đối chiếu tuyệt đối; leaderboard đúng |
| 5. Tích hợp | Gắn field mới và service xếp hạng, batch metadata, frontend type/cache; admin review | Hiển thị nhất quán nguồn điểm, phiên bản và độ trễ; UI theo DESIGN/ANTISLOP |
| 6. Chạy song song và mở dùng | Shadow trên fixture/full scope được cấp quyền, load/fault test, xử lý sai lệch, kiểm tra 317 bài | Báo cáo chất lượng/hiệu năng; coverage và policy được duyệt; mới bật feature flag |

Các giai đoạn 2 và 3 có thể phát triển dựa trên cùng fixture contract khi schema đã ổn định, nhưng fit không chạy trên staging chưa hoàn tất. Giai đoạn 4 có thể kiểm tra bằng bảng điểm đầu cố định trước khi mô hình đủ chất lượng. Không cần triển khai 2PL ở V1.

Không chốt lịch ngày công chỉ từ số bài. Sau giai đoạn 0–1 mới có dữ liệu về pair volume, provider thiếu gì và nhu cầu phân bậc; cập nhật estimate theo kết quả đó.

## 14. Bản đồ file dự kiến

| Phần | File/module |
| --- | --- |
| Models và migration | `backend/app/models/scoring.py`, đăng ký `models/dashboard.py`, revision mới trong `backend/migrations/versions/` |
| Gateway/contracts | Mở rộng `services/source_gateway.py`; route/schema/mock query trong `source_api_mock/`; contract tests hai phía |
| Worker | `backend/app/scoring/worker.py`, `jobs.py`, `sync.py`, `dataset.py`, `calibration.py`, `publication.py`, `reconciliation.py` |
| Serving | `backend/app/services/scoring_service.py`, `backend/app/schemas/scoring.py`, endpoint read/admin và router |
| Integration | `student_catalog_service.py`, `class_student_service.py`, `heatmap_service.py`, teacher endpoints; không dùng lại source rank cho score mới |
| Infrastructure | Service `scoring-worker` trong Compose, dependency pin cho worker, volume dataset, CPU/RAM/thread budgets, health/lag metrics |
| Frontend | API/types/query keys và các nơi hiển thị điểm; sửa vừa đủ phạm vi sau khi backend contract chốt |
| Verification | Test scoring unit/integration/fault/model; script data audit/reconcile/load benchmark; tài liệu vận hành |

Có thể dùng image worker riêng hoặc build target riêng để NumPy/SciPy và dataset không làm nặng đường API không cần thiết. Pool DB/HTTP tạo một lần cho worker và đóng đúng lifecycle; không mở kết nối mỗi cặp.

## 15. Checklist trước bật chính thức

- [ ] Band, bước làm tròn, prior, verdict eligibility và scope đã được ghi vào policy bất biến.
- [ ] Các bài chưa có grade trong phạm vi chính thức đã được xử lý; không giấu điểm chưa tính.
- [ ] Source contract có snapshot đúng và kế hoạch nhận thay đổi/reconciliation khả thi; quyền worker được provider xác nhận.
- [ ] Không có SQL/kết nối DB nguồn trong dashboard runtime; mọi schema mới thuộc dashboard và migration đã kiểm chứng.
- [ ] Full rebuild khớp incremental và oracle trên dữ liệu thật được cấp quyền.
- [ ] Mô hình được kiểm tra tính phù hợp và độ nhạy, các bài ít bằng chứng giữ điểm đầu/cũ.
- [ ] Publish/rollback qua barrier đã qua kiểm thử có AC/rejudge đồng thời.
- [ ] Toàn bộ nơi hiển thị/sắp xếp điểm đã dùng đúng metric, scope và version.
- [ ] Đã đo p95/p99, RSS, lượng request nguồn khi worker đang chạy và khi cache/Redis lỗi.
- [ ] Có audit người duyệt, metric sync lag, job stalled, score mismatch, band saturation; hướng dẫn xử lý và feature flag khôi phục.
- [ ] Khi có thay đổi UI: kiểm thử frontend/build/browser và audit antislop AFTER theo quy trình repository.

## 16. Nguồn kỹ thuật đã đối chiếu

- Kiến trúc và quyền: [DB_ARCHITECTURE.md](../backend/DB_ARCHITECTURE.md).
- Hợp đồng/giới hạn hiện tại: [Source API mock README](../source_api_mock/README.md) và `SourceGateway` trong repository.
- Bộ tối ưu giới hạn: [SciPy L-BFGS-B](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-lbfgsb.html).
- Log sigmoid ổn định số học: [SciPy log_expit](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.log_expit.html).
- Lựa chọn prior ảnh hưởng ước lượng IRT, nhất là ít dữ liệu: [Bayesian Prior Choice in IRT Estimation](https://pmc.ncbi.nlm.nih.gov/articles/PMC5037236/).

Chỉ tiêu hiệu năng, khoảng điểm và ngưỡng dữ liệu trong kế hoạch là đề xuất cần benchmark/duyệt, không phải kết quả đã đạt. Lượt này chỉ tạo kế hoạch, không thêm migration, không chạy hiệu chỉnh hoặc thay điểm người dùng.

from copy import deepcopy


ROOTS = [
    ("foundation", "Nền tảng lập trình", "Biến, biểu thức, điều khiển, hàm, kiểu dữ liệu và thao tác cơ bản.", [4, 5, 6, 7, 8, 10, 22, 33, 47, 59]),
    ("sequences", "Sắp xếp, tìm kiếm và xử lý dãy", "Sắp xếp, tìm kiếm, mảng, ma trận, hai con trỏ và tổng tiền tố.", [24, 25, 45, 74, 87, 88, 90, 94, 103, 105, 106]),
    ("enumeration", "Duyệt, quay lui và chia để trị", "Sinh cấu hình, vét cạn, đệ quy, quay lui, nhánh cận và chia để trị.", [13, 16, 17, 18, 20, 54, 91]),
    ("data-structures", "Cấu trúc dữ liệu", "STL, map, set, stack, queue, heap, DSU, Fenwick, segment tree và phân rã căn.", [23, 27, 28, 37, 38, 39, 44, 56, 58, 92, 96, 108, 110]),
    ("strings", "Xử lý xâu", "Xâu ký tự, tìm mẫu, hashing xâu và các thuật toán xử lý xâu.", [9, 26, 62, 75]),
    ("dp", "Quy hoạch động", "Trạng thái và chuyển trạng thái: dãy, bảng, chữ số, bitmask, cây và tối ưu quy hoạch động.", [14, 31, 61, 63, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 89]),
    ("graphs", "Đồ thị và cây", "Duyệt đồ thị, đường đi, liên thông, cây khung, luồng và thuật toán trên cây.", [15, 29, 30, 35, 40, 55, 57, 64, 93, 98, 99, 104]),
    ("math", "Toán học và số học", "Số học, tổ hợp, xác suất, lý thuyết số, đại số và các phép toán bit.", [11, 19, 32, 49, 52, 60, 66, 67, 68, 69, 70, 71, 72, 73, 95, 97, 100, 101, 102, 107]),
    ("geometry", "Hình học", "Điểm, đường, góc, đa giác và hình học tính toán.", [12]),
    ("greedy", "Tham lam", "Chọn phương án cục bộ có cơ sở để đạt mục tiêu toàn cục.", [21]),
    ("other", "Khác", "Tag tổng hợp, nhãn kỳ thi và các dạng chưa phân loại vào nhóm chuyên môn.", [36, 42, 43, 65]),
]
FIXED_NODES = [{"id": key, "title": title, "description": description, "parent_id": None}
               for key, title, description, _ in ROOTS]
DEFAULT_ASSIGNMENTS = {str(tag): key for key, _, _, tags in ROOTS for tag in tags}


def fixed_document():
    return {"nodes": deepcopy(FIXED_NODES), "assignments": dict(DEFAULT_ASSIGNMENTS)}

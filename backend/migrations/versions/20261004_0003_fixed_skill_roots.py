"""Fix the specialty roots and preserve the previous configuration snapshot."""
from alembic import op
import sqlalchemy as sa
import json
from datetime import datetime

revision = "20261004_0003"
down_revision = "20261004_0002"
branch_labels = None
depends_on = None
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


def converted_document(old):
    result = fixed_document()
    nodes = {node["id"]: node for node in old.get("nodes", [])}
    aliases = {title.casefold(): key for key, title, _, _ in ROOTS}
    aliases.update({"dp": "dp", "đồ thị": "graphs", "số học": "math"})
    for tag, node_id in old.get("assignments", {}).items():
        seen = set()
        while node_id in nodes and nodes[node_id].get("parent_id"):
            if node_id in seen:
                raise RuntimeError("Cyclic legacy skill configuration")
            seen.add(node_id)
            node_id = nodes[node_id]["parent_id"]
        root = nodes.get(node_id)
        key = aliases.get(root["title"].casefold()) if root else None
        if key is None:
            raise RuntimeError("Legacy assigned root requires an explicit mapping before migration: " + str(node_id))
        result["assignments"][str(tag)] = key
    return result


def upgrade():
    connection = op.get_bind()
    table = sa.table("skill_configuration", sa.column("id", sa.Integer),
        sa.column("draft", sa.JSON), sa.column("published", sa.JSON),
        sa.column("proposals", sa.JSON), sa.column("revision", sa.Integer),
        sa.column("published_version", sa.Integer), sa.column("updated_at", sa.DateTime),
        sa.column("taxonomy_backup", sa.JSON), sa.column("taxonomy_version", sa.Integer))
    row = connection.execute(sa.select(table.c.id, table.c.draft, table.c.published,
        table.c.proposals, table.c.revision, table.c.published_version).where(table.c.id == 1)).mappings().one()
    snapshot = dict(row)
    document = converted_document(row["draft"])
    op.add_column("skill_configuration", sa.Column("taxonomy_backup", sa.JSON, nullable=True))
    op.add_column("skill_configuration", sa.Column("taxonomy_version", sa.Integer, nullable=False, server_default="0"))
    connection.execute(table.update().where(table.c.id == 1).values(
        taxonomy_backup=snapshot, taxonomy_version=1, draft=document, published=document,
        revision=row["revision"] + 1, published_version=row["published_version"] + 1,
        updated_at=datetime.utcnow()))


def downgrade():
    connection = op.get_bind()
    raw = connection.execute(sa.text("SELECT taxonomy_backup FROM skill_configuration WHERE id=1")).scalar_one()
    snapshot = json.loads(raw) if isinstance(raw, str) else raw
    table = sa.table("skill_configuration", sa.column("id", sa.Integer),
        sa.column("draft", sa.JSON), sa.column("published", sa.JSON), sa.column("proposals", sa.JSON),
        sa.column("revision", sa.Integer), sa.column("published_version", sa.Integer))
    if snapshot:
        connection.execute(table.update().where(table.c.id == 1).values(
            **{key: snapshot[key] for key in ("draft", "published", "proposals", "revision", "published_version")}))
    op.drop_column("skill_configuration", "taxonomy_version")
    op.drop_column("skill_configuration", "taxonomy_backup")
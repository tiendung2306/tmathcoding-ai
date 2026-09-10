import re
from typing import Dict, Any, List, Optional, Tuple

DIFFICULTY_WEIGHTS: Dict[Optional[int], float] = {
    4: 1.0,   # Mức A - Nhớ (Cơ bản)
    5: 1.4,   # Mức B - Hiểu (Trung bình)
    6: 2.0,   # Mức C - Vận dụng (Khá)
    7: 2.8,   # Mức D - Phân tích (Khó)
    8: 3.8,   # Mức E - Đánh giá (Nâng cao)
    13: 5.0,  # Mức F - Sáng tạo (Olympic)
}
DEFAULT_DIFFICULTY_WEIGHT = 1.2

DIFFICULTY_TARGETS: Dict[str, Dict[str, float]] = {
    "quy_hoach_dong": {"all": 38.0, "1y": 22.0, "30d": 9.0, "7d": 4.5, "1d": 1.5},
    "cau_truc_du_lieu": {"all": 32.0, "1y": 19.0, "30d": 8.0, "7d": 3.5, "1d": 1.5},
    "xu_ly_xau": {"all": 30.0, "1y": 18.0, "30d": 7.5, "7d": 3.0, "1d": 1.5},
    "ham_co_ban": {"all": 39.0, "1y": 25.0, "30d": 10.0, "7d": 5.0, "1d": 2.5},
    "toan_hoc": {"all": 36.0, "1y": 22.0, "30d": 9.0, "7d": 4.5, "1d": 1.5},
    "hinh_hoc": {"all": 16.0, "1y": 10.0, "30d": 5.0, "7d": 2.0, "1d": 1.5},
    "do_thi": {"all": 38.0, "1y": 23.0, "30d": 9.0, "7d": 4.5, "1d": 1.5},
    "tham_lam": {"all": 22.0, "1y": 15.0, "30d": 6.0, "7d": 3.0, "1d": 1.5},
}


def analyze_source_code(source: str) -> Tuple[float, List[Dict[str, Any]]]:
    """Phân tích tĩnh mã nguồn C++ hoặc Python để chấm điểm chất lượng."""
    if not source:
        return 0.0, []

    score = 0.0
    items: List[Dict[str, Any]] = []

    # 1. Fast I/O (+2.0)
    if "sync_with_stdio" in source or "cin.tie" in source or "sys.stdin.readline" in source:
        score += 2.0
        items.append({
            "label": "Tối ưu I/O (Fast I/O)",
            "val": 2.0,
            "type": "bonus",
            "desc": "Sử dụng Fast I/O giúp tăng tốc độ đọc ghi dữ liệu"
        })

    # 2. Cấu trúc hàm / module (+3.0)
    cpp_funcs = re.findall(r"\b(void|int|long long|bool|double|string|auto)\s+([a-zA-Z0-9_]+)\s*\([^)]*\)\s*\{", source)
    custom_cpp = [f[1] for f in cpp_funcs if f[1] not in ["main", "if", "while", "for", "switch"]]
    py_funcs = re.findall(r"\bdef\s+([a-zA-Z0-9_]+)\s*\(", source)
    has_modular = len(custom_cpp) >= 1 or len(py_funcs) >= 2 or "struct " in source or "class " in source

    if has_modular:
        score += 3.0
        items.append({
            "label": "Cấu trúc hàm/module rõ ràng",
            "val": 3.0,
            "type": "bonus",
            "desc": "Tách nhỏ giải thuật thành các hàm xử lý chuyên biệt"
        })

    # 3. Ứng dụng cấu trúc dữ liệu chuẩn (+3.0)
    stl_matches = re.findall(r"\b(vector|map|unordered_map|set|unordered_set|queue|priority_queue|stack|deque|pair)\s*<", source)
    py_std = re.findall(r"\b(deque|defaultdict|Counter|heapq)\b", source)
    has_optimal_ds = bool(stl_matches or py_std or "#pragma GCC optimize" in source)

    if has_optimal_ds:
        score += 3.0
        items.append({
            "label": "Ứng dụng CTDL chuẩn tối ưu",
            "val": 3.0,
            "type": "bonus",
            "desc": "Sử dụng container hoặc chỉ thị tối ưu biên dịch chuẩn"
        })

    # 4. Kiểm tra gian lận / hardcode test (-8.0)
    hardcode_matches = re.findall(r"if\s*\([^)]*==[^)]*\)\s*(?:return|cout\s*<<|print\()", source)
    if len(hardcode_matches) >= 4:
        score -= 8.0
        items.append({
            "label": "Nghi vấn hardcode kết quả test case",
            "val": -8.0,
            "type": "penalty",
            "desc": "Phát hiện nhiều nhánh if-else in sẵn đáp án theo test case"
        })

    clamped_score = max(-10.0, min(10.0, score))
    return clamped_score, items


class CompetencyEvaluator:
    """Động cơ tính toán Năng lực Thuật toán Đa chiều với cơ chế Cộng/Trừ điểm."""

    @staticmethod
    def evaluate_pillar(
        pillar_key: str,
        time_range: str,
        submissions: List[Dict[str, Any]],
        problems_map: Dict[int, Dict[str, Any]],
        sample_sources: List[str],
    ) -> Dict[str, Any]:
        breakdown_items: List[Dict[str, Any]] = []

        # Tách danh sách bài AC
        ac_problems_set = set()
        ac_counts_by_group: Dict[Optional[int], int] = {}
        for pid, pdata in problems_map.items():
            if pdata.get("is_ac"):
                ac_problems_set.add(pid)
                gid = pdata.get("group_id")
                ac_counts_by_group[gid] = ac_counts_by_group.get(gid, 0) + 1

        ac_count = len(ac_problems_set)
        total_problems = len(problems_map)
        total_subs = len(submissions)

        # ----------------------------------------------------
        # THÀNH PHẦN 1: ĐIỂM NỀN TẢNG ĐỘ KHÓ (0 - 50đ)
        # ----------------------------------------------------
        if ac_count > 0:
            diff_sum = sum(
                DIFFICULTY_WEIGHTS.get(problems_map[pid].get("group_id"), DEFAULT_DIFFICULTY_WEIGHT)
                for pid in ac_problems_set
            )
            target_obj = DIFFICULTY_TARGETS.get(pillar_key, {})
            target_diff = target_obj.get(time_range, target_obj.get("all", 30.0))
            base_score = min(50.0, round((diff_sum / target_diff) * 50.0, 1)) if target_diff > 0 else 0.0

            # Tạo mô tả chi tiết độ khó
            group_desc_parts = []
            for gid, count in sorted(ac_counts_by_group.items(), key=lambda x: (x[0] or 0)):
                label = "Mức A" if gid == 4 else "Mức B" if gid == 5 else "Mức C" if gid == 6 else "Mức D" if gid == 7 else "Mức E" if gid == 8 else "Mức F" if gid == 13 else "Chưa phân mức"
                group_desc_parts.append(f"{count} {label}")
            group_desc = ", ".join(group_desc_parts)

            breakdown_items.append({
                "label": f"Điểm nền tảng ({ac_count} bài AC: {group_desc})",
                "val": base_score,
                "type": "base",
                "desc": f"Tích lũy theo độ khó bài toán (đạt {diff_sum:.1f}/{target_diff:.1f} chỉ tiêu)"
            })
        else:
            base_score = 0.0
            breakdown_items.append({
                "label": "Chưa có bài giải đúng (AC) trong kỳ",
                "val": 0.0,
                "type": "base",
                "desc": "Chưa ghi nhận bài toán hoàn thành"
            })

        # ----------------------------------------------------
        # THÀNH PHẦN 2: HÀNH VI NỘP BÀI (±15đ)
        # ----------------------------------------------------
        precision_mod = 0.0
        if ac_count > 0:
            clean_solves = sum(
                1 for pid in ac_problems_set if problems_map[pid].get("fail_before_ac", 0) <= 1
            )
            clean_rate = clean_solves / ac_count if ac_count > 0 else 0.0

            if clean_rate >= 0.70:
                precision_mod += 6.0
                breakdown_items.append({
                    "label": f"Thưởng độ chuẩn xác ({clean_rate * 100:.0f}% bài giải đúng trong 1-2 lần nộp)",
                    "val": 6.0,
                    "type": "bonus",
                    "desc": "Tư duy mạch lạc, tự kiểm thử tốt trước khi nộp"
                })
            elif clean_rate >= 0.50:
                precision_mod += 3.0
                breakdown_items.append({
                    "label": f"Thưởng giải bài gọn gàng ({clean_rate * 100:.0f}% bài đạt chuẩn 1-2 lần nộp)",
                    "val": 3.0,
                    "type": "bonus",
                    "desc": "Số lần thử sai tương đối ít"
                })

            ac_ratio = ac_count / total_problems if total_problems > 0 else 0.0
            if ac_ratio >= 0.60:
                precision_mod += 4.0
                breakdown_items.append({
                    "label": f"Thưởng kiên định ({ac_ratio * 100:.0f}% bài đã thử đạt AC)",
                    "val": 4.0,
                    "type": "bonus",
                    "desc": "Hoàn thành trọn vẹn phần lớn các bài toán đã bắt tay giải"
                })
            elif ac_ratio < 0.25 and total_problems >= 4:
                precision_mod -= 4.0
                breakdown_items.append({
                    "label": f"Trừ điểm bỏ dở (chỉ {ac_ratio * 100:.0f}% bài bắt đầu đạt AC)",
                    "val": -4.0,
                    "type": "penalty",
                    "desc": "Có dấu hiệu bỏ cuộc sau vài lần nộp thử hỏng"
                })

            # Phạt bài nộp chật vật (>= 5 lần thử sai)
            struggle_count = sum(
                1 for pid in problems_map if problems_map[pid].get("fail_before_ac", 0) >= 5
            )
            if struggle_count > 0:
                p_deduct = min(6.0, round(struggle_count * 1.5, 1))
                precision_mod -= p_deduct
                breakdown_items.append({
                    "label": f"Trừ điểm thử sai nhiều ({struggle_count} bài nộp sai >= 5 lần)",
                    "val": -p_deduct,
                    "type": "penalty",
                    "desc": "Nên kiểm tra lại thuật toán trên nháp/IDE trước khi nộp dồn dập"
                })

            # Phạt nộp quá dồn dập (< 30s giữa các lần nộp sai)
            rapid_count = 0
            for i in range(1, len(submissions)):
                s_prev = submissions[i - 1]
                s_curr = submissions[i]
                if (
                    s_prev.get("problem_id") == s_curr.get("problem_id")
                    and s_prev.get("result") != "AC"
                    and s_curr.get("date")
                    and s_prev.get("date")
                ):
                    dt = (s_curr["date"] - s_prev["date"]).total_seconds()
                    if 0 < dt < 30:
                        rapid_count += 1
            if rapid_count >= 2:
                precision_mod -= 3.0
                breakdown_items.append({
                    "label": "Trừ điểm spam nộp bài liên tiếp",
                    "val": -3.0,
                    "type": "penalty",
                    "desc": f"Phát hiện {rapid_count} lần nộp bài cách nhau dưới 30 giây"
                })

        precision_mod = max(-15.0, min(15.0, precision_mod))

        # ----------------------------------------------------
        # THÀNH PHẦN 3: HIỆU NĂNG THỰC THI (±15đ)
        # ----------------------------------------------------
        efficiency_mod = 0.0
        time_ratios = [
            problems_map[pid]["ac_time"] / problems_map[pid]["time_limit"]
            for pid in ac_problems_set
            if problems_map[pid].get("time_limit", 0) > 0
        ]
        avg_time_ratio = sum(time_ratios) / len(time_ratios) if time_ratios else 0.5
        tle_count = sum(1 for s in submissions if s.get("result") == "TLE")
        mle_count = sum(1 for s in submissions if s.get("result") == "MLE")

        if ac_count > 0:
            if avg_time_ratio < 0.20:
                efficiency_mod += 8.0
                breakdown_items.append({
                    "label": f"Thưởng tốc độ vượt trội (chạy trung bình {avg_time_ratio * 100:.0f}% Time limit)",
                    "val": 8.0,
                    "type": "bonus",
                    "desc": "Áp dụng thuật toán có độ phức tạp tiệm cận tối ưu"
                })
            elif avg_time_ratio < 0.50:
                efficiency_mod += 4.0
                breakdown_items.append({
                    "label": f"Thưởng tốc độ tốt (chạy trung bình {avg_time_ratio * 100:.0f}% Time limit)",
                    "val": 4.0,
                    "type": "bonus",
                    "desc": "Thuật toán xử lý nhanh và an toàn"
                })
            elif avg_time_ratio > 0.80:
                efficiency_mod -= 3.0
                breakdown_items.append({
                    "label": f"Trừ điểm chạy sát nút ({avg_time_ratio * 100:.0f}% Time limit)",
                    "val": -3.0,
                    "type": "penalty",
                    "desc": "Thuật toán có nguy cơ TLE trên các bộ test lớn"
                })

            if tle_count == 0 and ac_count >= 3:
                efficiency_mod += 3.0
                breakdown_items.append({
                    "label": "Thưởng kiểm soát độ phức tạp (0 bài TLE)",
                    "val": 3.0,
                    "type": "bonus",
                    "desc": "Tuyệt đối không bị lỗi vượt quá thời gian"
                })
            elif tle_count >= 5:
                efficiency_mod -= 5.0
                breakdown_items.append({
                    "label": f"Trừ điểm lỗi thời gian ({tle_count} lần dính TLE)",
                    "val": -5.0,
                    "type": "penalty",
                    "desc": "Cần tối ưu cấu trúc lặp hoặc nâng cấp giải thuật"
                })
            elif tle_count >= 2:
                efficiency_mod -= 2.5
                breakdown_items.append({
                    "label": f"Trừ điểm lỗi thời gian ({tle_count} lần dính TLE)",
                    "val": -2.5,
                    "type": "penalty",
                    "desc": "Từng gặp sự cố quá thời gian thực thi"
                })

            if mle_count == 0:
                efficiency_mod += 1.0
            else:
                efficiency_mod -= 2.0
                breakdown_items.append({
                    "label": f"Trừ điểm tràn bộ nhớ ({mle_count} lần dính MLE)",
                    "val": -2.0,
                    "type": "penalty",
                    "desc": "Cần lưu ý giới hạn cấp phát bộ nhớ mảng"
                })

        efficiency_mod = max(-15.0, min(15.0, efficiency_mod))

        # ----------------------------------------------------
        # THÀNH PHẦN 4: CHẤT LƯỢNG MÃ NGUỒN (±10đ)
        # ----------------------------------------------------
        code_quality_mod = 0.0
        if sample_sources and ac_count > 0:
            # Lấy mẫu phân tích 2-3 code tiêu biểu
            scores = []
            for src in sample_sources[:3]:
                sc, src_items = analyze_source_code(src)
                scores.append((sc, src_items))
            if scores:
                avg_code_score = sum(s[0] for s in scores) / len(scores)
                code_quality_mod = round(avg_code_score, 1)
                # Đưa các item giải thích tiêu biểu vào
                seen_labels = set()
                for _, src_items in scores:
                    for it in src_items:
                        if it["label"] not in seen_labels:
                            seen_labels.add(it["label"])
                            breakdown_items.append(it)
        else:
            code_quality_mod = 0.0

        code_quality_mod = max(-10.0, min(10.0, code_quality_mod))

        # ----------------------------------------------------
        # TÍNH TỔNG ĐIỂM NĂNG LỰC
        # ----------------------------------------------------
        raw_total = base_score + precision_mod + efficiency_mod + code_quality_mod
        final_score = max(0.0, min(100.0, round(raw_total, 1)))

        return {
            "score": final_score,
            "base_score": base_score,
            "precision_mod": precision_mod,
            "efficiency_mod": efficiency_mod,
            "code_quality_mod": code_quality_mod,
            "ac_count": ac_count,
            "total_subs": total_subs,
            "avg_time_ratio": round(avg_time_ratio, 2),
            "breakdown_items": breakdown_items,
        }

import re
from typing import Any, Dict, List

class FeatureExtractor:
    """
    Trích xuất đặc trưng thuật toán và cấu trúc dữ liệu từ mã nguồn AC (C++/Python)
    và ràng buộc N từ mô tả bài toán theo chuẩn SDD §4.3.
    """

    # Bảng chuyển chữ số superscript Unicode (⁵ -> 5)
    _SUPERSCRIPT_MAP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
    # Dạng nhân hệ số 10 mũ: "2*10^5", "2·10⁵", "2 x 10**5"
    _SCIENTIFIC_MUL_RE = re.compile(
        r'([0-9]+(?:[.,][0-9]+)?)\s*[*×·x]\s*10\s*(?:\^|\*\*)?\s*([0-9]+|[⁰¹²³⁴⁵⁶⁷⁸⁹]+)'
    )

    @classmethod
    def _normalize_number_notation(cls, text: str) -> str:
        """
        Chuẩn hóa các cách ghi số khoa học về số thập phân trước khi bóc tách:
        "2*10^5" -> "200000", "10⁵" -> "10^5".
        Nếu không chuẩn hóa, regex sẽ chỉ bắt được hệ số nhân (2) và mất đi
        số mũ, dẫn tới suy luận sai độ phức tạp thuật toán.
        """
        def replace_multiplied(match: "re.Match[str]") -> str:
            base = float(match.group(1).replace(",", "."))
            exponent = int(match.group(2).translate(cls._SUPERSCRIPT_MAP))
            return str(int(base * (10 ** exponent)))

        normalized = cls._SCIENTIFIC_MUL_RE.sub(replace_multiplied, text)
        normalized = re.sub(
            r'([0-9]+)\s*([⁰¹²³⁴⁵⁶⁷⁸⁹]+)',
            lambda m: f"{m.group(1)}^{m.group(2).translate(cls._SUPERSCRIPT_MAP)}",
            normalized,
        )
        return normalized

    @classmethod
    def extract_constraints(cls, description: str) -> Dict[str, Any]:
        """
        Trích xuất các giới hạn N, M, K và ràng buộc thời gian từ văn bản đề bài.
        """
        constraints = {
            "n_limit_str": None,
            "n_max_val": None,
            "complexity_expectation": "Chưa xác định",
        }

        if not description:
            return constraints

        description = cls._normalize_number_notation(description)

        # 1. Tìm các biểu thức N <= 10^5, N <= 1000, 1 <= N <= 20, 10**5...
        patterns = [
            r'([Nn]|[Mm]|[Kk])\s*(?:\\le|<=|≤)\s*([0-9]+(?:\^[0-9]+|\*\*[0-9]+|(?:\.[0-9]+)?e\+?[0-9]+)?)',
            r'(?:\\le|<=|≤)\s*([Nn]|[Mm]|[Kk])\s*(?:\\le|<=|≤)\s*([0-9]+(?:\^[0-9]+|\*\*[0-9]+|(?:\.[0-9]+)?e\+?[0-9]+)?)',
            r'([Nn]|[Mm]|[Kk])\s*=\s*([0-9]+(?:\^[0-9]+|\*\*[0-9]+)?)',
            r'([0-9]+(?:\^[0-9]+|\*\*[0-9]+)?)\s*phần tử',
        ]

        found_limits = []
        for pat in patterns:
            matches = re.findall(pat, description)
            for m in matches:
                val_str = m[1] if isinstance(m, tuple) and len(m) > 1 else (m[0] if isinstance(m, tuple) else m)
                found_limits.append(str(val_str).strip())

        # Chuẩn hóa giá trị N lớn nhất phát hiện được
        max_n = None
        for raw in found_limits:
            try:
                # Xử lý 10^5 hoặc 10**5
                if '^' in raw:
                    base, exp = raw.split('^')
                    val = int(base) ** int(exp)
                elif '**' in raw:
                    base, exp = raw.split('**')
                    val = int(base) ** int(exp)
                elif 'e' in raw.lower():
                    val = int(float(raw))
                else:
                    val = int(re.sub(r'[^0-9]', '', raw))
                
                if val > 0 and (max_n is None or val > max_n):
                    max_n = val
                    constraints["n_limit_str"] = raw
            except Exception:
                continue

        constraints["n_max_val"] = max_n

        # Suy luận độ phức tạp thuật toán dựa trên N theo SDD §4.3
        if max_n is not None:
            if max_n <= 20:
                constraints["complexity_expectation"] = "O(2^N) hoặc O(N!) - Bitmask DP / Quay lui (Backtracking)"
            elif max_n <= 100:
                constraints["complexity_expectation"] = "O(N^3) đến O(N^4) - Floyd-Warshall / Nhân ma trận / DP 3D"
            elif max_n <= 500:
                constraints["complexity_expectation"] = "O(N^3) - Quy hoạch động / Duyệt đồ thị bậc 3"
            elif max_n <= 5000:
                constraints["complexity_expectation"] = "O(N^2) - Quy hoạch động 2D / 2 vòng lặp lồng nhau"
            elif max_n <= 200000:
                constraints["complexity_expectation"] = "O(N log N) hoặc O(N) - Sắp xếp / Segment Tree / Fenwick / Binary Search / BFS"
            elif max_n <= 1000000:
                constraints["complexity_expectation"] = "O(N) hoặc O(N log N) - Duyệt tuyến tính / Hash / Sàng nguyên tố"
            else:
                constraints["complexity_expectation"] = "O(sqrt(N)) hoặc O(log N) - Số học / Chia để trị / Tìm kiếm nhị phân"

        return constraints

    @staticmethod
    def extract_code_features(source_code: str) -> Dict[str, Any]:
        """
        Quét mã nguồn AC để phát hiện cấu trúc dữ liệu và thuật toán thực tế sử dụng.
        """
        features: List[str] = []
        tags_hit: Dict[str, int] = {}

        if not source_code:
            return {
                "detected_features": ["Không có mã nguồn"],
                "tags_hit": {},
                "primary_tag_candidate": 36,  # unknown
                "bloom_candidate": 4
            }

        code_lower = source_code.lower()

        # 1. Segment Tree & Fenwick Tree
        if re.search(r'\b(tree|st)\[\s*4\s*\*', source_code) or (
            ('update(' in code_lower or 'build(' in code_lower) and 'query(' in code_lower and ('tree[' in code_lower or 'node' in code_lower)
        ):
            features.append("Cấu trúc dữ liệu: Segment Tree (Cây phân đoạn)")
            tags_hit["segtree"] = 23  # ID 23 trong judge_problemtype
        elif re.search(r'(i\s*&\s*-i)', source_code) or (
            'bit[' in code_lower and ('update(' in code_lower or 'add(' in code_lower) and 'get(' in code_lower
        ):
            features.append("Cấu trúc dữ liệu: Fenwick Tree (Binary Indexed Tree)")
            tags_hit["fenwick"] = 44  # ID 44

        # 2. Graph: DFS / BFS / Dijkstra / Floyd / DSU
        has_queue = 'queue<' in source_code or 'deque<' in source_code or 'collections.deque' in source_code or 'popleft()' in source_code
        has_adj = re.search(r'vector\s*<\s*vector\s*<\s*int\s*>\s*>', source_code) or 'adj[' in code_lower or 'graph[' in code_lower or 'g[' in code_lower
        has_visited = 'visited' in code_lower or 'vis[' in code_lower or 'seen' in code_lower
        has_priority_queue = 'priority_queue' in source_code or 'heapq' in source_code

        if has_priority_queue and ('dist[' in code_lower or 'd[' in code_lower):
            features.append("Thuật toán đồ thị: Dijkstra tìm đường đi ngắn nhất")
            tags_hit["dijkstra"] = 30
        elif (has_queue and (has_adj or has_visited)) or 'bfs(' in code_lower:
            features.append("Thuật toán đồ thị: BFS (Tìm kiếm theo chiều rộng / Loang)")
            tags_hit["dfs_bfs"] = 15
        elif ('dfs(' in code_lower or 'void dfs' in code_lower or 'def dfs' in code_lower) and (has_adj or has_visited):
            features.append("Thuật toán đồ thị: DFS (Tìm kiếm theo chiều sâu)")
            tags_hit["dfs_bfs"] = 15
        elif re.search(r'\b(parent|par|root)\[', source_code) and ('find(' in code_lower or 'union' in code_lower or 'unite(' in code_lower):
            features.append("Cấu trúc dữ liệu đồ thị: Disjoint Set Union (DSU / Kruskal)")
            tags_hit["dsu"] = 58

        # 3. Dynamic Programming (Quy hoạch động)
        has_dp_table = re.search(r'\b(dp|f|memo)\[[^\]]+\]\[[^\]]+\]', source_code) is not None
        has_dp_1d = re.search(r'\b(dp|f)\[[^\]]+\]\s*=\s*(max|min|\()', source_code) is not None
        has_bitmask = '(1 <<' in source_code or '(1<<' in source_code or '& (1 <<' in source_code

        if has_dp_table:
            features.append("Thuật toán: Quy hoạch động 2 chiều (2D DP)")
            tags_hit["dp_all"] = 14
        elif has_bitmask and ('dp[' in code_lower or 'mask' in code_lower):
            features.append("Thuật toán: Quy hoạch động trạng thái Bitmask")
            tags_hit["bitwise"] = 60
        elif has_dp_1d:
            features.append("Thuật toán: Quy hoạch động (1D DP)")
            tags_hit["dp_all"] = 14

        # 4. Number Theory / Math (Số học)
        has_gcd = 'gcd(' in code_lower or '__gcd' in code_lower or 'math.gcd' in code_lower
        # Sàng nguyên tố: có vòng đánh dấu bội số stride "j += i" (đặc trưng riêng của sieve)
        has_sieve = 'sieve' in code_lower or 'sàng' in code_lower or (
            re.search(r'i\s*\*\s*i\s*<=', source_code) is not None
            and re.search(r'\+=\s*[a-z_]+\b', source_code) is not None
        )
        has_prime_check = 'is_prime' in code_lower or 'prime[' in code_lower

        if has_sieve:
            features.append("Số học: Sàng số nguyên tố")
            tags_hit["sh_sang_nguyen_to"] = 69
        elif has_prime_check:
            features.append("Số học: Kiểm tra số nguyên tố")
            tags_hit["sh_nguyen_to"] = 67
        elif has_gcd:
            features.append("Số học: Ước chung lớn nhất (GCD / LCM)")
            tags_hit["sh_uoc_boi"] = 66

        # 5. Binary Search (Tìm kiếm nhị phân)
        has_bin_search = 'lower_bound' in code_lower or 'upper_bound' in code_lower or 'binary_search' in code_lower or (
            re.search(r'while\s*\(\s*(l|low|left)\s*<=\s*(r|high|right)\s*\)', source_code) is not None and ('mid' in code_lower)
        )
        if has_bin_search:
            features.append("Phương pháp: Tìm kiếm nhị phân (Binary Search)")
            tags_hit["tknp"] = 25

        # 6. Basic Arrays, Strings, Sorting
        has_sort = 'sort(' in code_lower or '.sort()' in code_lower or 'sorted(' in code_lower
        if has_sort:
            features.append("Kỹ thuật: Sắp xếp dữ liệu (Sorting)")
            tags_hit["B02sapxep"] = 24

        has_string = 'string' in code_lower or 'str' in code_lower or 'getline' in code_lower
        if has_string and len(features) == 0:
            features.append("Cơ bản: Xử lý xâu ký tự")
            tags_hit["A07xaukytu"] = 9

        # Nếu chưa phát hiện gì đặc biệt
        if not features:
            if 'vector<' in source_code or 'int a[' in source_code:
                features.append("Cơ bản: Mảng một chiều và duyệt cơ bản")
                tags_hit["A05mangmotchieu"] = 7
            else:
                features.append("Cơ bản: Biến, phép toán và rẽ nhánh")
                tags_hit["A01pheptoan"] = 4

        # Xác định Primary Tag và Bloom Level dự kiến
        primary_id = 4
        bloom_id = 5  # B (Hiểu)

        if "segtree" in tags_hit:
            primary_id = 23
            bloom_id = 8  # E (Đánh giá) hoặc 7 (D)
        elif "fenwick" in tags_hit:
            primary_id = 44
            bloom_id = 7  # D (Phân tích)
        elif "dijkstra" in tags_hit:
            primary_id = 30
            bloom_id = 7  # D
        elif "dfs_bfs" in tags_hit:
            primary_id = 15
            bloom_id = 6  # C (Vận dụng)
        elif "dp_all" in tags_hit:
            primary_id = 14
            bloom_id = 7  # D
        elif "bitwise" in tags_hit:
            primary_id = 60
            bloom_id = 7  # D
        elif "sh_sang_nguyen_to" in tags_hit:
            primary_id = 69
            bloom_id = 6  # C
        elif "sh_nguyen_to" in tags_hit:
            primary_id = 67
            bloom_id = 6  # C
        elif "sh_uoc_boi" in tags_hit:
            primary_id = 66
            bloom_id = 5  # B
        elif "tknp" in tags_hit:
            primary_id = 25
            bloom_id = 6  # C
        elif "B02sapxep" in tags_hit:
            primary_id = 24
            bloom_id = 5  # B
        elif "dsu" in tags_hit:
            primary_id = 58
            bloom_id = 7  # D
        elif "A07xaukytu" in tags_hit:
            primary_id = 9
            bloom_id = 5  # B
        elif "A05mangmotchieu" in tags_hit:
            primary_id = 7
            bloom_id = 4  # A (Nhớ)

        return {
            "detected_features": features,
            "tags_hit": tags_hit,
            "primary_tag_candidate": primary_id,
            "bloom_candidate": bloom_id
        }

    @classmethod
    def analyze(cls, source_code: str, description: str, time_limit: float = 1.0, memory_limit: int = 256000) -> Dict[str, Any]:
        """
        Tổng hợp phân tích toàn diện mã nguồn AC và ràng buộc đề bài.
        Trả về context có cấu trúc chuẩn cho LLM Prompt và bộ heuristic fallback.
        """
        constraints = cls.extract_constraints(description)
        code_features = cls.extract_code_features(source_code)

        summary_lines = [
            "- Đặc trưng mã nguồn AC:",
            *(f"  * {f}" for f in code_features["detected_features"]),
            "- Ràng buộc đề bài:",
            f"  * Giới hạn thời gian: {time_limit}s | Bộ nhớ: {memory_limit // 1000 if memory_limit else 256}MB",
        ]
        if constraints["n_limit_str"]:
            summary_lines.append(f"  * Ràng buộc phát hiện: N <= {constraints['n_limit_str']}")
            summary_lines.append(f"  * Kỳ vọng độ phức tạp: {constraints['complexity_expectation']}")
        else:
            summary_lines.append("  * Ràng buộc N: Không tìm thấy rõ ràng, ước lượng theo thời gian chạy")

        features_summary = "\n".join(summary_lines)

        heuristic_reasoning = (
            f"Phân tích mã nguồn AC phát hiện: {', '.join(code_features['detected_features'])}. "
            f"Kết hợp ràng buộc ({constraints['complexity_expectation']}), thuật toán giải pháp khớp với chủ đề này."
        )

        return {
            "constraints": constraints,
            "code_features": code_features,
            "features_summary": features_summary,
            "heuristic_primary_tag_id": code_features["primary_tag_candidate"],
            "heuristic_bloom_group_id": code_features["bloom_candidate"],
            "heuristic_reasoning": heuristic_reasoning
        }

feature_extractor = FeatureExtractor()

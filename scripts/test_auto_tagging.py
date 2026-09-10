import sys
import os

# Set backend in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.feature_extractor import feature_extractor

def test_feature_extractor():
    print("=== TEST 1: BFS & Graph Traversal ===")
    bfs_code = """
    #include <iostream>
    #include <vector>
    #include <queue>
    using namespace std;

    int main() {
        int n, m;
        cin >> n >> m;
        vector<vector<int>> adj(n + 1);
        vector<bool> visited(n + 1, false);
        queue<int> q;
        q.push(1);
        visited[1] = true;
        while (!q.empty()) {
            int u = q.front(); q.pop();
            for (int v : adj[u]) {
                if (!visited[v]) {
                    visited[v] = true;
                    q.push(v);
                }
            }
        }
    }
    """
    desc_bfs = "Cho đồ thị vô hướng gồm N đỉnh và M cạnh. Biết N <= 10^5, M <= 2*10^5. Tìm đường đi ngắn nhất."
    res_bfs = feature_extractor.analyze(bfs_code, desc_bfs, time_limit=1.0)
    print("BFS Patterns:", res_bfs["code_features"]["detected_features"])
    print("BFS Constraints:", res_bfs["constraints"])
    print("BFS Heuristic Tag:", res_bfs["heuristic_primary_tag_id"])
    print("BFS Bloom Group:", res_bfs["heuristic_bloom_group_id"])
    assert res_bfs["heuristic_primary_tag_id"] == 15, f"Expected 15 (dfs_bfs), got {res_bfs['heuristic_primary_tag_id']}"
    assert res_bfs["constraints"]["n_max_val"] == 200000, f"Expected 200000 (2*10^5 sau khi chuẩn hóa), got {res_bfs['constraints']['n_max_val']}"
    print("-> PASS: BFS test")

    print("\n=== TEST 2: 2D Dynamic Programming ===")
    dp_code = """
    #include <iostream>
    #include <vector>
    using namespace std;

    int dp[1005][1005];
    int main() {
        int n, m;
        cin >> n >> m;
        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {
                dp[i][j] = max(dp[i-1][j], dp[i][j-1]) + 1;
            }
        }
    }
    """
    desc_dp = "Cho lưới ô vuông kích thước N x M. Với N <= 1000, M <= 1000. Tính số điểm lớn nhất."
    res_dp = feature_extractor.analyze(dp_code, desc_dp)
    print("DP Patterns:", res_dp["code_features"]["detected_features"])
    print("DP Heuristic Tag:", res_dp["heuristic_primary_tag_id"])
    assert res_dp["heuristic_primary_tag_id"] == 14, f"Expected 14 (dp_all), got {res_dp['heuristic_primary_tag_id']}"
    print("-> PASS: 2D DP test")

    print("\n=== TEST 3: Segment Tree ===")
    st_code = """
    int tree[400005];
    void update(int id, int l, int r, int pos, int val) {
        if (l == r) { tree[id] = val; return; }
        int mid = (l + r) / 2;
        if (pos <= mid) update(2*id, l, mid, pos, val);
        else update(2*id+1, mid+1, r, pos, val);
        tree[id] = tree[2*id] + tree[2*id+1];
    }
    int query(int id, int l, int r, int u, int v) {
        if (v < l || r < u) return 0;
        if (u <= l && r <= v) return tree[id];
        int mid = (l + r) / 2;
        return query(2*id, l, mid, u, v) + query(2*id+1, mid+1, r, u, v);
    }
    """
    desc_st = "Cho dãy số A có N phần tử, N <= 100000. Thực hiện Q truy vấn cập nhật và tính tổng."
    res_st = feature_extractor.analyze(st_code, desc_st)
    print("ST Patterns:", res_st["code_features"]["detected_features"])
    print("ST Heuristic Tag:", res_st["heuristic_primary_tag_id"])
    assert res_st["heuristic_primary_tag_id"] == 23, f"Expected 23 (segtree), got {res_st['heuristic_primary_tag_id']}"
    print("-> PASS: Segment Tree test")

    print("\n=== TEST 4: Sieve & Number Theory ===")
    sieve_code = """
    bool is_prime[1000005];
    void sieve(int n) {
        for (int i = 2; i <= n; i++) is_prime[i] = true;
        for (int i = 2; i * i <= n; i++) {
            if (is_prime[i]) {
                for (int j = i * i; j <= n; j += i) is_prime[j] = false;
            }
        }
    }
    """
    desc_sieve = "Đếm số lượng số nguyên tố không vượt quá N. Với N <= 10^6."
    res_sieve = feature_extractor.analyze(sieve_code, desc_sieve)
    print("Sieve Patterns:", res_sieve["code_features"]["detected_features"])
    print("Sieve Heuristic Tag:", res_sieve["heuristic_primary_tag_id"])
    assert res_sieve["heuristic_primary_tag_id"] == 69, f"Expected 69 (sh_sang_nguyen_to), got {res_sieve['heuristic_primary_tag_id']}"

    # Kiểm tra nguyên tố bằng chia thử (không có vòng sàng stride) -> tag 67
    trial_code = """
    bool is_prime(int n) {
        if (n < 2) return false;
        for (int i = 2; i * i <= n; i++) {
            if (n % i == 0) return false;
        }
        return true;
    }
    """
    res_trial = feature_extractor.analyze(trial_code, "Kiểm tra số N có nguyên tố không, N <= 10^9.")
    print("Trial Heuristic Tag:", res_trial["heuristic_primary_tag_id"])
    assert res_trial["heuristic_primary_tag_id"] == 67, f"Expected 67 (sh_nguyen_to), got {res_trial['heuristic_primary_tag_id']}"
    print("-> PASS: Sieve & Prime test")

    print("\n=== TEST 5: Bitmask DP / Backtracking (N <= 20) ===")
    mask_code = """
    int dp[1 << 20];
    int main() {
        int n; cin >> n;
        for (int mask = 0; mask < (1 << n); mask++) {
            for (int i = 0; i < n; i++) {
                if (!(mask & (1 << i))) {
                    dp[mask | (1 << i)] = max(dp[mask | (1 << i)], dp[mask] + 1);
                }
            }
        }
    }
    """
    desc_mask = "Cho tập hợp N công việc, N <= 20. Phân công công việc để tối ưu hóa chi phí."
    res_mask = feature_extractor.analyze(mask_code, desc_mask)
    print("Bitmask Patterns:", res_mask["code_features"]["detected_features"])
    print("Bitmask Constraints:", res_mask["constraints"]["complexity_expectation"])
    print("Bitmask Heuristic Tag:", res_mask["heuristic_primary_tag_id"])
    assert res_mask["heuristic_primary_tag_id"] == 60, f"Expected 60 (bitwise), got {res_mask['heuristic_primary_tag_id']}"
    assert "Bitmask DP" in res_mask["constraints"]["complexity_expectation"]
    print("-> PASS: Bitmask test")

    print("\n=== TEST 6: Ràng buộc N dạng nhân hệ số & superscript (regression BUG-1) ===")
    desc_mul = "Cho mảng A gồm N phần tử. Biết N <= 2*10^5."
    res_mul = feature_extractor.analyze("", desc_mul)
    print("Multiplied Constraints:", res_mul["constraints"])
    assert res_mul["constraints"]["n_max_val"] == 200000, f"Expected 200000, got {res_mul['constraints']['n_max_val']}"

    desc_sup = "Với N ≤ 10⁵ phần tử."
    res_sup = feature_extractor.analyze("", desc_sup)
    print("Superscript Constraints:", res_sup["constraints"])
    assert res_sup["constraints"]["n_max_val"] == 100000, f"Expected 100000, got {res_sup['constraints']['n_max_val']}"

    desc_small = "N nhỏ (N <= 20), phù hợp bitmask."
    res_small = feature_extractor.analyze("", desc_small)
    assert res_small["constraints"]["n_max_val"] == 20, f"Expected 20, got {res_small['constraints']['n_max_val']}"
    print("-> PASS: Constraint parsing test")

    print("\n>>> ALL 6 FEATURE EXTRACTOR TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_feature_extractor()

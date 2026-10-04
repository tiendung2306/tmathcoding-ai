"""Local integration probe: optional AI stores proposals, never applies a tree."""
import argparse
import asyncio
import httpx


async def run(admin_id, ai, scope_check=False):
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000/api/v1", timeout=200,
                                 headers={"X-User-ID": str(admin_id)}) as client:
        before = await client.get("/admin/skill-config")
        before.raise_for_status()
        state = before.json()
        nodes = [
            {"id": "other", "title": "Khác", "description": "Các tag không phù hợp với nhóm đã định nghĩa."},
            {"id": "ds", "title": "Cấu trúc dữ liệu", "description": "Segment Tree, Fenwick Tree và container STL: Map, Set, Vector, Stack, Queue."},
            {"id": "dp", "title": "Quy hoạch động", "description": "Quy hoạch động dãy số, bảng hai chiều, chữ số, bitmask và trên cây."},
        ]
        if scope_check:
            nodes = [node for node in nodes if node["id"] != "dp"]
        assignments = {str(tag["id"]): "other" for tag in state["tags"]}
        for tag_id in (39, 38, 85):
            assignments.pop(str(tag_id), None)
        doc = {"nodes": nodes, "assignments": assignments}
        if ai:
            response = await client.post("/admin/skill-config/suggest", json=doc)
            print("AI HTTP status:", response.status_code, flush=True)
            response.raise_for_status()
            print("AI suggestions:", response.json(), flush=True)
            if scope_check:
                placements = {item["tag_id"]: item["node_id"] for item in response.json()["suggestions"]}
                assert placements[38] == placements[39] == "ds" and placements[85] == "other", placements
                print("Scope check passed: no DP root, digit DP belongs to Other.", flush=True)
        after = await client.get("/admin/skill-config")
        after.raise_for_status()
        assert after.json()["revision"] == state["revision"] and after.json()["document"] == state["document"]
        print("Tree configuration unchanged; source is read-only. AI results are stored as proposals when requested.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-id", type=int, required=True)
    parser.add_argument("--ai", action="store_true")
    parser.add_argument("--scope-check", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.admin_id, args.ai, args.scope_check))

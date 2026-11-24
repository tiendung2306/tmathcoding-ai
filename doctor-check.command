#!/bin/bash
# Kiểm tra Code Doctor trên stack Docker đang chạy: migration, model, và chạy
# thật trên vài bài nộp (WA, AC, TLE) của cùng một bài toán.
# Double-click trong Finder hoặc chạy: ./doctor-check.command  (log: .doctor-check.log)
cd "$(dirname "$0")" || exit 1
export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
LOG="$PWD/.doctor-check.log"
{
echo "== START $(date)"
echo "== Dashboard DB"
docker compose exec -T dashboard-db sh -c 'MYSQL_PWD=$DATABASE_APP_PASSWORD mysql -u$DATABASE_APP_USER $MYSQL_DATABASE -Nse "SELECT version_num FROM alembic_version; SHOW TABLES LIKE \"doctor%\""' 2>&1
echo "== Ollama"
docker compose exec -T ollama ollama list 2>&1
echo "== Chọn bài nộp"
IDS=$(docker compose --profile local-source exec -T db sh -c 'MYSQL_PWD=$DATABASE_APP_PASSWORD mysql -u$DATABASE_APP_USER $MYSQL_DATABASE -Nse "
SELECT p.problem_id,
  (SELECT s2.id FROM judge_submission s2 JOIN judge_submissionsource x ON x.submission_id=s2.id WHERE s2.problem_id=p.problem_id AND s2.result=\"WA\" AND s2.language_id=p.language_id ORDER BY s2.id DESC LIMIT 1),
  (SELECT s3.id FROM judge_submission s3 JOIN judge_submissionsource x ON x.submission_id=s3.id WHERE s3.problem_id=p.problem_id AND s3.result=\"AC\" AND s3.language_id=p.language_id ORDER BY s3.id DESC LIMIT 1),
  IFNULL((SELECT s4.id FROM judge_submission s4 JOIN judge_submissionsource x ON x.submission_id=s4.id WHERE s4.problem_id=p.problem_id AND s4.result=\"TLE\" AND s4.language_id=p.language_id ORDER BY s4.id DESC LIMIT 1), 0)
FROM (SELECT s.problem_id, s.language_id, SUM(s.result=\"AC\") ac, SUM(s.result=\"WA\") wa
      FROM judge_submission s JOIN judge_language l ON l.id=s.language_id
      WHERE s.id > (SELECT MAX(id) - 30000 FROM judge_submission) AND l.\`key\` LIKE \"CPP%\"
      GROUP BY s.problem_id, s.language_id HAVING ac >= 3 AND wa >= 2 ORDER BY ac DESC LIMIT 1) p"' 2>&1 | tail -1)
echo "problem wa ac tle: $IDS"
# ONLY: loại bài chạy (mặc định cả ba). TIMEOUT: ghi đè DOCTOR_LLM_TIMEOUT_SECONDS cho lần chạy này.
ONLY="${ONLY:-WA}"; TIMEOUT="${TIMEOUT:-900}"
TIMEOUT_ARGS=(); [ -n "$TIMEOUT" ] && TIMEOUT_ARGS=(-e DOCTOR_LLM_TIMEOUT_SECONDS="$TIMEOUT")
echo "== Tốc độ Ollama"
docker compose exec -T backend python - <<'PY'
import httpx, time
from app.core.llm_adapter import doctor_profile
p = doctor_profile()
base = p.base_url.removesuffix("/v1")
t = time.monotonic()
r = httpx.post(f"{base}/api/generate", timeout=300, json={"model": p.model, "prompt": "Giải thích ngắn: mảng cộng dồn là gì? " * 40,
               "stream": False, "think": False, "options": {"num_ctx": p.context_window, "num_predict": 64}})
d = r.json()
pe, ev = d.get("prompt_eval_count", 0), d.get("eval_count", 0)
print(f"HTTP {r.status_code} | prompt {pe} token: {pe / max(d.get('prompt_eval_duration', 1) / 1e9, 1e-9):.1f} tok/s"
      f" | output {ev} token: {ev / max(d.get('eval_duration', 1) / 1e9, 1e-9):.1f} tok/s | tổng {time.monotonic() - t:.0f}s")
PY
echo "== Chạy Code Doctor ($ONLY)"
docker compose exec -T -e DOCTOR_IDS="$IDS" -e ONLY="$ONLY" "${TIMEOUT_ARGS[@]}" backend python - <<'PY'
import asyncio, json, os, time
from app.core.config import settings
from app.core.llm_adapter import doctor_profile
from app.services.code_doctor_service import code_doctor_service
from app.services.source_gateway import get_source_gateway_client

async def main():
    profile = doctor_profile()
    print("doctor model:", profile.model, "| base:", profile.base_url, "| ctx:", profile.context_window,
          "| timeout:", settings.DOCTOR_LLM_TIMEOUT_SECONDS)
    _, wa, ac, tle = (int(x) for x in os.environ["DOCTOR_IDS"].split())
    gateway = get_source_gateway_client()
    actor = settings.DASHBOARD_ADMIN_PROFILE_ID
    only = os.environ.get("ONLY", "WA AC TLE").split()
    for label, sid in (("WA", wa), ("AC", ac), ("TLE", tle)):
        if not sid or label not in only:
            continue
        start = time.monotonic()
        try:
            res = await code_doctor_service._diagnose_submission_core(sid, gateway, actor)
        except Exception as exc:
            print(f"\n### {label} {sid}: LỖI {type(exc).__name__}: {exc}")
            continue
        r = res.report
        print(f"\n### {label} submission {sid}  ({time.monotonic() - start:.0f}s)")
        if r is None:
            print("verdict-only:", res.diagnosis.advice)
            continue
        print("origin:", r.origin, "| reason:", r.fallback_reason, "| model:", r.model, "| confidence:", r.confidence)
        print("overview:", r.overview)
        print("direction:", r.direction, "| complexity:", r.estimated_complexity, "| expected:", r.expected_complexity)
        print("nearest:", r.nearest_approach and r.nearest_approach.model_dump())
        print("best:", r.best_approach and (r.best_approach.name, r.best_approach.time_complexity))
        for e in r.logic_errors:
            print("  LỖI", e.lines, e.what, "|", e.why, "|", e.fix, "|", e.evidence)
        for f in r.strengths:
            print("  +", f.lines, f.point)
        for f in r.weaknesses:
            print("  -", f.lines, f.severity, f.point)
        for f in r.static_facts:
            print("  tĩnh:", f.kind, f.lines, f.text)
        print("  hints:", r.student_hints)
        print("  limitations:", r.limitations)
    print("\n== Ngân hàng lời giải")
    problem_id = int(os.environ["DOCTOR_IDS"].split()[0])
    for a in await code_doctor_service.store.list_approaches(problem_id):
        print(f"  #{a.id} {a.name} | {a.control_flow} | members={a.member_count} | rep={a.representative_submission_id} | card={a.card_origin}")
    await gateway.close()
    from app.core.dashboard_database import dashboard_database
    await dashboard_database.close()

asyncio.run(main())
PY
echo "== Log backend gần nhất"
docker compose logs --no-color --since 20m backend 2>&1 | grep -iE "code doctor|error|traceback" | tail -20
echo "== DONE $(date)"
} 2>&1 | tee "$LOG"

#!/bin/bash
cd "$(dirname "$0")" || exit 1
export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
{
docker compose --profile local-source restart source-api-mock
sleep 6
docker compose exec -T backend python - <<'PY'
import os, time, httpx
base = os.environ["SOURCE_API_BASE_URL"]; tok = os.environ["SOURCE_API_TOKEN"]
c = httpx.Client(base_url=base + "/", headers={"Authorization": f"Bearer {tok}", "X-Actor-Profile-Id": "2"}, timeout=60)
r = c.get("contests/16171/problems"); print(r.status_code, r.text[:500])
r = c.get("teachers/2/contests", params={"state": "ended", "limit": 100})
items = [i for i in r.json()["items"] if i["class_ids"]]
for it in items:
    s = c.get(f"classes/{it['class_ids'][0]}/submissions", params={"from": it["starts_at"], "to": it["ends_at"], "limit": 100})
    if s.status_code == 200 and s.json().get("items"):
        print("contest with submissions:", it["contest_id"], it["code"], it["starts_at"], len(s.json()["items"]))
        p = c.get(f"contests/{it['contest_id']}/problems").json()["items"]
        print("  problems:", [(x["code"], x["points"], x["problem_points"], x["partial"]) for x in p][:6])
        print("  sample subs:", [(x["problem_code"], x["result"], x["points"]) for x in s.json()["items"][:8]])
        break
else:
    print("no ended contest among first 100 with submissions")
PY
echo EXIT=$?
} > .dev-check.log 2>&1

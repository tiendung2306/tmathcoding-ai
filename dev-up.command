#!/bin/bash
# Khởi động toàn bộ stack local (Source API mock + backend + frontend) bằng Docker.
# Double-click trong Finder hoặc chạy: ./dev-up.command
cd "$(dirname "$0")" || exit 1
export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
LOG="$PWD/.dev-up.log"
SERVICES="db source-api-mock dashboard-db dashboard-migrate redis ollama backend scoring-worker frontend"

wait_http() { # url, seconds
  for _ in $(seq 1 "$2"); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "$1")
    if [ "$code" != "000" ]; then echo "$1 -> HTTP $code"; return 0; fi
    sleep 1
  done
  echo "$1 -> KHÔNG phản hồi sau $2s"; return 1
}

{
  echo "== $(date)"
  echo "Docker server: $(docker version --format '{{.Server.Version}}' 2>&1)"
  docker compose --profile local-source up -d --build --renew-anon-volumes $SERVICES
  echo "COMPOSE_EXIT=$?"
  echo "== Kiểm tra dịch vụ"
  wait_http http://localhost:8000/docs 120
  wait_http http://localhost:5173/ 120
  echo "== Dữ liệu Source DB"
  docker compose --profile local-source exec -T db sh -c \
    'MYSQL_PWD=$DATABASE_APP_PASSWORD mysql -u$DATABASE_APP_USER $MYSQL_DATABASE -Nse "select \"users\", count(*) from judge_profile union all select \"submissions\", count(*) from judge_submission union all select \"contests\", count(*) from judge_contest union all select \"contest_problems\", count(*) from judge_contestproblem union all select \"orgs\", count(*) from judge_organization"' 2>&1
  echo "== Trạng thái"
  docker compose --profile local-source ps -a --format 'table {{.Service}}\t{{.State}}\t{{.Status}}'
  echo "== Log gần nhất"
  docker compose --profile local-source logs --no-color --tail=40 dashboard-migrate source-api-mock backend frontend 2>&1
  echo "== DONE $(date)"
} 2>&1 | tee "$LOG"

echo
echo "Mở http://localhost:5173 để dùng dashboard. Dừng: docker compose --profile local-source down"

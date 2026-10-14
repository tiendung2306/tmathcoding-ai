# Source API mock

Standalone read-only provider for the `/integration/v1` profile, teacher,
class, student, contest, submission, and problem-catalog contract. It reads the source database directly using
`SOURCE_DB_*` (or `SOURCE_DATABASE_URL`) and does not import dashboard database
models or credentials. Give its database user `SELECT` permissions only. The
container listens on port `8001`.

Run locally after installing `source_api_mock/requirements.txt`:

```sh
SOURCE_DB_HOST=localhost SOURCE_DB_USER=source_readonly SOURCE_DB_PASSWORD=... \
SOURCE_DB_NAME=tmathcoding SOURCE_API_TOKEN=local-test-token \
SOURCE_API_ALLOWED_ACTORS=2,9 uvicorn source_api_mock.main:app --host 0.0.0.0 --port 8001
```

Calls require `Authorization: Bearer <SOURCE_API_TOKEN>` and
`X-Actor-Profile-Id`. The mock accepts only actor IDs listed in
`SOURCE_API_ALLOWED_ACTORS`; the requested teacher/profile is checked against
the actor, except a source super admin may inspect another profile. Class and
student records are filtered by source ownership before pagination. List cursors
are signed, opaque, query-bound cursors with a 15-minute lifetime. The mock hashes
the full ordered result set and returns `409` if a cursor is reused for another
query or the result set changed. The source queries do not share a database
snapshot transaction, so this does not guarantee snapshot isolation during writes.

For local fixture Compose only, the actor/scope lists accept `*` to cover
fixture users without maintaining a list as students log in. The service token
is still mandatory and every requested resource is checked against source ACLs;
wildcard scope does not grant access to another student's submissions or private
problems. Do not configure wildcard actor mapping or source/testcase scope in a
production provider.

`X-Actor-Profile-Id` and `SOURCE_API_ALLOWED_ACTORS` are mock-only actor mapping
for local integration tests. They are not suitable for production. A real
provider must authenticate the actor through its registered server-to-server
authorization or another trusted mapping, as described in the API contract.

Contest routes read `judge_contest` and its organization, author, and curator
mappings. A teacher can see contests attached to managed classes when
`is_visible=1`, plus contests they authored or curate. Super admins can see all
contests. Hidden contests are visible to their author/curator and super admins.
The mock does not interpret `is_private` or `is_organization_private`; their
production visibility semantics must be confirmed by the provider. Its current
visibility assumption is `is_visible` plus actor/class mapping as described
above.
`class_ids` only includes classes in the caller's accessible scope. Active state
uses `start_time <= at < end_time`; the source schema has no pause/cancel state,
so those rules are not inferred. Class sorting puts classes with a visible active
contest first. `updated_at` is null; `version` carries `version_update`.
`avatar_url` and `joined_at` are null because the current fixture schema does not
expose them.

Submission routes read `judge_submission`, `judge_problem`, `judge_language`,
`judge_submissionsource`, `judge_submissiontestcase`, and the class membership
tables. Date filters are UTC half-open intervals: `from <= submitted_at < to`.
Problem detail returns `title`, `tag_ids`, `updated_at`, and the source
`version_update` as `version`; the fixture's integer version is not a timestamp,
so `updated_at` is null unless the source later supplies an actual update time.
Problem descriptions are returned to any actor for public problems. Private or
organization-private problem details are restricted to source super admins in
this mock because the provider's class-level problem visibility rules are not
available in the fixture contract; production must supply and enforce that
authorization policy.
The catalog routes expose `judge_problemtype`, `judge_problemgroup`, and
`judge_problem_types`; problem pages count each problem once even when it has
several tags. Non-admin actors only see public, non-organization-private
problems. Catalog ETags and page cursors include a digest of visible problem
fields and tag relationships, so edits invalidate cached responses and stale
pages even when `version_update` did not change. `GET /tags` returns an ETag and
supports `If-None-Match`; `GET /analytics/catalog` does the same. Null tag/group
keys and titles fall back to stable ID-derived labels, and a problem without a
name falls back to its code or ID for titles and examples. `fields=summary`
omits descriptions from problem list items. Repeated `ids` parameters use
standard query array syntax, for example `?ids=12&ids=14`.
`analytics/catalog.tagged_problem_count` counts distinct visible problem IDs
with at least one tag. Student submission lists support `exclude_result`, which
is applied before result totals and cursor pagination.
Student analytics batch-check profile visibility before loading submissions. A
teacher can request students who share a managed class; a source super admin can
request enrolled students; a student can request their own profile. One missing
or out-of-scope ID rejects the aggregate with 404. Analytics use UTC half-open
date ranges, final `result` values, and distinct problem IDs for solved/attempted
union counts. `reference_now` is the maximum submission timestamp across profiles the actor
may view (managed-class students and self) and actor-visible problems. This keeps
the anchor stable between single-student and class requests. Super-admin requests
use the global source maximum; private or unrelated activity does not affect a
regular actor's response. `as_of` is response generation time. Embedded
`problem_facts` are null unless
requested and capped at 1,000 distinct student/problem pairs; larger requests
return 422 and should use the paged facts endpoint. Problem-facts cursors bind
actor, student, filters, catalog version, submission content, and tag/group
mappings, returning 409 when that snapshot changes. Both analytics routes apply
the actor's visible-problem scope so private problem submissions do not leak
counts or tag metadata.
`GET /classes/{id}/submissions` returns an opaque `high_watermark` accepted by
`/classes/{id}/submission-changes`; the list page cursor pins both the snapshot
and that same handoff cursor. If the snapshot changes between pages, the mock
returns `409` so the caller can restart.

The source fixture has no durable submission change log. The mock keeps a
process-local per-class ID/row-marker baseline and bounded event journal. Empty
polls check a SQL aggregate marker; only when the marker changes does the mock
reconcile row IDs/versions and fetch full payloads for changed rows. A
metadata-only reconciliation also runs every 10 seconds per class by default.
Set `SOURCE_API_RECONCILE_INTERVAL_SECONDS` to change the interval (minimum one
second). Changes not reflected in the aggregate are detected within one
reconciliation interval, plus request scheduling time. The aggregate covers
row count/IDs, verdict and status changes, score/time/memory
totals, and version totals. The per-row marker also compares result, status,
points, time, memory, and `version_update`, so a WA-to-AC update is detected
even if `version_update` does not change. Periodic reconciliation also checks
per-row verdict, status, score, time, memory, version, judged date, and rejudged
date. Other untracked edits may be delayed until periodic reconciliation. A
null changes cursor seeds the current snapshot as `created` events. Snapshot
cursors also bind the aggregate marker and return `409` when
the marker changes between pages.
Events that occur and revert between polls cannot be detected; process restart,
cursor expiry, or journal eviction invalidates old cursors with `409`. This is a
local integration strategy and does not provide production durability. The
provider must supply a durable change log, version cursor, or equivalent.

Submission metadata is visible only to the student, a manager of one of their
classes, or a super admin. Requests that include source code require the actor
to be listed in the mock-only `SOURCE_API_SOURCE_ACTORS` setting; requests that
include testcases require `SOURCE_API_TESTCASE_ACTORS`. When the testcase list
is unset, it inherits the source actor list. Missing scope returns 403, and the
mock does not log source code. Accepted samples and student submission samples
also require source scope. These actor lists are fixture-only and must be
replaced by provider-owned source and testcase authorization scopes in
production. Accepted samples are capped at three per problem. Student samples
take up to `per_group_limit` latest AC submissions per requested tag, then
deduplicate submissions that match multiple tags. Both sample responses include
`as_of`; rows with missing or empty source are excluded before sample ranking.
`GET /submissions/{id}?include=source` and `include=testcases` return 403 when
the corresponding scope is absent rather than returning a partial response.

`POST /analytics/students/alerts` checks all requested profile IDs and their
permissions before reading. It returns each student's latest submission time
and `has_stuck_problem`, which is true when the student has at least eight
non-AC submissions on one problem in `[at-24h, at)`. `ProblemFact` also includes
first-AC execution time, problem limits, and adjacent rapid-failure pair count
for batched skill and radar scoring. Aggregate and alerts requests accept at
most 100 profile IDs. Aggregate `include_problem_facts=true` is capped at 1,000
student/problem facts; requests exceeding that cap return 422 and should use
the paginated facts endpoint. `reference_now` is scoped to the actor's visible
students and problems (global only for super-admin), so private or unrelated
activity does not shift a regular actor's analytics window.

OpenAPI is served at `/integration/v1/openapi.json`; Swagger UI is at `/docs`.
Run the SQLite contract/auth/permission/pagination tests with
`python -m unittest source_api_mock.tests.test_api` in an environment containing
the source mock requirements.

## Docker Compose integration

The local Compose service builds a separate mock-only image from
`source_api_mock/Dockerfile` and gives source DB credentials only to the mock:

```yaml
services:
  source-api-mock:
    image: tmath-source-api-mock
    profiles: [local-source]
    command: ["uvicorn", "source_api_mock.main:app", "--host", "0.0.0.0", "--port", "8001"]
    environment:
      SOURCE_DB_HOST: db
      SOURCE_DB_PORT: "3306"
      SOURCE_DB_USER: ${SOURCE_DB_USER}
      SOURCE_DB_PASSWORD: ${SOURCE_DB_PASSWORD}
      SOURCE_DB_NAME: ${SOURCE_DB_NAME}
      SOURCE_API_TOKEN: ${SOURCE_API_TOKEN}
      SOURCE_API_ALLOWED_ACTORS: ${SOURCE_API_ALLOWED_ACTORS:-*}
      SOURCE_API_SOURCE_ACTORS: ${SOURCE_API_SOURCE_ACTORS:-*}
      SOURCE_API_TESTCASE_ACTORS: ${SOURCE_API_TESTCASE_ACTORS:-*}
    expose:
      - "8001"
    volumes:
      - ./source_api_mock:/app/source_api_mock:ro
    networks: [source-data, source-api]
    depends_on:
      db:
        condition: service_healthy
```

With that service entry integrated, start the local source database and mock
using `docker compose --profile local-source up -d --build`; the dashboard
gateway URL on the Compose network is `http://source-api-mock:8001/integration/v1`.
Compose connects the dashboard backend only to `source-api`, not `source-data`;
the mock bridges those networks. The local wildcard defaults require a valid
service token and still apply source ownership checks.
Do not include the mock in a production deployment. The production dashboard
must use the provider's API URL and credentials instead.

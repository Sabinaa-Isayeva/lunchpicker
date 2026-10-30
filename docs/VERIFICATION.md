# Verification results

Verified using Python 3.11, Django 5.2.18 and the pinned dependencies in `requirements.txt`.

| Check | Result |
| --- | --- |
| Django system check | No issues |
| Migration drift | No missing migrations |
| SQLite backend suite | 78 passed; 1 PostgreSQL-only concurrency test skipped |
| PostgreSQL 15 / Redis backend suite in Docker | 79 passed, including concurrent result finalization |
| Backend statement coverage | 94% (1,340 statements; 76 missed) |
| Shared browser API client and HTML escaping | 5 Node tests passed |
| Team/voting browser workflow | Passed in Chromium |
| Administrator/catalog browser workflow | Passed in Chromium |
| Docker application | Built; database, cache and web health checks passed; Nginx and scheduled worker running |

Coverage includes `accounts`, `teams`, `restaurants`, `sessions`, `analytics` and `core`; migrations and app test modules are excluded by `.coveragerc`. CI enforces an 80% minimum. Coverage is measured test execution, separate from the requirement mapping in `SPECIFICATION_COVERAGE.md`.

Browser checks exercise team creation, role changes, invitation preview/login/join, recurring session creation, rating updates/withdrawal, history/profile navigation, global settings/metrics and restaurant/menu editing with dietary flags. Temporary browser-created teams, sessions and restaurants are removed after successful checks.

Reproduction commands are in the main README. The PostgreSQL concurrency regression is intentionally skipped on SQLite because SQLite does not provide PostgreSQL row locks.

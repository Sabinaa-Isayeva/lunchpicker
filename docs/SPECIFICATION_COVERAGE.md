# Technical specification coverage

This maps the core requirements in `Lunch_Picker_Technical_Documentation.pdf` (sections 1–9) to the delivered application. Section 10 explicitly describes future opportunities and is outside this implementation.

| PDF requirement | Delivered behavior | Main verification |
| --- | --- | --- |
| 4.1 User and team administration | Staff can list all teams/users, manage account status and administrator roles; owners manage their own teams. Self-demotion/deactivation is prevented. | `test_specification.py`, workspace system/team screens |
| 4.1 Restaurant and menu CRUD | Admin catalog screen supports creation, editing, deletion, websites, prices, ratings and all three dietary flags. | Catalog regression tests; browser admin smoke |
| 4.1 Global rules and usage metrics | `/api/settings/` and `/api/analytics/system/`; default algorithm, voting mode, duration, anonymous voting policy and weighted base weight. | Settings, metrics and algorithm tests |
| 4.2 Team CRUD and roles | `/workspace/#teams`; create/rename/delete teams, add existing users, assign owner/member/guest, remove members. The founding owner is protected. Delegated owners have management permissions. | Team and role tests; browser workflow smoke |
| 4.2 Invitations | Generate, inspect and revoke expiring or permanent links. Public previews expose only the team name. Join is authenticated and idempotent; login/signup preserves the pending invitation. | Invite tests; logged-out invite → login → join browser flow |
| 4.2 Sessions and configuration | Team/session selectors and `/workspace/#sessions`; one-time/daily/weekly sessions, deadlines, algorithm, anonymity, voting mode, edits, cloning and deletion. | Session tests; recurring-session browser flow |
| 4.2 Proposals and menus | Active team members can propose a restaurant with matching menu items via the nested API. The existing moderated suggestion workflow is available in the UI, with owner/staff approval. | Proposal, menu-boundary and moderation tests |
| 4.3 Flexible voting | Single choice replaces the previous selection; multiple choice keeps one vote per proposal; rating supports actual 1–5 values and changes. Withdrawal closes at the same deadline as submission. | Voting-mode, deadline and rate-limit tests; browser rating flow |
| 4.3 Anonymity | Anonymous sessions expose only the caller's votes, including to owners/admins. Participant indicators and analytics omit individual anonymous participation. Rules cannot change after voting begins. | Privacy and rule-change tests |
| 2, 4.3 Automatic selection and notifications | Scheduled Docker worker runs `process_sessions` every minute. API and worker use the same atomic finalization, persist one result, notify members once and advance recurrence. Manual finalization is also available. | Worker/idempotence/result tests |
| 4.3 History and analytics | `/workspace/#history`; personal/team history filtered by inclusive date range and venue; restaurant/cuisine wins and participation summaries. Team membership is enforced. | History, date and outsider-access tests |
| 5 Models and read-only history | Existing entity relationships are retained; history is a read-only aggregate of selection results. New migrations add weighting and model validation. | Migration drift check; model/API tests |
| 6 API conventions | JWT authentication, role-scoped ViewSets, pagination/search/filtering, nested restaurant/menu/session routes. Shared browser client follows every page and refreshes tokens consistently. | Backend suite; Node API-client tests |
| 7 Access control and passwords | Authenticated team endpoints, private team joins, owner-only session writes, read-only guests, Argon2 passwords and Django password validation. Signup grants no implicit team access. | Authentication, signup, guest and owner regressions |
| 7 Rate limiting and auditing | Vote submissions, changes and withdrawals share a per-user limit of 5/minute; Redis shares limits between Gunicorn workers. Sensitive changes are recorded by the audit logger. | Update/delete rate-limit and audit tests |
| 7 Transport and browser safety | Same-origin JWT UI, Django CSRF middleware/admin forms, escaped user text, TLS deployment configuration and secure-cookie/HSTS settings. Local development uses HTTP. | Browser checks; Django checks; TLS configuration review |
| 8 Integrity and validation | Matching proposal/session/menu relationships, validated recurrence and date ranges, protected finalized sessions, bounded prices/ratings and unique names/venues. Client forms provide required fields and immediate date/range checks. | Validation regression tests; browser forms |
| 3, 9 Runtime and delivery | Python 3.11, Django 5.2 LTS, compatible DRF/JWT dependencies, PostgreSQL 15 or SQLite, Nginx/Gunicorn, Redis/worker and GitHub Actions. | Docker build/health, SQLite and PostgreSQL suites, browser smoke |

## Interpretation decisions

- The PDF names Django 5.0. The implementation uses its supported Django 5.2 LTS successor with Python 3.11; dependencies are pinned in `requirements.txt` and maintained through `requirements.in`.
- Restaurants remain a global catalog, consistent with the entity diagram and administrator-only catalog API. Name/address duplicates are rejected case-insensitively, and a restaurant can be proposed only once per session. Full organizational tenant isolation is explicitly a future expansion.
- Rating sessions use the sum of ratings for majority selection and weighted preference; single/multiple sessions use vote counts. Weighted preference adds the configurable positive base weight so every proposal remains eligible.
- OAuth, calendars, Slack/Teams bots, ML recommendations, native apps, ranked-choice voting, payments, SaaS tenancy and advanced interactive charts remain the PDF's future expansion items.

## Verification commands

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
coverage run -m pytest tests/
coverage report --fail-under=80
node --test tests/frontend/api.test.cjs
python tests/browser_smoke.py http://127.0.0.1:8000
```

The browser script requires a disposable database initialized with `seed_demo`; it removes its temporary team/session. Browser dependencies are in `requirements-browser.txt`.

# Lunch Picker

A Django application for coordinating team lunches. The interface is in Azerbaijani and uses plain HTML/JavaScript with Tailwind CSS. The API uses JWT authentication.

## Included workflows

- Teams: create, edit, delete, select between teams, invite by username or expiring link, revoke links, assign owner/member/guest roles and remove members.
- Sessions: schedule one-time/daily/weekly lunches, set deadlines, anonymity, voting mode and selection algorithm; edit, clone and delete sessions.
- Voting: single choice, multiple choice and 1–5 ratings, with changes and withdrawals before the deadline. Guests have read-only access.
- Catalog: administrator CRUD for restaurants and menus, including websites, ratings, prices, vegetarian/vegan/gluten-free flags.
- Suggestions: members submit tickets; team owners or administrators approve/reject them.
- Results: a scheduled worker automatically selects a winner, persists history, notifies members and schedules recurring sessions. Owners can also finalize an ended session manually.
- History and analytics: personal/team history with date and restaurant filters, restaurant/cuisine trends, participation and administrator usage totals.
- Profiles and administration: profile/password changes, account status/roles and global voting defaults/weighting.

The complete requirement mapping and interpretation decisions are in [docs/SPECIFICATION_COVERAGE.md](docs/SPECIFICATION_COVERAGE.md). The PDF's section 10 future opportunities are outside the core scope.

## Stack

Python 3.11, Django 5.2 LTS, Django REST Framework, SimpleJWT, PostgreSQL 15 (SQLite locally), Redis, Gunicorn, Nginx, pytest and coverage.py. Django 5.2 is the supported LTS successor to the PDF's Django 5.0 target. See the [Django release notes](https://docs.djangoproject.com/en/5.2/releases/5.2/).

Pinned dependencies are in `requirements.txt`; update them from `requirements.in` with `uv pip compile requirements.in --python-version 3.11 --output-file requirements.txt`.

## Run with Docker

```sh
docker compose up -d --build
docker compose exec web python manage.py seed_demo
```

Open http://localhost/. Five services run: `db`, `cache`, `web`, `worker` and `nginx`. The worker checks ended sessions every minute. Migrations and static-file collection run when the web container starts.

Demo users: `sabina`, `ali`, `leyla`, `reshad`; password: `lunch1234`. Sabina owns the demo team. Create a global administrator separately:

```sh
docker compose exec web python manage.py createsuperuser
```

Configuration uses `.env` (example in `.env.example`). Set unique `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY` values before deployment. If the database volume already exists, changing the password in `.env` alone does not change the existing PostgreSQL role password.

## Run locally

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Open http://127.0.0.1:8000/. A database is created by `migrate`; no database is shipped in the repository. For automatic results outside Docker, schedule `python manage.py process_sessions` every minute. `process_recurring` remains available for recurrence-only scheduling.

`DATABASE_URL` selects PostgreSQL; otherwise SQLite is used. `CACHE_URL` selects Redis; otherwise local development uses an in-process cache. Redis shares vote limits across production web workers.

## Pages

- `/`: login/signup, team/session selection, proposals, voting, results and notifications.
- `/workspace/`: team/membership/invite management, sessions, history, analytics and profiles; administrators also see users and global settings.
- `/food-admin/`: restaurant and menu management for administrators.
- `/admin-panel/`: suggestion moderation for team owners and administrators.
- `/join/<token>/`: invitation preview and authenticated join; login preserves the invitation.
- `/admin/`: Django administration.

Django serves `templates/index.html`. The root `index.html` and `script.js` are an old static prototype and are not the running application.

## Selection and privacy rules

- Majority: most votes for choice sessions; greatest sum of ratings for rating sessions. Ties are random.
- Random: uniform random proposal.
- Weighted: a weighted draw using vote count/rating sum plus the configured positive base weight.
- Finalization is atomic and idempotent. Results are immutable; notification and recurrence side effects run once.
- Anonymous votes are visible only to the voter, including when the requester is an owner or administrator. Anonymous individual participation is omitted from analytics and participant indicators.
- Vote submissions, updates and withdrawals count toward the per-user limit of five per minute. A limit violation returns HTTP 429.
- Registration never automatically enrolls a user in a private team.

## API additions

Existing catalog/session routes are retained. Management routes include:

```text
GET/POST     /api/teams/
GET/PATCH/DELETE /api/teams/{id}/
GET/POST/PATCH/DELETE /api/teams/{id}/members/
GET/POST     /api/teams/{id}/invite_link/
DELETE       /api/teams/{id}/invite_links/{token}/
GET          /api/join/{token}/preview/
GET/POST     /api/join/{token}/
GET/PATCH    /api/settings/
GET          /api/analytics/system/
GET          /api/analytics/team/{id}/
GET          /api/analytics/history/team/{id}/
GET          /api/analytics/history/me/
```

History and team analytics accept inclusive ISO `start`/`end` dates. History also accepts `restaurant` (ID or name) or `venue`. Team data requires membership or staff access. `PATCH .../members/` accepts `username` and `role`; the founding owner's membership cannot be changed.

JWT endpoints are `/api/auth/token/`, `/api/auth/token/refresh/` and `/api/auth/token/verify/`. Send `Authorization: Bearer <access>`. Public signup is `POST /api/users/`; profile details are at `/api/users/me/` and `/api/users/{id}/`.

## Verify

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
coverage run -m pytest tests/
coverage report --fail-under=80
node --test tests/frontend/api.test.cjs
```

The same backend commands can run with `docker compose exec -T web ...` against PostgreSQL. CI checks migration drift, the backend suite/coverage, the shared browser API client and the browser workflow smoke test.

For the browser smoke test, use a disposable seeded database and a running application:

```sh
pip install -r requirements-browser.txt
python -m playwright install chromium
python tests/browser_smoke.py http://127.0.0.1:8000
```

## HTTPS deployment

For TLS termination at Nginx, supply certificates for your hostname and run the optional override:

```sh
# TLS_CERT_DIR contains fullchain.pem and privkey.pem.
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d --build
```

This redirects HTTP to HTTPS and enables secure cookies/HSTS. Set `DJANGO_ALLOWED_HOSTS` for your deployment hostname in the web environment. TLS can also terminate at a trusted load balancer; configure forwarded HTTPS headers and Django's security environment flags accordingly. The default Compose configuration is for local HTTP development.

Audit events are written to `logs/audit.log` and the container console. Logs, local databases, environments and coverage output are ignored by Git.

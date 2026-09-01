# Lunch Picker

A small internal tool for teams who can never agree on where to eat. Someone opens a lunch session, people propose restaurants, everyone votes, and the app picks a winner instead of the group arguing about it in Slack for twenty minutes. It's a Django + Django REST Framework backend with a plain HTML/JS frontend bolted on top — no build step, no frontend framework, just static pages served straight from Django's template engine.

The interface itself is in Azerbaijani (this looks like it was built for a specific office — usernames in the demo seed are Azerbaijani names, and toast messages, error strings, etc. are in Azerbaijani too). The code and this README are in English.

## What it actually does

- **Teams** — you create a team, invite people to it either by username or by generating a shareable invite link (`/join/<uuid-token>/`). Teams have an owner and members; owners can promote/demote or remove people.
- **Restaurants & menus** — a shared catalog of restaurants with cuisine type, average price, rating, and a menu of items (with vegetarian/vegan/gluten-free flags).
- **Lunch sessions** — the core object. A session has a start/end time, can be recurring (daily/weekly), can be anonymous, and supports three voting modes (single choice, multiple choice, or 1–5 rating).
- **Proposals & voting** — team members propose a restaurant (optionally with specific menu items) for a session, then everyone votes. Votes are 1–5, one vote per proposal per person, and you can change or delete your vote before the session closes.
- **Suggestions (a moderation queue)** — instead of letting anyone add a proposal directly, there's a "suggestion" ticket system: a member submits a suggestion, and the team owner (or staff) approves or rejects it. Approving auto-creates the actual proposal.
- **Winner selection** — once a session ends, the owner triggers `/result/`, which locks in a winner using whichever algorithm the session was configured with:
  - **Majority vote** — most votes wins; ties are broken randomly.
  - **Random draw** — a proposal is picked at random, ignoring votes entirely.
  - **Weighted preference** — a weighted random draw where `weight = vote_count + 1`, so proposals with more votes are more likely to win but nothing is ever fully excluded.
  
  When a winner is picked, every team member gets a `Notification`, and if the session is recurring, the next occurrence is automatically spawned.
- **Analytics** — per-team stats (wins by restaurant, wins by cuisine, who's actually voting) and a personal/team history of past selections, both filterable by date range.
- **Audit log** — key actions (session creation, votes, suggestion approvals, invites, member removal, etc.) get written to `logs/audit.log` via a dedicated logger, separate from Django's normal logging.

There are three separate static-ish pages served by Django's `TemplateView`, not the DRF API:
- `/` — the main app (`index.html`) — team members create sessions, propose, and vote here.
- `/food-admin/` — restaurant/menu management (`food_admin.html`).
- `/admin-panel/` — a lightweight custom admin panel (`admin_panel.html`), separate from Django's built-in `/admin/`.
- `/join/<token>/` — the invite-link landing page.

## Tech stack

- **Django 3.2** + **Django REST Framework 3.13**, JWT auth via `djangorestframework-simplejwt`
- SQLite by default (there's a `db.sqlite3` already sitting in the repo with seed-able demo data), swaps to **PostgreSQL** automatically if you set a `DATABASE_URL` env var
- **Argon2** for password hashing (falls back to PBKDF2)
- **django-ratelimit** for basic abuse protection (votes are capped at 5/minute per the settings, though check `RATELIMIT_VOTES_PER_MINUTE` and confirm it's actually wired into the vote view before relying on it)
- **django-filter** for API filtering/search/ordering
- **pytest** + **pytest-django** + **coverage** for tests, with a GitHub Actions CI workflow that runs `manage.py check`, a migration-drift check, and the test suite with a 70% coverage floor
- Deploys via Docker: **Gunicorn** behind an **Nginx** reverse proxy, Postgres as a sidecar container

## Project layout

```
lunchpicker/        # Django project config (settings, root urls, wsgi/asgi)
accounts/           # Custom User model + JWT auth endpoints
teams/               # Teams, memberships, invite tokens
restaurants/         # Restaurant + MenuItem catalog
sessions/            # LunchSession, proposals, votes, suggestions, notifications — the core app
analytics/           # Team stats + history endpoints
core/                # Shared permissions, the selection-algorithm logic, audit logging helper
templates/           # index.html, food_admin.html, admin_panel.html, join.html
static/              # admin_panel.js, food_admin.js
tests/               # pytest suite (auth, teams, restaurants, sessions, suggestions, history)
nginx/               # nginx.conf used in the Docker Compose stack
```

Each Django app also ships its own `tests.py` in addition to the top-level `tests/` folder — there's some overlap here, so don't be surprised if similar things are tested in two places.

## Running it locally (no Docker)

You'll need Python 3.11-ish (the Dockerfile uses `python:3.11-slim`, but anything 3.9+ should work fine for local dev since nothing here is 3.11-specific).

```bash
python -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

Then open `http://127.0.0.1:8000/`.

The repo ships with a `db.sqlite3` already in place, so `migrate` may have little or nothing to do. If you'd rather start from a clean slate, just delete `db.sqlite3` before running `migrate`.

### Loading demo data

There's a management command that sets up four demo users, a team, a handful of restaurants with menus, and one live voting session with some votes already cast:

```bash
python manage.py seed_demo
```

It's idempotent (uses `get_or_create` everywhere), so running it twice won't duplicate anything. Demo logins are `sabina`, `ali`, `leyla`, `reshad`, all with the password `lunch1234`. `sabina` is the team owner.

### Creating an admin account

The custom `/admin-panel/` page is separate from Django's built-in admin, but you'll likely still want the built-in one at `/admin/` for direct database poking:

```bash
python manage.py createsuperuser
```

## Running it with Docker

```bash
docker compose up --build
```

This spins up three containers:
- **db** — Postgres 15, with a healthcheck so `web` waits for it to actually be ready
- **web** — the Django app via Gunicorn, migrating automatically on container start
- **nginx** — reverse proxy on port 80, serving static files directly and forwarding everything else to `web`

Once it's up, the app is at `http://localhost/`.

**Before you run this anywhere real**, change the two hardcoded secrets in `docker-compose.yml` — `POSTGRES_PASSWORD` and `DJANGO_SECRET_KEY` are both literally set to `change-me-in-prod`. They're fine for spinning things up locally to poke around, but don't ship them as-is.

Also worth noting: `lunchpicker/settings.py` has `DEBUG = True` and a hardcoded `SECRET_KEY` baked in as the default — both get overridden by environment variables (`DJANGO_DEBUG`, `DJANGO_SECRET_KEY`) in the Docker setup, but if you deploy `web` some other way, make sure you're actually setting those env vars and not just running with the defaults.

## Authentication

This is a JWT-based API (via `djangorestframework-simplejwt`), not session/cookie auth for the API endpoints:

```
POST /api/auth/token/          # { "username": ..., "password": ... } -> access + refresh tokens
POST /api/auth/token/refresh/  # refresh -> new access token
POST /api/auth/token/verify/   # check if a token is still valid
```

Access tokens live for 60 minutes, refresh tokens for 7 days (see `SIMPLE_JWT` in settings). Send the access token as `Authorization: Bearer <token>` on subsequent requests. Signing up a new user is just `POST /api/users/` — that endpoint is open to unauthenticated requests (everything else on `UserViewSet` requires auth, and non-staff users can only see/edit themselves).

## API surface, roughly

Everything below sits under `/api/`:

```
users/                                  DRF ModelViewSet — includes /users/me/
teams/                                  create/list/retrieve teams
teams/{id}/invite_link/       POST      generate a /join/ link
teams/{id}/members/            GET/POST/DELETE   manage membership
join/{token}/preview/          GET       public — peek at a team before logging in
join/{token}/                   GET/POST  accept an invite (requires auth)

restaurants/                            catalog CRUD
restaurants/{id}/menu-items/            nested menu item CRUD

sessions/                               lunch session CRUD
sessions/{id}/proposals/       GET/POST
sessions/{id}/votes/            GET/POST/PUT/DELETE
sessions/{id}/suggestions/     GET/POST
sessions/{id}/clone/            POST     owner-only, duplicates a session as a fresh draft
sessions/{id}/result/           GET/POST  GET to check, POST (owner-only, after end_time) to finalize

suggestions/{id}/approve/      POST      owner/staff — promotes a suggestion to a real proposal
suggestions/{id}/reject/       POST

notifications/                 GET       your own notifications
notifications/unread/          GET
notifications/{id}/read/       POST
notifications/read_all/        POST

analytics/team/{team_id}/               aggregate stats for a team
analytics/history/team/{team_id}/       past results for a team
analytics/history/me/                   past results you were involved in
```

Standard DRF pagination applies (20 items/page), and most list endpoints support filtering/search/ordering via query params (`django-filter` + DRF's `SearchFilter`/`OrderingFilter`).

## Running the tests

```bash
pip install pytest pytest-django coverage
coverage run -m pytest tests/
coverage report
```

CI runs the same thing with `--fail-under=70`, plus a `manage.py check` and a check that no migrations are missing (`makemigrations --check --dry-run`) — so if you add or change a model field, remember to actually generate the migration before pushing, or CI will catch it.

## A few things worth knowing before you touch this in production

- **`DEBUG` and `SECRET_KEY` defaults are unsafe.** They're overridden by env vars in the Docker Compose file, but the fallback values in `settings.py` are not something you want live anywhere reachable.
- **CORS isn't configured.** If you ever split the frontend off into its own origin (instead of Django serving the templates directly), you'll need to add `django-cors-headers` or similar — right now there's nothing handling cross-origin requests.
- **The two "admin" surfaces are different things.** `/admin/` is Django's built-in admin (model-level CRUD, needs `is_staff`/`is_superuser`). `/admin-panel/` is a custom page (`admin_panel.html` + `admin_panel.js`) built specifically for this app's workflows. Don't confuse the two when giving someone access.
- **`analytics/models.py` is currently empty** — the app exists (it's registered in `INSTALLED_APPS` and has its own `urls.py`/`views.py`) but doesn't define its own models; it just queries data that lives in the `sessions` app.
- **The `Vote.CHOICE_LIKE` constant** is a bit of a leftover — it's defined as `1` (used as the default for `choice`), but the actual choices are the full 1–5 range for rating-style voting. Worth double-checking if you extend the voting modes.
- **The included `db.sqlite3` has real-looking data in it already.** If you're forking this to start a fresh deployment, delete it and re-migrate rather than building on top of whatever's already seeded in there.

## License

No license file is included in this archive — check with whoever owns this project before reusing or redistributing the code.

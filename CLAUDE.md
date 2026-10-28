# CLAUDE.md

Internal Applicant Tracking System (CIDM 3312 Project #1). Staff-only Django app for Recruiters and
Admins. The source of truth is `prd/applicant-tracking-system.md`; the phased build order is
`plans/applicant-tracking-system.md`. Implement **one phase at a time** and stop for review.

## Stack

- Python 3.14, **Django ≥ 5.1** (currently 6.1), SQLite, **uv** for dependencies and the venv.
- Tailwind CSS + **DaisyUI** via **django-tailwind-cli** (`TAILWIND_CLI_USE_DAISY_UI`, which downloads
  the pinned `tailwind-cli-extra` binary). Source CSS: `tailwind/source.css`; built output
  `assets/css/tailwind.css` is gitignored.
- **HTMX** 2.0.11 as a pinned static copy at `assets/js/htmx.min.js`.
- **Ruff** for lint and format (config in `pyproject.toml`). Django's built-in test runner.
- No other JS framework, no bundler, no custom JavaScript beyond HTMX and DaisyUI behaviour.
- `django.contrib.admin` is intentionally **not installed**: it would bypass the permission rules
  and the append-only StageChange history.

## Commands

```bash
uv sync                                         # install everything
uv run python manage.py migrate                 # create db.sqlite3 (creates Recruiter/Admin groups)
uv run python manage.py createsuperuser         # first account; superusers count as Admin
uv run python manage.py tailwind build          # build the CSS once
uv run python manage.py tailwind runserver      # dev server + Tailwind watcher
uv run python manage.py test                    # full test suite
uv run ruff check . && uv run ruff format --check .
uv run python manage.py check
```

## TDD rule (every phase)

1. **Red:** write the phase's tests first; run them and confirm they fail for the right reason.
2. **Green:** write the least code that passes.
3. **Refactor** with tests green.
4. Run `ruff check`, `ruff format --check`, `manage.py check` and the full test suite.
5. Add a `PROMPTS.md` entry, then commit (and push when asked).

## Apps and ownership

- `config/`: settings and the root URLconf.
- `core`: base layout (DaisyUI drawer in `templates/base.html`), role helpers (`core/roles.py`),
  the `roles` context processor, shared badge partials, the dashboard. Test helpers live in
  `core/tests/utils.py` (`make_recruiter`, `make_admin`).
- `candidates`: Candidate. `jobs`: JobOpening and Skill (`/jobs/` and `/skills/`).
- `pipeline`: Application, StageChange and the single **stage-change service**.
- `staff`: staff management over Django's built-in `User` (no custom user model).

## Conventions

- **Auth:** `LoginRequiredMiddleware` protects every view; only login is public. Login/logout are
  Django's views at `/accounts/login/` and `/accounts/logout/` (logout is POST only).
- **Roles:** Django groups `Recruiter` and `Admin`, created by `core/migrations/0001_create_role_groups.py`.
  - `core.roles.is_admin(user)` / `role_name(user)` / `@admin_required` are shared by views and
    templates (`user_is_admin`, `user_role` in every template context).
  - Each later model migration attaches its permissions with
    `core.roles.grant_permissions(apps, group, app_label, model_name, actions)`. It creates any
    missing permission rows first, because Django only creates them in `post_migrate`, after all
    migrations have run, so they don't exist yet on a fresh database.
  - Recruiter: view/add/change on Candidate, JobOpening, Application; view on Skill. Admin: all of
    that plus delete on those three, add/change/delete on Skill, and view/add/change on `auth.User`
    (never delete; staff are deactivated).
  - Enforce on the server (403, nothing changed) **and** hide the control in templates.
- **URLs:** pk-based and namespaced per app (`core:dashboard`, `candidates:candidate_list`,
  `jobs:job_list`, `jobs:skill_list`, `pipeline:application_list`, `staff:staff_list`).
- **Templates:** every page extends `base.html` and fills `title` and `content`; one `<h1>` per page.
  Nav links use `core/_nav_link.html`, which marks the current page with `menu-active` and
  `aria-current="page"`. The drawer keeps `auto-cols-[max-content_minmax(0,1fr)]` so content never
  scrolls sideways at phone width.
- **HTMX:** the CSRF token is sent on every HTMX request through `hx-headers` on `<body>`. Stage
  actions and notes edits return partials when `HX-Request` is set.
- **Stage changes:** only through the stage-change service, with the check order: stale expected
  stage → action allowed → required note → guards; conditional `UPDATE … WHERE stage = expected`
  inside `transaction.atomic()`, one StageChange per updated row.

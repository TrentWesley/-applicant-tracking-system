# Applicant Tracking System

CIDM 3312 Project #1. An internal, staff-only Django app for tracking candidates, job openings
and applications through a fixed hiring pipeline (Applied → Screening → Interview → Final Review
→ Offer → Hired, plus Rejected and Withdrawn). Recruiters do the daily work; Admins also manage
skills, staff accounts and permanent deletes.

- Requirements: [`prd/applicant-tracking-system.md`](prd/applicant-tracking-system.md)
- Build plan: [`plans/applicant-tracking-system.md`](plans/applicant-tracking-system.md)
- Conventions for contributors and Claude Code: [`CLAUDE.md`](CLAUDE.md)
- Development log: [`PROMPTS.md`](PROMPTS.md)

## Stack

Python 3.14, Django 6.1, SQLite, [uv](https://docs.astral.sh/uv/), Tailwind CSS with DaisyUI
(through django-tailwind-cli), HTMX 2 (a pinned static copy), and Ruff.

## Run it

```bash
uv sync                                         # install dependencies into .venv
uv run python manage.py migrate                 # create db.sqlite3 and the Recruiter/Admin groups
uv run python manage.py createsuperuser         # first account (a superuser counts as an Admin)
uv run python manage.py tailwind build          # build the CSS once (downloads the Tailwind CLI)
uv run python manage.py tailwind runserver      # dev server with the Tailwind watcher
```

Open <http://127.0.0.1:8000/> and log in. Every page requires login. Use **Staff Management** to
create Recruiter and Admin accounts.

The settings are for local development: `DEBUG` is on, and the secret key falls back to a
public placeholder unless `DJANGO_SECRET_KEY` is set.

## Test and lint

```bash
uv run python manage.py test                    # full test suite
uv run ruff check . && uv run ruff format --check .
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

The suite includes real-thread concurrency tests, which run a worker process against a temporary
SQLite file, so a full run takes a few minutes.

## Roles

| Capability | Recruiter | Admin |
|---|:-:|:-:|
| View the dashboard, candidates, jobs and applications | ✓ | ✓ |
| Create and edit candidates; archive and restore | ✓ | ✓ |
| Create and edit jobs; assign skills; close and reopen | ✓ | ✓ |
| Create applications; edit notes; Advance, Back, Reject, Withdraw, Reactivate | ✓ | ✓ |
| Create, rename and delete skills | | ✓ |
| Permanently delete candidates, jobs and applications (subject to guards) | | ✓ |
| Create staff accounts, change roles, deactivate and reactivate | | ✓ |

Restricted actions are refused by the server (403, nothing changed) as well as hidden.

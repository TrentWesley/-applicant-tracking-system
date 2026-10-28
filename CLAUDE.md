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
- `candidates`: Candidate (`/candidates/`, `/candidates/archived/`, `/candidates/new/`,
  `/candidates/<pk>/`, `/candidates/<pk>/edit/`, POST `/candidates/<pk>/archive/` and
  `/restore/`) and `candidates/services.py` (`archive_candidate`, `restore_candidate`,
  `candidate_is_archived`); test helper `candidates.tests.utils.make_candidate`.
- `jobs`: JobOpening and Skill (`/jobs/`, `/jobs/new/`, `/jobs/<pk>/`, `/jobs/<pk>/edit/`,
  POST `/jobs/<pk>/close/` and `/jobs/<pk>/reopen/`, `/jobs/?skill=<pk>`; Admin-only `/skills/`,
  `/skills/new/`, `/skills/<pk>/edit/`, `/skills/<pk>/delete/`); test helpers `jobs.tests.utils.make_skill` and `make_job`.
- `pipeline`: Application, StageChange and the single **stage-change service**
  (`pipeline/services.py`: `create_application`, and `change_stage` for Advance, Back, Reject,
  Withdraw and Reactivate). Pages:
  `/applications/` (`?stage=<value>`, lowercase stored values such as `final_review`),
  `/applications/new/` (`?candidate=<pk>` preselects an active candidate), `/applications/<pk>/`
  (`?confirm=<action>` opens the inline note form; with `HX-Request` it returns only the stage
  card), POST `/applications/<pk>/transition/`. Test helper `pipeline.tests.utils.make_application`
  (creates through the service with a unique candidate; a `stage=` argument is set directly as
  test setup, so only the creation entry is in its history).
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
  `aria-current="page"`; pass `section="<view-name prefix>"` (`"candidates:"`, `"jobs:job_"`,
  `"jobs:skill_"`) so every page in that section highlights the link.
  The drawer keeps `auto-cols-[max-content_minmax(0,1fr)]` so content never scrolls sideways at
  phone width.
- **Forms:** ModelForms mix in `core.forms.DaisyUIFormMixin` (DaisyUI widget classes) and render
  each field with `core/_field.html` (label, required `*`, help text, and errors in
  `id_<field>_error`, which Django's `aria-describedby` points to). Invalid inputs get a red border
  from the `aria-invalid` rule in `tailwind/source.css` (it lives in `@layer utilities`, because
  DaisyUI 5's own rules sit in sublayers there). Checkbox lists use `core.forms.CheckboxSelectMultiple`;
  `_field.html` renders them in a `<fieldset>` with a `<legend>`.
- **Views:** generic CBVs with `core.views.StaffPermissionMixin` (Django's `PermissionRequiredMixin`
  with `raise_exception = True`: 403 for signed-in users without the permission). Templates hide controls with `perms.<app>.<codename>`.
- **Case-insensitive uniqueness:** a `UniqueConstraint(Lower(field))` in the model, plus a form
  `clean_<field>` that checks `__iexact` (excluding the instance being edited) so the message sits
  on the field.
- **Deleting a skill:** job skills go through the `JobSkill` model, whose `skill` FK is `PROTECT`.
  The skill delete view has no "is it used?" pre-check; it deletes inside `transaction.atomic()` and
  shows the refusal on `ProtectedError`, or on `IntegrityError` when the database's deferred FK
  check catches an assignment committed by another request during the delete.
- **HTMX:** the CSRF token is sent on every HTMX request through `hx-headers` on `<body>`. Stage
  actions and notes edits return partials when `HX-Request` is set.
- **Archived candidates:** an archived candidate never has an active application. Archive is
  refused while any application is active (the message lists them); Hired, Rejected and
  Withdrawn don't block it. Archive and Restore touch only `archived_at` and `updated_at`, and a
  repeated or stale one raises `CandidateStatusRefused`. The rule is held by the database:
  - SQLite triggers (`pipeline/0004_archived_candidate_guards`) refuse inserting an application
    for an archived candidate, moving one into an active stage, and archiving a candidate with
    an active application. Their messages contain `ARCHIVED_GUARD`, which the services turn back
    into their usual refusals.
  - `DATABASES["default"]["OPTIONS"]["transaction_mode"] = "IMMEDIATE"`: every `atomic()`
    takes the write lock at BEGIN, so concurrent check-then-write requests wait and then see
    each other's commit instead of failing with "database is locked".
    `candidates/tests/test_archive_concurrency.py` runs two real threads against a SQLite file
    (via `concurrency_worker.py`) to prove it.
  - Don't set `archived_at` directly in tests on a candidate with an active application: the
    trigger refuses it.
- **Edit forms save only their own fields** (`CandidateForm.save` uses `update_fields`): a full
  `save()` writes back every column from the copy the request loaded, undoing an Archive,
  Restore, Close or stage move committed in between. Follow this for any new edit form, such as
  application notes. (The Phase 3 job edit form doesn't yet; see PROMPTS.md Entry 21.)
- **Job status:** changes only through `jobs/services.py` (`close_job`, `reopen_job`): a
  conditional `UPDATE … WHERE status = <from>`, so a repeated or stale request raises
  `JobStatusUnchanged` ("already closed/open") and changes nothing. They never touch
  applications; the stage-change service never checks job status except when creating.
  `core/_job_status_badge.html` shows Open or **Job Closed**; the application list shows it only
  for closed jobs, and a closed job's detail page notes how many active applications remain.
- **Stage badges:** `core/_stage_badge.html` with `stage=` and `label=` (e.g.
  `label=application.get_stage_display`); one style each for early active stages, Offer, Hired, and
  Rejected/Withdrawn.
- **StageChange is append-only:** the model refuses `save()` on an existing row and `delete()`,
  the queryset refuses `update()`, `bulk_update()` and `delete()`, and a SQLite trigger (`pipeline/0002`) refuses any
  `UPDATE`. Rows go only through the cascade when their Application is deleted. Service refusals
  raise `StageChangeRefused` with the user-facing message.
- **Stage card:** `pipeline/_stage_card.html` (`id="stage-card"`) renders only the moves from
  `services.available_moves(stage, reactivate_to)`. Advance and Back are one form each with hidden
  `action` and `expected_stage`, `hx-post`, `hx-target="#stage-card"` and
  `hx-disabled-elt="find button"`. Reject, Withdraw and Reactivate (`Move.needs_note`) are links
  to `?confirm=<action>` (`hx-get`) that swap in the note form; Confirm posts to the same
  endpoint, Cancel re-fetches the card with `?focus=<action>` (autofocus returns to the link that
  opened the form), and a `NoteRequired` refusal keeps the form open. The
  detail view sends `Vary: HX-Request`. The HTMX response
  (`_transition_response.html`) is the card plus `_stage_history.html` swapped out of band; without
  HTMX the view redirects to the detail page with a message. Refusals return 200 so HTMX swaps the
  card with the reason. Views build the card's context with `pipeline.views.stage_card_context`.
- **Stage changes:** only through the stage-change service, with the check order: stale expected
  stage → action allowed → required note → guards; conditional `UPDATE … WHERE stage = expected`
  inside `transaction.atomic()`, one StageChange per updated row. Reactivate returns to the
  `from_stage` of the latest StageChange (`services.reactivation_target`); only an archived
  candidate blocks it, never a closed job. Hired allows no action.

# Plan: Applicant Tracking System

> Source PRD: `prd/applicant-tracking-system.md` (60 user stories, AC1–AC45).
> Context: `PROMPTS.md` (grill-me Q1–Q27), `prototypes/hiring-stage-logic-findings.md`,
> `prototypes/dashboard-ui-findings.md`.
> Status: approved breakdown (13 phases, order fixed). No production code has been written yet.

## Architectural decisions

These durable decisions apply to every phase.

- **Stack:** Python with **Django 5.1 or later**, SQLite, **uv** for dependencies and the virtual
  environment, Tailwind CSS with DaisyUI through **django-tailwind-cli**, **HTMX**, and **Ruff** for
  linting and formatting. Tests use Django's built-in test runner. There's no other JavaScript
  framework, no bundler, and no custom JavaScript beyond HTMX and DaisyUI's built-in behaviour.
- **Project package:** `config/` for settings and the root URLconf.
- **Owning apps:**
  - `core`: the base layout (DaisyUI drawer sidebar), shared badge partials, permission helpers and
    the dashboard.
  - `candidates`: Candidate.
  - `jobs`: JobOpening and Skill.
  - `pipeline`: Application, StageChange and the single **stage-change service**.
  - `staff`: staff account management over Django's built-in `User`. This app has no custom user
    model.
- **Authentication:** Django's built-in auth views at `/accounts/login/` and `/accounts/logout/`.
  `LoginRequiredMiddleware` makes every page except login require a signed-in user.
- **Authorization:**
  - **Groups:** two Django groups, `Recruiter` and `Admin`, created reproducibly by a migration and
    assigned Django model permissions.
  - **Recruiter permissions:** view, add and change on Candidate, JobOpening and Application, plus
    view on Skill. Archive and restore, close and reopen, stage moves and notes edits all count as
    *change*.
  - **Admin permissions:** everything a Recruiter has, plus delete on Candidate, JobOpening and
    Application, add, change and delete on Skill, and the auth `User` permissions used by Staff
    Management.
  - **Enforcement:** every restricted view checks the permission on the server, and templates hide
    the matching controls. A forbidden request returns 403 and changes nothing.
- **Models and relationships:**
  - `Candidate`: email unique ignoring case (a database constraint on `Lower(email)`); `source`
    TextChoices; `archived_at` is null while the candidate is active.
  - `JobOpening`: `employment_type`, `work_mode` and `status` TextChoices; `status` defaults to Open;
    `skills` is a many-to-many with `Skill`.
  - `Skill`: name unique ignoring case (a database constraint on `Lower(name)`).
  - `Application`:
    - foreign keys to Candidate (PROTECT), JobOpening (PROTECT) and `created_by` User (PROTECT);
    - `stage` TextChoices with 8 values;
    - `stage_changed_at`, `created_at` and editable `notes`;
    - a unique constraint on (candidate, job_opening).
  - `StageChange`:
    - foreign keys to Application (CASCADE) and `changed_by` User (PROTECT);
    - `from_stage` (null for the creation entry), `to_stage`, `changed_at` and `note`;
    - ordered by `changed_at`, then id;
    - append-only, written only by the stage-change service.
- **URLs:** pk-based, with named routes namespaced per app.
  - **Dashboard:** `/` (`core:dashboard`).
  - **Candidates:**
    - `/candidates/`, `/candidates/archived/`, `/candidates/new/`
    - `/candidates/<pk>/` and `/candidates/<pk>/edit/`
    - POST `/candidates/<pk>/archive/`, `/restore/` and `/delete/`
  - **Jobs:**
    - `/jobs/` (with `?skill=<pk>`), `/jobs/new/`
    - `/jobs/<pk>/` and `/jobs/<pk>/edit/`
    - POST `/jobs/<pk>/close/`, `/reopen/` and `/delete/`
  - **Skills (Admin):** `/skills/`, `/skills/new/`, `/skills/<pk>/edit/`, POST `/skills/<pk>/delete/`.
  - **Applications:**
    - `/applications/` (with `?stage=<stage>`)
    - `/applications/new/` (with `?candidate=<pk>` as an initial value)
    - `/applications/<pk>/`
    - POST `/applications/<pk>/notes/` and `/applications/<pk>/delete/`
    - POST `/applications/<pk>/transition/`, carrying `action` and `expected_stage`
  - **Staff (Admin):**
    - `/staff/` (with `?show=inactive`), `/staff/new/`
    - POST `/staff/<pk>/role/`, `/deactivate/` and `/reactivate/`
- **Stage-change rules:** these come from the PRD stage table.
  - **Check order:** (1) stale expected stage, (2) is the action allowed, (3) required note after
    trimming, (4) the candidate is not archived (for Reactivate).
  - **Applying a change:** inside `transaction.atomic()`, a conditional
    `UPDATE … WHERE stage = expected`. Exactly one StageChange row is written only when exactly one
    row was updated.
- **HTMX:** stage actions and notes edits return partials (the application card or row) when
  `HX-Request` is set. The CSRF token is sent with every HTMX request through the base template.
- **TDD workflow, every phase:**
  1. **Red:** write the phase's tests first and confirm they fail for the right reason.
  2. **Green:** write the least code that passes.
  3. **Refactor:** clean up with tests green.
  4. Run `ruff check`, `ruff format --check` and the full test suite.
  5. Add a `PROMPTS.md` entry, then commit and push.

---

## Phase 1: Project setup, login, roles and sidebar layout

**User stories**: 1, 2, 3, 4, 5, 59

### Objective and scope

Stand up a working Django project that a staff member can log in to and land on an empty dashboard
inside the sidebar layout. Anonymous users are redirected to login. The two roles exist, and the
Admin-only navigation group renders only for Admins. No ATS models yet.

### Dependencies

None.

### Implementation tasks

- Initialise the uv project with Django ≥ 5.1, django-tailwind-cli and Ruff (as a dev dependency),
  and configure Ruff in `pyproject.toml`.
- Create the `config` project and the five apps: `core`, `candidates`, `jobs`, `pipeline` and
  `staff`.
- Enable `LoginRequiredMiddleware`, wire up Django's login and logout views, and set the login
  redirect to the dashboard.
- Configure django-tailwind-cli with the DaisyUI plugin, and include HTMX from a pinned static copy
  or a pinned CDN version.
- Build the base template:
  - a DaisyUI drawer, open on large screens, with a labelled ☰ toggle on small ones;
  - navigation links: Dashboard, Candidates, Job Openings, Applications;
  - an Admin-only group with Skills and Staff Management;
  - the signed-in user and their role;
  - HTMX's CSRF header setup.
- Add a migration that creates the `Recruiter` and `Admin` groups. Later phases' migrations attach
  each model's permissions as those models are added.
- Add a small role helper (for example, an "is Admin" check) that templates and views share, plus
  a placeholder dashboard view at `/`.
- Write `CLAUDE.md` covering the stack, commands (uv, Tailwind, tests, Ruff), the TDD rule, app
  ownership and the conventions above.

### Tests to write first

- Anonymous GET of `/` and of a sample protected URL → redirect to login (AC1).
- A login page is reachable anonymously; valid credentials log in and land on the dashboard.
- An inactive user can't log in. This is Django's default behaviour, asserted here so later
  phases can rely on it.
- Both groups exist after migrating.
- The dashboard for a Recruiter doesn't contain the Skills or Staff Management links; for an
  Admin, it does (AC3, navigation part).
- The base layout renders the drawer toggle with an accessible label, and the four main navigation
  links.

### Acceptance criteria covered

AC1, AC3 (Admin navigation part), AC45 (quality gate set up).

### Completion checklist

- [ ] `uv sync` installs everything; `uv run python manage.py runserver` serves the login page.
- [ ] Tailwind builds through django-tailwind-cli, and DaisyUI styles render.
- [ ] Anonymous requests redirect to login on every page.
- [ ] Recruiter and Admin groups exist; Admin navigation appears only for Admins.
- [ ] `CLAUDE.md` written; `PROMPTS.md` entry added.
- [ ] Ruff lint and format pass; all tests pass; committed and pushed.

---

## Phase 2: Candidates (create, list, detail, edit)

**User stories**: 6, 7, 8, 9, 10

### Objective and scope

Recruiters and Admins can add, view, list and edit candidates, with duplicate emails refused in any
letter case. Archiving and deletion come later (Phases 8 and 10).

### Dependencies

Phase 1.

### Implementation tasks

- `Candidate` model with the PRD fields:
  - required first name, last name, email and source;
  - optional phone, source details, notes and profile URL;
  - `archived_at`, `created_at` and `updated_at`.
- Source TextChoices: Referral, Company Website, Job Board, LinkedIn, Career Fair, Agency and Other.
- Database constraint for email uniqueness ignoring case, plus form validation with the message
  "A candidate with this email already exists." The check excludes the candidate's own record when
  editing.
- Migration that grants Candidate view, add and change permissions to both groups, and delete to
  Admin only.
- List (non-archived candidates only), detail, create and edit views and templates in the sidebar
  layout. Each requires the matching permission.

### Tests to write first

- **Model:** a candidate whose email differs only in case raises an IntegrityError at the database
  level (AC4).
- **Form:**
  - the duplicate email in a different case is refused with the "already exists" message (AC4);
  - editing a candidate without changing their email is allowed;
  - missing first name, last name, email or source is refused; phone, source details, notes and URL
    may be blank; an invalid URL is refused; an invalid source value is refused (AC5).
- **Views:**
  - Recruiter and Admin can create, view, list and edit;
  - create redirects to the detail page;
  - edit applies the same validation as create (US 10);
  - the list excludes candidates with `archived_at` set;
  - a user without the permission gets 403 (permission test for this phase).

### Acceptance criteria covered

AC4, AC5 (AC2 and AC3 for candidate create and edit).

### Completion checklist

- [ ] Candidate model and migration with the case-insensitive email constraint.
- [ ] Create, edit, list and detail pages working in the sidebar layout.
- [ ] Duplicate-email message shown on create and edit.
- [ ] Permission tests pass.
- [ ] Ruff and tests pass; `PROMPTS.md` updated; committed and pushed.

---

## Phase 3: Skills and job openings

**User stories**: 20, 26, 27, 28, 29

### Objective and scope

Admins manage the skills list. Recruiters and Admins create and edit job openings with required
skills, and filter the job list by skill. Status always starts as Open and isn't editable on any
form. Close and Reopen come in Phase 7; deleting a job comes in Phase 10.

### Dependencies

Phase 1.

### Implementation tasks

- `Skill` model: name unique ignoring case, through a database constraint plus form validation.
- `JobOpening` model:
  - required title, employment type and work mode;
  - optional department, location and description;
  - `status`, which defaults to Open;
  - a many-to-many to Skill;
  - timestamps.
- Choices: employment type (Full-time, Part-time, Contract, Internship), work mode (On-site, Remote,
  Hybrid), and status (Open, Closed).
- Migration permissions:
  - JobOpening: view, add and change for both groups; delete for Admin only.
  - Skill: view for both groups; add, change and delete for Admin only.
- **Skills pages (Admin only):** list, create, rename and delete. Deleting is refused while any job,
  open or closed, uses the skill, with an error that lists those jobs.
- **Job pages:**
  - a list with a skill filter (`?skill=<pk>`) and a status badge;
  - a detail page showing the job's fields and skills;
  - create and edit forms with skill selection and **no status field**.

### Tests to write first

- **Skill:**
  - a duplicate name in a different case is refused by both the database and the form (AC15);
  - a Recruiter gets 403 on skill list, create, rename and delete (AC15, AC2);
  - an Admin can create, rename and delete an unused skill;
  - deleting a skill used by an open job, or by a closed job, is refused, the jobs are listed, and
    the skill still exists (AC16).
- **JobOpening:**
  - a new job is Open;
  - required fields and invalid choice values are refused;
  - a `status=Closed` value posted to the create or edit form is ignored (AC11).
- **Skills on jobs:** a job can have several skills and a skill can be on several jobs;
  `?skill=<pk>` returns exactly the jobs with that skill (AC14).
- **Permissions:** Recruiter and Admin can create, edit, list and view jobs (AC2, AC3).

### Acceptance criteria covered

AC11, AC14, AC15, AC16.

### Completion checklist

- [ ] Skill and JobOpening models and migrations, with the case-insensitive name constraint.
- [ ] Admin-only Skills pages; delete guard lists the jobs that use the skill.
- [ ] Job create and edit forms with no status field; new jobs start Open.
- [ ] Skill filter on the job list.
- [ ] Ruff and tests pass; `PROMPTS.md` updated; committed and pushed.

---

## Phase 4: Applications (creation, list, detail and history)

**User stories**: 32, 33, 34, 35, 45, 46

### Objective and scope

Recruiters link a candidate to a job from either New Application entry point. Each application
starts at Applied with its creation entry in the history, and appears in a stage-filtered list and
on a detail page with its history. This phase introduces the **stage-change service**, so that
creation already goes through it. Moves between stages come in Phases 5 and 6.

### Dependencies

Phases 2 and 3.

### Implementation tasks

- `Application` model:
  - foreign keys to Candidate (PROTECT), JobOpening (PROTECT) and `created_by` (PROTECT);
  - the 8-value stage choices (Applied, Screening, Interview, Final Review, Offer, Hired, Rejected,
    Withdrawn), with stage defined as active or terminal;
  - `stage_changed_at`, `created_at` and `notes`;
  - a unique constraint on (candidate, job_opening).
- `StageChange` model:
  - foreign keys to Application (CASCADE) and `changed_by` (PROTECT);
  - nullable `from_stage`, plus `to_stage`, `changed_at` and `note`;
  - chronological ordering.
- **Stage-change service, creation path:**
  - inside one transaction, create the application at Applied and its StageChange
    (null → Applied, changed_by = creator);
  - guards: the job is Open, the candidate is not archived, and the pair isn't a duplicate;
  - each refusal has a clear reason.
- **Create form:**
  - offers only Open jobs and non-archived candidates;
  - accepts `?candidate=<pk>` as an initial value that the user can change;
  - re-checks every guard on the server, including when the preselected candidate is invalid.
- **Entry points:** the New Application button on the Applications list, and on the candidate
  detail page (non-archived candidates only). The candidate detail page also lists the candidate's
  applications with stage badges.
- **Applications list:** filterable by `?stage=<stage>`, including applications on both open and
  closed jobs.
- **Detail page:** current stage, a notes display, and the read-only chronological history
  (from, to, who, when, note). There are no create, edit or delete screens for StageChange.
- First version of the shared **stage badge** partial, used on the list, the detail page and the
  candidate page.
- Migration permissions: Application view, add and change for both groups; delete for Admin only.
  StageChange gets no add, change or delete views.

### Tests to write first

- **Creating an application:**
  - creation yields stage Applied and exactly one StageChange (from null, to Applied, changed_by
    the creator), created in the same transaction (AC19);
  - if the StageChange write fails, no application is left behind (atomicity).
- **Refused creation, writing nothing** (AC20):
  - the job is Closed (status set directly in the test);
  - the candidate is archived (`archived_at` set directly);
  - a duplicate pair, both through the form and as an IntegrityError at the database level.
- **Entry points** (AC33):
  - the Applications list and a non-archived candidate's detail page both link to the same create
    URL;
  - the candidate page link preselects that candidate;
  - an archived candidate's page shows no button;
  - posting the form for an archived candidate is refused.
- **Form choices:** the form doesn't offer Closed jobs or archived candidates.
- **Stage filter:** `?stage=Applied` returns applications on both open and closed jobs, and only
  that stage (AC32).
- **History:** the detail page lists history oldest first; no URL exists for creating, editing or
  deleting a StageChange (AC30).
- **Permissions:** Recruiter and Admin can create applications (AC2).

### Acceptance criteria covered

AC19, AC20, AC30, AC32, AC33.

### Completion checklist

- [ ] Application and StageChange models and migrations with the constraints and `on_delete` rules
      above.
- [ ] The stage-change service handles creation atomically.
- [ ] Both New Application entry points share one form, with the candidate preselected from the
      candidate page.
- [ ] Stage-filtered list and detail page with history.
- [ ] Ruff and tests pass; `PROMPTS.md` updated; committed and pushed.

---

## Phase 5: Advance and Back over HTMX, with stale and double-click safety

**User stories**: 36, 37, 43, 44

### Objective and scope

From the application card or row, a Recruiter advances or moves back one stage with a single HTMX
click, and the card updates in place. Out-of-date clicks and double-clicks are refused safely.
Only allowed actions are rendered.

### Dependencies

Phase 4.

### Implementation tasks

- Extend the stage-change service with the transition table for **Advance** (any active stage →
  next; Offer → Hired) and **Back** (Screening through Offer → previous). Note is optional.
- Apply the check order:
  1. stale expected stage → "already updated";
  2. is the action allowed from the current stage;
  3. (required note, used from Phase 6);
  4. (guards, used from Phase 6).
- Apply each change with a conditional update inside `transaction.atomic()`
  (`filter(pk, stage=expected).update(...)`), writing one StageChange only when exactly one row
  was updated.
- Transition endpoint at POST `/applications/<pk>/transition/`, with `action` and `expected_stage`
  from a hidden field:
  - with HTMX, returns the refreshed card partial with a success or refusal message;
  - without HTMX, redirects to the detail page.
- Card partial that renders only the actions allowed for the current stage.

### Tests to write first

- **Service:**
  - every allowed Advance and Back in the table succeeds and writes exactly one StageChange with
    the correct from, to, user and note (AC21, Advance and Back rows);
  - Offer → Advance → Hired (AC22: Hired is reached only from Offer).
- **Refused moves, writing no StageChange** (AC22):
  - Back from Applied;
  - Advance or Back from Hired, Rejected and Withdrawn;
  - any attempt to skip a stage, including an unknown action and a request that names a target
    stage.
- **Stale request:** a request whose expected stage doesn't match the current stage is refused,
  with no change and no StageChange; the response contains the refreshed card and the "already
  updated" message (AC27).
- **Double-click:** two identical requests with the same expected stage produce exactly one
  transition and one StageChange (AC28).
- **HTMX:**
  - an HTMX request returns a partial (no `<html>` and no sidebar);
  - the rendered buttons match the allowed actions for each of the 8 stages (AC29);
  - the request requires a valid CSRF token.
- **Permissions:** Recruiter and Admin can move applications; a user without the change permission
  gets 403 with nothing changed (AC2).

### Acceptance criteria covered

AC21 (Advance and Back), AC22, AC27, AC28, AC29.

### Completion checklist

- [ ] The service enforces the check order and the conditional update.
- [ ] HTMX Advance and Back update the card in place.
- [ ] Stale and double-click requests are refused with a refreshed card.
- [ ] Ruff and tests pass; `PROMPTS.md` updated; committed and pushed.

---

## Phase 6: Reject, Withdraw and Reactivate; Hired is permanent

**User stories**: 38, 39, 41, 42

### Objective and scope

Recruiters reject or withdraw an active application, and reactivate a Rejected or Withdrawn one,
each through a small inline HTMX form with a required note. Reactivation returns the application
to the active stage it left. Hired allows no action and changes nothing else.

### Dependencies

Phase 5.

### Implementation tasks

- **Reject** and **Withdraw:** from any active stage; a note is required.
- **Reactivate:**
  - from Rejected or Withdrawn; a note is required;
  - the target is the `from_stage` of the application's latest StageChange;
  - guard: the candidate is not archived (check 4).
- Required-note check: refuse a note that is empty after trimming whitespace.
- Inline note form: an HTMX GET swaps in a note field and a Confirm button; Cancel restores the
  card. Confirm posts to the same transition endpoint.
- Hired renders no actions, and any request against it is refused.
- Make sure hiring touches only the selected application.

### Tests to write first

- **Allowed moves:** Reject and Withdraw from each active stage, and Reactivate from Rejected and
  from Withdrawn, each write exactly one StageChange with the note (AC21, remaining rows).
- **Missing or whitespace-only notes** for Reject, Withdraw and Reactivate are refused with no
  change and no StageChange; Advance and Back still succeed without a note (AC23).
- **Reactivation target:**
  - reactivation returns to the stage held before the latest Rejected or Withdrawn move (for
    example, Interview → Rejected → reactivated returns to Interview);
  - after repeated cycles, it returns to the most recent active stage (AC24).
- **Refused moves** (AC22): Reactivate from an active stage, Reject or Withdraw from a terminal
  stage.
- **Hired:** every action from Hired, including Reactivate, is refused (AC25, Hired part).
- **No side effects** (AC26): hiring leaves other applications for that job, the candidate's other
  applications, and the job's status unchanged.
- **Check order:** a stale request without a note reports "already updated", not "note required".
- **HTMX:**
  - the inline note form is a partial;
  - only allowed actions render for Rejected and Withdrawn (Reactivate only) and for Hired (none)
    (AC29).

### Acceptance criteria covered

AC21 (complete), AC23, AC24, AC25 (Hired part), AC26.

### Completion checklist

- [ ] Reject, Withdraw and Reactivate with required notes, through inline HTMX forms.
- [ ] Reactivation target read from the history; repeated cycles tested.
- [ ] Hired is permanent and has no side effects.
- [ ] Ruff and tests pass; `PROMPTS.md` updated; committed and pushed.

---

## Phase 7: Close and reopen jobs

**User stories**: 21, 22, 23, 24, 40

### Objective and scope

Recruiters close and reopen jobs only through dedicated actions. A closed job refuses new
applications, while its existing applications keep moving, including reactivation, which leaves
the job Closed. Closed jobs are clearly marked, along with whether they still have active
applications.

### Dependencies

Phase 6. Reactivation on a closed job needs the Phase 6 moves.

### Implementation tasks

- POST Close and Reopen actions on the job detail page; both require the JobOpening change
  permission. Each changes only the job's status.
- **Job Closed** badge partial on the job list, the job detail page, and on applications belonging
  to a closed job. The job detail page shows an active-applications note when the job is closed
  and still has active applications.
- Confirm that the stage-change service never checks job status for Reactivate.

### Tests to write first

- **Close:** status becomes Closed, and no application's stage or StageChange count changes; a new
  application for the job is refused (AC12).
- **Active applications on a closed job** can still Advance, Back, Reject and Withdraw (AC12).
- **Reopen:**
  - status becomes Open, and no application changes;
  - a new application for a different candidate succeeds;
  - a duplicate for an existing candidate and job pair is still refused (AC13).
- **Reactivation on a closed job** succeeds, writes one StageChange, and the job stays Closed; a
  new application to that job is still refused afterwards (AC25, closed-job part; mirrors
  walkthrough 6).
- **Status changes only through these actions:** editing the job with a status value leaves status
  unchanged (AC11 regression test).
- **Badges:** the Job Closed badge appears on a closed job, and on its applications in the list;
  the active-applications note appears only when relevant (US 23).
- **Permissions:** Recruiter and Admin can close and reopen jobs (AC2); GET on these endpoints
  isn't allowed.

### Acceptance criteria covered

AC12, AC13, AC25 (closed-job part).

### Completion checklist

- [ ] Dedicated Close and Reopen actions; status isn't editable anywhere else.
- [ ] New applications refused on closed jobs; existing ones keep moving and can be reactivated.
- [ ] Job Closed badge and active-applications note.
- [ ] Ruff and tests pass; `PROMPTS.md` updated; committed and pushed.

---

## Phase 8: Candidate archive and restore

**User stories**: 11, 12, 13, 14, 15, 16

### Objective and scope

Recruiters archive candidates whose applications are all terminal (Hired candidates included),
see them in an archived view, and restore them without changing anything else. Archived
candidates can't get new applications or have applications reactivated.

### Dependencies

Phases 6 and 7. Archiving is checked against terminal stages, and the reactivation guard needs
Reactivate.

### Implementation tasks

- POST Archive action: refused while any application is in an active stage, with an error listing
  those applications. Otherwise it sets `archived_at`.
- POST Restore action: clears `archived_at`, and changes nothing else.
- Archived candidates view at `/candidates/archived/`, linked from the candidate list. Its detail
  page shows the Restore action and no New Application button.
- Confirm that the creation guard (Phase 4) and the Reactivate guard (Phase 6) both use the
  candidate's archived state.

### Tests to write first

- **Refused archive:** archiving a candidate with an active application is refused, the error lists
  the applications, and `archived_at` stays empty (AC6).
- **Allowed archive:** archiving succeeds when all applications are Hired, Rejected or Withdrawn,
  including a candidate with a Hired application, or when there are no applications (AC6).
- **Lists:** archived candidates are excluded from the default list and appear in the archived view
  (AC7).
- **Restore:** `archived_at` is cleared, and every application stage and StageChange count is
  unchanged (AC8).
- **Archived candidates are blocked** (AC9, AC25 archived part):
  - a new application is refused;
  - reactivating their Rejected or Withdrawn application is refused with no StageChange;
  - after a restore, reactivation succeeds.
- **No side effects:** archiving leaves the Hired application, its history and the job's hired
  count unchanged.
- **Permissions:** Recruiter and Admin can archive and restore (AC2).

### Acceptance criteria covered

AC6, AC7, AC8, AC9, AC25 (archived part, which completes AC25).

### Completion checklist

- [ ] Archive guard lists active applications; Hired candidates can be archived.
- [ ] Archived view and Restore working.
- [ ] Archived candidates blocked from new applications and reactivation.
- [ ] Ruff and tests pass; `PROMPTS.md` updated; committed and pushed.

---

## Phase 9: Edit application notes

**User stories**: 49

### Objective and scope

Recruiters and Admins edit an application's general notes on its detail page. The stage, the
stage-changed-at time and the history are untouched, and StageChange notes stay unchangeable.

### Dependencies

Phase 4.

### Implementation tasks

- Notes form on the application detail page, posted to `/applications/<pk>/notes/`. It swaps the
  notes section in place with HTMX, and falls back to a redirect without HTMX.
- The update writes only the `notes` field. It never goes through the stage-change service.

### Tests to write first

- Recruiter and Admin can edit notes; afterwards stage, `stage_changed_at` and the StageChange
  count are unchanged (AC34).
- Notes can be cleared.
- A POST that includes `stage` or other fields changes only the notes.
- There's no URL for editing or deleting a StageChange or its note, and the history section renders
  read-only (AC34, AC30).
- An HTMX request returns the notes partial.

### Acceptance criteria covered

AC34.

### Completion checklist

- [ ] Notes editable in place; nothing else changes.
- [ ] StageChange history remains read-only.
- [ ] Ruff and tests pass; `PROMPTS.md` updated; committed and pushed.

---

## Phase 10: Admin permanent deletes

**User stories**: 17, 18, 30, 31, 47, 48

### Objective and scope

Admins permanently delete candidates, jobs and applications entered by mistake. Anything with
hiring history is refused with a clear error. Recruiters never see or reach these actions.

### Dependencies

Phases 4, 7 and 8.

### Implementation tasks

- **Candidate delete:** POST with a confirmation step, Admin only. Catch `ProtectedError` and
  explain the refusal.
- **Job delete:** POST with a confirmation step, Admin only. Allowed for Open or Closed jobs with no
  applications. A refusal suggests closing the job instead.
- **Application delete:** POST, Admin only. Allowed only at Applied with exactly one StageChange;
  the creation entry is removed by CASCADE.
- Each Delete button renders only for Admins, and only where the delete is possible.

### Tests to write first

- **Candidate:** an Admin deletes a candidate with no applications; deleting one with any
  application is refused, the error is shown, and nothing is removed (AC10).
- **Job:** an Admin deletes an Open or a Closed job with no applications; deleting one with
  applications is refused with the "close it instead" message (AC17).
- **Application** (AC31):
  - an Admin deletes a never-moved application, and its single StageChange is gone;
  - deleting an application that advanced and then went back to Applied is refused;
  - deleting a terminal application is refused.
- **Recruiter refusals:** a Recruiter gets 403 on all three delete endpoints, and nothing is
  removed (AC2, AC31). The Delete buttons are hidden for Recruiters.

### Acceptance criteria covered

AC10, AC17, AC31.

### Completion checklist

- [ ] Three Admin-only deletes with guards and clear errors.
- [ ] Recruiters are refused on the server and see no Delete buttons.
- [ ] Ruff and tests pass; `PROMPTS.md` updated; committed and pushed.

---

## Phase 11: Staff management

**User stories**: 50, 51, 52, 53, 54

### Objective and scope

Admins create staff accounts with a role, change roles, and deactivate and reactivate accounts.
Inactive staff are hidden by default but can be shown, and their names stay on history. Nobody can
lock out administration.

### Dependencies

Phase 1. Phases 4 to 6 provide the Application and StageChange records used in the history tests.

### Implementation tasks

- **Staff list:** `/staff/` lists active users with their role; `?show=inactive` includes inactive
  users.
- **Create:** username, name, email, password and role. The role is a group: Admin or Recruiter.
- **Change role:** POST that swaps the user between the two groups.
- **Deactivate and reactivate:** POST actions that toggle `is_active`. Nothing else about the user
  changes.
- **Admin protection:**
  - an Admin can't deactivate or demote themselves;
  - the last active Admin can't be deactivated or demoted;
  - each refusal changes nothing and shows a clear message.
- All staff views are Admin-only. There's no user delete action in the app.

### Tests to write first

- **Create:** an Admin creates a Recruiter and an Admin, and each is in the right group (AC35).
- **Deactivate** (AC36):
  - a deactivated user can't log in;
  - their name still renders on their Application and StageChange entries;
  - they're hidden from the default staff list and shown with `?show=inactive`.
- **Reactivate:** the user can log in again, and their Application and StageChange records are
  unchanged (AC37).
- **Recruiter refusals:** a Recruiter gets 403 on list, create, role change, deactivate and
  reactivate (AC37, AC2).
- **Admin protection** (AC38):
  - an Admin deactivating or demoting themselves is refused;
  - deactivating or demoting the last active Admin is refused;
  - each is tested with direct POST requests, and nothing changes;
  - with two active Admins, demoting the other one succeeds.
- **PROTECT on users:** deleting a user referenced by an Application or a StageChange raises
  `ProtectedError` (AC39).

### Acceptance criteria covered

AC35, AC36, AC37, AC38, AC39.

### Completion checklist

- [ ] Staff list (with the inactive option), create, role change, deactivate and reactivate.
- [ ] Self and last-Admin protection enforced on the server.
- [ ] Ruff and tests pass; `PROMPTS.md` updated; committed and pushed.

---

## Phase 12: Dashboard

**User stories**: 55, 56, 57, 58

### Objective and scope

The start page shows the four approved sections in variant A's layout. Each section is a query
over existing data, with no new fields or time-based rules.

### Dependencies

Phases 4 to 8.

### Implementation tasks

- **Summary stat tiles:**
  - open jobs;
  - active applications: the five active stages, on open and closed jobs;
  - total hires: every Hired application, regardless of job status or archive status.
- **Pipeline:** five stage cards, each linking to `/applications/?stage=<stage>`.
- **Needs Attention:** closed jobs that have active applications (with counts), and applications
  at Offer.
- **Recent Activity:** a table of the 10 most recent StageChanges, newest first, showing when,
  application, from → to, by whom, and note.
- The layout stays on one column at phone width (the findings' `grid-cols-1` fix). Build a test
  dataset modelled on the UI prototype's sample data.

### Tests to write first

- **Summary counts:** with a mixed dataset (active on open and closed jobs; Hired on a closed job
  and for an archived candidate; terminal stages), the three tiles equal the expected numbers
  (AC40).
- **Pipeline:** each stage count is correct, and its link is the stage-filtered list URL; following
  it lists the same number of applications (AC41).
- **Needs Attention:** lists exactly the closed jobs with active applications (with correct counts),
  and exactly the applications at Offer. It excludes closed jobs with only terminal applications
  (AC42).
- **Recent Activity:** with 12 StageChanges, exactly the 10 newest render, newest first (AC43).
- **Access:** the dashboard is the post-login page for both roles.

### Acceptance criteria covered

AC40, AC41, AC42, AC43.

### Completion checklist

- [ ] Four sections render with correct numbers and links.
- [ ] No sideways scrolling at 375px.
- [ ] Ruff and tests pass; `PROMPTS.md` updated; committed and pushed.

---

## Phase 13: Badges, detail-page summaries and final check

**User stories**: 19, 25, 60 (plus a final pass on 3, 4, 5 and 59)

### Objective and scope

Finish the consistent status badges and the detail-page summaries, then run the comprehensive
permission review and the final quality gate.

### Dependencies

Phases 1 to 12.

### Implementation tasks

- **Candidate detail page:** "Hired for…" lists the jobs the candidate was hired for, and also
  shows on an archived candidate's page.
- **Job detail page:** skills, the applications list, an active count and a hired count. The hired
  count includes archived candidates.
- **Shared badges:**
  - consistent stage badge colours (active stages, Offer, Hired, Rejected and Withdrawn);
  - **Awaiting Decision** on applications at Offer;
  - **Job Closed** everywhere a closed job or its applications appear;
  - all of them used on the list, detail, dashboard and candidate pages.
- **Accessibility pass:** semantic headings, real links and buttons, labelled controls, enough
  contrast, and no sideways scroll at phone width.
- **Permission review:** a single test that runs through every row of the PRD permission table for
  Recruiter, Admin and anonymous users.
- Update `CLAUDE.md` and the README with run and test instructions.

### Tests to write first

- **Detail pages:**
  - the candidate page shows "Hired for <job>", including for an archived candidate;
  - the job page shows the correct hired count, including for archived candidates (AC18).
- **Badges:**
  - Awaiting Decision appears for Offer applications and nowhere else;
  - Job Closed appears for closed jobs and their applications on list, detail and dashboard pages;
  - pages extend the sidebar layout (AC44).
- **Permission review** (AC2, AC3): every Recruiter action allowed for Recruiter; every Admin-only
  action is 403 for Recruiter with no data changed; every action allowed for Admin; every page
  redirects anonymous users (AC1 regression test).
- Admin navigation renders only for Admins on every main page (AC3).

### Acceptance criteria covered

AC2, AC3 (comprehensive), AC18, AC44, AC45 (final).

### Completion checklist

- [ ] "Hired for…" and the hired count are correct.
- [ ] Badges are consistent across all pages.
- [ ] The permission review passes.
- [ ] `ruff check` and `ruff format --check` are clean, and the full test suite passes.
- [ ] README and `CLAUDE.md` are final; `PROMPTS.md` updated; final commit pushed.

---

## Coverage check

### User stories → phase

| Phase | User stories |
|---|---|
| 1 | 1, 2, 3, 4, 5, 59 |
| 2 | 6, 7, 8, 9, 10 |
| 3 | 20, 26, 27, 28, 29 |
| 4 | 32, 33, 34, 35, 45, 46 |
| 5 | 36, 37, 43, 44 |
| 6 | 38, 39, 41, 42 |
| 7 | 21, 22, 23, 24, 40 |
| 8 | 11, 12, 13, 14, 15, 16 |
| 9 | 49 |
| 10 | 17, 18, 30, 31, 47, 48 |
| 11 | 50, 51, 52, 53, 54 |
| 12 | 55, 56, 57, 58 |
| 13 | 19, 25, 60 |

That's 60 of 60. Each story is listed once, under the phase that finishes it. Stories 3, 4, 5 and
59 are also re-checked in Phase 13.

### Acceptance criteria → phase

| AC | Phase(s) |
|---|---|
| AC1 | 1 (regression test in 13) |
| AC2 | permission tests in 2–11; comprehensive in 13 |
| AC3 | 1 (navigation); comprehensive in 13 |
| AC4, AC5 | 2 |
| AC6, AC7, AC8, AC9 | 8 |
| AC10 | 10 |
| AC11 | 3 (regression test in 7) |
| AC12, AC13 | 7 |
| AC14, AC15, AC16 | 3 |
| AC17 | 10 |
| AC18 | 13 |
| AC19, AC20 | 4 |
| AC21 | 5 (Advance and Back), 6 (completed) |
| AC22 | 5, 6 |
| AC23, AC24 | 6 |
| AC25 | 6 (Hired), 7 (closed job), 8 (archived) |
| AC26 | 6 |
| AC27, AC28 | 5 |
| AC29 | 5, 6 |
| AC30 | 4 (re-checked in 9) |
| AC31 | 10 |
| AC32, AC33 | 4 |
| AC34 | 9 |
| AC35, AC36, AC37, AC38, AC39 | 11 |
| AC40, AC41, AC42, AC43 | 12 |
| AC44 | 13 |
| AC45 | every phase; final in 13 |

That's 45 of 45.

# Applicant Tracking System — Prompt Log

## Entry 1

**Date:** 2026-10-27

**Phase:** Project setup

**Prompt:**
Pasted the professor's `/prototype` skill content and asked Claude Code to write it exactly into
`.claude/skills/prototype/SKILL.md`, `LOGIC.md` and `UI.md`, saved as UTF-8 without a BOM, without
modifying any other files.

**Result:**
- The three skill files had been created empty, which is why `/skills` showed "Skill" as the description.
- Claude Code wrote each file verbatim and verified the first bytes to confirm there was no BOM.
- It explained that PowerShell 5.1's `Set-Content -Encoding UTF8` adds a BOM, which can break the
  YAML frontmatter.

**Feedback and decisions:**
Accepted. Claude Code waited for the real lesson text rather than inventing `LOGIC.md` when the first
request arrived without the content.

---

## Entry 2

**Date:** 2026-10-27

**Phase:** Grill-me and requirements decisions (Questions 1–22)

**Prompt:**
`/grill-me`, then: "I'm building an internal Applicant Tracking System (ATS) for my CIDM 3312 project.
Interview me one question at a time to define the requirements before implementation. Cover candidates,
job openings, applications, hiring stages, skills, permissions, and edge cases. We also need to use
/prototype for both hiring-stage logic and dashboard UI design before finalizing the PRD. Do not write
production code yet." I then pasted the assignment's required functionality, technology and process,
to be treated as fixed constraints.

**Result:**
Claude Code asked one question at a time. For each question it stated what the question settles, listed
options with their trade-offs, and recommended one.

| # | Topic | Decision | Key reasoning |
|---|---|---|---|
| 1 | Source of requirements | Professor's brief is fixed; grill only what it leaves open | Grading criteria come before design ideas |
| 2 | Roles | **Admin + Recruiter**; Admin = Recruiter + staff accounts, skills list, permanent deletion; Django auth/groups/permissions | Real permission rules without per-job filtering (Hiring Manager role left as future work) |
| 3 | Candidate identity | **Email required and unique, ignoring case**; database constraint + form error | Stops duplicate candidates from bypassing the duplicate-application rule |
| 4 | Candidate source | **Required TextChoices** (Referral, Company Website, Job Board, LinkedIn, Career Fair, Agency, Other) + optional `source_details` | Clean data the dashboard can filter; no extra model |
| 5 | Candidate fields | First/last name, email, optional phone, source, source_details, optional notes, optional LinkedIn/portfolio URL, timestamps; **no résumé upload** | Meets "contact information" without file storage |
| 6 | Archive vs delete | Recruiters/Admins **archive and restore** (`archived_at`); **Admin-only permanent delete, only with no applications** (`on_delete=PROTECT`) | Reversible action for daily work; history can't be lost |
| 7 | Archiving with active applications | **Blocked** while any application is in Applied–Offer; error lists them; archived candidates can't receive new applications; restore changes nothing | Keeps data consistent; every stage change is deliberate |
| 8 | Job opening fields | Title; optional department, location, description; **employment_type** and **work_mode** TextChoices; status **Open/Closed only**; skills M2M; timestamps | Two cheap dropdowns help the dashboard; no Draft status, salary or deadlines |
| 9 | Closing a job | **Stops new applications only**; existing applications keep moving; UI marks closed jobs that still have active applications | Matches real hiring; no automatic data changes |
| 10 | Reopening a job | **Allows new applications again**; changes nothing else; unique candidate+job constraint still applies | Close and reopen are a mirror pair |
| 11 | Stage history | Current `stage` + `stage_changed_at`, plus an **append-only StageChange log** (from, to, changed_by, changed_at, note), written in **one transaction** | Real audit trail; shown on the application detail page |
| 12 | Allowed moves | **Forward or back one step**, no skipping; Reject/Withdraw from any active stage; Hired only from Offer; HTMX shows only allowed actions | Predictable, fully testable, one-click buttons |
| 13 | Undoing terminal stages | **Rejected/Withdrawn can be reactivated** to the stage they left (from the log), note required, Recruiters and Admins; **Hired is permanent**; originally blocked if the candidate is archived **or the job is closed** (see Entry 4) | Fixes mistakes and handles returning candidates |
| 14 | Creating an application | Always starts at **Applied**; creates the first StageChange (null → Applied) in the same transaction; guards: job Open, candidate not archived, no duplicate | The log is the complete story of every application |
| 15 | Skills scope | **Job openings only** (M2M); skill filter on the job list; candidate skills/matching listed as future work | Exactly what the brief requires |
| 16 | Skill rules | Name **unique ignoring case**; Admin-only create/rename/delete; **delete blocked while any job uses it**, error lists the jobs | M2M can't use PROTECT, so a simple check prevents silent removal |
| 17 | Deleting jobs | **Admin-only, blocked if any applications** (`PROTECT`); error suggests closing instead | Same pattern as candidates: nothing with history is deleted |
| 18 | Deleting applications | **Admin-only, only if it never moved** (at Applied with exactly one StageChange); `StageChange.application` uses CASCADE | Allows fixing data-entry mistakes without erasing history |
| 19 | Side effects of hiring | **None**; jobs can have multiple hires and stay Open; other applications untouched; hired count on job page, "Hired for…" on candidate page | The system enforces rules but never changes data for the user |
| 20 | Stale screens / double-clicks | Each HTMX request sends the **expected stage**; mismatch → no change, no log row, refreshed card with a message; conditional `UPDATE … WHERE stage = expected` inside `transaction.atomic()` | Safe on SQLite without row locking; double-clicks become harmless |
| 21 | Staff leaving | **Deactivate (`is_active`), never delete**; `created_by`/`changed_by` use PROTECT; Admins can't deactivate themselves or the last active Admin | History always shows who did what; avoids locking everyone out |
| 22 | Notes on Reject/Withdraw | **Required non-empty note** for Reject, Withdraw and Reactivate (inline HTMX form, validated on the server); optional for Advance/Back | Every move out of or back into the pipeline is explained |

**Feedback and decisions:**
I chose an option for every question and often added detail: test requirements, error messages, and
"use Django built-ins where possible". I asked throughout to keep the scope focused on the assignment.

---

## Entry 3

**Date:** 2026-10-27

**Phase:** Logic prototyping

**Prompt:**
```
/prototype Logic prototype for the Applicant Tracking System hiring-stage rules we just defined.
Test whether the stage model behaves correctly in these scenarios:
- Normal forward and backward stage transitions
- Rejected and Withdrawn applications being reactivated to their previous active stage
- Reactivation blocked when a candidate is archived or a job is closed
- Stale HTMX requests and accidental double-clicks
- Hired being permanent
- Required notes for Reject, Withdraw, and Reactivate
- Candidate archiving and job closing interactions
Follow LOGIC.md and create a standalone, interactive HTML prototype inside prototypes/.
Include free-play controls and walkthroughs for important edge cases. Record the findings and any
recommended changes. This is a throwaway experiment, not production Django code.
```

**Result:**
- `prototypes/hiring-stage-logic.html` is a single file with no install step. The rules live in a pure
  JavaScript module with no DOM code, and the page is a thin shell over it.
- **Free play:** add applications, archive or restore candidates, and close or reopen jobs. Two
  side-by-side recruiter screens only update when that recruiter acts or reloads, so out-of-date clicks
  can be reproduced. There's also a double-click button and a "show hidden buttons" option to watch the
  server refuse moves.
- **Six guided walkthroughs** check each step against the expected outcome: happy path and Hired being
  final, notes and reactivation, reactivation guards, two screens and double-clicks, archiving and
  closing jobs, and a misclick on a closed job.
- Every walkthrough step was run automatically in headless Edge. All steps matched the rules, every
  allowed move added exactly one history line, and every refused move added none.
- Findings are recorded in `prototypes/hiring-stage-logic-findings.md`:
  - **Server check order:** out-of-date stage first, then whether the move is allowed, then the
    required note (spaces-only counts as missing), then the reactivation guard.
  - **Reactivation target:** reading the previous stage from the log is reliable, because the last log
    entry of a Rejected or Withdrawn application is always the move into that stage.
  - **Two open questions:** a misclicked Reject on a closed job couldn't be undone without reopening
    the job (see Entry 4), and it wasn't settled whether hired candidates can be archived.

**Feedback and decisions:**
The prototype confirmed the stage model and surfaced two questions the paper design had missed
(Questions 23 and 24).

---

## Entry 4

**Date:** 2026-10-27

**Phase:** Grill-me — decisions driven by the logic prototype (Questions 23–24)

**Prompt:**
Answers to Questions 23 and 24, plus: "Please update the logic prototype and its findings to reflect
this decision, rerun the relevant walkthroughs, and record the result for the PRD."

**Result:**

**How the prototype changed the closed-job reactivation rule (Question 23):**
- **The original rule (Question 13):** reactivation was blocked if the job was closed. The reasoning
  was that reactivation would let people back into a closed job's pipeline.
- **What walkthrough 6 showed:** on a closed job, Reject is allowed, because active applications keep
  moving after a job closes (Question 9). Reactivation, however, was blocked. So a **misclicked Reject
  on a closed job could only be undone by reopening the job**, which briefly let anyone apply, then
  reactivating, then closing the job again. The two rules worked against each other.
- **The corrected reasoning:** reactivation only brings back an existing application, and closing a
  job only stops new applicants. Claude Code acknowledged that its Question 13 reasoning had been wrong.
- **The new rule, Option B:** Recruiters and Admins can reactivate Rejected or Withdrawn applications
  on closed jobs. The remaining safeguards are unchanged: the candidate must not be archived, a note
  is required, Hired stays permanent, the application returns to its previous active stage, exactly
  one StageChange is written, and out-of-date requests are refused. Reactivation never changes the
  job's Closed status.
- **Prototype updated:** the reactivation guard now checks only for an archived candidate.
  Walkthrough 3 ("Archived blocks, closed does not") and walkthrough 6 were rewritten. In walkthrough 6
  the misclick is now undone with a single Reactivate, the job stays Closed, and new applications are
  still refused. All six walkthroughs were rerun, and **all 48 steps matched the rules**.

**Question 24, archiving hired candidates:** Option A, allow it. No new rule is needed, since archiving
already requires every application to be terminal and Hired counts as terminal. Hired applications,
history and job hired counts are unchanged. Archived candidates stay reachable through an archived view.

**Feedback and decisions:**
Both decisions are recorded in `prototypes/hiring-stage-logic-findings.md` under "Decisions" and
"For the PRD".

---

## Entry 5

**Date:** 2026-10-27

**Phase:** Grill-me — dashboard content (Questions 25–26)

**Prompt:**
Answers to Questions 25 and 26 before starting the UI prototype.

**Result:**
| # | Topic | Decision | Key reasoning |
|---|---|---|---|
| 25 | Dashboard content | **Summary counts** (open jobs, active applications, total hires); **pipeline** counts for the five active stages, each linking to a stage-filtered application list; **needs attention** (closed jobs with active applications; applications at Offer); **recent activity** (the last 10 StageChanges). Existing models only; no new fields or time-based rules | Every section is a simple query over existing data; fixing the content first lets the UI variants differ only in structure |
| 26 | What counts as active | **All applications in the five active stages, on Open and Closed jobs**; total hires counts every Hired application regardless of job status or archive status; stage links include closed jobs; no dashboard job filter | Active applications on closed jobs are still live work under the Question 9 rule |

**Feedback and decisions:**
Accepted. The "stuck in stage" metric and a job filter were left out deliberately.

---

## Entry 6

**Date:** 2026-10-27

**Phase:** UI prototyping (Question 27)

**Prompt:**
"Please record this decision and proceed with the required /prototype UI experiment comparing three
structurally different dashboard layouts using DaisyUI. Do not begin the PRD or production
implementation yet." Claude Code ran `/prototype` with the UI branch: three structurally different ATS
dashboard layouts using Tailwind/DaisyUI, standalone with a CDN, and the content fixed by Questions 25
and 26.

**Result:**
- `prototypes/dashboard-ui.html` is one standalone page using the Tailwind and DaisyUI browser builds
  from a CDN, with no Django setup. All three variants share one realistic dataset: 4 open jobs, 25
  active applications (4 of them on closed jobs), and 4 hires.
- A separate dark switcher moves between variants with the ← / → keys and remembers the choice. Each
  pipeline count opens the stage-filtered list. Other actions show the URL they would open.
- **Variant A, Sidebar command center:** a DaisyUI drawer sidebar with an Admin group, stat tiles,
  five pipeline cards, a Needs attention card and an activity table, all visible at once.
- **Variant B, Pipeline board:** a top navbar, a kanban-style board of candidate cards per stage, a
  closed-jobs warning banner, "Job closed" and "Awaiting decision" badges, and activity in a
  slide-out panel.
- **Variant C, Inbox (list / detail):** a top link bar, the summary written as a sentence, the pipeline
  as one bar split into five sections, and Needs attention and Activity as tabs with a detail panel.
- **Checked:** headless-Edge screenshots at desktop width, plus a measurement at 375px phone width.
  Variant A's bottom grid scrolled sideways at first; it was fixed, and no variant scrolls sideways now.
- Findings and the comparison table are in `prototypes/dashboard-ui-findings.md`.

**Feedback and decisions:**
**Question 27: Variant A's Sidebar Command Center as the dashboard and the shell for every page, with
Variant B's status badges.**
- **Layout:** a responsive DaisyUI drawer with Dashboard, Candidates, Job Openings and Applications, and
  an **Admin-only** group with Skills and Staff Management.
- **Content:** all four sections visible, and the pipeline counts stay clickable.
- **Badges:** "Job Closed" and "Awaiting Decision" used wherever they apply.
- **Accessibility:** the design is responsive and accessible.
- **Interaction:** no drag-and-drop and no unnecessary JavaScript.

Why:
- A is the only variant that shows all four sections without extra clicks, and its sidebar scales to
  every page through one Django base template.
- B's board implied drag-and-drop, which doesn't fit the one-step, note-required moves, but its badges
  make the closed-job rule visible everywhere.
- C hid half the dashboard behind tabs and needed extra HTMX detail partials.

Note: the prototype shows the Admin group to a Recruiter for demonstration only. In production it must
appear only for Admins, and the views must enforce the permission too.

---

## Entry 7

**Date:** 2026-10-27

**Phase:** Planning documentation

**Prompt:**
"Before starting the PRD, please … update PROMPTS.md with a chronological summary of our /grill-me
session … document both /prototype experiments … record how the logic prototype led us to change the
closed-job reactivation rule in Question 23 … include the dashboard UI comparison … review the Git
changes, then commit and push … Do not create the PRD or begin production implementation yet."

**Result:**
This log was updated with Entries 1–7, and the prototypes and findings were committed and pushed to
GitHub.

**Feedback and decisions:**
The next step is `/to-prd`.

---

## Entry 8

**Date:** 2026-10-27

**Phase:** PRD

**Prompt:**
```
/to-prd Create a complete Product Requirements Document (PRD) for the Applicant Tracking System.
Use all 27 decisions from our grill-me session, PROMPTS.md, and both prototype findings files:
- prototypes/hiring-stage-logic-findings.md
- prototypes/dashboard-ui-findings.md
Follow the professor's assignment requirements and use the approved technology stack: Python, Django,
SQLite, uv, Tailwind CSS/DaisyUI through django-tailwind-cli, HTMX, Ruff, and automated Django tests.
Include: project overview and scope; Admin and Recruiter roles and permissions; Candidate, JobOpening,
Application, Skill, and StageChange models; functional and nonfunctional requirements; hiring-stage
transition rules and audit logging; validation, archiving, deletion, and concurrency safeguards;
dashboard requirements and selected UI design; acceptance criteria and testable requirements; explicit
out-of-scope features. Incorporate the prototype-driven changes, especially allowing reactivation on
closed jobs and permitting hired candidates to be archived. Create the PRD document, but do not
generate the implementation plan or write production code yet.
```
Follow-up prompt: finalise the two open details listed in the draft, review the PRD for consistency
with all 27 decisions and both findings documents, update this log, and report any remaining
contradictions. Don't commit yet; the milestone commit comes after the implementation plan.

**Result:**
`prd/applicant-tracking-system.md`, following the `/to-prd` template plus an acceptance-criteria section:
- **Problem Statement and Solution.**
- **User stories:** access and roles, candidates, job openings and skills, applications and stages,
  staff accounts, and dashboard and navigation (60 in the final version).
- **Implementation Decisions:**
  - the tech stack and conventions;
  - a Recruiter/Admin permission table;
  - all five models plus staff users, with fields, constraints and `on_delete` rules;
  - the stage transition table;
  - the single stage-change service, with the prototype's check order (out-of-date stage → move allowed
    → required note → archived-candidate guard) and the SQLite-safe conditional update;
  - archive and delete rules;
  - pages and HTMX behaviour;
  - the variant-A sidebar shell with variant-B badges, and the nonfunctional requirements.
- **Testable acceptance criteria** (AC1–AC45 in the final version).
- **Out of Scope** list and **Further Notes**.
- **Prototype-driven changes are included:** reactivation on closed jobs (Q23; user story 40, AC25)
  and archiving hired candidates (Q24; user story 13, AC6).

**Feedback and decisions:**
The first draft left two details open. I finalised them:
1. **Staff reactivation:** Admins can reactivate deactivated staff accounts by setting `is_active`
   back to true. Only Admins manage activation and deactivation, and all history is preserved.
   This added user story 52 and AC37, and the staff list gained a "show inactive" option.
2. **New Application entry points:** a button on the Applications list page and on the candidate
   detail page, both opening the same creation form. From a candidate's page, that candidate is
   preselected. This added user stories 32–33 and AC33. Archived candidates show no button, and the
   server still refuses them.

Claude Code then reviewed the PRD against Q1–Q27 and both findings documents. It found no
contradictions, and three minor unresolved details:
- **Last-Admin guard and role changes:** the guard covered deactivation, but not demoting the last
  active Admin, or yourself, to Recruiter.
- **How job status changes:** both the job edit form and the Close and Reopen actions could change it,
  and the default status for a new job wasn't stated.
- **Editing application notes:** there was no rule for whether the optional notes field can be edited
  after creation.

I accepted all three of Claude Code's recommendations, and they're now in the PRD:
3. **Admin role protection:** Admins can't demote themselves to Recruiter, and the last active Admin
   can't be demoted or deactivated. Both are enforced on the server and tested. This updated user
   story 53, the staff rules, and AC38.
4. **Job status:** new jobs default to Open, and status changes only through the dedicated Close and
   Reopen actions. The create and edit forms have no status field, and closing or reopening preserves
   applications and history. This updated user stories 20, 21 and 24, the JobOpening rules, and AC11.
5. **Application notes:** Recruiters and Admins can edit `Application.notes` after creation, with no
   stage change and no StageChange. StageChange notes stay immutable and can't be edited or deleted
   through the UI. This added user story 49, the Application and StageChange rules, and AC34.

**Final PRD counts:** 60 user stories and 45 acceptance criteria (AC1–AC45). It's internally
consistent and has no open questions.

---

## Entry 9

**Date:** 2026-10-27

**Phase:** Implementation planning (`/prd-to-plan`)

**Prompt:**
```
/prd-to-plan Create a phased implementation plan for my Applicant Tracking System using the
finalized PRD at prd/applicant-tracking-system.md. Read PROMPTS.md and both prototype findings
documents for context. Follow the professor's required planning process and break implementation
into manageable phases. Requirements: Cover all 60 user stories and 45 acceptance criteria. Use
Python, Django, SQLite, uv, Tailwind CSS/DaisyUI through django-tailwind-cli, HTMX, and Ruff.
Follow Test-Driven Development (Red-Green-Refactor). Include clear deliverables, dependencies, and
testing requirements for every phase. Keep the implementation focused on the assignment. Do not
write production code yet.
```
Follow-up prompt: approved the breakdown and asked for the plan file, with an objective and scope,
dependencies, implementation tasks, tests to write first, acceptance criteria covered and a
completion checklist for every phase, plus a check that all 60 user stories and AC1–AC45 are
accounted for.

**Result:**
Claude Code followed the skill's steps:
1. It read the PRD, both findings documents and this log, and confirmed the repository had no
   Django code yet.
2. It identified the durable architectural decisions.
3. It proposed tracer-bullet vertical slices as a numbered list, with user stories and ACs for
   each.
4. It asked me about granularity and order before writing anything.

**Architectural decisions (in the plan header):**
- **Django 5.1 or later,** so `LoginRequiredMiddleware` protects every page; a `config/` project
  package.
- **Five apps:**
  - `core`: base layout, badges, dashboard and permission helpers;
  - `candidates`;
  - `jobs`: JobOpening and Skill;
  - `pipeline`: Application, StageChange and the single stage-change service;
  - `staff`: built-in `User`, no custom user model.
- **Roles:** `Recruiter` and `Admin` groups using Django model permissions. Archiving, closing,
  stage moves and notes edits count as "change"; deletes, skills management and user management
  are Admin only. Every restricted view checks the permission on the server.
- **URLs:** pk-based and app-namespaced. Stage moves use one HTMX POST to
  `/applications/<pk>/transition/` carrying the action and the expected stage.
- **TDD in every phase:** Red, Green, Refactor; then Ruff, the full test suite, a `PROMPTS.md`
  entry, and a commit and push.

**Approved 13-phase breakdown:**

| # | Phase | User stories |
|---|---|---|
| 1 | Project setup, login, roles and sidebar layout | 1–5, 59 |
| 2 | Candidates (create, list, detail, edit) | 6–10 |
| 3 | Skills and job openings | 20, 26–29 |
| 4 | Applications (creation, list, detail and history) | 32–35, 45, 46 |
| 5 | Advance and Back over HTMX, with stale and double-click safety | 36, 37, 43, 44 |
| 6 | Reject, Withdraw and Reactivate; Hired is permanent | 38, 39, 41, 42 |
| 7 | Close and reopen jobs | 21–24, 40 |
| 8 | Candidate archive and restore | 11–16 |
| 9 | Edit application notes | 49 |
| 10 | Admin permanent deletes | 17, 18, 30, 31, 47, 48 |
| 11 | Staff management | 50–54 |
| 12 | Dashboard | 55–58 |
| 13 | Badges, detail-page summaries and final check | 19, 25, 60 |

- **Order:** close/reopen and archive come after the stage moves, because their key rules can only
  be tested once Reject and Reactivate exist. This mirrors how the logic prototype found the Q23
  problem.
- **Output:** `plans/applicant-tracking-system.md`, with coverage tables mapping every user story
  and AC to its phase. A script confirmed 60 of 60 user stories and 45 of 45 ACs.
- **Criteria built up over several phases:**
  - **AC21 and AC22 (stage moves):** Phases 5 and 6.
  - **AC25 (reactivation):** Phase 6 (Hired), Phase 7 (closed job), Phase 8 (archived candidate).
  - **AC2 and AC3 (permissions):** tested in each relevant phase, with a comprehensive review in
    Phase 13.

**Feedback and decisions:**
- I approved all 13 phases with no merges or splits, kept the order, and approved the five apps.
- I required Django 5.1 or later, permission tests in each relevant phase plus a final review,
  strict TDD, and staying focused on the assignment.
- **Open detail, reported by Claude Code:** Django creates model permissions only after migrations
  run, so the migration that assigns them to groups must create them first. This will be settled
  with a test in Phase 1.
- **Next step:** the milestone commit "Completed Grill me, PRD, and plan", then Phase 1.

---

## Entry 10

**Date:** 2026-10-27

**Phase:** Phase 1 implementation (project setup, login, roles and sidebar layout)

**Prompt:**
```
/implement Implement Phase 1 of my Applicant Tracking System using the approved plan at
plans/applicant-tracking-system.md. Before beginning, read: prd/applicant-tracking-system.md,
plans/applicant-tracking-system.md, PROMPTS.md, both prototype findings documents. Follow the
approved Phase 1 scope exactly: Django project setup, authentication, Recruiter/Admin roles,
sidebar layout, and initial dashboard. Requirements: use the approved technology stack and
architecture; follow strict Test-Driven Development (Red-Green-Refactor); resolve the
group-permissions initialization detail with automated tests; implement only Phase 1, do not
begin Phase 2; run Ruff, Django system checks, and the relevant automated tests; update PROMPTS.md
to document the implementation process; summarize files created, tests passed, any issues, and
the Git commit status. Stop after Phase 1 for my review.
```

**Result:**

*Setup.*
- `uv init` gave a Python 3.14 project. `uv add` installed Django 6.1.2 (meets "≥ 5.1") and
  django-tailwind-cli 4.8.2; Ruff 0.17.3 is a dev dependency.
- `startproject config` plus the five apps: `core`, `candidates`, `jobs`, `pipeline` and `staff`.
- `django.contrib.admin` was removed on purpose. It would be a back door around the permission
  rules and the append-only StageChange history.

*Red.*
- 37 tests were written first, in `core/tests/`:
  - `test_auth`: anonymous redirects (AC1), the login page, landing on the dashboard, `?next=`,
    wrong password, inactive user refused, and logout POST-only.
  - `test_roles`: both groups exist, the group permissions, the `grant_permissions` helper and the
    role helpers.
  - `test_layout`: drawer, accessible ☰ label, four main links, Admin group only for Admins
    (AC3), user and role, HTMX CSRF header, Tailwind link, login page without a sidebar.
  - `test_placeholders`: section pages; Recruiter 403 on Skills and Staff.
- First run: every module failed to import `core.roles`. After a compile-only stub
  (`NotImplementedError`), the run showed **7 failures and 35 errors, each for the expected reason**:
  404s instead of login redirects, missing groups, unknown URL names, and the stubbed helpers.

*Green.*
- `LoginRequiredMiddleware`, Django's `LoginView` and `LogoutView`, and a DaisyUI-styled login
  form. `LOGIN_REDIRECT_URL` is the dashboard.
- `core/roles.py`: `is_admin`, `role_name`, `@admin_required` and `grant_permissions`. A context
  processor puts `user_role` and `user_is_admin` in every template.
- `base.html`: the variant-A DaisyUI drawer, a labelled ☰ toggle, nav links that mark the current
  page, the Admin group rendered only for Admins, the user and role, a POST logout form, and
  `hx-headers` with the CSRF token.
- The dashboard view at `/`, and placeholder pages for Candidates, Job Openings, Applications,
  Skills and Staff, so every nav link is a real, login-protected route. Skills and Staff are
  Admin-only.
- htmx 2.0.11 is a pinned static copy. Tailwind builds through the pinned `tailwind-cli-extra`
  2.10.34 binary, which bundles DaisyUI.

**Group-permissions initialization detail (resolved, tested):**
- **Problem:** Django creates model permissions in a `post_migrate` signal, after *every* migration
  has run. On a fresh database, a data migration can't look them up.
- **Solution:** `grant_permissions(apps, group, app_label, model_name, actions)` first creates any
  missing content type and permission row, with the same codename and name Django uses, then
  adds it to the group. The signal later finds the rows and creates no duplicates.
- **Phase 1 migration (`core/0001_create_role_groups`):** creates both groups and gives Admin
  view, add and change on `auth.User` for Staff Management. There's no delete permission, because
  staff are deactivated, never deleted. Each later model migration will attach its own
  permissions with the same helper.
- **Tests:**
  - the test database is built by running the migrations, so the group tests prove it works on a
    fresh database;
  - after deleting the `auth.user` permissions, the helper recreates and assigns them;
  - running the helper twice is idempotent;
  - running Django's `create_permissions` afterwards adds no duplicates.
- **Also checked by hand:** `migrate core zero` removes both groups, and re-migrating restores them.

**Issue found and fixed: sideways scrolling at phone width.**
- Headless Edge showed the dashboard card clipped on small screens.
- Measuring showed the cause: DaisyUI's drawer puts the content in a `max-content` grid column, so
  long text widened the page to 1097px. This is the same bug the UI prototype found.
- **Red:** a regression test was added first and failed.
- **Fix:** `auto-cols-[max-content_minmax(0,1fr)]` on the drawer. The scroll width now equals the
  viewport width, and the desktop layout is unchanged (256px sidebar, 1000px content).

*Refactor.*
- Removed the startproject boilerplate (empty `models.py`, `tests.py` and `admin.py`), and moved
  the Tailwind source CSS out of `STATICFILES_DIRS` to clear a django-tailwind-cli warning.
- `SECRET_KEY` is read from `DJANGO_SECRET_KEY`, with a development fallback.
- `CLAUDE.md` documents the stack, commands, TDD rule, app ownership and conventions.

**Verification:**
- `ruff check` and `ruff format --check` are clean, and `manage.py check` reports no issues.
- `makemigrations --check` reports no changes, and **38 of 38 tests pass**.
- **Live server smoke test:**
  - anonymous `/` redirects to login;
  - the CSS and htmx files are served;
  - a Recruiter logs in and lands on `/`, sees no Staff Management link, and gets 403 on `/staff/`.

**Feedback and decisions:**
I approved Phase 1 and its four implementation decisions:
1. Superusers count as Admin, which bootstraps the first account through `createsuperuser`.
2. Placeholder section pages exist until their phases replace them. Skills and Staff are already
   Admin-only.
3. `django.contrib.admin` isn't installed.
4. The built CSS and the Tailwind CLI binary are gitignored and rebuilt with
   `manage.py tailwind build`.

**Final review before committing** (my follow-up prompt asked for a check of stubs, scaffold
leftovers, secrets, quality gates and acceptance criteria, then a commit and push):
- **Stubs:** `core/roles.py` has no `NotImplementedError` stubs or unreachable code. No TODOs or
  startproject leftovers remain in the settings, URLs or apps.
- **Secrets:** only throwaway test passwords are committed, and they exist only in the test
  database. Local demo accounts live only in the gitignored `db.sqlite3`. Built CSS, the CLI
  binary and `__pycache__` are excluded.
- **Fix:** the startproject-generated `SECRET_KEY` fallback looked like a real secret, so it was
  replaced with an obvious placeholder, `django-insecure-local-development-only`. Production
  reads `DJANGO_SECRET_KEY`.
- **Quality gates:**
  - `ruff check` and `ruff format --check` are clean;
  - `manage.py check` reports no issues;
  - `makemigrations --check` and `migrate --check` are clean;
  - **38 of 38 tests pass**.
- **Acceptance criteria:**
  - AC1: every page redirects anonymous users to login;
  - AC3 (navigation part): Admin links render only for Admins;
  - AC45: the quality gate is set up.
- Committed as "Phase 1: project setup, login, roles and sidebar layout" and pushed to `main`.
  Phase 2 has not been started.

---

## Entry 11

**Date:** 2026-10-27

**Phase:** Phase 2 implementation (Candidates: create, list, detail, edit)

**Prompt:**
```
/implement Implement Phase 2 of my Applicant Tracking System using the approved plan at
plans/applicant-tracking-system.md. Before beginning, read CLAUDE.md, the PRD, the implementation
plan, and PROMPTS.md. Follow the exact Phase 2 scope: Candidate model and required/optional fields;
candidate creation, listing, detail, and editing; required candidate source choices and optional
source details; case-insensitive email uniqueness enforced at the database and form levels;
Recruiter and Admin permissions; appropriate DaisyUI forms and templates. Requirements: strict TDD
(Red-Green-Refactor); write failing tests before implementing each feature; cover Phase 2 user
stories 6–10 and AC4–AC5; preserve Phase 1 functionality; run the complete test suite, Ruff lint
and format checks, Django system checks, and migration checks; update PROMPTS.md; stop after
Phase 2 for my review before committing or pushing. Do not start Phase 3.
```

**Result:**
Claude Code built Phase 2 in four Red-Green cycles. Each cycle's tests were run and seen to fail
for the expected reason before any code was written.

1. **Model** (`candidates/tests/test_models.py`, 11 tests).
   - **Red:** `candidates.models` didn't exist.
   - **Green:** `Candidate` and the `Source` TextChoices (Referral, Company Website, Job Board,
     LinkedIn, Career Fair, Agency, Other):
     - required first name, last name, email and source;
     - optional phone, source details, notes and "LinkedIn or portfolio URL";
     - `archived_at` (null = active, not editable), `created_at` and `updated_at`;
     - ordering by last name, then first name.
   - **Database guard:** `UniqueConstraint(Lower("email"))` with the message "A candidate with
     this email already exists." Tests show an IntegrityError for the same email in a different
     case, and for an identical email.
2. **Group permissions** (`test_permissions.py`, 3 tests).
   - **Red:** the groups had no candidate permissions.
   - **Green:** migration `0002_candidate_group_permissions` uses the Phase 1
     `grant_permissions` helper. Recruiter gets view, add and change; Admin also gets delete.
   - The migration reverses cleanly: `migrate candidates zero`, then re-migrate.
   - Phase 1's group tests were narrowed to `auth` permissions, so they keep holding as each phase
     adds model permissions.
3. **Form** (`test_forms.py`, 16 tests).
   - **Red:** `candidates.forms` didn't exist.
   - **Green:** `CandidateForm`. Its `clean_email` uses `__iexact`, excluding the record being
     edited, so the duplicate message appears on the email field. Once that field has an error,
     Django skips the database-constraint check, so the message isn't repeated.
   - **Tests cover (AC4, AC5):**
     - each required field;
     - optional fields left blank;
     - an invalid URL, email or source;
     - duplicates in another case, identical, and with surrounding spaces;
     - editing without changing the email, or changing only its case;
     - editing to another candidate's email;
     - a posted `archived_at` is ignored.
   - **Refactor:** a shared `DaisyUIFormMixin` in `core/forms.py`, which the Phase 1 login form
     now uses too.
4. **Views and templates** (`test_views.py`, 22 tests at first).
   - **Red:** the URL names didn't exist.
   - **Green:** generic CBVs with `PermissionRequiredMixin` and `raise_exception=True`:
     - list (non-archived only) at `/candidates/`;
     - detail at `/candidates/<pk>/`;
     - create at `/candidates/new/`, redirecting to detail with a success message;
     - edit at `/candidates/<pk>/edit/`, with the same validation as create (US 10).
   - **DaisyUI templates:** a table with an empty state; a detail card with a mailto link, source
     label, details and a notes card; and one shared form with a two-column grid that drops to one
     column on phones.
   - Add and Edit buttons are hidden from users without `add_candidate` or `change_candidate`.
   - **Permission tests:**
     - Recruiter and Admin can create, view, list and edit;
     - a user with no role gets 403 on every page, and a forbidden POST writes nothing;
     - a view-only user can view but gets 403 on create and edit;
     - anonymous users are redirected to login.
   - `_nav_link.html` gained an optional `section`, so "Candidates" stays highlighted on the
     detail, create and edit pages too.

**Visual check and accessibility fixes:**
- Headless-Edge screenshots of the list, detail and an edit form showing a duplicate email and an
  invalid URL matched the variant-A layout. All three pages have scroll width ≤ viewport width,
  so nothing scrolls sideways. The sample data was created inside a rolled-back transaction, so
  the local database stayed empty.
- The screenshots showed low-contrast pink error text and no red border on invalid inputs.
  Changes:
  - error text uses `text-red-700`;
  - one CSS rule borders inputs that have `aria-invalid="true"`.
- **Bug found and fixed:** Django 6 points invalid inputs at `aria-describedby="id_<field>_error"`,
  but no element had that id, so screen readers couldn't link a field to its error.
  - **Red:** a test was added first and failed.
  - **Fix:** the field partial now wraps errors in `<div id="id_<field>_error">`.

**Verification:**
- `ruff check` and `ruff format --check` are clean (the generated migration was formatted).
- `manage.py check` reports no issues; `makemigrations --check` and `migrate --check` are clean.
- **92 of 92 tests pass:** 38 from Phase 1 and 54 from Phase 2.
- **Covered:** user stories 6–10; AC4 (form and database); AC5; and AC2/AC3 for candidate create
  and edit.
- **Not started, as planned:** archive, restore and delete (Phases 8 and 10), and applications on
  the candidate page (Phase 4).

**Feedback and decisions:**
- I approved Phase 2.
- **Documented limitation: concurrent duplicate-email race.**
  - If two staff members save the same email at the same instant, both form checks can pass
    before either row is written.
  - The `Lower(email)` database constraint still refuses the second save, so no duplicate is
    ever stored. That person would see a server error instead of the friendly form message.
  - I decided to leave this as a documented limitation. Data integrity is protected, and
    handling the race is outside the assignment's scope.
- **Final review before committing:**
  - no stubs, TODOs or duplicate code remain; the temporary detail-route stub from cycle 1 was
    replaced;
  - only later-phase sections still use placeholder pages;
  - no credentials, `db.sqlite3`, built CSS, CLI binary or `__pycache__` are in the commit;
  - `ruff check` and `ruff format --check` are clean, `manage.py check` reports no issues, and
    `makemigrations --check` and `migrate --check` are clean;
  - 92 of 92 tests pass.
- Committed as "Phase 2: candidate management" and pushed to `main`. Phase 3 has not been
  started.

---

## Entry 12

**Date:** 2026-10-27

**Phase:** Phase 3 implementation (Skills and job openings)

**Prompt:**
```
/implement Implement Phase 3 of my Applicant Tracking System using the approved plan at
plans/applicant-tracking-system.md. Before beginning, read CLAUDE.md, the PRD, the implementation
plan, and PROMPTS.md. Follow the exact Phase 3 scope: Skill model with case-insensitive unique
names; Admin-only skill creation, listing, editing, and deletion, including preventing deletion of
skills assigned to jobs; JobOpening model with required title, employment type, and work mode; new
job openings default to Open; job creation, listing, detail, and editing; assign multiple skills to
job openings; filter job openings by skill; Recruiter and Admin permissions, enforced server-side;
DaisyUI forms and templates consistent with the existing sidebar layout. Requirements: strict TDD
(Red-Green-Refactor); write failing tests before implementing each feature; follow the Phase 3 user
stories and acceptance criteria; preserve all Phase 1 and Phase 2 functionality; do not implement
job close/reopen actions or permanent job deletion yet; run the complete test suite, Ruff lint and
format checks, Django system checks, and migration checks; update PROMPTS.md; stop after Phase 3
for my review before committing or pushing. Do not start Phase 4.
```

**Result:**
Claude Code built Phase 3 in four Red-Green cycles, plus three more Red-Green fixes found during
the visual check. Each time, the tests were run and seen to fail for the expected reason before
any code was written.

1. **Models** (`jobs/tests/test_models.py`, 17 tests).
   - **Red:** `jobs.models` didn't exist.
   - **Green:**
     - `Skill`: a name, `UniqueConstraint(Lower("name"))` with the message "A skill with this
       name already exists.", ordered alphabetically ignoring case.
     - `JobOpening`: required title, employment type (Full-time, Part-time, Contract,
       Internship) and work mode (On-site, Remote, Hybrid); optional department, location and
       description; timestamps; and `skills`, a many-to-many with `related_name="jobs"`.
     - `status` (Open, Closed) defaults to Open and is `editable=False`, so no ModelForm can
       include it. Phase 7's Close and Reopen actions will be the only way to change it.
   - **Tests:** the database refuses a skill name that differs only in case; required fields
     and invalid choices are refused; a new job is Open; one job can have many skills and one
     skill many jobs.
2. **Group permissions** (`test_permissions.py`, 3 tests).
   - **Red:** the groups had no `jobs` permissions.
   - **Green:** migration `0002_jobs_group_permissions` uses `grant_permissions`.
     - Recruiter: view, add and change on JobOpening; view on Skill.
     - Admin: all four on both models.
   - The migration reverses cleanly: `migrate jobs zero`, then re-migrate.
3. **Forms** (`test_forms.py`, 18 tests).
   - **Red:** `jobs.forms` didn't exist.
   - **Green:**
     - `SkillForm.clean_name` checks `__iexact`, excluding the skill being renamed, so the
       duplicate message sits on the name field. Surrounding spaces are stripped first.
     - `JobOpeningForm` has no status field, and skills are chosen with checkboxes.
     - A posted `status` is ignored on create, and on editing open or closed jobs (AC11).
   - A test showed `DaisyUIFormMixin` gave checkbox lists the text-input class. It now gives
     them `checkbox`.
4. **Views and templates** (`test_skill_views.py` 20 tests, `test_job_views.py` 32 tests).
   - **Red:** the URL names didn't exist.
   - **Green:** generic CBVs with `PermissionRequiredMixin` and `raise_exception=True`.
   - **Jobs:**
     - the list at `/jobs/` has a GET skill filter (`?skill=<pk>`), skill badges that link to
       the filtered list, and an Open or Closed status badge (`core/_job_status_badge.html`);
     - an unknown or malformed `?skill=` value is ignored;
     - detail at `/jobs/<pk>/`;
     - create at `/jobs/new/` and edit at `/jobs/<pk>/edit/`, both redirecting to the detail
       page with a success message.
   - **Skills (Admin only):**
     - the list at `/skills/` shows how many jobs use each skill;
     - create and rename both return to the list.
     - The list requires `view_skill` **and** `change_skill`. Recruiters can view skills
       (they appear on jobs) but get 403 on the management page.
   - **Skill delete:**
     - `/skills/<pk>/delete/` shows a confirmation page on GET and deletes on POST.
     - While any job, open or closed, uses the skill, both the page and a POST show "Python
       can't be deleted because…" with links to those jobs, offer no Delete button, and change
       nothing (AC16).
     - The first version guarded the POST with a `skill.jobs.exists()` check. It was replaced
       after review; see "Concurrency fix" below.
   - **Permission tests:**
     - Recruiters get 403 on every skill page, and their POSTs change nothing;
     - Admins and superusers can manage skills;
     - Recruiters and Admins can create, edit, list and view jobs;
     - a view-only user can't add or edit jobs;
     - anonymous users are redirected to login.
   - **Navigation:** Job Openings and Skills share the `jobs` namespace, so `_nav_link.html`'s
     `section` is now a view-name prefix (`"candidates:"`, `"jobs:job_"`, `"jobs:skill_"`).
     Tests check each link is marked current only on its own pages.
   - **Accessibility:** `_field.html` renders checkbox lists in a `<fieldset>` with a
     `<legend>`. Django gives these fields no single `<label for>` target.

**Visual check and fixes:**
- Headless-Edge screenshots of every new page used sample data inside a rolled-back
  transaction. They showed three bugs, and each got a failing test or a confirmed cause first:
  1. **Skill checkboxes overlapped the next field.** Django copies widget attrs onto the
     wrapping `<div>` too, so the whole list was drawn as one DaisyUI checkbox box.
     - **Red:** a test asserted the wrapper has no class.
     - **Fix:** `core.forms.CheckboxSelectMultiple` drops the class from the wrapper only. The
       new `.choice-grid` CSS lays the options out in a grid.
  2. **Invalid selects kept a grey border.** This also affected the Phase 2 candidate Source
     field.
     - **Cause:** DaisyUI 5 emits its components in sublayers of `@layer utilities` and colours
       borders through `--input-color`. Our rule in `@layer components` always lost.
     - **Fix:** the rule moved to `@layer utilities` and sets `--input-color`. The rebuilt
       screenshots show red borders on both inputs and selects.
  3. **The skill list wasn't alphabetical.** Django drops `Meta.ordering` from GROUP BY queries,
     and the job-count annotation makes one.
     - **Red:** an ordering test failed.
     - **Fix:** the view orders explicitly.
- **Phone width:** headless Edge won't size a window below about 492 px, so the pages were
  also measured inside a 375 px iframe. No page scrolls sideways; wide tables scroll inside
  their card.

**Verification:**
- `ruff check` and `ruff format --check` are clean; `manage.py check` reports no issues;
  `makemigrations --check` and `migrate --check` are clean.
- **182 of 182 tests passed** before review: 92 from Phases 1–2 and 90 from Phase 3.
- **Covered:** user stories 20, 26, 27, 28 and 29; AC11, AC14, AC15 and AC16; and AC2/AC3 for
  jobs and skills.
- **Not started, as planned:**
  - **Phase 4 onward:** applications and hired counts on the job page.
  - **Phase 7:** the Close and Reopen actions, Job Closed badges and the active-applications
    note.
  - **Phase 10:** permanent job deletion. Only deletion is Phase 10, not Close and Reopen.

**Decisions and limitations raised for review:**
- **Skills are optional on a job.** The plan lists only title, employment type and work mode as
  required; "required skills" in US 20 means the skills the job requires.
- **Skill-delete race.** If a job gained the skill between the check and the delete, the delete
  still went ahead and silently removed the skill from that job.

**Feedback and decisions:**
- I approved the Phase 3 implementation, including optional skills on a job.
- **I asked for the skill-delete race to be fixed before committing,** rather than documented.
  A skill must never be silently removed from a job.
- I asked for the documentation to make clear that Close and Reopen belong to Phase 7, not
  Phase 10.
  - **Found:** the plan, code comments and this entry already gave Phase 7, but the one wrapped
    "Not started" sentence was easy to misread. It's now the list above.

**Concurrency fix (TDD):**
- **Root cause:** for an automatic many-to-many, deleting a skill also runs
  `DELETE FROM jobs_jobopening_skills WHERE skill_id = …`. Any job link that exists at that
  moment, including one committed just after the `exists()` check, is wiped with no error.
- **Shown first:** a throwaway TransactionTestCase made `exists()` miss a real link. The skill
  was deleted and the link vanished. The test was removed afterwards.
- **Design:**
  - **Explicit through model:** `JobSkill`, with job FK CASCADE and skill FK **PROTECT**, plus a
    unique (job, skill) constraint and no model permissions of its own. Django now refuses to
    delete a used skill instead of deleting its links.
  - **Database foreign key as the final guard:** Django enables SQLite foreign-key enforcement
    and creates FKs as deferred. A skill row can't be deleted while a link references it, and a
    link to a deleted skill can't be inserted. The commit fails with `IntegrityError` in either
    order, whatever the timing, and nothing changes.
  - **View:** the `exists()` pre-check is gone, because a check-then-act step is the race. The
    view deletes inside `transaction.atomic()` and shows the same refusal page on
    `ProtectedError` or `IntegrityError`.
  - **Bug found by the tests:** a failed delete still clears the instance's pk, so the refusal
    page crashed. The view now reloads the skill before rendering.
  - **Migration:** Phase 3 wasn't committed, so `jobs/0001_initial` was regenerated. Django
    can't add `through=` to an existing many-to-many. The local database had no jobs data and
    was migrated back to zero and forward again.
- **SQLite transaction mode:** left at the default (deferred). The database FK closes the race
  without making every transaction take the write lock up front.
- **Regression tests:**
  - **Model (TestCase):**
    - deleting a used skill raises ProtectedError, and the link survives;
    - a duplicate (job, skill) row is refused;
    - deleting a job removes its links but not the skills.
  - **Race (`test_skill_delete_race.py`):** a TransactionTestCase that commits for real, so the
    deferred FK check runs. It restores the role groups afterwards with `serialized_rollback`.
    - Raw SQL can't delete a used skill.
    - A link to a just-deleted skill can't be inserted.
    - **End to end:** the delete's PROTECT lookup is blinded, as if another request committed
      the link right after it. The POST still shows the refusal, and the skill and link both
      survive.
  - **Red first:** without exception handling these tests failed with `ProtectedError` and
    `FOREIGN KEY constraint failed`.
- **Remaining edge, not silent:** if a job form is saved with a skill that an Admin deletes in
  the same instant, the job save fails with a server error. No data is lost or left
  inconsistent. This is the same kind of edge as Phase 2's duplicate-email race.

**Final review before committing:**
- No stubs, TODOs or debug code remain. The temporary `job_detail` stub route from cycle 1 and
  the jobs placeholder views were replaced.
- **Fixed during review:**
  - the `_nav_link.html` comment now says "contains" rather than "starts with", because the
    template's `in` test is a substring match;
  - Ruff asked for `JobSkill.__str__` (a test was added) and a combined `with` statement.
- **Left as is:** `JobsPermissionMixin` repeats Phase 2's three-line `CandidatePermissionMixin`.
  Merging them would mean editing approved Phase 2 code for little gain.
- No credentials, `db.sqlite3`, built CSS, Tailwind CLI binary or `__pycache__` are in the
  commit. The settings still read `DJANGO_SECRET_KEY` from the environment.
- CLAUDE.md documents the jobs URLs, test helpers, the nav `section` prefix, the checkbox
  widget, the CSS layer, and the skill-delete strategy.

**Final verification:**
- `ruff check` and `ruff format --check` are clean; `manage.py check` reports no issues;
  `makemigrations --check` and `migrate --check` are clean.
- **189 of 189 tests pass:** 92 from Phases 1–2 and 97 from Phase 3.
- Committed as "Phase 3: skills and job openings" and pushed to `main`. Phase 4 has not been
  started.

---

## Entry 13

**Date:** 2026-10-27

**Phase:** Phase 4 implementation (Applications: creation, list, detail and history)

**Prompt:**
```
/implement Implement Phase 4 of my Applicant Tracking System using the approved plan at
plans/applicant-tracking-system.md. Before beginning, read CLAUDE.md, the PRD, the implementation
plan, and PROMPTS.md. Follow the exact Phase 4 scope: Application model connecting a Candidate to
a JobOpening; enforce uniqueness for each candidate/job combination; new applications begin at the
Applied stage; create an initial StageChange record (null → Applied) when an application is
created; make StageChange history append-only and immutable; ensure application creation and its
initial history record happen atomically; prevent new applications for archived candidates or
closed jobs; application creation, listing, and detail pages; display the application stage and
history on the detail page; provide a New Application button on the Applications list and
Candidate detail page, with the candidate preselected when applicable; enforce Recruiter and Admin
permissions server-side; use DaisyUI templates consistent with the existing application.
Requirements: strict TDD (Red-Green-Refactor); write failing tests before implementing each
feature; follow the Phase 4 user stories and acceptance criteria; preserve Phases 1–3; do not
implement stage transitions, rejection, withdrawal, reactivation, or application notes editing
yet; run the complete test suite, Ruff lint and format checks, Django system checks, and migration
checks; update PROMPTS.md; stop after Phase 4 for my review before committing or pushing. Do not
begin Phase 5.
```

**Result:**
Claude Code built Phase 4 in five Red-Green cycles. Each cycle's tests were run and seen to fail
for the expected reason before any code was written.

1. **Models and immutable history** (`pipeline/tests/test_models.py`, 17 tests).
   - **Red:** `pipeline.models` didn't exist.
   - **Green, `Stage`:** TextChoices with the eight stages in pipeline order. `ACTIVE_STAGES` and
     `TERMINAL_STAGES` tuples, and a `Stage.is_active` property.
   - **Green, `Application`:**
     - candidate, job opening and `created_by` FKs, all PROTECT;
     - `stage` (default Applied), `stage_changed_at` and `created_by` are not editable, so no
       form can set them;
     - `created_at` and optional `notes`;
     - a unique (candidate, job_opening) constraint with the message "This candidate already has
       an application for this job.";
     - ordered most recently changed first.
   - **Green, `StageChange`:**
     - application FK CASCADE, `changed_by` FK PROTECT;
     - `from_stage` is null for the creation entry, as the plan specifies, with a `noqa` for
       Ruff's DJ001 rule on nullable CharFields;
     - `to_stage`, `changed_at` and `note`, ordered by `changed_at`, then id;
     - no model permissions (`default_permissions = ()`).
   - **Append-only, at two levels:**
     - **Model and queryset:** `save()` on an existing row, `delete()`, and queryset `update()`
       and `delete()` all raise `HistoryIsImmutable`.
     - **Database:** a SQLite `BEFORE UPDATE` trigger (migration `0002_stagechange_append_only`)
       refuses raw-SQL updates.
     - Deleting an Application still removes its history, because Django's cascade deletes rows
       directly. Phase 10's never-moved delete needs that, and a test covers it.
2. **Group permissions** (`test_permissions.py`, 4 tests).
   - **Red:** no `pipeline` permissions.
   - **Green:** migration `0003_application_group_permissions` grants view, add and change on
     Application to both groups, and delete to Admin.
   - A test confirms StageChange has no permissions to grant.
   - The pipeline migrations, including the trigger, reverse cleanly.
3. **Stage-change service, creation path** (`test_services.py`, 10 tests).
   - **Red:** `pipeline.services` didn't exist.
   - **Green:** `create_application`, inside one `transaction.atomic()`:
     - re-reads the job and candidate, so stale objects passed in can't slip past a guard;
     - checks the job is Open, the candidate isn't archived, and the pair isn't a duplicate;
     - creates the application at Applied, with a matching null → Applied StageChange
       (`changed_by` = the creator, same timestamp).
   - Refusals raise `StageChangeRefused` with a clear message.
   - **Race:** if two requests for the same pair both pass the check, the unique constraint fails
     the second insert. The service re-checks and turns it into the same duplicate refusal.
   - **Tests:**
     - atomicity: when the StageChange write fails, no application is left behind;
     - a stale job object, where the database already says Closed;
     - the duplicate race, with the pre-check missing the row and the re-check finding it.
4. **Creation form** (`test_forms.py`, 9 tests).
   - **Red:** `pipeline.forms` didn't exist.
   - **Green:** `ApplicationForm` has candidate, job opening and notes only.
     - It offers only Open jobs and non-archived candidates, labelled "Ann Lee (email)" and
       "Title (Department)".
     - A posted closed job or archived candidate gets a clear reason instead of Django's "Select a
       valid choice".
     - A duplicate pair shows the constraint's message as a form error.
5. **Views, entry points and badges** (`test_views.py` 30, `test_entry_points.py` 5,
   `core/tests/test_badges.py` 3).
   - **Red:** the URL names and the badge template didn't exist.
   - **Green:**
     - **List** at `/applications/`: stage filter links (All plus all eight stages, the current
       one marked with `aria-current`). `?stage=<value>` covers open and closed jobs; unknown
       values are ignored.
     - **Create** at `/applications/new/`:
       - `?candidate=<pk>` preselects an active candidate and can be changed;
       - an archived or unknown candidate is never preselected;
       - saving goes through the service, and a refusal from it appears as a form alert;
       - success redirects to the detail page.
     - **Detail** at `/applications/<pk>/`: stage badge, candidate and job links (with the job's
       status badge), creator, notes, and a read-only history table (when, from, to, by, note),
       oldest first.
       - The creation entry shows "New application" as its from-stage.
       - POST returns 405, and there are no stage actions.
     - **Candidate detail page:** a new Applications section with stage badges, and a New
       application button linking to `/applications/new/?candidate=<pk>`.
       - The button shows only for non-archived candidates and users with `add_application`.
       - An archived candidate's page says why there's no button.
     - **Stage badge:** `core/_stage_badge.html`, with one style each for early active stages
       (info), Offer (warning), Hired (success) and Rejected/Withdrawn (ghost).
     - The Applications nav link stays highlighted on every application page
       (`section="pipeline:"`).
   - **Test mistakes found on the first green run, and fixed:**
     - the helper's default creator clashed with an existing `recruiter` user;
     - a check didn't allow for Django marking the empty `---------` option `selected`;
     - a URL-name check read the root resolver, where namespaced names don't appear.

**Visual check:**
- Headless-Edge screenshots of the list, the detail page with history, the form showing a
  duplicate refusal, and a candidate page with applications. Sample data was created inside a
  rolled-back transaction.
- All seven rendered pages, including the filtered list and an archived candidate, were measured
  in a 375 px iframe. None scrolls sideways.

**Verification:**
- `ruff check` and `ruff format --check` are clean (Ruff flagged one unused import, a nested
  `with` and a long docstring in the new tests; all fixed). `manage.py check` reports no issues;
  `makemigrations --check` and `migrate --check` are clean.
- **Encoding slip, caught by `ruff format --check`:**
  - A helper script edited CLAUDE.md with Python's default Windows encoding (cp1252). Existing
    text round-tripped unchanged, but the newly added en dash ("Phases 5–6") was written as a
    cp1252 byte.
  - The byte was repaired, and every tracked and new text file was scanned: all are valid UTF-8.
  - Later scripted edits should open files with `encoding="utf-8"`.
- **267 of 267 tests pass:** 189 from Phases 1–3 and 78 from Phase 4.
- **Covered:** user stories 32, 33, 34, 35, 45 and 46; AC19, AC20, AC30, AC32 and AC33; and AC2
  for application creation.
- **Not started, as planned:**
  - Advance and Back over HTMX (Phase 5);
  - Reject, Withdraw and Reactivate (Phase 6);
  - Job Closed badges on applications (Phase 7);
  - notes editing (later phase);
  - Admin application delete (Phase 10).

**Decisions to review:**
- **Lowercase stage values in URLs** (`?stage=applied`, `?stage=final_review`), matching every
  other choice field. The plan's `?stage=Applied` is the label.
- **Application `created_at` and `stage_changed_at`** come from the service, so they can differ
  by microseconds. The creation StageChange uses exactly `stage_changed_at`.
- **Archive race, for Phase 8:** creating an application while another request archives the same
  candidate isn't guarded yet. Phase 8's archive check should run inside a transaction and
  re-check.

**Feedback and decisions:**
- I approved Phase 4.
- **I approved lowercase stage values in URLs** (`?stage=applied`, `?stage=final_review`). They
  match the stored values and every other choice field.
- **Concurrency follow-up, required in Phase 8:**
  - A new application can still be created for a candidate who is being archived at that
    moment. I agreed to leave this documented for now, but it must be fixed when archiving is
    built.
  - It's recorded as a required task under Phase 8 in `plans/applicant-tracking-system.md`. The
    archive check and the write of `archived_at` must not interleave with `create_application`,
    with a regression test.

**Final review before committing:**
- **Duplicate code removed:** the three-line permission mixin now had three copies
  (`CandidatePermissionMixin`, `JobsPermissionMixin`, `ApplicationPermissionMixin`).
  - They became one `core.views.StaffPermissionMixin`. This touched the approved Phase 2 and 3
    views.
  - It's a pure refactor: the existing 403 and login-redirect tests in every app passed
    unchanged.
- **Redundant query removed:** `preselected_candidate` is a `cached_property`, so its query runs
  once per request instead of twice.
- **Immutability confirmed, and one gap closed:**
  - **Already covered by tests:** `save()` on an existing row, `delete()`, queryset `update()`
    and `delete()`, and raw-SQL `UPDATE` (the trigger).
  - **New test: an existing pk.** A new instance reusing an existing pk makes Django try an
    `UPDATE`, which only the trigger stops. The test confirms it does.
  - **New test, which went red first:** `bulk_update()` doesn't go through `update()` in Django
    6, so only the trigger caught it, as a raw IntegrityError. The queryset now refuses
    `bulk_update()` with `HistoryIsImmutable` before anything reaches the database.
- **Atomicity confirmed:**
  - **Service tests:** creation runs inside one `transaction.atomic()`, and a failed history write
    leaves no application.
  - **New view-level test:** a real form POST where the history write fails leaves no
    application and no history.
- No stubs, TODOs or debug code remain. The temporary `application_detail` stub route and the
  pipeline placeholder view were replaced. Only `staff` still uses a placeholder, until a later
  phase.
- No credentials, `db.sqlite3`, built CSS, Tailwind CLI binary or `__pycache__` are in the
  commit. Every changed text file was confirmed to be valid UTF-8.

**Final verification:**
- `ruff check` and `ruff format --check` are clean; `manage.py check` reports no issues;
  `makemigrations --check` and `migrate --check` are clean.
- **270 of 270 tests pass:** 189 from Phases 1–3 and 81 from Phase 4.
- Committed as "Phase 4: applications and stage history" and pushed to `main`. Phase 5 has not
  been started.

---

## Entry 14

**Date:** 2026-10-27

**Phase:** Phase 5 implementation (Advance and Back over HTMX, with stale and double-click safety)

**Prompt:**
```
/implement Implement Phase 5 of my Applicant Tracking System using the approved plan at
plans/applicant-tracking-system.md. Before beginning, read CLAUDE.md, the PRD, the implementation
plan, and PROMPTS.md. Follow the exact Phase 5 scope: advance applications forward by one hiring
stage; move applications backward by one hiring stage; follow the approved stage progression
(Applied → Screening → Interview → Final Review → Offer → Hired); allow Hired only from Offer, and
make Hired permanent; record every successful transition as a new immutable StageChange entry
with the previous stage, new stage, acting user, timestamp, and optional note; update the
application's current stage and stage_changed_at atomically with its history entry; use HTMX
POST requests to perform stage transitions and refresh the appropriate UI sections; prevent
double-clicks and stale submissions using the expected-stage check and conditional database
updates; enforce Recruiter and Admin permissions server-side; display clear feedback when a
transition is refused; preserve stage history and ensure refused transitions create no history
entries. Requirements: strict TDD (Red-Green-Refactor); write failing tests before implementing
each feature; follow the Phase 5 user stories and acceptance criteria; preserve Phases 1–4; do
not implement Reject, Withdraw, or Reactivate (Phase 6), or job Close/Reopen or candidate
Archive/Restore (Phases 7 and 8); run the complete test suite, Ruff lint and format checks,
Django system checks, and migration checks; update PROMPTS.md; stop after Phase 5 for my review
before committing or pushing. Do not begin Phase 6.
```

**Result:**
Claude Code built Phase 5 in two Red-Green cycles, then checked the HTMX behaviour in a real
browser.

1. **Stage-change service: Advance and Back** (`pipeline/tests/test_transitions.py`, 18 tests).
   - **Red:** `Action`, `change_stage` and `available_moves` didn't exist.
   - **Green:**
     - **`Action`** TextChoices (Advance, Back), plus an explicit `TRANSITIONS` table:
       - Advance: Applied → Screening → Interview → Final Review → Offer → Hired;
       - Back: Screening through Offer, back one stage;
       - nothing from Hired, Rejected or Withdrawn.
     - **`available_moves(stage)`** gives the card its buttons.
     - **`change_stage(application, action, expected_stage, changed_by, note="")`**, inside
       `transaction.atomic()`:
       1. **Stale check:** reads the current stage. If it doesn't match `expected_stage`, it
          refuses with "This application was already updated, so nothing was changed. It's now
          at <stage>."
       2. **Allowed check:** an unknown action gets "That stage action isn't recognised."; a
          disallowed one gets "Back isn't allowed from Applied." or "Hired is permanent, so this
          application can't be moved."
       3. **Write:** a conditional `UPDATE … WHERE pk = … AND stage = expected` sets the stage and
          `stage_changed_at`. Exactly one StageChange (from, to, user, same timestamp, trimmed
          note) is written only when exactly one row was updated. Otherwise the move is refused as
          stale.
     - The service takes only an action, so no request can name a target stage. A test confirms
       passing `to_stage` raises `TypeError`.
   - **Tests:**
     - **AC21:** every Advance and Back.
     - **AC22:** Back from Applied; Advance and Back from Hired, Rejected and Withdrawn; unknown
       actions.
     - **Order:** the stale check comes before the allowed check.
     - **AC28:** a double-click moves exactly once.
     - **Race:** a move committed after the stale read is caught by the conditional UPDATE.
     - **AC29:** the moves for all eight stages.
   - **Mutation check:** making the UPDATE unconditional turned the race test red. The original
     was then restored.
   - **Test-helper bugs found, then fixed:**
     - `make_application` always reused one candidate email; it now creates unique applicants;
     - the race test's "unchanged" baseline needed a `refresh_from_db()`.
2. **Transition endpoint and HTMX card** (`test_transition_views.py`, 23 tests).
   - **Red:** the `application_transition` route didn't exist.
   - **Green:**
     - **Endpoint:** `ApplicationTransitionView` at POST `/applications/<pk>/transition/`.
       - It requires `pipeline.change_application` (403 otherwise). GET gets 405, and an unknown
         application gets 404.
       - **With HTMX** it returns `_transition_response.html`: the refreshed stage card with the
         feedback message inside, plus the history table swapped in out of band
         (`hx-swap-oob`).
       - Refusals return 200, so HTMX swaps the card with the reason. Success is
         `role="status"`, a refusal is `role="alert"`, and the message gets `autofocus` so it's
         announced after the swap.
       - **Without HTMX** it redirects to the detail page with a success or error message.
     - **Card:** `pipeline/_stage_card.html` replaces the stage rows in the detail page's Details.
       - It shows the stage badge, "since …", and "Hired is permanent." where relevant.
       - It has one form per allowed move ("Advance to Interview", "Back to Applied"), each with
         hidden `action` and `expected_stage`, `hx-post`, `hx-target="#stage-card"` and
         `hx-disabled-elt="find button"`.
       - Users without the change permission see no buttons.
     - **Shared context:** `stage_card_context()` feeds the detail page and the HTMX response.
       History moved into `_stage_history.html`.
   - **Tests:**
     - **AC29:** the partial has no `<html>` or sidebar, and the buttons match each of the
       eight stages.
     - **AC27:** a stale click returns the current card and "already updated", with no new
       StageChange.
     - **AC28:** a double-click; a posted target stage is ignored; plain-POST fallbacks.
     - **CSRF:** with `enforce_csrf_checks=True`, a POST without a token gets 403. The
       `X-CSRFToken` header that HTMX sends from `<body hx-headers>` is accepted.
     - **AC2:** Recruiter and Admin can move applications; view-only and no-role users get 403,
       and nothing changes.
   - **Two Phase 4 tests updated on purpose:** they asserted "no stage actions" on the detail
     page. They now assert the history section has no form or inputs, and the URL check expects
     `application_transition`. No URL creates, edits or deletes history.
   - **Test bugs found, then fixed:** a lazy CSRF token needed `str()`; the `post()` helper
     passed `follow=True` as form data; the read-only-history check ran into the sidebar's
     logout form.
3. **Refactor:** `change_stage` now returns the StageChange it wrote. The view builds "Moved from X
   to Y." from that entry instead of `stage_changes.last()`, which could describe another
   request's move.

**Browser check of the real HTMX swap:**
- A throwaway dev server ran from settings in the scratchpad, against a scratch SQLite file. It
  allowed `X_FRAME_OPTIONS = "SAMEORIGIN"` for the harness only. The project's settings and
  `db.sqlite3` were untouched, and the scratch database was deleted afterwards.
- **Harness:** a same-origin page logged in, clicked the real buttons and recorded the DOM after
  each `htmx:afterSettle`. The checks:
  - **In place:** the card swapped in place (still one sidebar), and the buttons changed with the
    stage.
  - **History:** the table refreshed out of band (1 → 2 → 3 → 4 rows).
  - **Focus:** it moved to the feedback alert.
  - **Double-click:** two quick clicks sent one POST, because `hx-disabled-elt` worked.
- A screenshot of a tampered, stale `expected_stage` showed the red "already updated" alert, the
  current stage with corrected buttons, and no new history row.

**Verification:**
- `ruff check` and `ruff format --check` are clean (one long line in the view was split);
  `manage.py check` reports no issues; `makemigrations --check` and `migrate --check` are clean.
  Phase 5 needed no migration.
- **311 of 311 tests pass:** 270 from Phases 1–4 and 41 from Phase 5.
- **Covered:** user stories 36, 37, 43 and 44; AC21 (Advance and Back rows), AC22, AC27, AC28
  and AC29; and AC2 for stage moves.
- **Not started, as planned:** Reject, Withdraw and Reactivate with required notes (Phase 6);
  Close and Reopen (Phase 7); Archive and Restore (Phase 8).

**Decisions to review:**
- **Moves live on the detail page's stage card only.** The list rows link to it. The plan says
  "card or row", and the Implementation tasks only call for the card partial.
- **Notes on moves:** Advance and Back are single clicks with no note field. The service and
  endpoint already accept an optional `note`, which Phase 6's inline forms will use.
- **Refusals return HTTP 200** with the card, because HTMX doesn't swap 4xx responses by
  default. Permission failures still return 403.

---

## Entry 15

**Date:** 2026-10-28

**Phase:** Phase 5 approval, final review, commit and push

**Prompt:**
```
I approve Phase 5. I approve all three implementation decisions: keep Advance and Back buttons on
the application detail page's Stage card only; keep Advance and Back as single-click actions
without a note box; return HTTP 200 for refused transitions so HTMX can display feedback, while
preserving HTTP 403 for permission failures. Before committing: review all Phase 5 changes for
leftover stubs, duplicate code, accidental changes, and formatting issues; confirm that every
successful stage transition creates exactly one immutable StageChange record and that refused
transitions create none; confirm that stale requests, double-clicks, and concurrent transitions
are handled safely; confirm no credentials, local database files, generated CSS, or build
artifacts are included; run the complete automated test suite, Ruff lint and format checks,
Django system checks, and migration checks one final time; update PROMPTS.md with my approval,
the three decisions, and the final verification results. Commit with the message "Phase 5: hiring
stage transitions". Push to the existing GitHub main branch. Report the final test count, commit
hash, push status, and any remaining issues. Do not begin Phase 6 yet.
```

**Approved decisions:**
1. Advance and Back live on the application detail page's Stage card only.
2. Advance and Back are single clicks with no note box. The service still accepts an optional
   note for Phase 6.
3. Refused transitions return HTTP 200 with the card and the reason, so HTMX swaps it in.
   Permission failures stay HTTP 403.

**Final review:**
- **No leftovers:** no stubs, TODOs or debug output in the Phase 5 files, and no changes outside
  `pipeline/`, `CLAUDE.md` and `PROMPTS.md`.
- **Two small cleanups:**
  - `ApplicationTransitionView` called `refresh_from_db()` again after a successful move,
    which the service already does. It now refreshes only after a refusal, so a stale card shows
    the current stage.
  - CLAUDE.md said the `make_application` `stage=` argument stood in "until Phases 5–6 add
    moves". It now describes the helper as it is, and the wrapping is fixed.
- **One StageChange per move, none on refusal:** `change_stage` writes the StageChange only after
  its conditional UPDATE changed exactly one row, inside the same `transaction.atomic()`. Every
  refusal is raised before that point. Tests check the count after each Advance and Back, after
  every refused move, and in the view tests (`assert_unchanged`). The Phase 4 append-only guards
  (model, queryset and SQLite trigger) still make each entry immutable.
- **Stale, double-click and concurrent requests:**
  - every form posts the `expected_stage` it showed, and a mismatch is refused as "already
    updated" before anything is written;
  - a second click gets the same refusal, and `hx-disabled-elt` stops the browser sending it at
    all;
  - a move committed between the stale read and the write is caught by `UPDATE … WHERE stage =
    expected`, which then updates no rows and writes no history. The race test proves this
    (and failed when the UPDATE was made unconditional).
- **Nothing sensitive or generated:** `db.sqlite3`, `assets/css/tailwind.css`, `.venv` and `.env`
  are gitignored and none is in the change set. A scan of the diff found no credentials.

**Final verification:**
- **311 of 311 tests pass:** 270 from Phases 1–4 and 41 from Phase 5.
- `ruff check` and `ruff format --check` are clean (93 files).
- `manage.py check` reports no issues.
- `makemigrations --check --dry-run` reports no changes; `migrate --check` is clean.

**Result:** committed as "Phase 5: hiring stage transitions" and pushed to `main`. Phase 6 not
started.

---

## Entry 16

**Date:** 2026-10-28

**Phase:** Phase 6 implementation (Reject, Withdraw and Reactivate; Hired is permanent)

**Prompt:**
```
/implement Implement Phase 6 of my Applicant Tracking System using the approved plan at
plans/applicant-tracking-system.md. Before beginning, read CLAUDE.md, the PRD, the implementation
plan, and PROMPTS.md. Follow the exact Phase 6 scope: allow active applications to be Rejected or
Withdrawn; require a nonblank reason for rejection and withdrawal; allow Rejected and Withdrawn
applications to be reactivated to their most recent active hiring stage; require a nonblank
reason for reactivation; prevent reactivation when the candidate is archived; allow reactivation
even when the job opening is Closed, as specified in the approved PRD; keep Hired permanent and
prevent Reject, Withdraw, or Reactivate from Hired; record each successful action as an
immutable StageChange entry, including its reason, actor, timestamp, previous stage, and new
stage; extend the existing atomic stage-change service, preserving stale-request and
double-click protections; add the appropriate forms and HTMX controls to the application detail
page; enforce Recruiter and Admin permissions server-side. Requirements: strict TDD
(Red-Green-Refactor); write failing tests before implementing each feature; follow the exact
Phase 6 user stories and acceptance criteria; preserve Phases 1–5; do not implement job
Close/Reopen or candidate Archive/Restore (Phases 7 and 8); run the complete test suite, Ruff lint
and format checks, Django system checks, and migration checks; update PROMPTS.md; stop after
Phase 6 for my review before committing or pushing. Do not begin Phase 7.
```

**Result:**
Claude Code built Phase 6 in two Red-Green cycles, ran two mutation checks, then checked the
HTMX behaviour in a real browser.

1. **Stage-change service: Reject, Withdraw and Reactivate** (`test_transitions.py`, 40 tests,
   up from 18).
   - **Red:** the tests failed to import `NoteRequired`, `Move` and `reactivation_target`.
   - **Green:**
     - **`Action`** gained Reject, Withdraw and Reactivate. Reject and Withdraw join the
       `TRANSITIONS` table from all five active stages.
     - **Reactivate** is allowed only from Rejected and Withdrawn. Its target comes from the
       history: `reactivation_target()` returns the `from_stage` of the latest StageChange.
       Only reactivation can leave Rejected or Withdrawn, so that entry is always the exit move.
       If the history doesn't end in that exit (only test setup can cause this), the service
       refuses rather than guess.
     - **Check order:** (1) stale, (2) allowed (Hired gets "Hired is permanent" for every
       action), (3) required note after trimming, which raises `NoteRequired`, a subclass of
       `StageChangeRefused`, (4) for Reactivate, the candidate isn't archived. A closed job is
       not checked, and reactivation never changes its status.
     - The write is unchanged: the same conditional `UPDATE … WHERE stage = expected` and exactly
       one StageChange (with the trimmed note) per updated row.
     - **`available_moves(stage, reactivate_to=None)`** adds Reactivate for Rejected and
       Withdrawn. `Move.label` gives "Reject", "Reactivate to Interview" and so on, and
       `Move.needs_note` tells the card which moves open a note form.
   - **Tests:**
     - **AC21:** Reject and Withdraw from every active stage; Reactivate from Rejected and from
       Withdrawn, each with one correct StageChange.
     - **AC22:** Reactivate from each active stage; Reject, Withdraw, Advance and Back from
       Rejected and Withdrawn.
     - **AC23:** empty, spaces-only and newline/tab notes refused for all three; Advance and
       Back still need no note.
     - **AC24:** Interview → Rejected → back to Interview, then Final Review → Withdrawn → back
       to Final Review, then Screening → Rejected → back to Screening (10 history rows).
     - **AC25:** an archived candidate blocks Reactivate; a closed job doesn't, and stays
       Closed; every action from Hired is refused, even with a note.
     - **AC26:** hiring leaves the other application for that job, the candidate's application
       for another job, the job's status and the candidate unchanged.
     - **Order:** stale before the note ("already updated", not "note required"); allowed
       before the note; the note before the archived guard.
     - **Double-click:** a repeated Reject writes one entry.
   - **Mutation checks:**
     - Disabling the required-note check turned 10 subtests red.
     - Reading the oldest exit entry instead of the latest turned the repeated-cycles test red.
     - Both were restored.
2. **Inline note forms over HTMX** (`test_transition_views.py`, 45 tests, up from 23).
   - **Red:** 20 failures; the card had no note links or form. One error was a test bug:
     the base setUp's job made `JobOpening.objects.get()` ambiguous, so it now uses the pk.
   - **Green:**
     - **Card:** Advance and Back stay single-click forms. Reject, Withdraw and Reactivate are
       links to `/applications/<pk>/?confirm=<action>` with `hx-get`, which swap in the card
       with the note form open.
     - **Note form:** a fieldset ("Reject this application"; Reactivate adds "Returns to
       Interview."), a required, autofocused "Reason" textarea, Confirm, and Cancel (which
       re-fetches the card). It posts `action`, `expected_stage` and `note` to the existing
       transition endpoint, with `hx-disabled-elt`.
     - **No new URLs:** `ApplicationDetailView` returns just `_stage_card.html` when
       `HX-Request` is set, and sends `Vary: HX-Request` so caches keep the page and the card
       apart. Without HTMX, the same links open the full page with the form.
     - **Refusals:** a `NoteRequired` refusal keeps the form open with `aria-invalid="true"`
       pointing at the alert. Without HTMX it redirects to `?confirm=<action>` with the
       message. Every other refusal (stale, archived, Hired) closes the form and shows the
       reason.
     - `?confirm=` is ignored for actions the stage doesn't allow, and for users without the
       change permission.
   - **Tests:** the card's links and forms for all eight stages (AC29); the note form as a
     partial; Cancel; the no-JavaScript fallback; Reject, Withdraw and Reactivate end to end;
     a blank note keeps the form open; a stale Reject without a note says "already updated";
     a double-clicked Confirm; archived-candidate and closed-job reactivation; Hired refuses all
     three; and 403 for view-only users.
   - **One Phase 5 test updated on purpose:** the Offer card now has four `hx-target`
     attributes (Reject and Withdraw links added), not two.
3. **Refactor:** the archived-candidate check became a named lazy queryset instead of a wrapped
   expression.

**Browser check of the real HTMX swap:**
- **Setup:** the same approach as Phase 5. A throwaway dev server ran from settings in the
  scratchpad against a scratch SQLite file (with `X_FRAME_OPTIONS = "SAMEORIGIN"` for the
  harness only). The Tailwind CSS was rebuilt for the new classes (gitignored output). The
  project's settings and `db.sqlite3` were untouched, and the scratch database was deleted.
- **Harness:** headless Chrome clicked the real controls and recorded the card after each
  `htmx:afterSettle`:
  - **Reject:** opened the form in place (one sidebar, URL unchanged), with focus in the
    reason field.
  - **Cancel:** restored the card.
  - **Empty note:** the browser's `required` check stopped it, so no POST was sent.
  - **Spaces-only note:** the server refused it, and the form stayed open with `aria-invalid`.
  - **Confirm with a reason:** moved Interview → Rejected, and the history refreshed (3 → 4
    rows) with the note.
  - **Reactivate:** the form said "Returns to Interview."
  - **Double-clicked Confirm:** sent one POST and returned to Interview (5 rows).
- A screenshot of a refused blank Withdraw showed the red alert, the open form with the red
  `aria-invalid` border, and the cursor in the field.

**Verification:**
- **355 of 355 tests pass:** 311 from Phases 1–5 and 44 new.
- `ruff check` and `ruff format --check` are clean (93 files).
- `manage.py check` reports no issues.
- `makemigrations --check --dry-run` and `migrate --check` are clean. Phase 6 needed no
  migration.
- **Covered:** user stories 38, 39, 41 and 42 (and 40, reactivation on a closed job); AC21 (now
  complete), AC23, AC24, AC25 and AC26, plus AC22, AC27–AC29 and AC2 for the new actions.
- **Not started, as planned:** Close and Reopen (Phase 7); Archive and Restore (Phase 8). The
  archived-candidate guard is tested by setting `archived_at` directly.

**Decisions to review:**
- **Note links reuse the detail URL** (`?confirm=<action>`, partial on `HX-Request`) instead of
  adding a new GET route. This keeps the plan's URL list unchanged and gives a no-JavaScript
  fallback.
- **A missing note keeps the form open,** while other refusals close it, because only a missing
  note is fixed by typing.
- **Archived candidates can still be rejected or withdrawn.** The PRD guards only Reactivate.
- **Known gap:** after Cancel, keyboard focus returns to the page body, not the button that
  opened the form.

---

## Entry 17

**Date:** 2026-10-28

**Phase:** Phase 6 approval, Cancel focus fix, final review, commit and push

**Prompt:**
```
I approve Phase 6 and all three implementation decisions. Before committing, please make one
small accessibility improvement: when a user opens a Reject, Withdraw, or Reactivate reason form
and selects Cancel, restore keyboard focus to the action that originally opened the form. Ensure
this works with HTMX and does not break the no-JavaScript fallback. Follow Red-Green-Refactor for
this change and add an appropriate regression test. Keep the fix small and within Phase 6 scope.
Then: review all Phase 6 changes for leftover stubs, duplicate code, accidental changes, and
formatting issues; confirm that required reasons, reactivation history, Hired permanence, and
archived-candidate guards remain correct; confirm every successful transition creates exactly
one immutable StageChange and refused transitions create none; confirm no credentials, local
databases, generated CSS, or build artifacts are included; run the complete test suite, Ruff lint
and format checks, Django system checks, and migration checks; update PROMPTS.md with my
approval, the accessibility improvement, and final verification results; commit with the
message "Phase 6: reject withdraw and reactivate applications"; push to the existing GitHub main
branch; report the final test count, commit hash, push status, and remaining issues. Do not
begin Phase 7 yet.
```

**Approved decisions:**
1. Note links reuse the detail URL (`?confirm=<action>`, card-only on `HX-Request`) rather than a
   new route.
2. Only a missing-note refusal keeps the form open; other refusals close it.
3. Archived candidates can still be rejected or withdrawn; only Reactivate is guarded.

**Accessibility improvement: Cancel returns focus to the opening link**
- **Red:** three new regression tests in `NoteFormTests`:
  - after Cancel, the Reject and Withdraw links carry `autofocus`, with and without HTMX;
  - Reactivate gets the same;
  - `?focus=` is ignored for actions with no link (`advance`, `back`, an unavailable
    `reactivate`, unknown and empty values).

  Two existing assertions changed from "Cancel links to the bare detail URL" to "Cancel links to
  `?focus=<action>`". The run showed 7 failures for that reason.
- **Green:**
  - Cancel's `href` and `hx-get` are now `/applications/<pk>/?focus=<action>`.
  - `stage_card_context` accepts `focus` and keeps it only when that action is one of the card's
    note links. The link then renders with `autofocus`.
  - HTMX focuses `[autofocus]` in swapped content. Without JavaScript the same `href` loads the
    full page with the form closed and the link marked `autofocus`.
  - No new URL, view or JavaScript.
- **Refactor:** `stage_card_context` looks up `confirming` and `focus` from one dict of
  note-requiring moves.
- **Browser check** (throwaway scratch server and database, deleted afterwards):
  - in headless Chrome, opening Reject or Withdraw put focus in the reason field;
  - after Cancel, focus was on the Reject or Withdraw link again, and the URL was unchanged.
  - The full-page fallback rendered the form closed with `autofocus` on Withdraw, but headless
    Chrome didn't move focus into the harness iframe on a full load. That focus step was
    therefore checked through the markup, not observed in the browser.

**Final review:**
- **No leftovers:** no stubs, TODOs or debug output, and no duplicate code. Changes are limited
  to `pipeline/` (service, views, stage card, two test files), `CLAUDE.md` and `PROMPTS.md`.
  Ruff reformatted one test file.
- **Rules still covered by passing tests:**
  - **Required reasons:** empty, spaces-only and newline/tab notes refused for Reject, Withdraw
    and Reactivate.
  - **Reactivation history:** returns to the latest exit's `from_stage`, across repeated cycles;
    refused if the history doesn't end in an exit.
  - **Hired permanence:** every action refused, with or without a note.
  - **Archived candidate:** blocks Reactivate, after the note check; a closed job doesn't block
    it and stays Closed.

  The service was not changed by the focus fix.
- **One StageChange per move, none on refusal:** the StageChange is written only after the
  conditional UPDATE changed exactly one row, inside the same transaction. Every refusal is
  raised before it. Tests check the count for each allowed move, each refusal, stale and
  double-clicked requests, and the race. The append-only model, queryset and SQLite trigger keep
  the entries immutable.
- **Nothing sensitive or generated:** `db.sqlite3`, `assets/css/tailwind.css`, `.env`, `.venv` and
  `.django_tailwind_cli` are gitignored and none is in the change set. A scan of the diff found no
  credentials.

**Final verification:**
- **358 of 358 tests pass:** 311 from Phases 1–5 and 47 from Phase 6.
- `ruff check` and `ruff format --check` are clean (93 files).
- `manage.py check` reports no issues.
- `makemigrations --check --dry-run` reports no changes; `migrate --check` is clean.

**Result:** committed as "Phase 6: reject withdraw and reactivate applications" and pushed to
`main`. Phase 7 not started.

---

## Entry 18

**Date:** 2026-10-28

**Phase:** Phase 7 implementation (Close and reopen jobs)

**Prompt:**
```
/implement Implement Phase 7 of my Applicant Tracking System using the approved plan at
plans/applicant-tracking-system.md. Before beginning, read CLAUDE.md, the PRD, the implementation
plan, and PROMPTS.md. Follow the exact Phase 7 scope: add dedicated Close and Reopen actions for
job openings; ensure new job openings default to Open; keep job status changes out of the
general create/edit forms; closing a job must prevent new applications from being created for
that job; existing applications on a Closed job must remain visible and retain their complete
stage history; existing applications on a Closed job must still be able to Advance, move Back,
Reject, Withdraw, and Reactivate, following all existing stage rules; reopening a job must allow
new applications again without changing existing applications or their history; preserve the
rule that Reactivate is allowed on Closed jobs unless the candidate is archived; require
appropriate Recruiter or Admin permissions for Close and Reopen; display the correct Open or
Closed status and available actions in the job interface; handle stale or repeated Close/Reopen
requests safely and provide clear feedback. Requirements: strict TDD (Red-Green-Refactor); write
failing tests before implementing each feature; follow the exact Phase 7 user stories and
acceptance criteria; preserve Phases 1–6; do not implement candidate Archive/Restore (Phase 8)
or Admin permanent deletion (Phase 10); run the complete test suite, Ruff lint and format checks,
Django system checks, and migration checks; update PROMPTS.md; stop after Phase 7 for my review
before committing or pushing. Do not begin Phase 8.
```

**Result:**
Claude Code built Phase 7 in one Red-Green cycle. Phase 3 had already made `status`
`editable=False`, defaulted it to Open and kept it off the job forms, and its tests already proved
that a posted status is ignored on create and edit (AC11). Those tests still pass unchanged.

1. **Red:** two new test files, plus one deliberate change to a Phase 3 test.
   - `jobs/tests/test_close_reopen.py` (21 tests) failed to import `jobs.services`.
   - `pipeline/tests/test_closed_jobs.py` (11 tests) failed because the `job_close` route didn't
     exist.
   - The Phase 3 job-list test now expects the PRD's ">Job Closed<" wording instead of
     ">Closed<".
2. **Green:**
   - **`jobs/services.py`:**
     - `close_job(job)` and `reopen_job(job)` each run one conditional
       `UPDATE … WHERE pk = … AND status = <from>`. It sets the new status and `updated_at`
       (`.update()` skips `auto_now`), then refreshes the job in place.
     - If no row changed (a double-click, a second tab, or a stale page), they raise
       `JobStatusUnchanged`: "This job is already closed, so nothing was changed." or "…already
       open…".
     - They never touch applications or history.
   - **Views:** `JobCloseView` and `JobReopenView` at POST `/jobs/<pk>/close/` and `/reopen/`
     (the plan's URLs).
     - They share a small `JobStatusActionView`: POST only (GET gets 405), and
       `jobs.change_jobopening` is required (403 otherwise; Recruiter and Admin both have it).
     - Each redirects to the job with a success message ("Data Analyst closed. It no longer
       accepts new applications.") or the refusal as an error message.
   - **Job detail:**
     - an open job shows "Close job"; a closed one shows "Reopen job" (both hidden without the
       change permission);
     - a closed job with active applications shows "This job is closed but still has N active
       application(s)." (US 23).
   - **Badge:** `core/_job_status_badge.html` now reads **Job Closed** for closed jobs, as the
     PRD names it, and still reads Open for open ones. The application list adds the badge
     next to the job only for applications on closed jobs. The application detail page already
     showed it.
   - **Unchanged:** the stage-change service. It checks job status only when creating, so
     moves and Reactivate on a closed job already worked.
3. **Refactor:** the two action views store their service function with `staticmethod`.
4. **Mutation check:** making the job UPDATE unconditional turned 5 tests red (repeated, stale
   and double requests). The original was restored.

**Tests (AC12, AC13, AC25 closed-job part, US 21–24 and 40):**
- **Close and Reopen:** status and `updated_at` change; repeated and stale requests are refused
  and change nothing; and no application's stage, stage time or history count changes,
  including another job's.
- **Through the real Close action:**
  - new applications are refused by the form ("Choose an open job…") and the service;
  - the create form stops offering the job;
  - after Reopen, another candidate can apply, but the existing pair is still refused as a
    duplicate.
- **Moves on a closed job:** Advance, Back, Reject, Withdraw and Hire all work over HTMX, and the
  job stays Closed. The usual rules still apply (Back from Applied, a missing note). The stage
  card still offers the moves, and the full history stays visible.
- **Walkthrough 6:**
  - a Reject on a closed job is undone with one Reactivate, which writes one StageChange;
  - the job stays Closed, and a new applicant is still refused.
- **Badges and note:**
  - Job Closed appears only on closed-job rows in the application list, including a
    stage-filtered list;
  - the note appears for 1 and for 2 active applications, but not on open jobs or on closed
    jobs where everything is terminal.
- **Permissions:** Recruiter and Admin can close and reopen (AC2). A view-only user gets 403 and
  sees no buttons; an anonymous user is sent to login; an unknown job gets 404.

**Browser check:**
- A throwaway server ran on scratch settings and a scratch database, which was deleted
  afterwards. The Tailwind CSS was rebuilt for `badge-warning` and `alert-warning` (gitignored
  output).
- Headless Chrome clicked the real "Close job" button. The page reloaded with the success
  message, a "Reopen job" button, the yellow Job Closed badge, and "This job is closed but still
  has 1 active application."

**Verification:**
- **390 of 390 tests pass:** 358 from Phases 1–6 and 32 new.
- `ruff check` and `ruff format --check` are clean (96 files).
- `manage.py check` reports no issues.
- `makemigrations --check --dry-run` and `migrate --check` are clean. Phase 7 needed no
  migration.
- **Not started, as planned:** candidate Archive and Restore (Phase 8); Admin permanent deletes
  (Phase 10); the job detail's applications list and hired count, and Job Closed on the
  dashboard and candidate pages (Phase 9).

**Decisions to review:**
- **No confirmation step for Close or Reopen.** Each is a single POST button, because Reopen
  undoes Close exactly and neither changes any application.
- **The status badge now reads "Job Closed"** wherever it appears (job list, job detail,
  application detail, the skill-delete page's list of jobs). Open jobs still read "Open". On
  the application list, only closed jobs get a badge.
- **Repeated or stale requests show an error message,** like stage refusals, not a silent
  success.

---

## Entry 19

**Date:** 2026-10-28

**Phase:** Phase 7 approval, final review, commit and push

**Prompt:**
```
I approve Phase 7 and all three implementation decisions. Before committing: review all Phase 7
changes for leftover stubs, duplicate code, accidental changes, and formatting issues; confirm
that Close and Reopen only change the job's status and updated timestamp, without modifying
existing applications or their stage history; confirm that new applications are blocked on
Closed jobs and allowed again after Reopen; confirm that existing applications on Closed jobs can
still Advance, move Back, Reject, Withdraw, and Reactivate; confirm that stale requests, repeated
actions, and permissions are handled correctly; confirm no credentials, local database files,
generated CSS, or build artifacts are included; run the complete automated test suite, Ruff lint
and format checks, Django system checks, and migration checks; update PROMPTS.md with my
approval, the three decisions, and final verification results. Commit with the message "Phase 7:
close and reopen job openings". Push to the existing GitHub main branch. Report the final test
count, commit hash, push status, and any remaining issues. Do not begin Phase 8 yet.
```

**Approved decisions:**
1. Close and Reopen are single POST buttons with no confirmation step.
2. The shared status badge reads "Job Closed" for closed jobs everywhere, and "Open" for open
   ones. The application list shows it only for applications on closed jobs.
3. A repeated or stale Close/Reopen shows an error message ("already closed/open, so nothing was
   changed").

**Final review:**
- **No leftovers:** no stubs, TODOs or debug output, and no duplicate code. Changes are limited
  to the jobs service, views, URLs and detail template; the shared badge; the application list;
  the tests; `CLAUDE.md` and `PROMPTS.md`.
- **One formatting fix:** the `jobs` line in CLAUDE.md was re-wrapped to the file's width.
- **Close and Reopen change only the job:** `_set_status` updates only `status` and
  `updated_at` on the one job row. A test records every application's stage, stage time and
  history count on that job, closes and reopens it, and finds them identical. The total
  StageChange count and another job's status are unchanged too.
- **New applications:**
  - after a real Close, the form ("Choose an open job…") and the service both refuse, and the
    form stops offering the job;
  - after Reopen, a new candidate's application is accepted, and a duplicate pair is still
    refused.
- **Moves on a closed job:**
  - Advance, Back, Reject, Withdraw and Hire all succeed over HTMX, and the job stays Closed;
  - Reactivate after a Reject on a closed job writes one StageChange, and the job stays Closed
    and still refuses newcomers;
  - the usual rules still apply.
- **Stale, repeated and permissions:** the conditional UPDATE refuses a repeated or stale
  request and changes nothing (mutation-checked). GET gets 405, a view-only user gets 403 with
  no change, an anonymous user is sent to login, and an unknown job gets 404. Recruiter and Admin
  can both close and reopen.
- **Nothing sensitive or generated:** `db.sqlite3`, `assets/css/tailwind.css`, `.env`, `.venv` and
  `.django_tailwind_cli` are gitignored and none is in the change set. A scan found no
  credentials.

**Final verification:**
- **390 of 390 tests pass:** 358 from Phases 1–6 and 32 from Phase 7.
- `ruff check` and `ruff format --check` are clean (96 files).
- `manage.py check` reports no issues.
- `makemigrations --check --dry-run` reports no changes; `migrate --check` is clean.

**Result:** committed as "Phase 7: close and reopen job openings" and pushed to `main`. Phase 8
not started.

---

## Future Entries

Add a new entry for each significant interaction with Claude Code, especially during:

- PRD and implementation planning
- Phase-by-phase implementation
- Testing, debugging, and revisions

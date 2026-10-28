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

## Future Entries

Add a new entry for each significant interaction with Claude Code, especially during:

- PRD and implementation planning
- Phase-by-phase implementation
- Testing, debugging, and revisions

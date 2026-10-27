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

## Future Entries

Add a new entry for each significant interaction with Claude Code, especially during:

- PRD and implementation planning
- Phase-by-phase implementation
- Testing, debugging, and revisions

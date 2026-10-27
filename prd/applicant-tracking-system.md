# PRD — Applicant Tracking System (CIDM 3312 Project #1)

**Date:** 2026-10-27
**Status:** Draft for implementation planning
**Sources:** grill-me decisions Q1–Q27 (logged in `PROMPTS.md`), `prototypes/hiring-stage-logic-findings.md`,
`prototypes/dashboard-ui-findings.md`

## Problem Statement

A company's recruiting staff track candidates, job openings and hiring progress across spreadsheets,
email and memory. They cannot reliably tell:
- who is at which hiring stage for which job, or who moved them there and why;
- whether the same person has been entered twice, or applied twice for the same job;
- what is still in progress on a job that has stopped accepting applicants.

Mistakes are hard to undo safely. A misclick can erase history, two recruiters can overwrite each
other's changes, and deleting a record can quietly remove an applicant's whole hiring trail. Staff
need one internal system that keeps this information consistent, shows what needs attention, and
records every hiring decision.

## Solution

An internal, staff-only web application where Recruiters and Admins:

- maintain **candidate** records, with contact details and where each candidate came from;
- maintain **job openings**, with their required **skills** and an Open or Closed status;
- connect candidates to jobs through **applications**, with at most one per candidate per job;
- move each application through a fixed hiring pipeline: Applied → Screening → Interview →
  Final Review → Offer → Hired, or out to Rejected or Withdrawn. Moves are one click and use HTMX, so
  the page never fully reloads;
- see a complete, unchangeable **history** of every stage change, recording who made it, when, and why;
- start from a **dashboard** that summarises the pipeline, highlights what needs attention, and shows
  recent activity.

The system enforces its rules on the server and never changes data on the user's behalf. Archiving,
closing, reopening and hiring have no hidden side effects, and anything with application history can
never be permanently deleted. Candidates never log in.

## User Stories

### Access and roles

1. As a staff member, I want to log in with my own account, so that only authorised staff can see candidate data.
2. As a visitor who isn't logged in, I want to be redirected to the login page from any ATS page, so that no candidate data is exposed.
3. As a Recruiter, I want to manage candidates, job openings, applications and hiring stages, so that I can do my daily recruiting work.
4. As an Admin, I want every Recruiter ability plus staff account management, the skills list and permanent deletion, so that restricted and destructive actions stay with a small group.
5. As a Recruiter, I want Admin-only navigation and actions hidden from me, and refused by the server if I try them anyway, so that I can't accidentally perform restricted actions.

### Candidates

6. As a Recruiter, I want to add a candidate with first name, last name, email, optional phone, source, optional source details, optional notes and an optional LinkedIn or portfolio URL, so that I have everything needed to identify and contact them.
7. As a Recruiter, I want to pick the candidate's source from a fixed list (Referral, Company Website, Job Board, LinkedIn, Career Fair, Agency, Other), so that sources are consistent and can be counted.
8. As a Recruiter, I want an optional "source details" field, so that I can record who referred someone or which job board they used.
9. As a Recruiter, I want the system to reject a candidate whose email already exists, ignoring letter case, with a clear message that a candidate with that email already exists, so that duplicate people can't be created.
10. As a Recruiter, I want to edit a candidate's details, with the same validation as creating one, so that records stay accurate.
11. As a Recruiter, I want to archive a candidate, so that they no longer clutter the default candidate list.
12. As a Recruiter, I want archiving refused while the candidate has any active application, with a message listing those applications, so that nobody leaves the candidate list while still in a hiring pipeline.
13. As a Recruiter, I want to archive a candidate who was hired, as long as none of their applications is active, so that people who are now employees leave the active list.
14. As a Recruiter, I want an archived-candidates view and the ability to restore a candidate, so that archiving is never permanent.
15. As a Recruiter, I want restoring a candidate to leave all their application stages and history unchanged, so that restoring is safe.
16. As a Recruiter, I want archived candidates blocked from new applications and from reactivation until they are restored, so that archiving really removes them from the pipeline.
17. As an Admin, I want to permanently delete a candidate who has no applications, so that records entered by mistake can be removed.
18. As an Admin, I want deletion of a candidate with any applications refused with a clear error, so that hiring history can never be lost.
19. As a Recruiter, I want a candidate's detail page to show their applications and which jobs they were hired for, so that I can see their full status in one place.

### Job openings and skills

20. As a Recruiter, I want to create and edit job openings, with a title, optional department, location and description, an employment type (Full-time, Part-time, Contract, Internship), a work mode (On-site, Remote, Hybrid) and required skills, with new jobs starting as Open, so that postings describe the role and are ready for applicants.
21. As a Recruiter, I want to close a job with a dedicated Close action (not through the edit form), so that it stops accepting new applications and status changes are always deliberate.
22. As a Recruiter, I want existing applications on a closed job to keep moving through the stages, so that I can finish interviewing people already in the pipeline.
23. As a Recruiter, I want closed jobs clearly marked, along with whether they still have active applications, so that unfinished work on closed jobs is visible.
24. As a Recruiter, I want to reopen a closed job with a dedicated Reopen action, so that it accepts new applications again, without any existing application or history changing.
25. As a Recruiter, I want a job's detail page to show its skills, its applications, and how many candidates were hired, so that I can see the job's status at a glance.
26. As a Recruiter, I want to filter the job list by skill, so that I can find jobs needing a particular skill.
27. As a Recruiter, I want to assign existing skills to a job, so that its requirements are recorded consistently.
28. As an Admin, I want to create, rename and delete skills, with names unique ignoring case, so that the skills list stays clean.
29. As an Admin, I want deletion of a skill that any job uses (open or closed) refused with a list of those jobs, so that no job silently loses a requirement.
30. As an Admin, I want to permanently delete a job opening with no applications, whether Open or Closed, so that postings created by mistake can be removed.
31. As an Admin, I want deletion of a job with any applications refused with a clear error suggesting I close it instead, so that hiring history is kept.

### Applications and hiring stages

32. As a Recruiter, I want a New Application button on the Applications list page and on a candidate's detail page, both opening the same creation form, so that I can link a candidate to a job from wherever I'm working.
33. As a Recruiter, I want the candidate already selected when I start a new application from that candidate's detail page, so that I only need to choose the job.
34. As a Recruiter, I want every new application to start at Applied automatically, so that no stage is skipped.
35. As a Recruiter, I want creation refused when the job is closed, the candidate is archived, or the candidate already has an application for that job (even after the job is reopened), with a clear reason, so that the pipeline stays valid.
36. As a Recruiter, I want to advance an application one stage, or move it back one stage, so that I can record progress and correct mistakes.
37. As a Recruiter, I want only the actions allowed for the current stage shown (Advance, Back, Reject, Withdraw, or Reactivate), so that I can't attempt an invalid move.
38. As a Recruiter, I want to reject or withdraw an active application by confirming a required note in a small inline form, so that every exit from the pipeline is explained and accidental clicks are caught.
39. As a Recruiter, I want to reactivate a Rejected or Withdrawn application with a required note, returning it to the active stage it left, so that I can fix mistakes and bring back returning candidates.
40. As a Recruiter, I want reactivation to work on a closed job without reopening it or changing its status, so that a misclicked Reject on a closed job can be undone without letting new applicants in.
41. As a Recruiter, I want Hired to be permanent, so that completed hires can never be altered.
42. As a Recruiter, I want hiring someone to change only that application (no automatic job closing, rejections or withdrawals), so that multi-hire roles and the candidate's other applications are unaffected.
43. As a Recruiter, I want each stage change to update in place without a full page reload, so that working through the pipeline is fast.
44. As a Recruiter, I want a click from an out-of-date screen, or a double-click, to be refused without any change and my card to refresh with an explanation, so that I never move an application by accident.
45. As a Recruiter, I want an application's detail page to show its full stage history in chronological order (from, to, who, when, note), so that I can see exactly how it got where it is.
46. As a Recruiter, I want to filter the application list by stage, covering both open and closed jobs, so that I can work through everyone at a given stage.
47. As an Admin, I want to permanently delete an application that has never moved from Applied, so that data-entry mistakes can be removed.
48. As an Admin, I want deletion refused for any application that has ever moved (even one that later returned to Applied), so that real hiring history is never erased.
49. As a Recruiter, I want to edit an application's general notes after it is created, without changing its stage or adding a history entry, so that I can keep context up to date while the stage history stays a record of stage moves only.

### Staff accounts

50. As an Admin, I want to create staff accounts and assign them the Admin or Recruiter role, so that new staff can work in the system.
51. As an Admin, I want to deactivate a departing staff member's account instead of deleting it, so that they can no longer log in but their name stays on every history entry.
52. As an Admin, I want to reactivate a deactivated staff account, so that a returning staff member can log in again with their history intact.
53. As an Admin, I want the system to stop me deactivating or demoting my own account, and stop anyone deactivating or demoting the last active Admin, so that nobody gets locked out of administration.
54. As an Admin, I want inactive users hidden from the default staff list but viewable on request, and still shown in historical records, so that the list stays current, inactive accounts can be found for reactivation, and history stays complete.

### Dashboard and navigation

55. As a staff member, I want a dashboard as my starting page showing open jobs, active applications and total hires, so that I can see the state of hiring at a glance.
56. As a staff member, I want the dashboard pipeline to show how many active applications are at each of the five active stages, including applications on closed jobs, with each count linking to the stage-filtered application list, so that I can go straight to the work.
57. As a staff member, I want a Needs Attention section listing closed jobs that still have active applications and applications at Offer, so that I know what to follow up.
58. As a staff member, I want a Recent Activity section showing the 10 most recent stage changes, so that I can see what changed recently.
59. As a staff member, I want consistent sidebar navigation (Dashboard, Candidates, Job Openings, Applications, plus Skills and Staff Management for Admins) that collapses into a menu on small screens, so that the app is easy to use on any device.
60. As a staff member, I want consistent status badges (stage, Job Closed, Awaiting Decision), so that I can recognise important states anywhere in the app.

## Implementation Decisions

### Technology and project conventions

- Python and Django, with SQLite as the database and **uv** for dependency and environment management.
- Tailwind CSS with DaisyUI through **django-tailwind-cli**; **HTMX** for in-place interactions. No other
  JavaScript framework, no bundler, and no custom JavaScript beyond HTMX and DaisyUI's built-in behaviour.
- **Ruff** for linting and formatting. **Automated Django tests**, written test-first, phase by phase.
- Django's built-in authentication, groups and permissions. No custom user model and no custom auth system.
- `CLAUDE.md` and `PROMPTS.md` are maintained throughout; progress is committed and pushed to GitHub.

### Roles and permissions

- Two Django groups: **Recruiter** and **Admin**. Admin has every Recruiter permission plus the
  restricted ones below. Every ATS page requires login. Candidates have no accounts.
- Restricted actions are enforced in the views, not only hidden in templates. A forbidden request
  changes nothing and returns a permission error.

| Capability | Recruiter | Admin |
|---|:-:|:-:|
| View dashboard, candidates, jobs, applications | ✓ | ✓ |
| Create and edit candidates; archive and restore | ✓ | ✓ |
| Create and edit jobs; assign skills; close and reopen | ✓ | ✓ |
| Create applications; edit application notes; Advance, Back, Reject, Withdraw, Reactivate | ✓ | ✓ |
| Create, rename and delete skills | | ✓ |
| Permanently delete candidates, jobs, applications (subject to guards) | | ✓ |
| Create staff accounts, assign roles, deactivate and reactivate accounts | | ✓ |

### Data model

**Candidate**
- first name and last name (required)
- email (required): unique **ignoring case**, enforced by a database constraint on the lower-cased
  value plus form validation with a clear "a candidate with this email already exists" message
- phone (optional)
- source (required; choices: Referral, Company Website, Job Board, LinkedIn, Career Fair, Agency, Other)
- source details (optional text)
- notes (optional text)
- profile URL for LinkedIn or a portfolio (optional, validated as a URL)
- archived-at timestamp (empty = active)
- created-at and updated-at timestamps
- No résumé upload and no separate Source model.

**JobOpening**
- title (required)
- department, location and description (optional plain text)
- employment type (required; choices: Full-time, Part-time, Contract, Internship)
- work mode (required; choices: On-site, Remote, Hybrid)
- status (choices: Open, Closed): **defaults to Open** when a job is created. It is **not** on the
  create or edit form, and it changes **only** through the dedicated Close and Reopen actions, which
  never change any application or StageChange.
- skills (many-to-many with Skill)
- created-at and updated-at timestamps
- No salary, deadline, Draft status or Department model.

**Skill**
- name (required): unique ignoring case, enforced by a database constraint plus form validation.

**Application**
- candidate (foreign key, **PROTECT**)
- job opening (foreign key, **PROTECT**)
- current stage (choices: Applied, Screening, Interview, Final Review, Offer, Hired, Rejected, Withdrawn)
- stage-changed-at timestamp
- created-by (staff user, **PROTECT**)
- created-at timestamp
- notes (optional general notes): Recruiters and Admins can **edit them after creation**. Editing notes
  never changes the stage or stage-changed-at, and never creates a StageChange.
- A database **unique constraint on (candidate, job opening)**, plus a form-level check with a clear message.

**StageChange** (append-only audit log)
- application (foreign key, **CASCADE**; only a never-moved application can ever be deleted)
- from-stage (empty for the creation entry)
- to-stage
- changed-by (staff user, **PROTECT**)
- changed-at timestamp
- note (optional; required for Reject, Withdraw and Reactivate)
- Ordered chronologically. No create, edit or delete screens: rows are written only by the
  stage-change service, and a row, **including its note**, is immutable once written. StageChange
  notes are separate from the editable general notes on Application.

**Staff users**
- Django users with the `is_active` flag. Admins deactivate an account by setting it to false and
  reactivate it by setting it to true; nothing else about the user or their history changes.
- Users are never deleted, because the PROTECT links from Application and StageChange preserve history.

### Stage model and transitions

- **Active stages:** Applied, Screening, Interview, Final Review, Offer.
- **Terminal stages:** Hired (permanent), Rejected, Withdrawn.

| Action | Allowed from | Result | Note |
|---|---|---|---|
| Create | — | Applied (creation logged as empty → Applied) | — |
| Advance | any active stage | next stage; Offer → **Hired** | optional |
| Back | Screening, Interview, Final Review, Offer | previous stage (never from Applied) | optional |
| Reject | any active stage | Rejected | **required** |
| Withdraw | any active stage | Withdrawn | **required** |
| Reactivate | Rejected, Withdrawn | the active stage it was in just before (from-stage of its latest StageChange) | **required** |
| — | Hired | no action allowed | — |

- **No skipping stages.** Hired is reachable only from Offer.
- **Reactivation guard (changed by the logic prototype):** blocked only when the **candidate is archived**.
  A **closed job does not block reactivation**, and reactivation never changes the job's status. Closing a
  job stops *new* intake; reactivating an existing application isn't new intake.
- **Reactivation target:** a Rejected or Withdrawn application can only leave that stage through
  reactivation, so its latest StageChange is always the move into the terminal stage. That entry's
  from-stage is the stage to return to. Repeated reject or withdraw and reactivate cycles return to the
  most recent active stage.
- **Creation guards:** the job must be Open, the candidate must not be archived, and there can be no
  existing application for the same candidate and job.
- **No automatic side effects anywhere:**
  - hiring never closes a job or changes other applications;
  - closing or reopening a job never changes applications;
  - archiving or restoring a candidate never changes applications.

### Stage-change service, audit logging and concurrency

- All stage changes, including the creation entry, go through **one service** that every view and test uses.
- Each stage-change request carries the **expected current stage** (a hidden field in the HTMX form).
  The server checks requests in this order:
  1. **Stale check:** the expected stage must equal the current stage. If not, it's refused with
     "already updated".
  2. **Legality:** the action must be allowed from the current stage.
  3. **Required note:** Reject, Withdraw and Reactivate need a note that is non-empty after trimming.
  4. **Guards:** for Reactivate, the candidate must not be archived.
- **Applying a change:** inside a single database transaction, the service makes a conditional update
  that sets the new stage and stage-changed-at **only where the stage still equals the expected stage**.
  It writes exactly one StageChange only if exactly one row was updated. This keeps concurrent requests
  and double-clicks safe on SQLite without row locking. A failure at any point leaves no partial change.
- **Refused requests** change nothing and write no StageChange. The HTMX response returns the
  application's refreshed card or row, with a clear message.
- Application creation and its initial StageChange happen in one transaction.

### Archiving and deletion rules

- **Candidate archive:** allowed only when none of the candidate's applications is active. Hired,
  Rejected and Withdrawn all count as terminal, so hired candidates can be archived. When it's refused,
  the error lists the active applications.
- **Candidate restore:** clears the archived-at timestamp and changes nothing else.
- **Permanent deletes** are Admin-only, each with a clear error when it's refused:
  - **Candidate:** only with no applications. Enforced by PROTECT, which is also caught and explained
    in the view.
  - **Job opening:** only with no applications, whether Open or Closed. The error suggests closing
    the job instead.
  - **Application:** only if it is at Applied **and** has exactly one StageChange, the creation entry.
    That entry is removed with it.
  - **Skill:** only if no job, open or closed, uses it. This needs an explicit many-to-many check,
    because PROTECT doesn't apply to many-to-many relationships.
- **Staff:** deactivated, never deleted, and reactivated by an Admin when needed. Only Admins can
  change activation or roles. Deactivating and reactivating preserve every Application and
  StageChange record.
- **Admin role protection,** enforced on the server, not just hidden in the UI:
  - an Admin can't **deactivate** their own account, or **demote** it to Recruiter;
  - the **last active Admin** can't be deactivated or demoted by anyone.
  
  A refused request changes nothing and explains why.

### Pages, URLs and interactions

- **Base layout (UI convention, from the UI prototype):**
  - a responsive DaisyUI drawer sidebar: always open on large screens, a labelled ☰ toggle on small ones;
  - navigation: Dashboard, Candidates, Job Openings, Applications, plus an Admin-only group with
    Skills and Staff Management that is rendered only for Admins;
  - the signed-in user and their role shown in the sidebar.
- **Shared badges, used everywhere:** stage badges with consistent colours (active stages, Offer,
  Hired, and Rejected/Withdrawn), **Job Closed** on any job or application belonging to a closed job,
  and **Awaiting Decision** on applications at Offer.
- **Dashboard,** the start page after login (variant A's layout):
  1. **Summary counts:** open job openings, active applications (the five active stages, on open and
     closed jobs), and total hires (every Hired application, regardless of job status or archive status).
  2. **Hiring pipeline:** five clickable stage counts, each linking to the application list filtered by
     that stage, including closed jobs.
  3. **Needs Attention:** closed jobs that still have active applications (with counts), and
     applications at Offer.
  4. **Recent Activity:** the 10 most recent StageChanges (when, application, from → to, by whom, note).

  It uses only existing models and fields, with no time-based rules and no job filter.
- **Candidates:**
  - the list shows non-archived candidates by default, with a separate archived view;
  - the detail page shows contact details, source, notes, applications with stage badges, "Hired for…",
    a **New Application** button (shown only for non-archived candidates), and the Archive or Restore
    and Admin Delete actions;
  - create and edit forms.
- **Job openings:**
  - the list can be filtered by skill and shows status badges;
  - the detail page shows fields, skills, applications, active count, hired count, and a Job Closed
    badge (with an active-applications note when relevant);
  - create and edit forms with skill selection and **no status field** (new jobs are Open);
  - dedicated **Close** and **Reopen** actions (the only way status changes), and Admin Delete.
- **Applications:**
  - the list can be filtered by stage; a stage filter includes applications on open and closed jobs;
  - **New Application** entry points: a button on the Applications list page and one on the candidate
    detail page. Both open the **same creation form**. From a candidate's page, the candidate is
    preselected (passed to the form as an initial value); the user can still change it;
  - the create form offers only Open jobs and non-archived candidates, and the server still enforces
    every guard, including when a preselected candidate is invalid;
  - the detail page shows the current stage, the allowed actions, the editable general notes, and the
    chronological history (read-only, including its notes);
  - Admin Delete appears for applications that have never moved.
- **Stage actions** are HTMX POST requests that swap the application's card or row in place:
  - Advance and Back are single clicks;
  - Reject, Withdraw and Reactivate first open a small inline form with a note field and a Confirm button;
  - only actions allowed for the current stage are rendered, but the server re-validates everything;
  - HTMX requests include the CSRF token.
- **Skills** (Admin): list, create, rename, delete.
- **Staff Management** (Admin): list active staff, with an option to show inactive accounts; create
  an account with a role; change a role; deactivate; reactivate. Role changes and deactivation obey
  the Admin role protection rules.

### Nonfunctional requirements

- **Security:** login required everywhere; permissions enforced on the server; CSRF protection on all
  POST and HTMX requests; no candidate-facing pages.
- **Integrity:** database constraints back every uniqueness rule; multi-row changes are atomic; all
  validation runs on the server, not just the client.
- **Usability and accessibility:**
  - responsive from phone width (no sideways page scrolling) to desktop;
  - semantic headings, real links and buttons, labelled controls, enough contrast;
  - error messages say what was refused and why.
- **Simplicity:** no drag-and-drop and no extra JavaScript; plain Django views, forms and templates
  with HTMX partials.
- **Quality:** Ruff passes; the automated test suite passes before each commit; development is
  test-first, one phase at a time.

## Acceptance Criteria and Testable Requirements

Each item below should map to one or more automated Django tests.

**Authentication and permissions**
- AC1: An anonymous request to any ATS page redirects to login.
- AC2: A Recruiter can do every Recruiter action in the permission table, and gets a permission error,
  with no data changed, on every Admin-only action (skills management, permanent deletes, staff management).
- AC3: An Admin can do every action. Admin-only navigation renders for Admins and not for Recruiters.

**Candidates**
- AC4: Creating a candidate with an email that matches an existing one in any letter case fails with
  the "already exists" message. This is enforced by both the form and the database constraint.
- AC5: First name, last name, email and source are required. Phone, source details, notes and profile
  URL are optional. An invalid URL is rejected.
- AC6: Archiving is refused while the candidate has any active application, and the error lists them.
  It succeeds when every application is Hired, Rejected or Withdrawn, including a candidate with a
  Hired application.
- AC7: Archived candidates are excluded from the default list and appear in the archived view.
- AC8: Restoring clears archived-at, and no application stage or StageChange changes.
- AC9: An archived candidate can't get a new application or have an application reactivated.
- AC10: An Admin can delete a candidate with no applications. Deleting one with applications is
  refused with a clear error and nothing is removed.

**Job openings and skills**
- AC11: Job create and edit validate required fields and the choice values. A newly created job is
  Open. The create and edit forms have no status field, and a status value submitted to them is
  ignored, so status changes only through the Close and Reopen actions.
- AC12: Closing a job blocks new applications. Existing active applications on it can still be advanced,
  moved back, rejected and withdrawn. No application changes when the job closes.
- AC13: Reopening allows new applications and changes no application. A duplicate application for the
  same candidate and job is still refused after reopening.
- AC14: A job can have many skills, and a skill can belong to many jobs. Filtering the job list by a
  skill returns exactly the jobs with that skill.
- AC15: Skill names are unique ignoring case. Only Admins can create, rename or delete skills.
- AC16: Deleting a skill used by any job (open or closed) is refused and the jobs are listed. An unused
  skill can be deleted.
- AC17: An Admin can delete a job with no applications (Open or Closed). Deleting a job with any
  applications is refused with the "close it instead" message.
- AC18: The job detail page shows the hired count, and the candidate detail page shows "Hired for…".

**Applications and stages**
- AC19: A new application starts at Applied and creates exactly one StageChange (empty → Applied,
  changed-by = creator) in the same transaction.
- AC20: Creation is refused for a closed job, an archived candidate, or a duplicate pair, and nothing
  is written.
- AC21: Every allowed transition in the stage table succeeds and writes exactly one StageChange with
  the correct from, to, user and note.
- AC22: Every disallowed transition is refused and writes no StageChange. This covers skipping, Back
  from Applied, Advance or Back from a terminal stage, Reject or Withdraw from a terminal stage, any move
  from Hired, Reactivate from an active stage, and Hired from anything but Offer.
- AC23: Reject, Withdraw and Reactivate with a missing or whitespace-only note are refused, with no
  stage change and no StageChange. Advance and Back succeed without a note.
- AC24: Reactivation returns the application to the stage it was in before its latest Rejected or
  Withdrawn move, including after repeated cycles.
- AC25: Reactivation succeeds on a **closed** job and leaves the job Closed. It's refused when the
  candidate is archived. Hired can never be reactivated.
- AC26: Hiring changes only the selected application. Other applications for that job and that
  candidate, and the job's status, are unchanged.
- AC27: A stage-change request whose expected stage doesn't match the current stage is refused, with
  no change and no StageChange, and the response contains the refreshed card and a message.
- AC28: Two identical requests with the same expected stage (a double-click) produce exactly one
  transition and one StageChange.
- AC29: Stage changes respond to HTMX requests with a partial, not a full page, and only the allowed
  actions are rendered for each stage.
- AC30: There are no create, edit or delete screens for StageChange. The application detail page lists
  its history chronologically.
- AC31: An Admin can delete an application at Applied with exactly one StageChange, and its creation
  entry is removed. Deleting an application that has ever moved is refused, even if it's back at
  Applied. Recruiters can never delete applications.
- AC32: Filtering applications by stage includes applications on both open and closed jobs.
- AC33: The Applications list page and the detail page of a non-archived candidate both show a New
  Application button leading to the same creation form. From a candidate's page, that candidate is
  preselected. An archived candidate's page shows no button, and submitting the form for an archived
  candidate is still refused.
- AC34: Recruiters and Admins can edit an application's general notes after creation. The stage,
  stage-changed-at and StageChange count are unchanged afterwards. There's no way through the UI to
  edit or delete a StageChange or its note.

**Staff accounts**
- AC35: An Admin can create a staff account with the Admin or Recruiter role.
- AC36: Deactivating an account prevents login. The user's name still appears on their Application and
  StageChange records, and they're hidden from the default staff list but shown when inactive accounts
  are requested.
- AC37: An Admin can reactivate a deactivated account. The user can log in again, and none of their
  Application or StageChange records changed. Recruiters can't deactivate, reactivate or change the
  role of any account.
- AC38: The server refuses an Admin deactivating their own account or demoting it to Recruiter, and
  refuses anyone deactivating or demoting the last active Admin. This holds for requests sent directly,
  not only through the UI. Each refusal changes nothing and shows a clear message.
- AC39: Deleting a user referenced by an application or stage change is prevented by PROTECT.

**Dashboard and UI**
- AC40: The summary counts equal the open-job count, the count of applications in the five active
  stages (on open and closed jobs), and the count of all Hired applications.
- AC41: Each of the five pipeline counts is correct and links to the application list filtered by
  that stage.
- AC42: Needs Attention lists exactly the closed jobs that have active applications (with counts) and
  exactly the applications at Offer.
- AC43: Recent Activity shows the 10 most recent StageChanges, newest first.
- AC44: Pages use the sidebar layout and the shared badges. Job Closed appears for closed jobs, and
  Awaiting Decision appears for applications at Offer.

**Quality gates**
- AC45: Ruff lint and format checks pass, and the full Django test suite passes.

## Out of Scope

- A candidate portal, candidate logins, or any public-facing pages.
- A Hiring Manager role or per-job ownership and visibility filtering.
- Résumé or file uploads.
- Candidate skills, skill matching and proficiency levels.
- Salary ranges, application deadlines, a Draft job status, numbers of openings, and a Department model.
- A separate admin-managed Source model.
- Hiring rounds, or reapplying through a second application for the same job.
- Skipping stages, choosing a starting stage, or moving more than one step at a time.
- Required reasons from a fixed list for Reject or Withdraw (free-text notes only).
- Automatic side effects: auto-closing jobs on hire, auto-rejecting other applicants, auto-withdrawing
  on archive, or reactivating on reopen.
- Editing or deleting StageChange history through the app.
- Deleting staff accounts, and custom user models.
- Drag-and-drop pipeline boards, kanban views, and custom JavaScript beyond HTMX and DaisyUI.
- Time-based metrics such as "stuck in stage" or hires this month, and a job filter on the dashboard.
- Email or other notifications, calendar or interview scheduling, and integrations with job boards.
- Record locking (concurrency is handled by the expected-stage check).
- Production deployment and databases other than SQLite.

## Further Notes

- **Prototype evidence.** Two throwaway prototypes informed this PRD and remain in the repository:
  - The **logic prototype** (six walkthroughs, all steps verified automatically) confirmed the stage
    model and led to two decisions:
    - **Q23:** reactivation is allowed on closed jobs. The original rule made a misclicked Reject on a
      closed job impossible to undo without reopening the job.
    - **Q24:** hired candidates can be archived.
  - The **UI prototype** compared three dashboard layouts and selected **variant A, the sidebar
    command center, with variant B's status badges.** That choice is the convention for every page.
- **Possible future enhancements** (not committed): a Hiring Manager role with per-job visibility,
  candidate skills and match display, structured rejection reasons, time-in-stage metrics, and a
  dashboard job filter.
- **Decisions finalised after the first PRD draft:**
  - Admins can reactivate deactivated staff accounts (`is_active` set back to true). Only Admins
    manage activation, and all history is preserved.
  - New Application appears on the Applications list page and the candidate detail page. Both use the
    same form, and the candidate detail page preselects its candidate. (The UI prototype also showed the
    button on the dashboard header; that was a throwaway mock-up, and the dashboard doesn't get one.)
  - **Admin role protection:** an Admin can't demote themselves to Recruiter, and the last active
    Admin can't be demoted or deactivated. This extends Q21's deactivation guard to role changes.
  - **Job status:** new jobs default to Open. Status changes only through the Close and Reopen
    actions, never the edit form, and closing or reopening preserves applications and history.
  - **Application notes:** the general notes can be edited after creation, with no stage change and no
    StageChange. StageChange notes stay immutable.
- **Seed data.** The sample dataset in the UI prototype (7 jobs, 36 applications) makes a good basis
  for development seed data and dashboard tests.

# Dashboard UI prototype — findings

Prototype: `prototypes/dashboard-ui.html` (throwaway; open by double-click — needs internet for the
Tailwind/DaisyUI CDN). Switch variants with the bottom bar or the ← / → keys.
Date: 2026-10-27

## Question

Which dashboard layout should become the ATS's UI convention — for the dashboard itself and for the
page shell every other page uses?

Content was fixed beforehand (Q25/Q26), so variants differ only in structure:

1. Summary counts — open job openings, active applications (all five active stages, on Open **and**
   Closed jobs), total hires (all Hired applications, regardless of job status or candidate archive status).
2. Hiring pipeline — counts for Applied, Screening, Interview, Final Review, Offer; each links to
   `/applications/?stage=<stage>` (open and closed jobs).
3. Needs attention — closed jobs with active applications; applications at Offer.
4. Recent activity — the 10 most recent StageChange records.

Stack: Tailwind + DaisyUI (browser CDN builds for the prototype only), matching the project's
django-tailwind-cli + DaisyUI + HTMX stack. One shared sample dataset, so every variant shows the
same numbers (4 open jobs, 25 active applications — 4 on closed jobs — 4 hires).

## Variants compared

| | A · Sidebar command center | B · Pipeline board | C · Inbox (list / detail) |
|---|---|---|---|
| Navigation | Left sidebar with Admin group; ☰ drawer on phones | Top navbar; Admin dropdown | Plain top link bar |
| Summary counts | Three DaisyUI stat tiles | Badges beside the page title | One sentence |
| Pipeline | Five count cards with progress bars, "View list →" | Kanban-style columns showing up to 4 candidate cards + "View all" | One bar split into five sections sized by count |
| Needs attention | Card with two lists | Warning banner (closed jobs) + highlighted Offer cards | Tab in a list; selecting an item shows detail beside it |
| Recent activity | Always-visible table, notes shown | Hidden in a slide-out side panel | Second tab of the list |
| Strengths | All four sections visible at once; shell scales to every page; simplest Django base template | Most visual; shows who is at each stage; clear status badges | Action-focused; uncluttered |
| Weaknesses | Plainest look | Board implies drag-and-drop, which our one-step, note-required moves don't fit; activity hidden by default | Two sections hidden behind tabs; detail pane needs extra HTMX partials and tests |

Checked: desktop screenshots of each variant in headless Edge; at 375px width no variant scrolls
sideways (variant A initially did — its bottom grid needed `grid-cols-1` — fixed).

## Decision (Q27)

**Variant A's Sidebar Command Center, with Variant B's status badges.**

- A is the dashboard design **and** the page shell for every ATS page.
- Responsive DaisyUI drawer: sidebar always open on large screens, ☰ toggle on small screens.
- Navigation: Dashboard, Candidates, Job Openings, Applications; an **Admin-only** group with Skills and
  Staff Management. (The prototype shows the Admin group to a Recruiter for demonstration; in production
  it must render only for Admins, and the views must also enforce the permission.)
- All four dashboard sections visible at once, as in variant A.
- The five pipeline counts stay clickable links to the stage-filtered application list.
- Borrow B's badges wherever an application or job appears: **Job Closed**, and **Awaiting Decision** for
  applications at Offer; stage badges styled consistently (active stages / Offer / Hired / Rejected & Withdrawn).
- Responsive and accessible: semantic headings, real links/buttons, labelled menu toggle, sufficient contrast.
- No drag-and-drop and no JavaScript beyond HTMX and DaisyUI's built-in behaviour.

### Why

- A is the only variant that shows all four approved sections without extra clicks.
- Its sidebar shell grows naturally to Candidates, Jobs, Applications, Skills and Staff, so one Django
  base template serves the whole app.
- B's board implied drag-and-drop between stages, which conflicts with the agreed one-step,
  note-required, stale-checked transitions — but its badges make the closed-job rule visible everywhere.
- C hid half the dashboard behind tabs and needed extra HTMX detail partials for little benefit.

## For the PRD

- Base template: DaisyUI drawer sidebar (variant A); Admin nav group rendered only for Admins.
- Dashboard: four sections as above, all queries over existing models — no new fields, models,
  time-based rules or job filter.
- Shared badge styles for stages, Job Closed and Awaiting Decision, reused on every page.
- No drag-and-drop; stage changes use the HTMX buttons defined in the logic prototype.

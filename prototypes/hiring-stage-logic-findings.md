# Hiring-stage logic prototype — findings

Prototype: `prototypes/hiring-stage-logic.html` (throwaway; open by double-click).
Date: 2026-10-27

## Question

Do the hiring-stage rules agreed in the grill-me session behave correctly in the awkward cases —
forward/back moves, reject/withdraw and reactivation, the archived-candidate and closed-job guards,
stale screens and double-clicks, required notes, and Hired being permanent?

## What was checked

Six guided walkthroughs (50 steps), each with the outcome the rules predict. All 50 were run
automatically in headless Edge against the prototype's pure logic module:

- Every step produced the predicted outcome (allowed / refused).
- Every successful move or creation added exactly one history entry; every refused one added none.
- A double-click produced one move and one refusal (both requests carry the same expected stage).

## Findings

1. **The rules hold together.** No contradictions between stage moves, archiving, closing/reopening,
   and reactivation were found.
2. **Order of server checks matters.** The prototype checks, in order: (1) stale expected stage,
   (2) is the move legal from the current stage, (3) required note present after trimming whitespace,
   (4) reactivation guards. Checking staleness first gives the clearest message when a screen is out of date.
   Spaces-only notes must count as missing.
3. **Reactivation target lookup is reliable** because a Rejected/Withdrawn application can only leave
   that stage through reactivation — so its latest StageChange is always the move into the terminal stage,
   and its `from_stage` is the stage to return to. Repeated reject/reactivate cycles return to the most
   recent active stage (walkthrough 2).
4. **Misclick on a closed job (walkthrough 6) — RESOLVED.** Originally, Reject/Withdraw were allowed on a
   closed job's active applications but reactivation was blocked while the job was closed, so a mistaken
   Reject could only be undone by reopening the job (briefly accepting new applications from anyone).
5. **Archiving hired candidates — RESOLVED.** Hired is a terminal stage, so a candidate whose applications
   are all terminal (including Hired) can be archived. Confirmed as intended (Decision 2).

## Decisions

### Decision 1 — reactivation is allowed on closed jobs (Q23, 2026-10-27)

Closing a job stops **new** applications only. Reactivating an existing Rejected/Withdrawn application is
not new intake, so a closed job does not block it. Recruiters and Admins can both do it.

Unchanged safeguards: candidate must not be archived; non-empty note required; Hired stays permanent;
returns to the previous active stage; exactly one StageChange per success; stale requests refused.
Reactivation never changes the job's Closed status.

Prototype updated (walkthroughs 3 and 6 rewritten) and all six walkthroughs re-run — 48/48 steps match:

- Walkthrough 3: reactivation refused while the candidate is archived; refused without a note; succeeds
  on the still-closed job after restore; a new application to the closed job is still refused; job stays Closed.
- Walkthrough 6: a misclicked Reject on a closed job is undone with a single Reactivate (back to Offer);
  a stale second Reject from another screen is refused; new applications still refused; job stays Closed.

### Decision 2 — hired candidates can be archived (Q24, 2026-10-27)

No new rule: archiving is allowed whenever all of a candidate's applications are terminal (Hired,
Rejected, Withdrawn) — so hired candidates can be archived by Recruiters or Admins.

- Archiving does not change Hired applications, StageChange history, or job hired counts.
- Archived candidates are hidden from the default candidate list but reachable through the archived
  candidate view (which still shows "Hired for …").
- Restoring changes no application stages or history.

The prototype already behaves this way (walkthrough 1 ends with a Hired application; free play allows
archiving that candidate), so no prototype change was needed.

## For the PRD

- Server check order for stage moves: (1) stale expected stage, (2) move legal from current stage,
  (3) required note present after trimming, (4) reactivation guard (candidate not archived).
- Reactivation guard is **candidate archived only**; job status is not checked.
- Archive guard is **no active applications**; Hired counts as terminal.
- Job hired counts include archived candidates.
- Needs an archived candidate view (decide its form in the UI prototype).

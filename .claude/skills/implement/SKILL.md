---
name: implement
description: Implement one approved phase from a PRD and plan using feedback loops.
argument-hint: "@prd/<feature>.md @plans/<feature>.md implement phase <N>"
disable-model-invocation: true
---

# Implement

## 1. Understand the Phase

Read the referenced PRD and plan. Explore the codebase to understand the relevant files,
patterns, and conventions. If the request does not identify a phase, ask which one.

Implement only that phase. Do not begin the next one.

## 2. Implement the Phase

Invoke the `/tdd` skill for the current phase and follow its instructions, including approval pauses for selected behaviors or confirmation when no behaviors qualify.
Implement all remaining acceptance criteria using the project's normal development and testing process.

## 3. Run Feedback Loops

Run the complete automated test suite, linter, and formatter using the project's configured tools, and resolve any failures.
Perform additional relevant checks and confirm that existing functionality still works.

## 4. Manual Verification

Explain how I can manually verify the completed phase or feature in the browser, including the expected results.
Stop and wait for my confirmation that manual verification passed before marking the phase complete.

## 5. Finish the Phase

Update `PROMPTS.md` using its existing format to document the AI session.
After manual verification is approved, commit the completed phase and push it to GitHub.

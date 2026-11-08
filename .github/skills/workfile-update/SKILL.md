---
name: workfile-update
description: Update docs/WORKFILE.md after completing work in Menu Planner, so the status, phase checkboxes, and log stay accurate. Use at the end of every phase or batch and before a commit.
---

# Update the WORKFILE

`docs/WORKFILE.md` is the live progress record. Update it at each meaningful transition.

Steps:
1. Set "Last updated" to today's date and a short note.
2. Update the Status block: Phase, Now, Next, Blockers. Keep each item to one line.
3. Tick the phase checkboxes you finished: `[x]` done, `[~]` in progress, `[!]` blocked. Do not tick anything you did not verify.
4. Update the phase header line with `Status:` and the commit hash once committed.
5. Add a Log row: date, what was done, verification counts, and what is still unverified.

Rules:
- Record commits by short hash (for example `a2d9ac5`) after they exist. Do not write "not committed" for work already in git.
- Keep open questions visible under Blockers until the user answers them.
- Keep the file readable: one line per item, no long prose.

## Summary

<!-- What problem does this change solve? Keep the scope explicit. -->

## Evidence and verification

- [ ] `py -m pytest` (if crawler/backend changed)
- [ ] `npm.cmd test` (if frontend changed)
- [ ] `npm.cmd run typecheck` (if TypeScript changed)
- [ ] `npm.cmd run build` (if frontend/build changed)
- [ ] `npm.cmd run test:e2e` (if serving or user flows changed)
- [ ] `git diff --check`

Commands/results or blockers:

## Data and security review

- [ ] No contact fields, credentials, raw private snapshots, or generated artifacts were added.
- [ ] Public/control-plane trust boundaries were preserved or documented.
- [ ] Accessibility and English/French behavior were reviewed for UI changes.

## Reviewer notes

<!-- Link an issue/plan, decision record, screenshots, API examples, and known limitations. -->

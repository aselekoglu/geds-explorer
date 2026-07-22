# Implementation Plan: Lighter Discover Canvas and Stable Drill-Down

## Overview

Replace Ripple Grid with a performance-budgeted Dot Field, remove the expensive global Magic Bento motion pass while preserving the premium bubble surface, move bubble facts into a click-only fixed panel, and make hierarchy navigation atomic so stale bubbles never flash between levels.

This is a plan only. No runtime behavior is changed by this document.

## Architecture decisions

1. **Dot Field is the only ambient animation.** The Magic Bento visual treatment remains on bubbles, but its global 480px spotlight scan, pointer-driven tilt, and magnetism are removed. A cheap CSS hover/focus emphasis remains.
2. **Use the requested Dot Field values exactly:** `bulgeStrength=58`, `dotSpacing=18`, `cursorRadius=600`, `waveAmplitude=1`, and `glowRadius=110`. Keep `sparkle=false` and `bulgeOnly=true`.
3. **Adapt rather than copy the reference implementation verbatim.** The reference redraws every dot on every animation frame. The product version will run at a capped 30 FPS, listen only inside the canvas, pause when hidden/offscreen, and render a static frame for reduced motion.
4. **Hierarchy changes are atomic.** A selected child is fetched before the visible `rootId`, slice, focus, and history are committed together. The previous level remains stable behind a small loading state while the request is pending.
5. **Bubble facts are selection state, not hover state.** A click/Enter/Space selects the bubble, opens a fixed top-right information panel, and starts drill-down when children exist. Empty-canvas click and Escape close the panel.
6. **No extra animation dependency.** Dot Field uses the existing browser Canvas API. After Ripple Grid is removed, remove `ogl` if no other import remains.

## Dependency graph

```text
Interaction/performance baseline
    |
    +-- Atomic constellation view state
    |       |
    |       +-- Stable click-selected facts panel
    |
    +-- Remove global Magic Bento motion
            |
            +-- Optimized Dot Field replacement
                    |
                    +-- Full regression and performance gate
```

## Task 1: Add a real interaction-performance baseline

**Description:** Extend the existing performance coverage to measure the current Discover pointer path and level transition before changing animation code.

**Acceptance criteria:**

- [ ] A repeatable test sweeps the pointer across the desktop canvas for five seconds and records long tasks and pointer-to-paint latency.
- [ ] A drill test detects any frame that renders nodes from the previous slice under the next `rootId`.
- [ ] Desktop and 390px mobile baselines are recorded in test output.

**Verification:**

- [ ] Run `npm.cmd run test:e2e -- tests/e2e/performance.spec.ts`.
- [ ] Confirm the baseline fails when a synthetic 60ms pointer handler or stale-slice frame is introduced.

**Dependencies:** None.

**Files likely touched:**

- `tests/e2e/performance.spec.ts`
- `tests/e2e/constellation.spec.ts`

**Estimated scope:** Small.

## Task 2: Make hierarchy navigation atomic

**Description:** Replace the separate `rootHistory`/`slice` update path with a loaded-view plus pending-view state. Fetch the target slice first, ignore stale responses with a request token/AbortController, then commit the new root, slice, focus, and history in one render. Cache loaded levels for immediate Back navigation.

**Acceptance criteria:**

- [ ] Clicking CRA, SSC, or any child never displays unrelated siblings between levels.
- [ ] The current map stays stable with a non-blocking `Opening {team}...` status until the next slice is ready.
- [ ] Rapid double-clicks and out-of-order responses cannot commit the wrong level.

**Verification:**

- [ ] Unit test with delayed and reversed promises.
- [ ] E2E drill through at least three levels and Back twice.
- [ ] The stale-frame detector from Task 1 reports zero stale frames.

**Dependencies:** Task 1.

**Files likely touched:**

- `src/features/constellation/ConstellationPage.tsx`
- `src/features/constellation/ConstellationPage.test.tsx`
- `tests/e2e/constellation.spec.ts`

**Estimated scope:** Medium.

## Task 3: Replace hover popup with a fixed selected-team panel

**Description:** Turn the moving `ConstellationHoverCard` into a fixed information panel anchored to the stage's top-right corner. Remove hover-driven inspection. Pointer click and keyboard activation set the selected node; empty space and Escape dismiss it.

**Acceptance criteria:**

- [ ] Merely hovering a bubble never opens or moves the information panel.
- [ ] Clicking or keyboard-activating a bubble opens one panel at a stable top-right position.
- [ ] Clicking blank canvas or pressing Escape closes it; clicking the panel or zoom controls does not.

**Verification:**

- [ ] Unit tests cover hover, click, keyboard, blank-canvas click, panel click, and Escape.
- [ ] Desktop visual check confirms the panel does not move during zoom/pan.
- [ ] At 390px the panel uses the responsive bottom overlay and does not create page overflow.

**Dependencies:** Task 2.

**Files likely touched:**

- `src/features/constellation/Constellation.tsx`
- `src/features/constellation/ConstellationPage.tsx`
- `src/features/constellation/ConstellationHoverCard.tsx` (rename to `ConstellationInfoPanel.tsx`)
- `src/styles/premium.css`
- constellation unit/E2E tests

**Estimated scope:** Medium.

## Checkpoint: Interaction correctness

- [ ] Tasks 1-3 tests pass.
- [ ] No stale bubble flash is observable at 0.25x video playback.
- [ ] Mouse, touch, and keyboard selection agree.
- [ ] Product review before visual-engine replacement.

## Task 4: Retire the heavy Magic Bento motion pass

**Description:** Preserve the layered mineral gradients, sheen, selected ring, and static depth treatment, but remove the stage-wide pointer loop that calls `getBoundingClientRect()` for every bubble and writes CSS variables to all nodes. Replace it with CSS hover/focus emphasis on the active bubble only.

**Acceptance criteria:**

- [ ] `updateSpotlight`, the 156-node geometry scan, per-node magnetism transforms, and Magic Bento data flags are removed.
- [ ] Bubble appearance remains premium in light and dark themes.
- [ ] Hover/focus changes only the active bubble and does not trigger layout reads.

**Verification:**

- [ ] Browser performance trace contains no per-pointer loop over all `.constellation-node` elements.
- [ ] Visual regression screenshots cover light, dark, selected, hovered, and quality-warning bubbles.

**Dependencies:** Task 1.

**Files likely touched:**

- `src/features/constellation/Constellation.tsx`
- `src/styles/magic-bubbles.css`
- `src/features/constellation/Constellation.test.tsx`

**Estimated scope:** Small.

## Task 5: Replace Ripple Grid with optimized Dot Field

**Description:** Add a typed Canvas-based Dot Field with the requested values and product theme colors. Render at most 30 FPS, pause outside the viewport or when the document is hidden, bind pointer events to the stage rather than `window`, and render only a static frame under reduced motion.

**Acceptance criteria:**

- [ ] Ripple Grid is absent and Dot Field reports `58 / 18 / 600 / 1 / 110` through stable test attributes.
- [ ] The canvas pauses when offscreen/hidden and resumes without jumping.
- [ ] `ogl` is removed from dependencies if `rg "from \"ogl\"" src` returns no matches.

**Verification:**

- [ ] Unit tests cover prop updates, cleanup, visibility pause, and reduced motion.
- [ ] `npm.cmd run build` succeeds and the production bundle no longer contains Ripple Grid/OGL.
- [ ] Desktop and mobile visual checks confirm the Dot Field stays behind bubbles and never intercepts input.

**Dependencies:** Task 4.

**Files likely touched:**

- `src/features/constellation/DotField.tsx`
- `src/features/constellation/ConstellationPage.tsx`
- `src/features/constellation/RippleGrid.tsx` (remove)
- `src/styles/premium.css`
- `package.json`
- `package-lock.json`

**Estimated scope:** Medium.

## Task 6: Enforce final performance and UX gates

**Description:** Run the complete suite and compare the new interaction trace against Task 1. Tune only within the agreed stop rules; do not reintroduce a second ambient animation.

**Acceptance criteria:**

- [ ] No main-thread task over 50ms during a five-second pointer sweep.
- [ ] Pointer-to-next-paint p95 is under 50ms and Dot Field draw p95 is under 8ms on the desktop test machine.
- [ ] Cached Discover remains useful under 2.5 seconds; unit, build, E2E, and axe checks all pass.

**Verification:**

- [ ] `npm.cmd test`
- [ ] `npm.cmd run build`
- [ ] `npm.cmd run test:e2e`
- [ ] Manual light/dark, desktop/390px, zoom/pan, click-dismiss, drill/Back review.

**Dependencies:** Tasks 2-5.

**Files likely touched:**

- `tests/e2e/performance.spec.ts`
- `tests/e2e/constellation.spec.ts`
- targeted unit tests

**Estimated scope:** Medium.

## Stop rules

- If Dot Field draw p95 exceeds 8ms, first freeze the wave while the pointer is outside the stage; do not reduce the user's five requested values silently.
- If long tasks remain after removing global Magic Bento motion, cap Dot Field to 24 FPS before changing visual density.
- If the fixed panel obscures selected bubbles on small screens, use the planned bottom overlay; do not reintroduce anchor-following positioning.
- If atomic prefetch fails, keep the current level and show a retry state; never commit an empty or mismatched slice.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Official Dot Field is CPU Canvas and redraws every dot continuously | High | 30 FPS cap, visibility/offscreen pause, stage-local events, reduced-motion static frame |
| Large `cursorRadius=600` affects most desktop dots | Medium | Batch one Canvas path and avoid per-dot DOM writes |
| Fetching before commit makes slow navigation feel unresponsive | Medium | Keep current map stable and show explicit pending status immediately |
| Click both opens facts and drills | Medium | Keep selected parent facts visible while its child slice loads/opens |
| Fixed panel covers mobile content | Medium | Responsive bottom overlay below the map toolbar |

## Open questions

None required before implementation. The recommended decision is explicit: Dot Field is the sole ambient animation; Magic Bento remains as a static bubble art direction plus cheap active-bubble hover/focus feedback.

# Implementation Plan: Uncapped Dot Field, Border Glow Refresh, and About Developer Lanyard

## Status and scope

Status: implemented and verified on July 22, 2026. The portrait remains intentionally pending; the live card uses the `AS` fallback until the supplied asset is added.

The work has four outcomes:

1. Remove the explicit Dot Field FPS cap without reintroducing an idle animation loop.
2. Remove Magic Bento behavior and branding from constellation bubbles.
3. align every Border Glow instance with the requested React Bits settings and the product palette.
4. Expand `About the data` into a general `About` page that preserves all methodology content and adds a suspended, clickable developer profile.

## Architecture decisions

### Dot Field

- Remove `frameInterval`, `last`, and the `data-active-frame-rate` contract.
- Keep the dirty-frame scheduler: pointer/resize/theme/visibility changes mark the canvas dirty and schedule one native `requestAnimationFrame`.
- Do not create a continuous animation loop. Native rAF/pointer coalescing determines the available refresh rate, so 60/120/144 Hz displays can render naturally while an idle canvas costs zero frames.
- Preserve hidden/offscreen pause, reduced-motion static rendering, DPR cap, and the requested `58 / 18 / 600 / 1 / 110` visual values.

### Bubble styling

- Remove the `magic-bubbles.css` import and file.
- Retain only a static premium radial surface, readable labels, selected ring, quality indicators, and a simple focus-visible state.
- Remove Magic Bento-style scale, magnetism, animated sheen, hover filter, and large drop-shadow transitions from bubbles.
- Keep single-click details, double-click drill, wheel/pan, and explicit zoom controls unchanged.

### Border Glow

- Add the official `animated` behavior to the local typed component, but implement it as one cancelable sweep per visible instance rather than uncancelled timers on every mounted card.
- New defaults: `edgeSensitivity=15`, `glowIntensity=1.9`, `coneSpread=27`, `glowRadius=56`, `animated=true`.
- Use three distinct semantic palette colors so the gradient is visible in both themes:
  - teal/mint: `--glow-gradient-teal`
  - arctic blue: `--glow-gradient-blue`
  - warm amber: `--glow-gradient-amber`
- Define theme-specific values in tokens/theme overrides rather than hard-coding separate palettes at call sites.
- Disable the automatic sweep for `prefers-reduced-motion`; pointer/focus glow remains available without animation.
- Trigger the mount sweep only when an instance first intersects the viewport. This avoids animating every offscreen Org Walk card simultaneously.

### About composition

- Rename the navigation and page heading from `About the data` to `About` / `À propos`.
- Preserve every existing data methodology section, snapshot fact, limitation, privacy statement, vacancy caveat, and official GEDS link.
- Add a general product/developer introduction above the data methodology.
- Desktop layout: content column on the left; a sticky developer rail hangs from the top-right. The Lanyard strap/canvas occupies the back layer and the real DOM Profile Card is a child of the Lanyard wrapper in the foreground.
- Profile Card settings: behind glow off and icon off. The provided portrait, exact name, and developer title remain real HTML/image content.
- The entire profile card is a semantic external link to the provided website, with keyboard focus, visible focus treatment, `target="_blank"`, and `rel="noreferrer"`.
- Lanyard uses the requested camera distance of `45` through the local adapter API.
- The 3D stack is lazy-loaded only when `#about` is active. It must not increase the initial Discover chunk.
- Pause physics/rendering when the About rail is offscreen or the document is hidden. Use a static profile composition for reduced motion, WebGL failure, and compact/mobile layouts.

### Why the Profile Card is not a texture

The React Bits Lanyard renders a GLTF card inside WebGL, while Profile Card is interactive DOM/CSS. Converting Profile Card into a texture would remove its live text, link semantics, focus behavior, and tilt. The product adaptation therefore nests the DOM Profile Card inside a `DeveloperLanyard` wrapper while the 3D strap hangs behind it. Visually it is one lanyard badge; technically it remains accessible and clickable.

## Dependency graph

```text
Performance baseline
    |
    +-- Uncapped dirty-frame Dot Field
    +-- Remove Magic Bento bubble motion
    +-- Border Glow typed animation contract
            |
            +-- Apply global theme palette/defaults

Developer content contract (photo/name/title/URL)
    |
    +-- Profile Card
    +-- Lazy Lanyard adapter and 3D dependencies
            |
            +-- About page composition
                    |
                    +-- Accessibility, responsive, and performance gates
```

## Task 1: Establish bundle and animation baselines

**Acceptance criteria:**

- Record the current initial Discover JS/CSS gzip sizes and About lazy-chunk state.
- Add a test that proves Dot Field does not schedule another frame after a dirty frame is painted.
- Record pointer-to-paint and canvas draw p95 for desktop.

**Verification:** `npm.cmd run build` and targeted performance E2E.

**Dependencies:** None. **Scope:** Small.

## Task 2: Remove the Dot Field FPS limiter

**Acceptance criteria:**

- No `frameInterval`, 30/60 FPS constant, timestamp throttle, or FPS data attribute remains.
- Multiple pointer events before the browser frame coalesce into one draw.
- Idle, hidden, offscreen, and reduced-motion behavior stays zero-loop/static.

**Verification:** DotField unit tests, pointer sweep E2E, production build.

**Dependencies:** Task 1. **Scope:** Small.

## Task 3: Remove Magic Bento from bubbles

**Acceptance criteria:**

- `magic-bubbles.css` and its import are removed.
- Bubbles do not scale, magnetize, tilt, or run hover filter animations.
- Static gradient surface, selected state, focus-visible state, labels, click details, and double-click drill remain correct.

**Verification:** Constellation unit/E2E, light/dark screenshots, keyboard and double-click flow.

**Dependencies:** Task 1. **Scope:** Small.

## Checkpoint A: Discover remains fast

- Unit tests and build pass.
- Constellation E2E passes.
- No idle rAF loop and no Magic Bento handlers remain.
- Discover bundle does not include the future 3D stack.

## Task 4: Upgrade the Border Glow contract

**Acceptance criteria:**

- Local component accepts and tests `animated` with cancelable cleanup.
- Requested defaults are `15 / 1.9 / 27 / 56 / true`.
- Three visibly distinct theme-aware gradient colors are used in a consistent order.
- Visible instances sweep once; offscreen and reduced-motion instances do not animate.

**Verification:** component unit tests, timer/rAF cleanup test, light/dark visual check.

**Dependencies:** Task 1. **Scope:** Medium.

## Task 5: Normalize all Border Glow consumers

**Acceptance criteria:**

- Discover stage, match cards, Org Walk columns/matches, and people panels use the common defaults unless a documented visual exception exists.
- Old per-call intensity/radius overrides that conflict with the requested values are removed.
- Simultaneously visible cards do not create long tasks over 50 ms.

**Verification:** `rg "<BorderGlow"`, Org Walk/Discover E2E, performance trace.

**Dependencies:** Task 4. **Scope:** Medium.

## Checkpoint B: Glow system

- All Border Glow consumers render in both themes.
- Animated sweep is cancelable and reduced-motion safe.
- Gradient colors are distinct rather than three shades of the same hue.

## Task 6: Add Profile Card as an accessible developer link

**Acceptance criteria:**

- Adapt the official Profile Card with behind glow disabled and icon hidden.
- Render the supplied photo, exact developer name/title, and website link.
- Whole card is keyboard/click accessible; broken image and missing optional fields degrade cleanly.

**Verification:** component unit test, external-link attributes, image alt test, desktop/mobile visual check.

**Dependencies:** Developer inputs. **Scope:** Medium.

## Task 7: Add a lazy, performance-contained Lanyard

**Acceptance criteria:**

- Install only the verified React Bits Lanyard dependencies: Three.js, React Three Fiber, Drei, Rapier, and Meshline (plus required types).
- `cameraDistance=45` is represented by the adapter and covered by a contract test.
- Canvas/physics loads only on About, pauses offscreen/hidden, and has reduced-motion/mobile/WebGL fallback.
- The DOM Profile Card is visually attached inside the Lanyard wrapper and remains a real link above the canvas.

**Verification:** chunk analysis, About-only network/module check, visibility pause test, fallback test.

**Dependencies:** Task 6. **Scope:** Medium.

## Task 8: Restructure the About page

**Acceptance criteria:**

- Navigation reads `About`; page has one general About heading.
- Existing methodology content is preserved under a dedicated `About the data` subsection.
- Desktop developer badge hangs from the upper-right without covering text; mobile uses the static card composition without horizontal overflow.
- Loading/error states still expose the general About content even if `/api/meta` fails.

**Verification:** About unit tests, English/French copy tests, axe, desktop/390px screenshots.

**Dependencies:** Tasks 6-7. **Scope:** Medium.

## Final checkpoint

- `npm.cmd test`
- `npm.cmd run build`
- `npm.cmd run test:e2e`
- Axe has no serious/critical issues.
- Initial Discover gzip size does not absorb the 3D dependencies.
- Dot Field draw p95 remains under 8 ms and idle frames remain zero.
- About desktop/mobile and light/dark visual review passes.

## Stop rules

- If removing the explicit FPS cap pushes Dot Field draw p95 over 8 ms, optimize dot drawing/DPR before adding any new limiter; do not silently restore a fixed cap.
- If animated Border Glow causes a long task, serialize visible one-shot sweeps or disable auto-sweep on repeated list cards while retaining pointer/focus glow.
- If the 3D About chunk leaks into the initial bundle, stop and fix the dynamic import boundary before visual polish.
- If WebGL/physics cannot stay below the agreed About frame budget, keep the static DOM Profile Card and make the Lanyard enhancement desktop-capability-only.
- Do not turn the Profile Card into a canvas texture; accessibility and click semantics are non-negotiable.

## Required user inputs before Tasks 6-8

1. Portrait image file.
2. Exact display name.
3. Exact title text (default can be `Developer`).
4. Full website/developer-page URL.
5. Optional handle/status/contact label and preferred portrait alt text.

## Source references

- React Bits Border Glow: requested settings plus local cancelable/reduced-motion adaptation.
- React Bits Profile Card: `behindGlowEnabled=false`, icon omitted, real DOM profile content.
- React Bits Lanyard: Three/Fiber/Drei/Rapier/Meshline implementation, adapted behind an About-only lazy boundary.

## Final implementation note

- Verification: 86/86 unit tests, production build, and 22/22 E2E tests pass.
- Initial JS is 108.79 kB gzip; the About-only Lanyard chunk is 237.83 kB gzip.
- Root visual QA rejected the Rapier prototype because the production CSP blocks its WebAssembly initialization. The final Lanyard uses a CSP-safe Three/MeshLine spring-pendulum model instead of weakening `script-src`, reducing the lazy chunk from 1,087.73 kB gzip.
- `Ata Selekoglu`, `Developer`, the tracked website URL, Profile Card options, and camera distance `45` are implemented. Only the portrait file remains pending.

## Stock Lanyard correction — July 22, 2026

The user rejected the custom spring-pendulum approximation. It has been removed from the rendered page and replaced with the official React Bits implementation and assets: Rapier rope/spherical joints, Drei environment lighting, MeshLine patterned band, draggable GLB card, and metal clip/clamp. The server CSP now grants only `wasm-unsafe-eval` plus the required `blob:` sources; general `unsafe-eval` remains disallowed. Profile Card is intentionally not rendered at this checkpoint. The supplied `ata-speaking-2.png` portrait is stored for the next phase.

Current verification: 86/86 frontend unit tests, 27/27 API/CSP tests, production build, and 22/22 full E2E tests. Initial JS remains 108.76 kB gzip; the About-only stock Lanyard chunk is 1,128.10 kB gzip and includes the real Three/Drei/Rapier implementation.

## Superseding plan: transparent falling Profile Card lanyard - July 23, 2026

Status: implemented on July 23, 2026 and awaiting Checkpoint A visual approval.

This section supersedes the earlier right-side developer rail and "DOM card in front of the canvas" composition. The accepted outcome is one physical Lanyard whose stock white logo card is replaced by the supplied React Bits Profile Card.

### Confirmed intent

- About remains a normal content page; it does not reserve a second column for the Lanyard.
- No visible Lanyard panel, border, shadow, tinted stage, or background is rendered.
- A transparent Lanyard overlay occupies only the upper-right hero area.
- The fixed rope origin sits above the visible viewport so the strap appears to descend directly from the browser's top edge.
- The official patterned band, metal clip/clamp, Rapier joints, gravity, swing, and pointer drag remain the primary motion system.
- The stock white GLB card surface is not rendered. The physical badge surface is the supplied React Bits Profile Card.
- The Profile Card uses `ata-speaking-2.png`, `Ata Selekoglu`, and `Developer`.
- Handle, online status, mini-avatar, contact strip, icon pattern, and behind-card glow are omitted.
- Profile Card tilt is disabled. A lightweight pointer/hover shine or glow may remain, but it must not rotate the card independently of Rapier.
- The full badge is a tracked external link to `https://aselekoglu.github.io/?utm_source=geds-career-atlas&utm_medium=profile-card&utm_campaign=about-developer`.
- A pointer movement above the drag threshold manipulates the physical badge; a press/release below the threshold activates the website link.
- On narrow screens the same composition remains visible at roughly 60-65% desktop scale in the upper-right, with protected space so it does not cover the About heading.

### Assumptions to validate in the first visual checkpoint

1. The Lanyard belongs to the About hero and scrolls away with that hero instead of following the reader through the entire methodology.
2. The transparent interaction region can be constrained to the upper-right area; it must not block text selection, links, or scrolling elsewhere on the page.
3. The existing photo crop remains full-body and bottom-aligned inside the Profile Card unless visual QA proves a tighter crop is needed.
4. Existing Lanyard lazy loading, camera distance `45`, CSP allowances, and dependency versions remain unchanged.

### Architecture decision: DOM Profile Card on the Rapier badge body

The Profile Card must remain real DOM so its text, image, external-link semantics, keyboard focus, and hover treatment stay accessible. It will be mounted with Drei's transformed HTML layer at the stock card rigid body's position and rotation.

- Keep the stock `RigidBody`, rope/spherical joints, metal clip/clamp meshes, and MeshLine strap.
- Stop rendering `nodes.card`; retain only the clip and clamp from `card.glb`.
- Resize the physical `CuboidCollider` to the rendered Profile Card aspect ratio.
- Attach a transformed HTML host to the badge rigid body so the DOM card follows the same translation and rotation each physics frame.
- Bridge DOM pointer coordinates into the existing camera-unprojection drag calculation.
- Track pointer travel and cancel link navigation after a real drag; preserve normal click and keyboard activation otherwise.
- Separate pointer glow from tilt in the Profile Card adapter. Pointer variables may drive shine/glare, but no CSS rotation may be applied.

This is intentionally not a texture conversion. A texture would lose live text, focus, link semantics, responsive typography, and the requested hover behavior.

### Dependency graph

```text
Confirmed content and interaction contract
    |
    +-- Task 1: Profile Card adapter and tests
    |
    +-- Task 2: DOM-to-Rapier proof
            |
            +-- Task 3: Replace the stock card surface
                    |
                    +-- Task 4: Transparent About hero composition
                            |
                            +-- Task 5: Responsive, fallback, and full QA
```

### Task 1: Adapt the supplied Profile Card without tilt

**Description:** Add the supplied React Bits Profile Card as a typed local component and separate pointer glow from tilt so the card can retain a restrained hover shine without introducing a second rotation system.

**Acceptance criteria:**

- [ ] The card renders `ata-speaking-2.png`, `Ata Selekoglu`, and `Developer`.
- [ ] There is no handle, status, mini-avatar, contact strip, icon pattern, or behind glow.
- [ ] Tilt and device-orientation handlers are absent; pointer glow does not create an independent transform.
- [ ] The whole card is an accessible tracked external link with visible keyboard focus.

**Verification:**

- [ ] Component tests cover content, omitted UI, tracked URL, keyboard semantics, and disabled tilt.
- [ ] Light/dark isolated screenshots show a readable portrait and restrained glow.

**Dependencies:** None.

**Files likely touched:**

- `src/features/about/profile-card/ProfileCard.tsx`
- `src/features/about/profile-card/ProfileCard.css`
- `src/features/about/profile-card/ProfileCard.test.tsx`
- `src/features/about/assets/ata-speaking-2.png`

**Estimated scope:** Medium.

### Task 2: Prove the DOM-to-Rapier interaction bridge

**Description:** Before visual polish, attach a minimal DOM badge host to the existing card rigid body and prove that it follows physics, drags from DOM pointer events, and distinguishes click from drag.

**Acceptance criteria:**

- [ ] The DOM host follows the card body's translation and rotation without a one-frame visual split from the clip.
- [ ] Dragging wakes the rope bodies and moves the badge through the existing camera-unprojection path.
- [ ] Movement above a small CSS-pixel threshold suppresses navigation; a stationary click remains available.
- [ ] Pointer capture is released on pointer-up, pointer-cancel, window blur, and unmount.

**Verification:**

- [ ] Focused interaction test covers press, drag, release, and subsequent click.
- [ ] Browser visual check confirms the clip and DOM badge remain attached through a wide swing.
- [ ] No stuck `grabbing` cursor or leaked listeners remain.

**Dependencies:** Task 1.

**Files likely touched:**

- `src/features/about/lanyard/Lanyard.tsx`
- `src/features/about/lanyard/Lanyard.css`
- `src/features/about/lanyard/Lanyard.test.tsx`
- `tests/e2e/about.spec.ts`

**Estimated scope:** Medium.

### Checkpoint A: physical badge contract

- [ ] Stock band, clip/clamp, gravity, and Rapier joints remain unchanged.
- [ ] White logo card surface is absent.
- [ ] DOM Profile Card follows the physical badge body.
- [ ] Drag and click are both reliable and do not trigger each other accidentally.
- [ ] Human visual review approves the attachment point and card scale before layout work continues.

### Task 3: Replace the stock card with the final Profile Card

**Description:** Mount the finished Profile Card on the validated rigid-body host, tune its scale/collider/attachment offset, and remove the old placeholder developer-card implementation from the rendered path.

**Acceptance criteria:**

- [ ] The supplied portrait is the card's main full-body image over the card gradient.
- [ ] Name/title remain legible during rest and moderate swing.
- [ ] Clip/clamp visually connect to the top centre of the Profile Card.
- [ ] Hover glow is visible but does not fight the physical rotation.
- [ ] The tracked website opens only on a genuine click or keyboard activation.

**Verification:**

- [ ] Desktop drag-and-click E2E passes in light and dark themes.
- [ ] Accessibility snapshot exposes one developer link with the expected name.
- [ ] Visual comparison covers rest, hover, drag, and release states.

**Dependencies:** Task 2.

**Files likely touched:**

- `src/features/about/lanyard/Lanyard.tsx`
- `src/features/about/profile-card/ProfileCard.tsx`
- `src/features/about/profile-card/ProfileCard.css`
- `tests/e2e/about.spec.ts`

**Estimated scope:** Medium.

### Task 4: Remove the developer rail and create the transparent About overlay

**Description:** Return About to a single content flow and position the transparent Lanyard above the upper-right hero area without a visible container.

**Acceptance criteria:**

- [ ] `.about-page__developer` no longer creates a grid column, stage, border, radius, shadow, or background.
- [ ] The rope origin is outside the visible top edge; no anchor point or rope start is visible.
- [ ] The initial About viewport shows the Profile Card in the upper-right without covering the heading or introduction.
- [ ] The transparent overlay does not block interactions outside the badge's intended hit area.
- [ ] About the Data retains its full existing copy and width.

**Verification:**

- [ ] Desktop screenshots at 1920x1080 and 1440x900 in both themes.
- [ ] Text selection, About link activation, page scrolling, and Lanyard dragging all work in one browser pass.
- [ ] DOM/layout assertions prove there is no reserved right rail or horizontal overflow.

**Dependencies:** Task 3.

**Files likely touched:**

- `src/routes/about.tsx`
- `src/styles/methodology.css`
- `src/features/about/lanyard/Lanyard.css`
- `tests/e2e/about.spec.ts`

**Estimated scope:** Medium.

### Task 5: Responsive, fallback, performance, and release verification

**Description:** Tune mobile scale and fallbacks, then run the complete regression and performance gates.

**Acceptance criteria:**

- [ ] At 390px the Lanyard remains upper-right at roughly 60-65% scale, its anchor remains hidden, and the About heading is unobscured.
- [ ] Reduced motion or WebGL/WASM failure shows a static Profile Card in the same visual area without a blank stage.
- [ ] About-only lazy loading remains intact; Discover does not absorb the 3D/Profile Card code.
- [ ] The removed tilt system adds no second continuous animation loop.
- [ ] Desktop About physics remains responsive during hover and drag.

**Verification:**

- [ ] `npm.cmd test`
- [ ] `npm.cmd run build`
- [ ] `npm.cmd run test:e2e`
- [ ] `py -m pytest tests/test_career_api.py -q`
- [ ] Bundle comparison against the current 108.76 kB gzip initial JS baseline.
- [ ] Browser checks: page identity, no blank/overlay, no relevant console errors, desktop/mobile screenshots, drag, click, keyboard, scroll, and responsive overflow.

**Dependencies:** Tasks 1-4.

**Files likely touched:**

- `src/routes/about.tsx`
- `src/styles/methodology.css`
- `src/features/about/lanyard/*`
- `src/features/about/profile-card/*`
- `tests/e2e/about.spec.ts`

**Estimated scope:** Medium.

### Stop rules

- If transformed HTML cannot remain visually attached to the Rapier body and clip during drag, stop before layout polish and present the measured failure; do not fake the result with a separate floating card.
- If the DOM card blocks the About content outside its visible bounds, shrink the interaction region before continuing.
- If click-versus-drag remains ambiguous after a threshold and pointer-capture pass, prioritize drag and expose the website as an explicit keyboard-accessible card link rather than allowing accidental navigation.
- If the photo becomes unreadable at mobile scale, adjust crop and typography before increasing the overlay footprint.
- Do not restore the purple stage, separate developer rail, Profile Card tilt, contact strip, or stock white logo card.

### Plan approval gate

Implementation starts only after the user reviews this superseding plan. Checkpoint A requires another visual approval before the About layout is finalized.

### Implementation verification - July 23, 2026

- The stock white `nodes.card` mesh is no longer rendered; the GLB metal clip/clamp, Rapier joints, gravity, MeshLine band, and camera distance `45` remain.
- The real DOM Profile Card follows the badge rigid body through Drei transformed HTML and bridges DOM pointer coordinates into the camera-unprojection drag path.
- Drag navigation suppression, subsequent click activation, keyboard activation, blur/cancel cleanup, mobile scale, reduced-motion fallback, and WebGL fallback are covered.
- Verification passed: 92/92 frontend unit tests, 24/24 application E2E tests (including axe), 27/27 API/CSP tests, and the production build.
- Independent review tightened the non-physics fallback: static Profile Cards now use a link cursor and preserve vertical touch scrolling instead of advertising drag behavior.
- Initial JS is 108.87 kB gzip versus the 108.76 kB baseline. Profile Card remains a separate 1.31 kB gzip About-only chunk; the physical Lanyard chunk is 1,130.80 kB gzip.
- Playwright visual QA covered 1440x900 light/dark and 390x844 mobile. Final human approval of card scale, crop, and clip alignment remains the only open Checkpoint A item.

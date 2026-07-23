# About and Animation Overhaul Checklist

## Current checkpoint: stock Lanyard first

- [x] Replace the custom approximation with the official React Bits Lanyard implementation.
- [x] Use the official `card.glb` and `lanyard.png` assets.
- [x] Preserve the real Rapier rope joints, draggable card, metal clip/clamp, MeshLine band, and Drei lighting.
- [x] Keep camera distance `45` and About-only lazy loading.
- [x] Add the narrow `wasm-unsafe-eval`/`blob:` CSP requirements without enabling general `unsafe-eval`.
- [x] Keep About mounted behind an error boundary when WebGL/WASM is unavailable.
- [x] Remove Profile Card from the rendered About page until the stock Lanyard is accepted.
- [x] Save `ata-speaking-2.png` as the supplied portrait for the next phase; do not render it yet.
- [x] Verify the stock textured face, patterned band, clip/clamp, hover cursor, drag, release, and physics response.
- [x] Pass 86/86 frontend unit tests, 27/27 API/CSP tests, production build, and 22/22 E2E tests.

## Next phase — only after stock Lanyard approval

- [x] Integrate the supplied portrait into the exact React Bits Profile Card.
- [x] Combine Profile Card with Lanyard without replacing the stock physics/asset behavior.
- [x] Revalidate accessibility, drag interaction, responsive layout, CSP, and bundle boundaries.

## Approved intent - transparent physical Profile Card lanyard

### Phase 1: Profile Card contract

- [x] Add the supplied React Bits Profile Card as a typed local component.
- [x] Use `ata-speaking-2.png`, `Ata Selekoglu`, and `Developer`.
- [x] Make the full card link to the tracked `aselekoglu.github.io` URL.
- [x] Remove handle, status, mini-avatar, contact strip, icon, and behind glow.
- [x] Separate hover shine/glow from tilt; disable tilt and device orientation.
- [x] Add Profile Card content, omission, link, keyboard, and motion tests.

### Phase 2: Physical integration

- [x] Attach a transformed DOM badge host to the existing Rapier card rigid body.
- [x] Preserve the stock band, rope/spherical joints, clip/clamp, gravity, and drag response.
- [x] Stop rendering the stock white logo card mesh.
- [x] Resize the collider and align the clip with the Profile Card top centre.
- [x] Bridge DOM pointer coordinates into the physics drag calculation.
- [x] Add a drag threshold so dragging never opens the website accidentally.
- [x] Clean up pointer capture/cursor/listeners on release, cancel, blur, and unmount.

### Checkpoint A: approve the physical badge

- [x] Verify the Profile Card stays attached through rest, hover, drag, swing, and release.
- [x] Verify click and keyboard open the tracked website while a real drag does not.
- [ ] Obtain visual approval for card scale, crop, and clip alignment.

### Phase 3: About composition

- [x] Remove the reserved right column and purple developer stage.
- [x] Render a transparent Lanyard overlay in the About hero's upper-right.
- [x] Place the rope origin above the visible viewport so the strap enters from the browser edge.
- [x] Keep the overlay hit area from blocking About text, links, selection, or scrolling.
- [x] Preserve all About the Data content and full content width.
- [x] Scale the same composition to roughly 60-65% on narrow screens.
- [x] Protect the mobile About heading from overlap.

### Phase 4: Fallback and verification

- [x] Provide a static Profile Card fallback for reduced motion and WebGL/WASM failure.
- [x] Confirm About-only lazy loading and the current initial bundle boundary.
- [x] Run all frontend unit tests and the production build.
- [x] Run full About and application E2E tests.
- [x] Run crawler API/CSP tests.
- [x] Capture light/dark desktop and 390px mobile screenshots.
- [x] Confirm no relevant console errors, horizontal overflow, stuck cursor, or accidental navigation.

# Constellation hierarchy layout evaluation

Date: 2026-07-11  
Snapshot: `edd5d0f4269da97163b33a5cf7dd8c850ad51331a913721e0ce7a07e1977fce5`  
Dataset scale: 156 root institutions, 26,421 organization units, 193,163 current people records.

## Decision

Circle packing remains the primary Constellation layout. It is the only candidate that simultaneously communicates relative branch scale, feels spatial and exploratory, preserves a stable “government universe” overview, and provides sufficiently large pointer targets for the most important institutions. A synchronized semantic list is the authoritative accessible alternative and becomes list-first below 760 CSS pixels.

## Candidate comparison

| Criterion | Circle pack | Partition / icicle | Treemap |
| --- | --- | --- | --- |
| Hierarchy readability | Strong overview and branch drill-down; containment is intuitive after selection | Strongest ancestor/depth reading, but long labels and 5+ levels become narrow strips | Strong containment, weaker depth reading when many similarly sized siblings compete |
| Label density | Direct labels reserved for large/selected circles; inspector carries full names | High at shallow depth, rapidly degrades as bands narrow | Highest rectangular label capacity, but dense roots become visually noisy |
| Hit targets | Large institutions naturally receive large targets; small nodes use synchronized list | Deep nodes can become too thin for 44px targets | Better than partition, but small leaf rectangles still fall below target |
| Focus continuity | Stable ID ordering plus branch repacking gives a coherent “zoom into a system” transition | Excellent linear ancestor continuity, less constellation-like | Moderate; large positional changes are common when the selected metric changes |
| Showcase / wow factor | Highest; visually distinctive and aligned with the approved constellation concept | Analytical, but reads like a conventional hierarchy chart | Efficient, but familiar dashboard language rather than a virtual government experience |
| Accessibility strategy | Semantic list mirrors selected state and actions | Still requires a semantic tree/list | Still requires a semantic tree/list |

## Determinism and visual semantics

- Nodes sort by descending selected value and then stable organization ID.
- `d3.hierarchy` + `pack.size` + fixed padding is used; no random or force simulation is present.
- Circle area represents people indexed in overview mode and match strength in interest mode.
- Partial/fallback quality uses an amber labelled outline.
- Recorded vacancy uses a dotted amber outline and the exact “Recorded as vacant in GEDS — unverified” label; it never uses success green.
- `has_more` is exposed for bounded aggregate branches, so truncation is explicit.

## Measured budgets

Five local Chrome/Node release-gate samples, milliseconds:

- 156-root circle pack: `8.7121, 0.8986, 0.5646, 0.5427, 0.4566`; median `0.5646`, target `<50`.
- 2,000-node circle pack: `13.5374, 11.3644, 7.5950, 7.4249, 7.4643`; median `7.5950`, target `<150`.

Both budgets have substantial margin. Partition or treemap is therefore not justified by performance. Circle pack remains primary; Organization Walk provides the precise top-down analytical complement.

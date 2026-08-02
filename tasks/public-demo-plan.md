# Implementation Plan: GEDS public read-only demo

## Overview

Prepare the existing Career Atlas for a public, read-only deployment without exposing the crawler/control plane. A full crawl is running independently. The first implementation slice defines a versioned public projection, keeps the current read API bounded, and makes the public metadata/quality state explicit so a hosted database can be attached after the crawl is validated.

## Decisions confirmed for this slice

- Person display names are approved for the public directory surface.
- Start the full crawl now; implementation must not wait for its completion.
- The crawler, control database, raw SQLite files, and import credentials remain private.
- Public data is read-only and must expose snapshot/as-of/quality semantics.

## Task list

### Phase 1: Public contract

- [x] Add a projection manifest/schema describing the public snapshot, including metadata, departments, organization hierarchy/profile, bounded search, and people rows.
- [x] Add contract tests for GET-only routes, limits, stable snapshot metadata, and the explicitly approved display-name fields.
- [x] Update the public-surface documentation so it no longer claims that names are excluded, while retaining the no-contact-fields guarantee.

### Phase 2: Projection and local adapter

- [x] Add a deterministic export command that reads only the validated canonical snapshot and writes an allow-listed projection artifact.
- [x] Add privacy/count/hash validation before an artifact can be marked publishable.
- [x] Keep the existing SQLite adapter working for local review and make the API response metadata consistent with the projection manifest.

### Phase 3: Hosted deployment seam

- [x] Add a provider-neutral read-store interface so the same API can read the local projection now and hosted Postgres later.
- [ ] Add Vercel deployment configuration for the static Vite UI plus same-origin read-only API, without packaging the master SQLite database.
- [x] Document the manual canary: export -> validate -> staging import -> smoke test -> active snapshot pointer.

## Checkpoints

- After Phase 1: crawler tests and API contract tests pass; no control route is mounted.
- After Phase 2: a projection can be generated from a completed canonical snapshot and rejected when quality/privacy checks fail.
- Before deployment: choose hosted Postgres provider, import one validated snapshot, run browser/API smoke tests, and review the public payload.

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Full crawl is incomplete or partial | High | Keep it out of public import until quality is reviewed; show as-of and quality status. |
| Person names are public | High | User explicitly approved names; continue excluding contact fields and private crawler metadata. |
| Large SQLite is unsuitable for Vercel | High | Export a small versioned projection; never bundle the master database. |
| Hosted DB choice is not finalized | Medium | Keep the adapter provider-neutral; provision Neon/Supabase only after explicit selection. |

## Open questions before live deployment

- Neon or Supabase for the hosted public projection?
- Is a `partial_overlay` snapshot acceptable for a labelled preview, or must the first public link wait for `complete`?
- What manual refresh cadence should be promised, if any?

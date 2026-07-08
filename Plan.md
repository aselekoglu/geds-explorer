# GEDS Crawl + Explorer Planning

**Goal:** GEDS datasini once guvenli ve kontrollu sekilde crawl edip analiz edilebilir snapshot'a cevirmek; ardindan bu snapshot ustune daha iyi search/filter/tree explorer urunu kurmak.

**Architecture:** Crawl ve urun ayri tutulacak. Crawler resmi GEDS sayfalarini rate-limit ile gezecek, contact alanlarini saklamayacak, kisi kayitlarinda sadece isim/title/org path/source link tutacak. Urun tarafi crawler ciktisini okuyacak ve sonradan API/UI kararlari degisse bile data snapshot yeniden kullanilabilecek.

**Tech Stack:** Python crawler, SQLite/JSONL snapshot, pytest, later FastAPI + Postgres + React/TanStack Table + tree visualization.

## Estimate

- **LLM token maliyeti:** Crawl'in kendisi token harcamaz; script lokal calisir. Codex sadece implementasyon, log okuma ve ozetleme icin token harcar.
- **Crawler implementation + ilk run izleme:** yaklasik `30k-70k` Codex token.
- **10 kurum IT-first crawl:** tahmini `1k-8k` GEDS page request, `20-200 MB` raw/parsed data, `20-120 dk` runtime.
- **Tum 156 kurum:** crawler olgunlastiktan sonra tahmini `20k-100k+` request, `8 saat-3 gun` arasi; kisi detay sayfalari fetch edilirse daha uzun.
- **Onemli default:** Telefon/email saklanmayacak; kisi icin resmi GEDS source URL verilecek.

## Plan A: Crawl Snapshot

### Summary

Ilk run sadece 10 teknoloji-heavy kurumla baslayacak: SSC, TBS, ISED, ESDC, CRA, PSPC, StatCan, NRC, NRCan, DND. Ama crawler generic olacak; ayni kod sonra 156 kurumun tamamina calisacak.

### Key Changes

- Create crawler project under `work/geds-crawler/`.
- Create read-only fetcher for:
  - department seed list: `https://geds-sage.gc.ca/en/GEDS?pgid=012`
  - organization pages: `pgid=014&dn=...`
  - person source links: `pgid=015&dn=...`, stored as link only, not crawled for contact details in v1.
- Parse and store:
  - departments: name, dn, source_url
  - org units: name, dn, parent_dn, department_dn, depth, org_path, source_url
  - people index: display_name, title, org_dn, department_dn, source_url
  - roles/titles where visible, without phone/email fields
  - crawl metadata: first_seen, last_seen, crawl_run_id
- Output:
  - `outputs/geds-snapshot-YYYY-MM-DD/geds.sqlite`
  - `outputs/geds-snapshot-YYYY-MM-DD/org_units.jsonl`
  - `outputs/geds-snapshot-YYYY-MM-DD/people_index.jsonl`
  - `outputs/geds-snapshot-YYYY-MM-DD/crawl_report.md`

### Crawler Behavior

- Start with seed allowlist of 10 departments.
- BFS crawl org tree via `pgid=014` links.
- Deduplicate by decoded/canonical `dn`.
- Rate limit: default `1 request/sec`.
- Retry: max 3 attempts, exponential backoff `2s, 5s, 15s`.
- Save progress every page so interrupted crawl can resume.
- Do not store phone/email values even if visible in summary HTML.
- Preserve source URLs so user can click official GEDS page for contact details.
- Produce crawl report with:
  - departments crawled
  - org unit count
  - people count
  - skipped/error URLs
  - top title keywords
  - top org path keywords
  - runtime and request count

### Test Plan

- Unit test parser against saved HTML fixtures for:
  - department list count extraction
  - org child link extraction
  - people summary extraction with contact fields stripped
  - DN deduplication
- Integration dry-run:
  - crawl only SSC root + depth 1
  - confirm SQLite tables are populated
  - confirm no phone/email columns exist
  - confirm person rows have `source_url`
- Acceptance criteria:
  - 10 selected departments crawl without crashing
  - output snapshot opens locally
  - report lists counts and errors
  - no contact fields are persisted

## Plan B: GEDS Explorer Product

### Summary

Urun, crawler snapshot ustune kurulacak. Ilk hedef "GoC icinde IT/software/data/AI/cyber ekipleri ve title'lari hizli bulmak" olacak; contact discovery degil, org/person/title discovery olacak.

### Key Changes

- API layer:
  - `/api/search?q=developer`
  - `/api/departments`
  - `/api/orgs?keyword=IT`
  - `/api/orgs/:dn/tree`
  - `/api/people?title=developer&department=SSC`
  - `/api/facets/titles`
- UI:
  - left tree navigation by department/org
  - top global search
  - filters for department, org keyword, title keyword
  - result table with name, title, department, org path, source link
  - tree highlights branches matching search/filter
- Ranking:
  - exact title match first
  - org path keyword match second
  - fuzzy title/org match third
- Privacy/product default:
  - no phone/email shown
  - every person has "Open official GEDS page"
  - no bulk contact export

### Test Plan

- API tests:
  - search returns deterministic ranked results
  - filters combine correctly
  - source URL is present for each person
  - contact fields are absent from API response
- UI tests:
  - user can search `developer`
  - user can filter to one department
  - tree expands to matched org branch
  - source link opens official GEDS URL
- Product acceptance:
  - "Find all developer/software/data/AI-related titles in SSC/TBS/ISED" can be answered in under 30 seconds from the UI.
  - "Which branches contain AI/data/software teams?" can be answered without manually opening every GEDS department page.

## Assumptions

- Initial crawl scope is **10 IT-first institutions**.
- Contact fields are **not stored**; official GEDS source link is stored instead.
- First product version is local/private analysis, not public commercial redistribution.
- GEDS pages are treated as source of truth; snapshot always records crawl date and source URL.

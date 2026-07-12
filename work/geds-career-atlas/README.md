# GEDS Career Atlas

Career Atlas turns a canonical GEDS snapshot into an explainable, bilingual way to discover Government of Canada teams, observed role families, career-conversation leads, and the required Government Constellation showcase.

## Local setup

Prerequisites: Node.js/npm, Python 3.11+, Chrome, and a published/indexed canonical master database.

```powershell
cd work\geds-career-atlas
npm.cmd install
npm.cmd run dev
```

Vite serves frontend development only. API requests expect a Career Atlas backend at `/api`; for an integrated production-style review, build and serve from the crawler package:

```powershell
cd work\geds-career-atlas
npm.cmd run build

cd ..\geds-crawler
$env:PYTHONPATH="src"
py -m geds_crawler.career_cli serve `
  --master-db ..\..\outputs\master\geds-master.sqlite `
  --frontend-dir ..\geds-career-atlas\dist `
  --host 127.0.0.1 `
  --port 8780
```

Open `http://127.0.0.1:8780/`.

## Verification

```powershell
cd work\geds-career-atlas
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:e2e
```

The Playwright setup uses `GEDS_MASTER_DB` when provided; otherwise it resolves the repository's `outputs\master\geds-master.sqlite`. It starts Python without a shell and shuts down the direct child process, which works in Windows environments where `taskkill` is restricted. If port 8780 is already healthy, it reuses that server and does not stop it.

## Product trust model

- Search expands controlled English/French taxonomy terms and shows the interpretation, confidence, and source-field evidence behind each result.
- Organization names and titles remain source strings; product-owned navigation and explanations switch between English and French.
- Partial/stale quality, bounded/aggregated branches, and source failures remain visible rather than being silently hidden.
- Career-conversation leads are title-based suggestions for research. They never claim that a person is a hiring manager or currently hiring.
- `Recorded as vacant in GEDS — unverified` means only that the directory snapshot contained a vacancy marker. There is no GC Jobs integration and no application action.
- Saved maps stay in browser local storage. They exclude people, contact fields, and source URLs; notes never enter URLs or API requests.
- Public API routes are GET-only and separate from the unauthenticated crawler control plane.

## Generated artifacts

- `dist\`: production frontend bundle; generated, not committed.
- `test-results\` and Playwright traces/screenshots: generated diagnostics; not committed.
- `outputs\master\geds-master.sqlite`: canonical runtime database; generated outside this package and never committed.

Durable design, implementation plan, progress, layout evaluation, and acceptance evidence live under `docs\superpowers\`.

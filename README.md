# GEDS Explorer

GEDS Explorer is a research and engineering workspace for turning official Government of Canada Electronic Directory Services (GEDS) pages into privacy-conscious, explainable snapshots and a read-only Career Atlas. The crawler preserves source links and organization/title context while intentionally excluding phone, email, fax, and address fields from stored person records.

This repository is currently a source repository for local development and controlled publication. It is not an official Government of Canada service, and a GEDS vacancy marker is not a verified job opening.

## Repository layout

- `work/geds-crawler/` — Python 3.11+ crawler, snapshot store, control-plane tooling, public projection, and Career Atlas API.
- `work/geds-career-atlas/` — Vite + React + TypeScript read-only frontend.
- `analysis/` — reproducible analysis scripts, notebooks, and source notes.
- `docs/` — handoffs, plans, specifications, audit evidence, and contribution guidance.
- `outputs/` — local/generated snapshots; ignored by Git and never commit-ready.

The crawler/control plane and public Career Atlas are separate trust boundaries. Do not expose the control plane to an untrusted network; read [`work/geds-crawler/SECURITY.md`](work/geds-crawler/SECURITY.md) before running it.

## Prerequisites

- Windows PowerShell examples below assume Node.js/npm and Python 3.11+ are installed.
- A local canonical snapshot is required for integrated Career Atlas serving. Generated databases are not included in this repository.

## Quick start

Install and test the crawler:

```powershell
cd work\geds-crawler
py -m pip install -e ".[dev]"
py -m pytest
```

Install and run the frontend in Vite development mode:

```powershell
cd work\geds-career-atlas
npm.cmd install
npm.cmd run dev
```

Vite serves the frontend only. To run the integrated read-only API and built frontend, build the app and use the crawler's Career Atlas server:

```powershell
cd work\geds-career-atlas
npm.cmd run build

cd ..\geds-crawler
py -m geds_crawler.career_cli serve `
  --master-db ..\..\outputs\master\geds-master.sqlite `
  --frontend-dir ..\geds-career-atlas\dist `
  --host 127.0.0.1 `
  --port 8780
```

Open `http://127.0.0.1:8780/`. Use `--host 0.0.0.0` only for a trusted-LAN review and never for an untrusted network.

## Verification commands

Run the focused checks for each package before opening a pull request:

```powershell
cd work\geds-crawler
py -m pytest

cd ..\geds-career-atlas
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:e2e
```

The E2E suite may require a canonical database. Set `GEDS_MASTER_DB` to an approved local snapshot when the default `outputs\master\geds-master.sqlite` is unavailable.

## Data and safety boundaries

- Source data comes from official GEDS pages; snapshots record crawl context and source URLs.
- Stored person records omit contact fields. Do not add bulk contact collection or export without an explicit, separately reviewed decision.
- Public API payloads are read-only and must not include crawler/control-plane metadata.
- Generated databases, `dist/`, test reports, and traces stay untracked.
- The control plane is an operator surface, not a public service. Follow the security policy before changing bind or authentication behavior.

## Contributing

Read [`CONTRIBUTING.md`](CONTRIBUTING.md), then use [`docs/contribution-checklist.md`](docs/contribution-checklist.md) before submitting a change. The checklist covers scope, privacy, tests, documentation, and review evidence.

## License

Project code and original project assets are licensed under [Apache-2.0](LICENSE). Government of Canada source content, trademarks, and third-party dependencies may have separate terms; see [`docs/LICENSING.md`](docs/LICENSING.md). This repository does not claim Government of Canada compliance, certification, or endorsement. Read [`docs/government-of-canada-open-source-readiness.md`](docs/government-of-canada-open-source-readiness.md) for evidence and remaining verification work.

## Reporting

For security issues, follow [`SECURITY.md`](SECURITY.md). For bugs and proposed changes, open an issue in [aselekoglu/geds-explorer](https://github.com/aselekoglu/geds-explorer) with reproducible steps, affected package, and verification results.

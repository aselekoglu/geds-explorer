# GEDS Public Career Atlas and Private Admin Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Ship independently bounded public and private GEDS experiences with coordinated light/dark themes, a leaf-team people browser, official GEDS links, and conservative observed-classification badges.

**Architecture:** Extend the read-only Career API with a paginated direct-team people endpoint and a pure classification parser. Add focused React theme and people-list components to Career Atlas. Keep crawler control routes inside the existing private Admin Console, adding only theme state and a persistent private-admin identity; no admin route or mutation is introduced into Career Atlas.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, pytest, React 19, TypeScript 6, Vite 8, Vitest, Testing Library, CSS custom properties.

## Global Constraints

- Public Career Atlas remains GET-only and never calls `/api/control/*`.
- Public person payloads contain no email, phone, fax, address, raw database path, or crawler state.
- Classification is displayed only from an explicit structured value or an allow-listed token in observed title text; never infer it from job meaning.
- Initial observed-classification allow-list: `EC`, `CO`, `IT`, and legacy `CS`.
- Valid person links must use `https://geds-sage.gc.ca/`.
- Both applications support `Light`, `Dark`, and `System`; Career Atlas defaults to light, Admin defaults to system.
- Public and Admin navigation remain disjoint.

---

### Task 1: Public people read model and classification parser

**Files:**
- Create: `work/geds-crawler/src/geds_crawler/career_people.py`
- Modify: `work/geds-crawler/src/geds_crawler/career_repository.py`
- Modify: `work/geds-crawler/src/geds_crawler/career_api.py`
- Test: `work/geds-crawler/tests/test_career_people.py`
- Test: `work/geds-crawler/tests/test_career_repository.py`
- Test: `work/geds-crawler/tests/test_career_api.py`

**Interfaces:**
- Produces: `extract_observed_classifications(title: str | None) -> tuple[str, ...]`.
- Produces: `PublicPerson`, `PeoplePage`, and `CareerRepository.people(org_id, query, classification, sort, limit, offset)`.
- Produces: `GET /api/orgs/{org_id}/people` with bounded query, classification, sort, limit, and offset parameters.

- [x] **Step 1: Write failing parser tests**

```python
def test_explicit_classifications_are_normalized_without_semantic_guessing():
    assert extract_observed_classifications("Economist - EC-04") == ("EC-04",)
    assert extract_observed_classifications("IT02 / CS2") == ("IT-02", "CS-02")
    assert extract_observed_classifications("Software Developer") == ()
```

- [x] **Step 2: Run parser tests and verify RED**

Run: `py -m pytest work/geds-crawler/tests/test_career_people.py -q`
Expected: FAIL because `career_people` does not exist.

- [x] **Step 3: Implement the pure parser and immutable public models**

```python
ALLOWED_GROUPS = frozenset({"EC", "CO", "IT", "CS"})
CLASSIFICATION_RE = re.compile(r"(?<![A-Z0-9])(EC|CO|IT|CS)[- ]?(\d{1,2})(?!\d)", re.I)

def extract_observed_classifications(title: str | None) -> tuple[str, ...]:
    values = []
    for group, level in CLASSIFICATION_RE.findall(title or ""):
        normalized = f"{group.upper()}-{int(level):02d}"
        if normalized not in values:
            values.append(normalized)
    return tuple(values)
```

- [x] **Step 4: Run parser tests and verify GREEN**

Run: `py -m pytest work/geds-crawler/tests/test_career_people.py -q`
Expected: PASS.

- [x] **Step 5: Write failing repository and API contract tests**

```python
page = repository.people(org_id=org_id, query="ada", classification="IT-02", sort="name", limit=20, offset=0)
assert page.items[0].display_name == "Ada"
assert page.items[0].observed_classifications == ("IT-02",)
assert page.items[0].source_url.startswith("https://geds-sage.gc.ca/")
assert not {"email", "phone", "address"} & dataclasses.asdict(page.items[0]).keys()
```

- [x] **Step 6: Run focused repository/API tests and verify RED**

Run: `py -m pytest work/geds-crawler/tests/test_career_repository.py work/geds-crawler/tests/test_career_api.py -q`
Expected: FAIL because `people()` and the route do not exist.

- [x] **Step 7: Implement direct-team query, official-host validation, paging, filtering, and route**

The SQL must bind `snapshot_id` and `org_dn` for the selected organization, use `people_current.org_dn` for direct membership, and never join descendants. Perform classification filtering on parsed results before final pagination when SQLite has no structured classification column. Return `404` for an unknown organization, `422` for unsupported sort or classification values, and a non-clickable empty `source_url` when the stored URL is not an official GEDS HTTPS URL.

- [x] **Step 8: Run backend tests and verify GREEN**

Run: `py -m pytest work/geds-crawler/tests/test_career_people.py work/geds-crawler/tests/test_career_repository.py work/geds-crawler/tests/test_career_api.py -q`
Expected: PASS.

### Task 2: Career Atlas people browser

**Files:**
- Modify: `work/geds-career-atlas/src/api/types.ts`
- Modify: `work/geds-career-atlas/src/api/client.ts`
- Create: `work/geds-career-atlas/src/features/people/PeopleInTeam.tsx`
- Create: `work/geds-career-atlas/src/features/people/PeopleInTeam.test.tsx`
- Create: `work/geds-career-atlas/src/styles/people.css`
- Modify: `work/geds-career-atlas/src/features/profile/TeamProfileLoader.tsx`
- Modify: `work/geds-career-atlas/src/features/profile/TeamProfile.tsx`
- Modify: `work/geds-career-atlas/src/main.tsx`
- Modify: `work/geds-career-atlas/src/i18n/en.ts`
- Modify: `work/geds-career-atlas/src/i18n/fr.ts`
- Test: `work/geds-career-atlas/src/api/client.test.ts`
- Test: `work/geds-career-atlas/src/features/profile/TeamProfileLoader.test.tsx`

**Interfaces:**
- Consumes: `GET /api/orgs/{org_id}/people`.
- Produces: `PublicPerson`, `PeoplePage`, `CareerApiClient.people(...)`, and `<PeopleInTeam>`.

- [x] **Step 1: Write failing client and component tests**

```tsx
render(<PeopleInTeam orgId="ai" client={client} />)
expect(await screen.findByText("Ada Lovelace")).toBeVisible()
expect(screen.getByText("IT-02")).toHaveAccessibleName("Classification observed in title: IT-02")
expect(screen.getByRole("link", {name: /View in official GEDS/i})).toHaveAttribute("href", officialUrl)
expect(screen.queryByText(/email|phone/i)).not.toBeInTheDocument()
```

- [x] **Step 2: Run frontend focused tests and verify RED**

Run: `npm.cmd test -- src/api/client.test.ts src/features/people/PeopleInTeam.test.tsx`
Working directory: `work/geds-career-atlas`
Expected: FAIL because the people client/component is missing.

- [x] **Step 3: Implement types, client method, and accessible responsive people list**

The component owns search, classification filter, sort, loading, empty, and retry states. It resets visible results when `orgId` changes, aborts the stale request, exposes a table on wide screens and labelled stacked rows via CSS on narrow screens, and only renders the official link when `source_url` is non-empty.

- [x] **Step 4: Integrate only for leaf teams**

`TeamProfileLoader` requests people only when `profile.child_count === 0`. `TeamProfile` renders the people section after snapshot/quality/source facts and before role summaries. Non-leaf profiles keep aggregate counts and do not silently show descendant people.

- [x] **Step 5: Run frontend focused tests and verify GREEN**

Run: `npm.cmd test -- src/api/client.test.ts src/features/people/PeopleInTeam.test.tsx src/features/profile/TeamProfileLoader.test.tsx src/features/profile/TeamProfile.test.tsx`
Working directory: `work/geds-career-atlas`
Expected: PASS.

### Task 3: Career Atlas light/dark/system theme

**Files:**
- Create: `work/geds-career-atlas/src/theme/theme.ts`
- Create: `work/geds-career-atlas/src/theme/ThemeControl.tsx`
- Create: `work/geds-career-atlas/src/theme/ThemeControl.test.tsx`
- Modify: `work/geds-career-atlas/src/app/App.tsx`
- Modify: `work/geds-career-atlas/src/styles/tokens.css`
- Modify: `work/geds-career-atlas/src/styles/global.css`
- Modify: `work/geds-career-atlas/src/i18n/en.ts`
- Modify: `work/geds-career-atlas/src/i18n/fr.ts`

**Interfaces:**
- Produces: `ThemeChoice = "light" | "dark" | "system"`, `resolveTheme()`, `applyTheme()`, and `<ThemeControl>`.

- [x] **Step 1: Write failing theme persistence and system-resolution tests**

```tsx
render(<ThemeControl />)
fireEvent.change(screen.getByLabelText("Theme"), {target: {value: "dark"}})
expect(document.documentElement.dataset.theme).toBe("dark")
expect(localStorage.getItem("geds-career-theme")).toBe("dark")
```

- [x] **Step 2: Run theme test and verify RED**

Run: `npm.cmd test -- src/theme/ThemeControl.test.tsx`
Working directory: `work/geds-career-atlas`
Expected: FAIL because theme modules do not exist.

- [x] **Step 3: Implement theme state and red/white semantic tokens**

Use `data-theme="light|dark"` on `<html>`. Light is the initial Career Atlas choice. Dark uses deep navy-neutral surfaces, warm off-white text, and the same red-family accent. Replace component-facing cyan token usage with semantic `--accent`, `--accent-contrast`, `--focus`, and state tokens.

- [x] **Step 4: Integrate visible theme control into the public shell**

Place it with language controls, keep the navigation public-only, and do not add an Admin link.

- [x] **Step 5: Run theme, app, typecheck, and build verification**

Run: `npm.cmd test -- src/theme/ThemeControl.test.tsx src/app/App.test.tsx && npm.cmd run typecheck && npm.cmd run build`
Working directory: `work/geds-career-atlas`
Expected: all commands exit 0.

### Task 4: Admin Console private identity and dual theme

**Files:**
- Modify: `work/geds-crawler/src/geds_crawler/ui_server.py`
- Modify: `work/geds-crawler/tests/test_ui_server.py`

**Interfaces:**
- Produces: Admin-only `Light`, `Dark`, and `System` control stored as `geds-admin-theme`.
- Preserves: existing control routes and operator navigation.

- [x] **Step 1: Write failing rendered-HTML tests**

```python
assert 'Private admin' in html
assert 'geds-admin-theme' in html
assert 'data-theme' in html
assert 'Career Atlas' in html
assert 'Government Explorer' not in admin_navigation_fragment
```

- [x] **Step 2: Run Admin UI tests and verify RED**

Run: `py -m pytest work/geds-crawler/tests/test_ui_server.py -q`
Expected: FAIL on missing private identity/theme contract.

- [x] **Step 3: Add semantic light/dark Admin tokens and persistent theme control**

The existing control-plane information architecture and mutations remain unchanged. Add a visible `Private admin` badge in the shell, a public Career Atlas external link, an accessible theme select, a pre-paint script that resolves saved/system choice, and a `matchMedia` listener for system changes. Light uses neutral/white surfaces with red accent; dark uses navy-neutral surfaces with coordinated red accent.

- [x] **Step 4: Run Admin UI tests and verify GREEN**

Run: `py -m pytest work/geds-crawler/tests/test_ui_server.py work/geds-crawler/tests/test_control_api.py -q`
Expected: PASS.

### Task 5: Boundary, regression, and live visual verification

**Files:**
- Modify: `work/geds-career-atlas/src/app/App.test.tsx`
- Modify: `work/geds-crawler/tests/test_career_api.py`
- Modify: `docs/superpowers/specs/2026-07-12-geds-public-admin-experience-design.md`

**Interfaces:**
- Verifies the completed public/private boundary and marks the design status implemented only after evidence exists.

- [x] **Step 1: Add explicit cross-surface regression tests**

Career Atlas tests assert public navigation and theme/people controls while rejecting crawler, run-history, schedules, start/stop, and private-admin text. Admin tests assert operator navigation and private identity without mounting the Career Atlas discovery journey.

- [x] **Step 2: Run complete automated verification**

Run: `py -m pytest -q`
Working directory: `work/geds-crawler`
Expected: PASS.

Run: `npm.cmd test && npm.cmd run typecheck && npm.cmd run build`
Working directory: `work/geds-career-atlas`
Expected: PASS.

- [x] **Step 3: Start the local Career API/frontend and Admin Console**

Use the existing project CLIs and canonical master DB. Bind only to the local/LAN addresses already documented by the repository. Record process IDs and stop only processes started for this verification.

- [x] **Step 4: Browser-verify both applications at desktop and mobile widths**

Check Career Atlas light/dark/system switching, leaf-team people rows, classification badges, official links, loading/empty states, public-only navigation, and mobile reflow. Check Admin light/dark/system switching, private badge, operator navigation, and absence of public discovery screens. Capture screenshots for the handoff.

- [x] **Step 5: Run final diff and requirement audit**

Run: `git diff --check` and compare every acceptance criterion in `docs/superpowers/specs/2026-07-12-geds-public-admin-experience-design.md` with code/tests/browser evidence.
Expected: no whitespace errors and no uncovered acceptance criterion.

- [x] **Step 6: Commit the verified implementation**

```powershell
git add work/geds-crawler work/geds-career-atlas docs/superpowers
git commit -m "feat: separate and theme GEDS public and admin experiences"
```

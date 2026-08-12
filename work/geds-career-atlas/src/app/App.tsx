import { useEffect, useMemo, useRef, useState } from "react"
import { CareerApiClient } from "../api/client"
import type { DepartmentPage } from "../api/types"
import type { AtlasMeta } from "../features/about/DataMethodology"
import { ConstellationPage } from "../features/constellation/ConstellationPage"
import { DiscoverPage } from "../features/discover/DiscoverPage"
import { FilterRail, type DiscoverScope } from "../features/discover/FilterRail"
import { OrganizationExplorer } from "../features/org-walk/OrganizationExplorer"
import { ProfileDrawer } from "../features/profile/ProfileDrawer"
import { TeamProfileLoader } from "../features/profile/TeamProfileLoader"
import { useLanguage } from "../i18n/i18n"
import { AboutPage } from "../routes/about"
import { readPublicView, type PublicView } from "../state/publicView"
import { ThemeControl } from "../theme/ThemeControl"

function readUrlState() {
  const params = new URLSearchParams(location.search)
  return {
    query: params.get("q") ?? "",
    focus: params.get("focus"),
    scope: { department: params.get("department") ?? "" },
    view: readPublicView(location.hash),
  }
}

function SearchIcon() {
  return <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false"><circle cx="11" cy="11" r="6.5" fill="none" stroke="currentColor" strokeWidth="2"/><path d="m16 16 4 4" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2"/></svg>
}

function CloseIcon() {
  return <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" focusable="false"><path d="m5 5 10 10M15 5 5 15" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8"/></svg>
}

function DisclosureChevron() {
  return <svg className="disclosure-chevron" viewBox="0 0 20 20" width="18" height="18" aria-hidden="true" focusable="false"><path d="m5 7.5 5 5 5-5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.75"/></svg>
}

export function App() {
  const initial = useMemo(readUrlState, [])
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(initial.focus)
  const [query, setQuery] = useState(initial.query)
  const [scope, setScopeState] = useState<DiscoverScope>(initial.scope)
  const [view, setView] = useState<PublicView>(initial.view)
  const [departments, setDepartments] = useState<DepartmentPage["items"]>([])
  const [meta, setMeta] = useState<AtlasMeta | null>(null)
  const [exploreExpanded, setExploreExpanded] = useState(Boolean(initial.query || initial.scope.department))
  const searchRef = useRef<HTMLInputElement>(null)
  const client = useMemo(() => new CareerApiClient(), [])
  const { language, setLanguage, t } = useLanguage()
  const selectedDepartment = useMemo(() => departments.find(item => item.name === scope.department), [departments, scope.department])
  const institutionRoot = useMemo(() => selectedDepartment ? {
    org_id: selectedDepartment.department_id,
    name: selectedDepartment.name,
    depth: 0,
    child_count: 1,
    direct_people_count: 0,
    descendant_people_count: 0,
  } : undefined, [selectedDepartment])
  const otherLanguage = language === "en" ? "fr" : "en"
  const officialGedsUrl = language === "en" ? "https://geds-sage.gc.ca/en/GEDS" : "https://geds-sage.gc.ca/fr/SAGE"

  useEffect(() => {
    const restore = () => {
      const next = readUrlState()
      setQuery(next.query)
      setSelectedOrgId(next.focus)
      setScopeState(next.scope)
      setView(next.view)
      if (next.query || next.scope.department) setExploreExpanded(true)
    }
    addEventListener("popstate", restore)
    addEventListener("hashchange", restore)
    return () => {
      removeEventListener("popstate", restore)
      removeEventListener("hashchange", restore)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    client.departments(controller.signal).then(result => setDepartments(result.items)).catch(() => undefined)
    client.meta(controller.signal).then(setMeta).catch(() => undefined)
    return () => controller.abort()
  }, [client])

  useEffect(() => {
    document.title = `${view === "about" ? t("about.pageTitle") : view === "explorer" ? t("app.explorerTitle") : t("app.discoverTitle")} — GEDS Explorer`
  }, [t, view])

  function writeUrl(update: (params: URLSearchParams) => void, hash = location.hash || "#discover") {
    const params = new URLSearchParams(location.search)
    update(params)
    history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}${hash}`)
  }

  function updateQuery(value: string) {
    setQuery(value)
    if (value && view !== "discover") setView("discover")
    writeUrl(params => value ? params.set("q", value) : params.delete("q"), value ? "#discover" : location.hash || "#discover")
  }

  function clearSearch() {
    updateQuery("")
    requestAnimationFrame(() => searchRef.current?.focus())
  }

  function applyRoleQuery(title: string) {
    const value = title.trim()
    setQuery(value)
    setExploreExpanded(true)
    setSelectedOrgId(null)
    writeUrl(params => {
      value ? params.set("q", value) : params.delete("q")
      params.delete("focus")
    }, location.hash || "#discover")
  }

  function selectOrg(orgId: string) {
    const params = new URLSearchParams(location.search)
    params.set("focus", orgId)
    history.pushState(null, "", `${location.pathname}?${params}${location.hash || "#discover"}`)
    setSelectedOrgId(orgId)
  }

  function clearOrg() {
    writeUrl(params => params.delete("focus"))
    setSelectedOrgId(null)
  }

  function updateScope(next: DiscoverScope) {
    writeUrl(params => {
      next.department ? params.set("department", next.department) : params.delete("department")
      params.delete("focus")
      params.delete("domain")
      params.delete("confidence")
      params.delete("vacancy")
    })
    setSelectedOrgId(null)
    setScopeState(next)
  }

  function languageHref() {
    const params = new URLSearchParams(location.search)
    params.set("lang", otherLanguage)
    return `${location.pathname}?${params}${location.hash}`
  }

  const taskCopy = view === "explorer" ? {
    eyebrow: t("app.explorerEyebrow"),
    title: t("app.explorerTitle"),
    intro: t("app.explorerIntro"),
  } : {
    eyebrow: t("app.discoverEyebrow"),
    title: t("app.discoverTitle"),
    intro: t("app.discoverIntro"),
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main">{t("app.skip")}</a>
    <header className="service-header">
      <div className="service-header__context service-container">
        <p><span>{t("app.dataSourcePrefix")}</span> <a href={officialGedsUrl} target="_blank" rel="noreferrer">{t("app.government")}</a></p>
        <div className="service-header__context-actions">
          <span className="independent-label">{t("app.independentShort")}</span>
          <a className="language" href={languageHref()} lang={otherLanguage} hrefLang={otherLanguage} onClick={event => { event.preventDefault(); setLanguage(otherLanguage) }}>{language === "en" ? "Français" : "English"}</a>
        </div>
      </div>
      <div className="identity-rule" aria-hidden="true" />
      <div className="product-header service-container">
        <a className="product-brand" href="#discover" onClick={() => setView("discover")} aria-label={t("app.homeLabel")}>
          <span className="product-brand__monogram" aria-hidden="true">GE</span>
          <span><strong>GEDS Explorer</strong><small>{t("app.productDescriptor")}</small></span>
        </a>
        <nav className="product-nav" aria-label={t("app.primaryNavigation")}>
          <a href="#discover" aria-current={view === "discover" ? "page" : undefined} className={view === "discover" ? "active" : undefined} onClick={() => setView("discover")}>{t("nav.discover")}</a>
          <a href="#explorer" aria-current={view === "explorer" ? "page" : undefined} className={view === "explorer" ? "active" : undefined} onClick={() => setView("explorer")}>{t("nav.explorer")}</a>
          <a href="#about" aria-current={view === "about" ? "page" : undefined} className={view === "about" ? "active" : undefined} onClick={() => setView("about")}>{t("nav.about")}</a>
        </nav>
        <ThemeControl />
      </div>
    </header>

    <main id="main">
      {view !== "about" && <section className="task-header">
        <div className="service-container task-header__disclosure">
          <button type="button" className="task-header__toggle" aria-expanded={exploreExpanded} aria-controls="geds-search-explore-panel" onClick={() => { const next = !exploreExpanded; setExploreExpanded(next); if (next) requestAnimationFrame(() => searchRef.current?.focus()) }}>
            <span>{t("app.discoverEyebrow")}</span><DisclosureChevron/>
          </button>
          <div id="geds-search-explore-panel" className="task-header__content" hidden={!exploreExpanded}>
            <div className="task-header__layout">
              <header className="task-header__intro">
                <p className="service-kicker">{taskCopy.eyebrow}</p>
                <h1>{taskCopy.title}</h1>
                <p>{taskCopy.intro}</p>
              </header>
              <div className="task-header__controls">
                <form className="service-search" role="search" onSubmit={event => event.preventDefault()}>
                  <div className="service-search__body">
                <label htmlFor="geds-search">{t("app.searchLabel")}</label>
                <p id="geds-search-hint">{t("app.searchHint")}</p>
                <div className="service-search__field">
                  <SearchIcon />
                  <input ref={searchRef} id="geds-search" type="search" value={query} onChange={event => updateQuery(event.target.value)} onKeyDown={event => { if (event.key === "Escape" && query) { event.preventDefault(); clearSearch() } }} placeholder={t("app.placeholder")} aria-describedby="geds-search-hint" autoComplete="off" spellCheck={false}/>
                  {query && <button type="button" className="service-search__clear" aria-label={t("app.clearSearch")} onClick={clearSearch}><CloseIcon/><span>{t("app.clear")}</span></button>}
                </div>
                <FilterRail departments={departments} value={scope} qualityStatus={meta?.quality_status ?? "loading"} onChange={updateScope}/>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      </section>}

      <div className={`service-workspace${view === "discover" ? " service-workspace--discover" : ""}`}>
        {view === "discover" && <div className={`discover-workspace${query ? " discover-workspace--searching" : ""}${exploreExpanded ? "" : " discover-workspace--header-collapsed"}`}>
          {query && <DiscoverPage search={query} client={client} scope={scope} onScopeChange={updateScope} onProfile={selectOrg}/>}
          <ConstellationPage client={client} query={query} focus={selectedOrgId ?? undefined} onProfile={selectOrg} scope={scope} rootOrgId={selectedDepartment?.department_id}/>
        </div>}
        {view === "explorer" && <OrganizationExplorer client={client} onProfile={selectOrg} selectedOrgId={selectedOrgId} rootOrg={institutionRoot} query={query} institutionName={scope.department}/>}
        {view === "about" && <AboutPage client={client}/>}
      </div>
    </main>

    <footer className="service-footer">
      <div className="service-container service-footer__layout">
        <div>
          <strong>GEDS Explorer</strong>
          <p>{t("app.independentLong")}</p>
        </div>
        <nav aria-label={t("app.footerNavigation")}>
          <a href="#about" onClick={() => setView("about")}>{t("nav.about")}</a>
          <a href={officialGedsUrl} target="_blank" rel="noreferrer">{t("about.official")}</a>
          <a href="https://www.canada.ca/" target="_blank" rel="noreferrer">Canada.ca</a>
        </nav>
        <p className="service-footer__source">{t("app.source")}<br/>{t("app.publicReadOnly")}</p>
      </div>
    </footer>

    <ProfileDrawer open={Boolean(selectedOrgId)} onClose={clearOrg} label={t("profile.eyebrow")}>{selectedOrgId && <TeamProfileLoader orgId={selectedOrgId} client={client} onRoleQuery={applyRoleQuery}/>}</ProfileDrawer>
  </div>
}

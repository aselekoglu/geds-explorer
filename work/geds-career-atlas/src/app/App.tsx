import { useEffect, useMemo, useState } from "react"
import { CareerApiClient } from "../api/client"
import { ConstellationPage } from "../features/constellation/ConstellationPage"
import { DiscoverPage } from "../features/discover/DiscoverPage"
import { FilterRail, type DiscoverFilters } from "../features/discover/FilterRail"
import { OrganizationExplorer } from "../features/org-walk/OrganizationExplorer"
import { TeamProfileLoader } from "../features/profile/TeamProfileLoader"
import { SavedMap } from "../features/saved-map/SavedMap"
import { useLanguage } from "../i18n/i18n"
import { AboutPage } from "../routes/about"
import type { DepartmentPage } from "../api/types"
import type { AtlasMeta } from "../features/about/DataMethodology"
import { ThemeControl } from "../theme/ThemeControl"

function initialState() {
  const params = new URLSearchParams(location.search)
  return { query: params.get("q") ?? "", focus: params.get("focus") }
}

export function App() {
  const initial = useMemo(initialState, [])
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(initial.focus)
  const [query, setQuery] = useState(initial.query)
  const initialParams=useMemo(()=>new URLSearchParams(location.search),[])
  const [filters,setFilterState]=useState<DiscoverFilters>({domain:initialParams.get("domain")??"",department:initialParams.get("department")??"",confidence:(initialParams.get("confidence") as DiscoverFilters["confidence"])||"exploratory",vacancy:initialParams.get("vacancy")==="true"})
  const [departments,setDepartments]=useState<DepartmentPage["items"]>([])
  const [meta,setMeta]=useState<AtlasMeta|null>(null)
  const client = useMemo(() => new CareerApiClient(), [])
  const { language, setLanguage, t } = useLanguage()
  useEffect(()=>{const restore=()=>{const params=new URLSearchParams(location.search);setQuery(params.get("q")??"");setSelectedOrgId(params.get("focus"))};addEventListener("popstate",restore);return()=>removeEventListener("popstate",restore)},[])
  useEffect(()=>{const controller=new AbortController();client.departments(controller.signal).then(result=>setDepartments(result.items)).catch(()=>undefined);client.meta(controller.signal).then(setMeta).catch(()=>undefined);return()=>controller.abort()},[client])
  function replaceUrl(next: { query?: string; focus?: string | null }) {
    const params = new URLSearchParams(location.search)
    if (next.query !== undefined) next.query ? params.set("q", next.query) : params.delete("q")
    if (next.focus !== undefined) next.focus ? params.set("focus", next.focus) : params.delete("focus")
    history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}`)
  }
  function selectOrg(orgId: string) { const params=new URLSearchParams(location.search);params.set("focus",orgId);history.pushState(null,"",`${location.pathname}?${params}${location.hash}`);setSelectedOrgId(orgId) }
  function clearOrg(){const params=new URLSearchParams(location.search);params.delete("focus");history.pushState(null,"",`${location.pathname}${params.size?`?${params}`:""}${location.hash}`);setSelectedOrgId(null)}
  function setFilters(next:DiscoverFilters){const params=new URLSearchParams(location.search);next.domain?params.set("domain",next.domain):params.delete("domain");next.department?params.set("department",next.department):params.delete("department");next.confidence!=="exploratory"?params.set("confidence",next.confidence):params.delete("confidence");next.vacancy?params.set("vacancy","true"):params.delete("vacancy");history.replaceState(null,"",`${location.pathname}${params.size?`?${params}`:""}${location.hash}`);setFilterState(next)}
  function openTour(state: { q: string; categories: string[]; mode: "constellation"; focus?: string }) {
    setQuery(state.q)
    setSelectedOrgId(state.focus ?? null)
    const params = new URLSearchParams(location.search)
    params.set("q", state.q)
    params.set("mode", state.mode)
    state.categories.length ? params.set("categories", state.categories.join(",")) : params.delete("categories")
    state.focus ? params.set("focus", state.focus) : params.delete("focus")
    history.pushState(null, "", `${location.pathname}?${params}`)
    document.getElementById("constellation")?.scrollIntoView({ behavior: "smooth" })
  }
  return <div className="app-shell">
    <a className="skip-link" href="#main">{t("app.skip")}</a>
    <aside className="side-nav" aria-label="Primary navigation">
      <div className="brand"><span className="brand-mark" aria-hidden="true">✦</span><span>GEDS <b>{t("app.brand")}</b></span></div>
      <nav><a href="#discover" className="active">{t("nav.discover")}</a><a href="#explorer">{t("nav.explorer")}</a><a href="#constellation">{t("nav.constellation")}</a><a href="#tours">{t("nav.tours")}</a><a href="#about">{t("nav.about")}</a></nav>
      <div className="nav-footer">{t("app.source")}<br />{t("app.publicReadOnly")}</div>
    </aside>
    <main id="main">
      <header className="command-bar" id="discover"><label><span className="sr-only">{t("app.interest")}</span><input value={query} onChange={event => { setQuery(event.target.value); replaceUrl({ query: event.target.value }) }} placeholder={t("app.placeholder")} /></label><button type="button">{t("app.filters")}</button><ThemeControl/><button type="button" className="language" onClick={() => setLanguage(language === "en" ? "fr" : "en")}>{language === "en" ? "Français" : "English"}</button></header>
      <FilterRail departments={departments} value={filters} qualityStatus={meta?.quality_status??"loading"} onChange={setFilters}/>
      {query && <DiscoverPage search={query} client={client} filters={filters} onFiltersChange={setFilters} />}
      <ConstellationPage client={client} query={query} focus={selectedOrgId ?? undefined} onFocus={selectOrg} filters={filters} />
      <div id="explorer"><OrganizationExplorer client={client} onSelect={selectOrg} selectedOrgId={selectedOrgId} /></div>
      <SavedMap client={client} lang={language} onOpen={openTour} current={{ q: query, categories: filters.domain?[filters.domain]:[], department:filters.department||undefined, confidence: filters.confidence, vacancy: filters.vacancy, lang: language, mode: "constellation", focus: selectedOrgId ?? undefined }} />
      <AboutPage client={client} />
    </main>
    <aside className={`detail-panel${selectedOrgId?" detail-panel--open":""}`}><button className="close" aria-label={t("app.close")} onClick={clearOrg}>×</button>{selectedOrgId ? <TeamProfileLoader orgId={selectedOrgId} client={client} /> : <><p className="breadcrumb">{t("app.government")}</p><h2>{t("app.selectOrg")}</h2><p className="role-count">{t("app.selectHint")}</p><p>{t("app.sourceSignals")}</p></>}</aside>
  </div>
}

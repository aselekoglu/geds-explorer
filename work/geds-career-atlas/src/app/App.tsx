import { useMemo, useState } from "react"
import { CareerApiClient } from "../api/client"
import { ConstellationPage } from "../features/constellation/ConstellationPage"
import { DiscoverPage } from "../features/discover/DiscoverPage"
import { OrganizationExplorer } from "../features/org-walk/OrganizationExplorer"
import { TeamProfileLoader } from "../features/profile/TeamProfileLoader"
import { SavedMap } from "../features/saved-map/SavedMap"
import { useLanguage } from "../i18n/i18n"
import { AboutPage } from "../routes/about"

function initialState() {
  const params = new URLSearchParams(location.search)
  return { query: params.get("q") ?? "", focus: params.get("focus") }
}

export function App() {
  const initial = useMemo(initialState, [])
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(initial.focus)
  const [query, setQuery] = useState(initial.query)
  const client = useMemo(() => new CareerApiClient(), [])
  const { language, setLanguage, t } = useLanguage()
  function replaceUrl(next: { query?: string; focus?: string | null }) {
    const params = new URLSearchParams(location.search)
    if (next.query !== undefined) next.query ? params.set("q", next.query) : params.delete("q")
    if (next.focus !== undefined) next.focus ? params.set("focus", next.focus) : params.delete("focus")
    history.replaceState(null, "", `${location.pathname}${params.size ? `?${params}` : ""}`)
  }
  function selectOrg(orgId: string) { setSelectedOrgId(orgId); replaceUrl({ focus: orgId }) }
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
      <header className="command-bar" id="discover"><label><span className="sr-only">{t("app.interest")}</span><input value={query} onChange={event => { setQuery(event.target.value); replaceUrl({ query: event.target.value }) }} placeholder={t("app.placeholder")} /></label><button type="button">{t("app.filters")}</button><button type="button" className="language" onClick={() => setLanguage(language === "en" ? "fr" : "en")}>{language === "en" ? "Français" : "English"}</button></header>
      <div className="filter-rail"><button type="button">{t("app.organizations")}</button><button type="button">{t("app.levels")}</button><button type="button">{t("app.canada")}</button><button type="button">{t("app.workTypes")}</button></div>
      {query && <DiscoverPage search={query} client={client} />}
      <ConstellationPage client={client} query={query} focus={selectedOrgId ?? undefined} onFocus={selectOrg} />
      <div id="explorer"><OrganizationExplorer client={client} onSelect={selectOrg} /></div>
      <SavedMap client={client} lang={language} onOpen={openTour} current={{ q: query, categories: [], confidence: "exploratory", vacancy: false, lang: language, mode: "constellation", focus: selectedOrgId ?? undefined }} />
      <AboutPage client={client} />
    </main>
    <aside className="detail-panel"><button className="close" aria-label={t("app.close")} onClick={() => { setSelectedOrgId(null); replaceUrl({ focus: null }) }}>×</button>{selectedOrgId ? <TeamProfileLoader orgId={selectedOrgId} client={client} /> : <><p className="breadcrumb">{t("app.government")}</p><h2>{t("app.selectOrg")}</h2><p className="role-count">{t("app.selectHint")}</p><p>{t("app.sourceSignals")}</p></>}</aside>
  </div>
}

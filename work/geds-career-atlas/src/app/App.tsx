import { useEffect, useMemo, useState } from "react"
import { CareerApiClient } from "../api/client"
import type { DepartmentPage } from "../api/types"
import type { AtlasMeta } from "../features/about/DataMethodology"
import { ConstellationPage } from "../features/constellation/ConstellationPage"
import { DiscoverPage } from "../features/discover/DiscoverPage"
import { FilterRail, type DiscoverScope } from "../features/discover/FilterRail"
import { OrganizationExplorer } from "../features/org-walk/OrganizationExplorer"
import { TeamProfileLoader } from "../features/profile/TeamProfileLoader"
import { ProfileDrawer } from "../features/profile/ProfileDrawer"
import { useLanguage } from "../i18n/i18n"
import { AboutPage } from "../routes/about"
import { readPublicView, type PublicView } from "../state/publicView"
import { ThemeControl } from "../theme/ThemeControl"

function readUrlState(){
  const params=new URLSearchParams(location.search)
  return {query:params.get("q")??"",focus:params.get("focus"),scope:{department:params.get("department")??""},view:readPublicView(location.hash)}
}

export function App(){
  const initial=useMemo(readUrlState,[])
  const [selectedOrgId,setSelectedOrgId]=useState<string|null>(initial.focus)
  const [query,setQuery]=useState(initial.query)
  const [scope,setScopeState]=useState<DiscoverScope>(initial.scope)
  const [view,setView]=useState<PublicView>(initial.view)
  const [departments,setDepartments]=useState<DepartmentPage["items"]>([])
  const [meta,setMeta]=useState<AtlasMeta|null>(null)
  const client=useMemo(()=>new CareerApiClient(),[])
  const {language,setLanguage,t}=useLanguage()
  const selectedDepartment=useMemo(()=>departments.find(item=>item.name===scope.department),[departments,scope.department])
  const institutionRoot=useMemo(()=>selectedDepartment?{org_id:selectedDepartment.department_id,name:selectedDepartment.name,depth:0,child_count:1,direct_people_count:0,descendant_people_count:0}:undefined,[selectedDepartment])

  useEffect(()=>{
    const restore=()=>{const next=readUrlState();setQuery(next.query);setSelectedOrgId(next.focus);setScopeState(next.scope);setView(next.view)}
    addEventListener("popstate",restore);addEventListener("hashchange",restore)
    return()=>{removeEventListener("popstate",restore);removeEventListener("hashchange",restore)}
  },[])
  useEffect(()=>{const controller=new AbortController();client.departments(controller.signal).then(result=>setDepartments(result.items)).catch(()=>undefined);client.meta(controller.signal).then(setMeta).catch(()=>undefined);return()=>controller.abort()},[client])

  function writeUrl(update:(params:URLSearchParams)=>void,hash=location.hash||"#discover"){
    const params=new URLSearchParams(location.search);update(params)
    history.replaceState(null,"",`${location.pathname}${params.size?`?${params}`:""}${hash}`)
  }
  function updateQuery(value:string){setQuery(value);if(value&&view!=="discover")setView("discover");writeUrl(params=>value?params.set("q",value):params.delete("q"),value?"#discover":location.hash||"#discover")}
  function selectOrg(orgId:string){const params=new URLSearchParams(location.search);params.set("focus",orgId);history.pushState(null,"",`${location.pathname}?${params}${location.hash||"#discover"}`);setSelectedOrgId(orgId)}
  function clearOrg(){writeUrl(params=>params.delete("focus"));setSelectedOrgId(null)}
  function updateScope(next:DiscoverScope){
    writeUrl(params=>{next.department?params.set("department",next.department):params.delete("department");params.delete("focus");params.delete("domain");params.delete("confidence");params.delete("vacancy")})
    setSelectedOrgId(null)
    setScopeState(next)
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main">{t("app.skip")}</a>
    <aside className="side-nav" aria-label="Primary navigation">
      <div className="brand"><span className="brand-mark" aria-hidden="true">✦</span><span>GEDS <b>{t("app.brand")}</b></span></div>
      <nav>
        <a href="#discover" aria-current={view==="discover"?"page":undefined} className={view==="discover"?"active":undefined} onClick={()=>setView("discover")}>{t("nav.discover")}</a>
        <a href="#explorer" aria-current={view==="explorer"?"page":undefined} className={view==="explorer"?"active":undefined} onClick={()=>setView("explorer")}>{t("nav.explorer")}</a>
        <a href="#about" aria-current={view==="about"?"page":undefined} className={view==="about"?"active":undefined} onClick={()=>setView("about")}>{t("nav.about")}</a>
      </nav>
      <div className="nav-footer">{t("app.source")}<br/>{t("app.publicReadOnly")}</div>
    </aside>
    <main id="main">
      {view!=="about"&&<><header className="command-bar"><label><span className="sr-only">{t("app.interest")}</span><input value={query} onChange={event=>updateQuery(event.target.value)} placeholder={t("app.placeholder")}/></label><ThemeControl/><button type="button" className="language" onClick={()=>setLanguage(language==="en"?"fr":"en")}>{language==="en"?"Français":"English"}</button></header><FilterRail departments={departments} value={scope} qualityStatus={meta?.quality_status??"loading"} onChange={updateScope}/></>}
      {view==="discover"&&<div className={`discover-workspace${query?" discover-workspace--searching":""}`}>{query&&<DiscoverPage search={query} client={client} scope={scope} onScopeChange={updateScope}/>}<ConstellationPage client={client} query={query} focus={selectedOrgId??undefined} onFocus={selectOrg} scope={scope} rootOrgId={selectedDepartment?.department_id}/></div>}
      {view==="explorer"&&<OrganizationExplorer client={client} onProfile={selectOrg} selectedOrgId={selectedOrgId} rootOrg={institutionRoot}/>} 
      {view==="about"&&<AboutPage client={client}/>} 
    </main>
    <ProfileDrawer open={Boolean(selectedOrgId)} onClose={clearOrg} label={t("profile.eyebrow")}>{selectedOrgId&&<TeamProfileLoader orgId={selectedOrgId} client={client}/>}</ProfileDrawer>
  </div>
}

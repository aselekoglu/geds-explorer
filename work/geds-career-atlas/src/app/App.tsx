import { useMemo, useState } from "react"
import { CareerApiClient } from "../api/client"
import { ConstellationPage } from "../features/constellation/ConstellationPage"
import { DiscoverPage } from "../features/discover/DiscoverPage"
import { OrganizationExplorer } from "../features/org-walk/OrganizationExplorer"
import { TeamProfileLoader } from "../features/profile/TeamProfileLoader"
import { SavedMap } from "../features/saved-map/SavedMap"

function initialState(){const params=new URLSearchParams(location.search);return{query:params.get("q")??"",focus:params.get("focus")}}

export function App() {
  const initial=useMemo(initialState,[])
  const [selectedOrgId,setSelectedOrgId]=useState<string|null>(initial.focus)
  const [query,setQuery]=useState(initial.query)
  const client=useMemo(()=>new CareerApiClient(),[])
  function replaceUrl(next:{query?:string;focus?:string|null}){const params=new URLSearchParams(location.search);if(next.query!==undefined){next.query?params.set("q",next.query):params.delete("q")}if(next.focus!==undefined){next.focus?params.set("focus",next.focus):params.delete("focus")}history.replaceState(null,"",`${location.pathname}${params.size?`?${params}`:""}`)}
  function selectOrg(orgId:string){setSelectedOrgId(orgId);replaceUrl({focus:orgId})}
  function openTour(state:{q:string;categories:string[];mode:"constellation";focus?:string}){setQuery(state.q);setSelectedOrgId(state.focus??null);const params=new URLSearchParams(location.search);params.set("q",state.q);params.set("mode",state.mode);state.categories.length?params.set("categories",state.categories.join(",")):params.delete("categories");state.focus?params.set("focus",state.focus):params.delete("focus");history.pushState(null,"",`${location.pathname}?${params}`);document.getElementById("constellation")?.scrollIntoView({behavior:"smooth"})}
  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to content</a>
    <aside className="side-nav" aria-label="Primary navigation"><div className="brand"><span className="brand-mark" aria-hidden="true">✦</span><span>GEDS <b>Career Atlas</b></span></div><nav><a href="#discover" className="active">Discover</a><a href="#explorer">Government Explorer</a><a href="#constellation">Constellation</a><a href="#tours">Tours</a></nav><div className="nav-footer">Source: GEDS snapshot<br/>Public, read-only explorer</div></aside>
    <main id="main"><header className="command-bar" id="discover"><label><span className="sr-only">Career interest</span><input value={query} onChange={event=>{setQuery(event.target.value);replaceUrl({query:event.target.value})}} placeholder="AI, cybersecurity, policy" /></label><button type="button">Filters</button><button type="button" className="language">FR</button></header><div className="filter-rail"><button type="button">Organizations</button><button type="button">All levels</button><button type="button">All Canada</button><button type="button">All work types</button></div>{query&&<DiscoverPage search={query} client={client}/>}<ConstellationPage client={client} query={query} focus={selectedOrgId??undefined} onFocus={selectOrg}/><div id="explorer"><OrganizationExplorer client={client} onSelect={selectOrg}/></div><SavedMap client={client} onOpen={openTour} current={{q:query,categories:[],confidence:"exploratory",vacancy:false,lang:"en",mode:"constellation",focus:selectedOrgId??undefined}}/></main>
    <aside className="detail-panel"><button className="close" aria-label="Close detail panel" onClick={()=>{setSelectedOrgId(null);replaceUrl({focus:null})}}>×</button>{selectedOrgId?<TeamProfileLoader orgId={selectedOrgId} client={client}/>:<><p className="breadcrumb">Government of Canada</p><h2>Select an organization</h2><p className="role-count">Choose a constellation node or an Organization Walk row to inspect observed team details.</p><p>Role titles and vacancy markers are source-derived signals, not job postings.</p></>}</aside>
  </div>
}

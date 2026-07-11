import { useMemo, useState } from "react"
import { CareerApiClient } from "../api/client"
import { DiscoverPage } from "../features/discover/DiscoverPage"
import { OrganizationExplorer } from "../features/org-walk/OrganizationExplorer"
import { TeamProfileLoader } from "../features/profile/TeamProfileLoader"

const clusters = ["Canada Revenue Agency", "National Defence", "Health Canada", "Environment and Climate Change Canada", "Employment and Social Development Canada", "Innovation, Science and Economic Development Canada"]

export function App() {
  const [selected, setSelected] = useState("Privy Council Office")
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null)
  const [query, setQuery] = useState("")
  const client = useMemo(() => new CareerApiClient(), [])
  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to content</a>
    <aside className="side-nav" aria-label="Primary navigation"><div className="brand"><span className="brand-mark">*</span><span>GEDS <b>Career Atlas</b></span></div><nav><a href="#discover" className="active">Discover</a><a href="#explorer">Government Explorer</a><a href="#constellation">Constellation</a><a href="#tours">Tours</a></nav><div className="nav-footer">Source: GEDS snapshot<br/>Public, read-only explorer</div></aside>
    <main id="main"><header className="command-bar"><label><span className="sr-only">Career interest</span><input value={query} onChange={event => { setQuery(event.target.value); history.replaceState(null, "", `?q=${encodeURIComponent(event.target.value)}`) }} placeholder="AI, cybersecurity, policy" /></label><button>Filters</button><button className="language">FR</button></header><div className="filter-rail"><button>Organizations</button><button>All levels</button><button>All Canada</button><button>All work types</button></div>{query && <DiscoverPage search={query} client={client} />}
      <section className="atlas" aria-label="Government constellation"><div className="atlas-heading"><h1>Government at a glance</h1><p>Explore organizations and discover where your interests connect to Canada&apos;s public service.</p></div><div className="constellation">{clusters.map((name, index) => <button key={name} className={`orbit orbit-${index}`} onClick={() => setSelected(name)}><span>*</span>{name}</button>)}<button className="core" onClick={() => setSelected("Privy Council Office")} aria-pressed={selected === "Privy Council Office"}>o<small>Privy Council Office</small></button></div><p className="legend">Selected · Organization · hierarchy relationship</p></section>
      <OrganizationExplorer client={client} onSelect={setSelectedOrgId} />
    </main><aside className="detail-panel"><button className="close" aria-label="Close detail panel" onClick={() => setSelectedOrgId(null)}>x</button>{selectedOrgId ? <TeamProfileLoader orgId={selectedOrgId} client={client} /> : <><p className="breadcrumb">Government of Canada / Core Public Administration</p><h2>{selected}</h2><p className="role-count">Choose an organization in the Org Walk to see observed team details.</p><p>Constellation introduces areas of government; the explorer shows the source-derived hierarchy behind them.</p></>}</aside>
  </div>
}

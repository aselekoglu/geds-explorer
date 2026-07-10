import { useMemo, useState } from "react"
import { CareerApiClient } from "../api/client"
import { DiscoverPage } from "../features/discover/DiscoverPage"
import { OrganizationExplorer } from "../features/org-walk/OrganizationExplorer"

const clusters = ["Canada Revenue Agency", "National Defence", "Health Canada", "Environment and Climate Change Canada", "Employment and Social Development Canada", "Innovation, Science and Economic Development Canada"]

export function App() {
  const [selected, setSelected] = useState("Privy Council Office")
  const [query, setQuery] = useState("")
  const client = useMemo(() => new CareerApiClient(), [])
  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to content</a>
    <aside className="side-nav" aria-label="Primary navigation"><div className="brand"><span className="brand-mark">*</span><span>GEDS <b>Career Atlas</b></span></div><nav><a href="#discover" className="active">Discover</a><a href="#explorer">Government Explorer</a><a href="#constellation">Constellation</a><a href="#tours">Tours</a></nav><div className="nav-footer">Source: GEDS snapshot<br/>Public, read-only explorer</div></aside>
    <main id="main"><header className="command-bar"><label><span className="sr-only">Career interest</span><input value={query} onChange={event => { setQuery(event.target.value); history.replaceState(null, "", `?q=${encodeURIComponent(event.target.value)}`) }} placeholder="AI, cybersecurity, policy" /></label><button>Filters</button><button className="language">FR</button></header><div className="filter-rail"><button>Organizations</button><button>All levels</button><button>All Canada</button><button>All work types</button></div>{query && <DiscoverPage search={query} client={client} />}
      <section className="atlas" aria-label="Government constellation"><div className="atlas-heading"><h1>Government at a glance</h1><p>Explore organizations and discover where your interests connect to Canada&apos;s public service.</p></div><div className="constellation">{clusters.map((name, index) => <button key={name} className={`orbit orbit-${index}`} onClick={() => setSelected(name)}><span>*</span>{name}</button>)}<button className="core" onClick={() => setSelected("Privy Council Office")} aria-pressed={selected === "Privy Council Office"}>o<small>Privy Council Office</small></button></div><p className="legend">Selected · Organization · hierarchy relationship</p></section>
      <OrganizationExplorer client={client} />
    </main><aside className="detail-panel"><button className="close" aria-label="Close detail panel">x</button><p className="breadcrumb">Government of Canada / Core Public Administration</p><h2>{selected}</h2><p className="role-count">Observed roles and vacancy status are source-derived signals, not a job listing.</p><p>Explore its hierarchy, current roles, and why this organization may match your interests.</p><section><h3>Explore hierarchy</h3><ol><li>Government of Canada</li><li>Core Public Administration</li><li><strong>{selected}</strong></li></ol></section><section><h3>Examples of observed roles</h3><ul className="role-list"><li>Policy Analyst</li><li>Cybersecurity Advisor</li><li>Data Scientist</li></ul></section><section><h3>Why you might be a good match</h3><p><b>Security and trust</b><br/>Matched organization evidence and related roles.</p></section><footer>Any vacancy signal is unverified. Confirm it through an official job posting.</footer></aside>
  </div>
}

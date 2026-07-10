import { useEffect, useState } from "react"
import type { OrgPage } from "../../api/types"

type RootClient = { rootChildren: (signal?: AbortSignal) => Promise<OrgPage> }

export function OrganizationExplorer({ client }: { client: RootClient }) {
  const [page, setPage] = useState<OrgPage | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    client.rootChildren(controller.signal).then(setPage).catch(value => { if (value.name !== "AbortError") setError(true) })
    return () => controller.abort()
  }, [client])
  if (error) return <p role="status">Organization data is unavailable right now.</p>
  if (!page) return <p role="status">Loading government organizations…</p>
  return <section className="org-explorer" aria-labelledby="org-explorer-title">
    <div><p className="eyebrow">ORGANIZATION WALK</p><h2 id="org-explorer-title">Start at the top</h2><p>Choose an organization to see its teams and observed role titles.</p></div>
    <div role="tree" aria-label="Top-level government organizations" className="org-root-list">
      {page.items.map(node => <button key={node.org_id} role="treeitem" aria-level={node.depth + 1}><span>{node.name}</span><small>{node.child_count} teams · {node.descendant_people_count.toLocaleString()} people indexed</small></button>)}
    </div>
  </section>
}

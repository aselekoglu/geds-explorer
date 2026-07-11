import { useEffect, useState } from "react"
import type { OrgNode, OrgPage } from "../../api/types"

type RootClient = {
  rootChildren: (signal?: AbortSignal) => Promise<OrgPage>
  children: (orgId: string, signal?: AbortSignal) => Promise<OrgPage>
}
type Column = { parent?: OrgNode; items: OrgNode[] }

export function OrganizationExplorer({ client, onSelect }: { client: RootClient; onSelect?: (orgId: string) => void }) {
  const [columns, setColumns] = useState<Column[]>([])
  const [error, setError] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    client.rootChildren(controller.signal).then(page => setColumns([{ items: page.items }])).catch(value => { if (value.name !== "AbortError") setError(true) })
    return () => controller.abort()
  }, [client])
  async function open(node: OrgNode, columnIndex: number) {
    const page = await client.children(node.org_id)
    setColumns(current => [...current.slice(0, columnIndex + 1), { parent: node, items: page.items }])
  }
  const selectedPath = columns.slice(1).map(column => column.parent?.name).filter(Boolean).join(" / ")
  if (error) return <p role="status">Organization data is unavailable right now.</p>
  if (!columns.length) return <p role="status">Loading government organizations...</p>
  return <section className="org-explorer" aria-labelledby="org-explorer-title">
    <div><p className="eyebrow">ORGANIZATION WALK</p><h2 id="org-explorer-title">Start at the top</h2><p>Choose an organization to see its teams and observed role titles.</p></div>
    {selectedPath && <nav aria-label="Selected organization path">{selectedPath}</nav>}
    <div className="org-columns">
      {columns.map((column, columnIndex) => <div key={column.parent?.org_id ?? "root"} className="org-root-list" role="tree" aria-label={column.parent ? `${column.parent.name} teams` : "Top-level government organizations"}>
        {column.items.map(node => <button key={node.org_id} role="treeitem" aria-level={node.depth + 1} aria-expanded={node.child_count > 0 ? columns[columnIndex + 1]?.parent?.org_id === node.org_id : undefined} onClick={() => { onSelect?.(node.org_id); void open(node, columnIndex) }} onKeyDown={event => { if ((event.key === "ArrowRight" || event.key === "Enter") && node.child_count) { event.preventDefault(); onSelect?.(node.org_id); void open(node, columnIndex) } if (event.key === "ArrowLeft" && columnIndex) { event.preventDefault(); setColumns(current => current.slice(0, columnIndex)) } }}><span>{node.name}</span><small>{node.child_count} teams · {node.descendant_people_count.toLocaleString()} people indexed</small></button>)}
      </div>)}
    </div>
  </section>
}

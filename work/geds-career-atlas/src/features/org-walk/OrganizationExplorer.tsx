import { useEffect, useState } from "react"
import type { OrgNode, OrgPage } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"

type RootClient = { rootChildren: (signal?: AbortSignal) => Promise<OrgPage>; children: (orgId: string, signal?: AbortSignal) => Promise<OrgPage> }
type Column = { parent?: OrgNode; items: OrgNode[] }

export function OrganizationExplorer({ client, onSelect }: { client: RootClient; onSelect?: (orgId: string) => void }) {
  const [columns, setColumns] = useState<Column[]>([])
  const [error, setError] = useState(false)
  const { t, formatNumber } = useLanguage()
  useEffect(() => { const controller = new AbortController(); client.rootChildren(controller.signal).then(page => setColumns([{ items: page.items }])).catch(value => { if (value.name !== "AbortError") setError(true) }); return () => controller.abort() }, [client])
  async function open(node: OrgNode, columnIndex: number) { const page = await client.children(node.org_id); setColumns(current => [...current.slice(0, columnIndex + 1), { parent: node, items: page.items }]) }
  const selectedPath = columns.slice(1).map(column => column.parent?.name).filter(Boolean).join(" / ")
  if (error) return <p role="status">{t("orgWalk.unavailable")}</p>
  if (!columns.length) return <p role="status">{t("orgWalk.loading")}</p>
  return <section className="org-explorer" aria-labelledby="org-explorer-title">
    <div><p className="eyebrow">{t("orgWalk.eyebrow")}</p><h2 id="org-explorer-title">{t("orgWalk.title")}</h2><p>{t("orgWalk.intro")}</p></div>
    {selectedPath && <nav aria-label={t("orgWalk.path")}>{selectedPath}</nav>}
    <div className="org-columns">{columns.map((column, columnIndex) => <div key={column.parent?.org_id ?? "root"} className="org-root-list" role="tree" aria-label={column.parent ? t("orgWalk.teamLabel", { name: column.parent.name }) : t("orgWalk.top")}>
      {column.items.map(node => <button key={node.org_id} role="treeitem" aria-level={node.depth + 1} aria-expanded={node.child_count > 0 ? columns[columnIndex + 1]?.parent?.org_id === node.org_id : undefined} onClick={() => { onSelect?.(node.org_id); void open(node, columnIndex) }} onKeyDown={event => { if ((event.key === "ArrowRight" || event.key === "Enter") && node.child_count) { event.preventDefault(); onSelect?.(node.org_id); void open(node, columnIndex) } if (event.key === "ArrowLeft" && columnIndex) { event.preventDefault(); setColumns(current => current.slice(0, columnIndex)) } }}><span>{node.name}</span><small>{t("orgWalk.summary", { teams: node.child_count, people: formatNumber(node.descendant_people_count) })}</small></button>)}
    </div>)}</div>
  </section>
}

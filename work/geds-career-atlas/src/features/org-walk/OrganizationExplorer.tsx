import { useEffect, useState } from "react"
import type { OrgNode, OrgPage } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import { OrgBreadcrumb } from "./OrgBreadcrumb"
import { OrgColumn } from "./OrgColumn"

type RootClient = { rootChildren: (signal?: AbortSignal) => Promise<OrgPage>; children: (orgId: string, signal?: AbortSignal) => Promise<OrgPage>;ancestors?:(orgId:string,signal?:AbortSignal)=>Promise<OrgPage> }
type Column = { parent?: OrgNode; items: OrgNode[] }

export function OrganizationExplorer({ client, onSelect, selectedOrgId,rootOrg }: { client: RootClient; onSelect?: (orgId: string) => void;selectedOrgId?:string|null;rootOrg?:OrgNode }) {
  const [columns, setColumns] = useState<Column[]>([])
  const [error, setError] = useState(false)
  const { t } = useLanguage()
  useEffect(() => {
    const controller = new AbortController()
    async function load(){
      setError(false)
      if(rootOrg){const page=await client.children(rootOrg.org_id,controller.signal);setColumns([{parent:rootOrg,items:page.items}]);return}
      const root=await client.rootChildren(controller.signal)
      if(!selectedOrgId||!client.ancestors){setColumns([{items:root.items}]);return}
      const lineage=await client.ancestors(selectedOrgId,controller.signal)
      const descendants=await Promise.all(lineage.items.map(node=>client.children(node.org_id,controller.signal)))
      setColumns([{items:root.items},...lineage.items.map((node,index)=>({parent:node,items:descendants[index].items}))])
    }
    void load().catch(value=>{if(value.name!=="AbortError")setError(true)})
    return()=>controller.abort()
  },[client,selectedOrgId,rootOrg])
  async function open(node: OrgNode, columnIndex: number) { const page = await client.children(node.org_id); setColumns(current => [...current.slice(0, columnIndex + 1), { parent: node, items: page.items }]) }
  if (error) return <p role="status">{t("orgWalk.unavailable")}</p>
  if (!columns.length) return <p role="status">{t("orgWalk.loading")}</p>
  return <section className="org-explorer" aria-labelledby="org-explorer-title">
    <div><p className="eyebrow">{t("orgWalk.eyebrow")}</p><h2 id="org-explorer-title">{t("orgWalk.title")}</h2><p>{t("orgWalk.intro")}</p></div>
    <OrgBreadcrumb path={columns.slice(1).map(column=>column.parent?.name).filter((name):name is string=>Boolean(name))} label={t("orgWalk.path")} onBack={()=>setColumns(current=>current.slice(0,-1))}/>
    <div className="org-columns">{columns.map((column,columnIndex)=><OrgColumn key={column.parent?.org_id??"root"} label={column.parent?t("orgWalk.teamLabel",{name:column.parent.name}):t("orgWalk.top")} items={column.items} columnIndex={columnIndex} expandedId={columns[columnIndex+1]?.parent?.org_id} onOpen={(node,index)=>{onSelect?.(node.org_id);void open(node,index)}} onBack={index=>setColumns(current=>current.slice(0,index))}/>)}</div>
  </section>
}

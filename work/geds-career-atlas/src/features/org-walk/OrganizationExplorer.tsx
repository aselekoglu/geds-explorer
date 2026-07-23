import { useEffect, useState } from "react"
import type { OrgNode, OrgPage, SearchResult } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import { OrgBreadcrumb } from "./OrgBreadcrumb"
import { OrgColumn } from "./OrgColumn"
import { PeopleInTeam, type PeopleClient } from "../people/PeopleInTeam"
import { BorderGlow } from "../../components/BorderGlow"

type RootClient = { rootChildren: (signal?: AbortSignal) => Promise<OrgPage>; children: (orgId: string, signal?: AbortSignal) => Promise<OrgPage>;ancestors?:(orgId:string,signal?:AbortSignal)=>Promise<OrgPage>;search?:(query:string,signal?:AbortSignal)=>Promise<SearchResult>;people?:PeopleClient["people"] }
type Column = { parent?: OrgNode; items: OrgNode[]; leaf?: boolean }
type Match={org_id:string;name:string}

export function OrganizationExplorer({ client, onProfile, selectedOrgId,rootOrg,query="",institutionName="" }: { client: RootClient; onProfile?: (orgId: string) => void;selectedOrgId?:string|null;rootOrg?:OrgNode;query?:string;institutionName?:string }) {
  const [columns, setColumns] = useState<Column[]>([])
  const [error, setError] = useState(false)
  const [matches,setMatches]=useState<Match[]>([])
  const [searchState,setSearchState]=useState<"idle"|"loading"|"empty"|"error">("idle")
  const { t } = useLanguage()
  useEffect(() => {
    const controller = new AbortController()
    async function load(){
      setError(false)
      if(rootOrg){const page=await client.children(rootOrg.org_id,controller.signal);setColumns([{parent:rootOrg,items:page.items}]);return}
      const root=await client.rootChildren(controller.signal)
      if(!selectedOrgId||!client.ancestors){setColumns([{items:root.items}]);return}
      const lineage=await client.ancestors(selectedOrgId,controller.signal)
      const descendants=await Promise.all(lineage.items.map(node=>node.child_count===0?Promise.resolve(null):client.children(node.org_id,controller.signal)))
      setColumns([{items:root.items},...lineage.items.map((node,index)=>descendants[index]?({parent:node,items:descendants[index]!.items}):({parent:node,items:[],leaf:true}))])
    }
    void load().catch(value=>{if(value.name!=="AbortError")setError(true)})
    return()=>controller.abort()
  },[client,selectedOrgId,rootOrg])
  useEffect(()=>{
    const controller=new AbortController()
    const value=query.trim()
    if(!value||!client.search){setMatches([]);setSearchState("idle");return()=>controller.abort()}
    setSearchState("loading")
    client.search(value,controller.signal).then(result=>{
      const unique=new Map<string,Match>()
      for(const item of result.items){if(!item.org_id)continue;if(institutionName&&item.department_name!==institutionName)continue;if(!unique.has(item.org_id))unique.set(item.org_id,{org_id:item.org_id,name:item.organization_name})}
      const next=[...unique.values()]
      setMatches(next);setSearchState(next.length?"idle":"empty")
    }).catch(value=>{if(value.name!=="AbortError"){setMatches([]);setSearchState("error")}})
    return()=>controller.abort()
  },[client,query,institutionName])
  async function drill(node: OrgNode, columnIndex: number) {
    if(node.child_count===0){setColumns(current=>[...current.slice(0,columnIndex+1),{parent:node,items:[],leaf:true}]);return}
    const page = await client.children(node.org_id)
    setColumns(current => [...current.slice(0, columnIndex + 1), { parent: node, items: page.items }])
  }
  async function restoreMatch(orgId:string){
    if(!client.ancestors)return
    const lineage=(await client.ancestors(orgId)).items
    if(rootOrg){
      const rootIndex=lineage.findIndex(node=>node.org_id===rootOrg.org_id)
      const scoped=rootIndex>=0?lineage.slice(rootIndex):lineage
      const first=await client.children(rootOrg.org_id)
      const next:Column[]=[{parent:rootOrg,items:first.items}]
      for(const node of scoped.slice(1)){if(node.child_count===0)next.push({parent:node,items:[],leaf:true});else next.push({parent:node,items:(await client.children(node.org_id)).items})}
      setColumns(next);return
    }
    const root=await client.rootChildren()
    const next:Column[]=[{items:root.items}]
    for(const node of lineage){if(node.child_count===0)next.push({parent:node,items:[],leaf:true});else next.push({parent:node,items:(await client.children(node.org_id)).items})}
    setColumns(next)
  }
  const breadcrumbColumns=columns.flatMap((column,columnIndex)=>column.parent?[{columnIndex,label:column.parent.name}]:[])
  if (error) return <p role="status">{t("orgWalk.unavailable")}</p>
  if (!columns.length) return <p role="status">{t("orgWalk.loading")}</p>
  return <section className="org-explorer" aria-labelledby="org-explorer-title">
    <div><p className="eyebrow">{t("orgWalk.eyebrow")}</p><h2 id="org-explorer-title">{t("orgWalk.title")}</h2><p>{t("orgWalk.intro")}</p></div>
    {query.trim()&&<BorderGlow as="section" className="org-matches" aria-labelledby="org-matches-title" fillOpacity={0.045}><div className="org-matches__heading"><div><p>{t("orgWalk.searchContext")}</p><h3 id="org-matches-title">{t("orgWalk.matchesFor",{query:query.trim()})}</h3></div><p>{t("orgWalk.matchesHint")}</p></div>{searchState==="loading"&&<p role="status">{t("orgWalk.searching")}</p>}{searchState==="empty"&&<p role="status">{t("orgWalk.noMatches")}</p>}{searchState==="error"&&<p role="status">{t("orgWalk.searchError")}</p>}<div className="org-match-list">{matches.map(match=><article className="org-match" key={match.org_id}><button type="button" className="org-match__primary" aria-label={t("orgWalk.openInHierarchy",{name:match.name})} onClick={()=>void restoreMatch(match.org_id)}>{match.name}</button><button type="button" className="org-match__profile" aria-label={t("orgWalk.openProfile",{name:match.name})} onClick={()=>onProfile?.(match.org_id)}><span>{t("orgWalk.profileAction")}</span><span aria-hidden="true">↗</span></button></article>)}</div></BorderGlow>}
    <OrgBreadcrumb path={breadcrumbColumns.map(item=>item.label)} label={t("orgWalk.path")} onBack={()=>setColumns(current=>current.slice(0,-1))} onSelect={index=>{
      const selected=breadcrumbColumns[index]
      if(selected)setColumns(current=>current.slice(0,selected.columnIndex+1))
    }}/>
    <div className="org-columns">{columns.map((column,columnIndex)=>column.leaf&&column.parent&&client.people?<BorderGlow key={`${column.parent.org_id}-people`} className="org-people-column" fillOpacity={0.055}><header><span>{t("people.title")}</span><strong>{column.parent.name}</strong></header><PeopleInTeam orgId={column.parent.org_id} client={{people:(orgId,peopleQuery,signal)=>client.people!(orgId,peopleQuery,signal)}}/></BorderGlow>:column.leaf?<div key={`${column.parent?.org_id}-leaf`} className="org-empty-column" role="status"><strong>{column.parent?.name}</strong><span>{t("people.empty")}</span></div>:<OrgColumn key={column.parent?.org_id??"root"} label={column.parent?t("orgWalk.teamLabel",{name:column.parent.name}):t("orgWalk.top")} items={column.items} columnIndex={columnIndex} expandedId={columns[columnIndex+1]?.parent?.org_id} onDrill={(node,index)=>void drill(node,index)} onProfile={orgId=>onProfile?.(orgId)} onBack={index=>setColumns(current=>current.slice(0,index))}/>)}</div>
  </section>
}

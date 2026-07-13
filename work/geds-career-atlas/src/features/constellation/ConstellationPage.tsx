import { useEffect, useMemo, useState } from "react"
import type { ConstellationSlice, SearchResult } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import { Constellation, type ConstellationNode, type NodeAnchor } from "./Constellation"
import { ConstellationBoundary } from "./ConstellationBoundary"
import { ConstellationHoverCard } from "./ConstellationHoverCard"
import type { DiscoverScope } from "../discover/FilterRail"

type SliceClient = { constellationSlice: (rootId?: string, signal?: AbortSignal) => Promise<ConstellationSlice>; constellation?: (query: string, signal?: AbortSignal) => Promise<SearchResult> }
type Inspection={node:ConstellationNode;anchor:NodeAnchor}

export function ConstellationPage({ client, query = "", focus, onProfile, scope={department:""},rootOrgId }: { client: SliceClient; query?: string; focus?: string; onProfile?: (orgId: string) => void;scope?:DiscoverScope;rootOrgId?:string }) {
  const [slice,setSlice]=useState<ConstellationSlice|null>(null)
  const [matches,setMatches]=useState<SearchResult|null>(null)
  const [rootHistory,setRootHistory]=useState<Array<string|undefined>>([rootOrgId])
  const [localFocus,setLocalFocus]=useState<string|undefined>(focus)
  const [inspection,setInspection]=useState<Inspection|null>(null)
  const [selectedLeaf,setSelectedLeaf]=useState<string|undefined>()
  const [error,setError]=useState(false)
  const {t,formatNumber}=useLanguage()
  const rootId=rootHistory.at(-1)
  const activeFocus=focus??localFocus

  useEffect(()=>{setRootHistory([rootOrgId]);setLocalFocus(undefined);setInspection(null);setSelectedLeaf(undefined)},[rootOrgId])
  useEffect(()=>{const controller=new AbortController();setError(false);client.constellationSlice(rootId,controller.signal).then(next=>{setSlice(next);setInspection(null);setSelectedLeaf(undefined)}).catch(value=>{if(value.name!=="AbortError")setError(true)});return()=>controller.abort()},[client,rootId])
  useEffect(()=>{const controller=new AbortController();if(query.trim()&&client.constellation)client.constellation(query,controller.signal).then(setMatches).catch(value=>{if(value.name!=="AbortError")setMatches(null)});else setMatches(null);return()=>controller.abort()},[client,query])

  const interestNodes=useMemo(()=>{
    const grouped=new Map<string,ConstellationNode&{department_name:string}>()
    for(const item of matches?.items??[]){if(!item.org_id)continue;if(scope.department&&item.department_name!==scope.department)continue;const current=grouped.get(item.org_id);if(current)current.value=(current.value??0)+Math.max(1,item.score);else grouped.set(item.org_id,{id:item.org_id,name:item.organization_name,value:Math.max(1,item.score),department_name:item.department_name??"",vacancy_count:item.vacancy_signal?1:0})}
    return [...grouped.values()]
  },[scope,matches])
  const hasQuery=Boolean(query.trim())
  const visualNodes:ConstellationNode[]=hasQuery?interestNodes:(slice?.nodes.map(node=>({id:node.org_id,name:node.name,value:Math.max(1,node.descendant_people_count),child_count:node.child_count,direct_people_count:node.direct_people_count,descendant_people_count:node.descendant_people_count,quality_status:node.quality_status,vacancy_count:node.vacancy_count,has_more:node.has_more}))??[])
  useEffect(()=>{if(visualNodes.length&&!visualNodes.some(node=>node.id===activeFocus)){const first=[...visualNodes].sort((a,b)=>(b.value??0)-(a.value??0)||a.id.localeCompare(b.id))[0];setLocalFocus(first.id)}},[activeFocus,visualNodes])

  function inspect(node:ConstellationNode,anchor:NodeAnchor){setLocalFocus(node.id);setInspection({node,anchor})}
  function drill(node:ConstellationNode){
    setLocalFocus(node.id)
    setInspection({node,anchor:inspection?.node.id===node.id?inspection.anchor:{x:310,y:310}})
    if(node.child_count===0){setSelectedLeaf(node.id);return}
    setSelectedLeaf(undefined)
    setRootHistory(history=>[...history,node.id])
  }
  function goBack(){setRootHistory(history=>history.length>1?history.slice(0,-1):history)}

  if(!slice&&!error)return <p role="status" className="constellation-loading">{t("constellation.loading")}</p>
  if(!slice)return <section className="constellation-page"><h1>{t("constellation.title")}</h1><p role="status">{t("constellation.unavailable")}</p></section>
  return <section className="constellation-page" id="constellation">
    <header className="constellation-heading">{rootHistory.length>1&&<button type="button" className="constellation-back" onClick={goBack}>{t("common.back")}</button>}<div><h1>{query.trim()?t("constellation.queryTitle",{query:query.trim()}):t("constellation.title")}</h1><p>{query.trim()?t("constellation.queryIntro",{count:formatNumber(interestNodes.length)}):t("constellation.intro")}</p></div></header>
    {error&&<p className="constellation-error" role="status">{t("constellation.retryStatus")}</p>}
    {hasQuery&&!matches?<p role="status" className="constellation-loading">{t("orgWalk.searching")}</p>:hasQuery&&!interestNodes.length?<p role="status" className="constellation-empty">{t("discover.noMatch")}</p>:<div className="constellation-stage"><ConstellationBoundary nodes={visualNodes} label={t("constellation.map")} focus={activeFocus} onFocus={id=>{const node=visualNodes.find(item=>item.id===id);if(node)drill(node)}}><Constellation nodes={visualNodes} focus={activeFocus} onDrill={drill} onInspect={inspect} topLevel={!rootId}/></ConstellationBoundary>{inspection&&<ConstellationHoverCard node={inspection.node} anchor={inspection.anchor} onProfile={onProfile}/>}</div>}
    {selectedLeaf&&<p className="constellation-leaf-status" role="status">{t("orgWalk.noChildren")}</p>}
    <footer className="constellation-legend"><span><i className="legend-dot legend-dot--selected" />{t("constellation.selected")}</span><span><i className="legend-dot" />{query.trim()?t("constellation.matchingTeam"):t("constellation.organization")}</span><span>{t("constellation.area",{measure:query.trim()?t("constellation.matchStrength"):t("constellation.peopleMeasure")})}</span>{slice.truncated&&<span>{t("constellation.aggregated")}</span>}</footer>
  </section>
}

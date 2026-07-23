import { useEffect, useMemo, useRef, useState } from "react"
import type { ConstellationSlice, SearchResult } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import { Constellation, type ConstellationNode } from "./Constellation"
import { ConstellationBoundary } from "./ConstellationBoundary"
import { ConstellationInfoPanel } from "./ConstellationInfoPanel"
import { DotField } from "./DotField"
import type { DiscoverScope } from "../discover/FilterRail"
import { BorderGlow } from "../../components/BorderGlow"

type SliceClient = { constellationSlice: (rootId?: string, signal?: AbortSignal) => Promise<ConstellationSlice>; constellation?: (query: string, signal?: AbortSignal) => Promise<SearchResult> }
type View={rootId?:string;slice:ConstellationSlice|null;history:Array<string|undefined>}

export function ConstellationPage({ client, query = "", focus, onProfile, scope={department:""},rootOrgId }: { client: SliceClient; query?: string; focus?: string; onProfile?: (orgId: string) => void;scope?:DiscoverScope;rootOrgId?:string }) {
  const [view,setView]=useState<View>({rootId:rootOrgId,slice:null,history:[rootOrgId]})
  const [matches,setMatches]=useState<SearchResult|null>(null)
  const [localFocus,setLocalFocus]=useState<string|undefined>(focus)
  const [inspection,setInspection]=useState<ConstellationNode|null>(null)
  const [selectedLeaf,setSelectedLeaf]=useState<string|undefined>()
  const [pending,setPending]=useState<string|undefined>()
  const [error,setError]=useState(false)
  const cache=useRef(new Map<string|undefined,ConstellationSlice>())
  const request=useRef<{id:number;controller?:AbortController}>({id:0})
  const {t,formatNumber}=useLanguage()
  const [darkTheme,setDarkTheme]=useState(()=>document.documentElement.dataset.theme==="dark")
  const rootId=view.rootId
  const activeFocus=focus??localFocus

  function open(root:string|undefined,history:Array<string|undefined>,node?:ConstellationNode){
    request.current.controller?.abort();const controller=new AbortController();const id=request.current.id+1;request.current={id,controller};setPending(node?.name??"");setError(false)
    const cached=cache.current.get(root)
    const load=cached?Promise.resolve(cached):client.constellationSlice(root,controller.signal).then(slice=>{cache.current.set(root,slice);return slice})
    load.then(slice=>{if(request.current.id!==id)return;setView({rootId:root,slice,history});setLocalFocus(node?.id);setSelectedLeaf(undefined);setPending(undefined)}).catch(value=>{if(value.name!=="AbortError"&&request.current.id===id){setError(true);setPending(undefined)}})
  }
  useEffect(()=>{cache.current.clear();setInspection(null);setSelectedLeaf(undefined);setLocalFocus(undefined);open(rootOrgId,[rootOrgId]);return()=>request.current.controller?.abort()},[client,rootOrgId])
  useEffect(()=>{const root=document.documentElement;const observer=new MutationObserver(()=>setDarkTheme(root.dataset.theme==="dark"));observer.observe(root,{attributes:true,attributeFilter:["data-theme"]});return()=>observer.disconnect()},[])
  useEffect(()=>{const controller=new AbortController();if(query.trim()&&client.constellation)client.constellation(query,controller.signal).then(setMatches).catch(value=>{if(value.name!=="AbortError")setMatches(null)});else setMatches(null);return()=>controller.abort()},[client,query])

  const interestNodes=useMemo(()=>{const grouped=new Map<string,ConstellationNode&{department_name:string}>();for(const item of matches?.items??[]){if(!item.org_id)continue;if(scope.department&&item.department_name!==scope.department)continue;const current=grouped.get(item.org_id);if(current)current.value=(current.value??0)+Math.max(1,item.score);else grouped.set(item.org_id,{id:item.org_id,name:item.organization_name,value:Math.max(1,item.score),department_name:item.department_name??"",vacancy_count:item.vacancy_signal?1:0})}return [...grouped.values()]},[scope,matches])
  const hasQuery=Boolean(query.trim())
  const visualNodes:ConstellationNode[]=useMemo(()=>hasQuery?interestNodes:(view.slice?.nodes.filter(node=>node.org_id!==rootId).map(node=>({id:node.org_id,name:node.name,value:Math.max(1,node.descendant_people_count),child_count:node.child_count,direct_people_count:node.direct_people_count,descendant_people_count:node.descendant_people_count,quality_status:node.quality_status,vacancy_count:node.vacancy_count,has_more:node.has_more}))??[]),[hasQuery,interestNodes,rootId,view.slice])
  useEffect(()=>{if(visualNodes.length&&!visualNodes.some(node=>node.id===activeFocus)){const first=[...visualNodes].sort((a,b)=>(b.value??0)-(a.value??0)||a.id.localeCompare(b.id))[0];setLocalFocus(first.id)}},[activeFocus,visualNodes])
  function drill(node:ConstellationNode){setInspection(null);setLocalFocus(node.id);if(node.child_count===0){setSelectedLeaf(node.id);return}setSelectedLeaf(undefined);open(node.id,[...view.history,node.id],node)}
  function selectNode(node:ConstellationNode){setLocalFocus(node.id);setSelectedLeaf(undefined);setInspection(node)}
  function goBack(){if(view.history.length>1){const history=view.history.slice(0,-1);open(history.at(-1),history)}}

  if(!view.slice&&!error)return <p role="status" className="constellation-loading">{t("constellation.loading")}</p>
  if(!view.slice)return <section className="constellation-page"><h1>{t("constellation.title")}</h1><p role="status">{t("constellation.unavailable")}</p></section>
  return <section className="constellation-page" id="constellation">
    <header className="constellation-heading">{view.history.length>1&&<button type="button" className="constellation-back" onClick={goBack}>{t("common.back")}</button>}<div><h1>{query.trim()?t("constellation.queryTitle",{query:query.trim()}):t("constellation.title")}</h1><p>{query.trim()?t("constellation.queryIntro",{count:formatNumber(interestNodes.length)}):t("constellation.intro")}</p></div></header>
    {error&&<p className="constellation-error" role="status">{t("constellation.retryStatus")}</p>}{pending&&<p className="constellation-pending" role="status">{t("constellation.opening",{name:pending})}</p>}
    {hasQuery&&!matches?<p role="status" className="constellation-loading">{t("orgWalk.searching")}</p>:hasQuery&&!interestNodes.length?<p role="status" className="constellation-empty">{t("discover.noMatch")}</p>:<BorderGlow className="constellation-stage" data-testid="constellation-stage" borderRadius={22} fillOpacity={darkTheme?0.1:0.06} backgroundColor="var(--canvas)" onClick={event=>{const target=event.target as Element;if(!target.closest(".constellation-node, .constellation-toolbar, .constellation-info-panel, [role='option']"))setInspection(null)}}><DotField bulgeStrength={58} dotSpacing={18} cursorRadius={600} waveAmplitude={1} glowRadius={110}/><ConstellationBoundary nodes={visualNodes} label={t("constellation.map")} focus={activeFocus} onSelect={id=>{const node=visualNodes.find(item=>item.id===id);if(node)selectNode(node)}} onDrill={id=>{const node=visualNodes.find(item=>item.id===id);if(node)drill(node)}}><Constellation nodes={visualNodes} focus={activeFocus} onDrill={drill} onSelect={selectNode} topLevel={!rootId}/></ConstellationBoundary>{inspection&&<ConstellationInfoPanel node={inspection} onClose={()=>setInspection(null)} onProfile={onProfile}/>}</BorderGlow>}
    {selectedLeaf&&<p className="constellation-leaf-status" role="status">{t("orgWalk.noChildren")}</p>}
    <footer className="constellation-legend"><span><i className="legend-dot legend-dot--selected" />{t("constellation.selected")}</span><span><i className="legend-dot" />{query.trim()?t("constellation.matchingTeam"):t("constellation.organization")}</span><span>{t("constellation.area",{measure:query.trim()?t("constellation.matchStrength"):t("constellation.peopleMeasure")})}</span>{view.slice.truncated&&<span>{t("constellation.aggregated")}</span>}</footer>
  </section>
}

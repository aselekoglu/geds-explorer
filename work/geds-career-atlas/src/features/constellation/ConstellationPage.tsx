import { useEffect, useMemo, useState } from "react"
import type { ConstellationSlice, SearchResult } from "../../api/types"
import { Constellation } from "./Constellation"

type SliceClient={constellationSlice:(rootId?:string,signal?:AbortSignal)=>Promise<ConstellationSlice>;constellation?:(query:string,signal?:AbortSignal)=>Promise<SearchResult>}

export function ConstellationPage({client,query="",focus,onFocus}:{client:SliceClient;query?:string;focus?:string;onFocus?:(orgId:string)=>void}){
  const [slice,setSlice]=useState<ConstellationSlice|null>(null)
  const [matches,setMatches]=useState<SearchResult|null>(null)
  const [rootId,setRootId]=useState<string|undefined>(focus)
  const [localFocus,setLocalFocus]=useState<string|undefined>(focus)
  const [error,setError]=useState(false)
  const activeFocus=focus??localFocus
  useEffect(()=>{const controller=new AbortController();setError(false);client.constellationSlice(rootId,controller.signal).then(setSlice).catch(value=>{if(value.name!=="AbortError")setError(true)});return()=>controller.abort()},[client,rootId])
  useEffect(()=>{const controller=new AbortController();if(query.trim()&&client.constellation){client.constellation(query,controller.signal).then(setMatches).catch(value=>{if(value.name!=="AbortError")setMatches(null)})}else setMatches(null);return()=>controller.abort()},[client,query])
  const interestNodes=useMemo(()=>{const grouped=new Map<string,{id:string;name:string;value:number}>();for(const item of matches?.items??[]){if(!item.org_id)continue;const current=grouped.get(item.org_id);if(current)current.value+=Math.max(1,item.score);else grouped.set(item.org_id,{id:item.org_id,name:item.organization_name,value:Math.max(1,item.score)})}return [...grouped.values()]},[matches])
  const visualNodes=query.trim()&&interestNodes.length?interestNodes:(slice?.nodes.map(node=>({id:node.org_id,name:node.name,value:Math.max(1,node.descendant_people_count)}))??[])
  useEffect(()=>{if(visualNodes.length&&!visualNodes.some(node=>node.id===activeFocus)){const first=[...visualNodes].sort((a,b)=>b.value-a.value||a.id.localeCompare(b.id))[0];setLocalFocus(first.id);onFocus?.(first.id)}},[activeFocus,onFocus,visualNodes])
  function select(orgId:string){setLocalFocus(orgId);onFocus?.(orgId)}
  function reset(){setRootId(undefined);setLocalFocus(undefined)}
  if(error)return <section className="constellation-page"><h1>Government at a glance</h1><p role="status">The visual map is unavailable. Use Organization Walk to continue exploring.</p></section>
  if(!slice)return <p role="status" className="constellation-loading">Loading government map...</p>
  const selected=slice.nodes.find(node=>node.org_id===activeFocus)
  const selectedMatch=matches?.items.find(item=>item.org_id===activeFocus)
  return <section className="constellation-page" id="constellation">
    <header className="constellation-heading"><div><h1>{query.trim()?`Where “${query.trim()}” appears`:`Government at a glance`}</h1><p>{query.trim()?`${interestNodes.length.toLocaleString()} relevant teams illuminated from observed organization and role-title evidence.`:`Explore organizations and discover where your interests connect to Canada's public service.`}</p></div>{rootId&&<button type="button" onClick={reset}>All government</button>}</header>
    <div className="constellation-stage"><Constellation nodes={visualNodes} focus={activeFocus} onFocus={select}/>{(selected||selectedMatch)&&<aside className="constellation-evidence" aria-live="polite"><h2>{selected?.name??selectedMatch?.organization_name}</h2><p><strong>Matched because</strong> {selectedMatch?.evidence[0]?.source_text??`this organization appears in the selected hierarchy slice.`}</p>{selected&&<dl><div><dt>People indexed</dt><dd>{selected.descendant_people_count.toLocaleString()}</dd></div><div><dt>Child teams</dt><dd>{selected.child_count}</dd></div></dl>}{selected?.child_count?<button type="button" onClick={()=>setRootId(selected.org_id)}>Explore branch</button>:null}</aside>}</div>
    <footer className="constellation-legend"><span><i className="legend-dot legend-dot--selected"/>Selected</span><span><i className="legend-dot"/>{query.trim()?`Matching team`:`Organization`}</span><span>Circle area = {query.trim()?`match strength`:`people indexed`}</span>{slice.truncated&&<span>This branch is aggregated for performance.</span>}</footer>
  </section>
}

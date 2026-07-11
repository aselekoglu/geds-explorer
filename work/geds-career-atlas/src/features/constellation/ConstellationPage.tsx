import { useEffect, useState } from "react"
import type { ConstellationSlice } from "../../api/types"
import { Constellation } from "./Constellation"

type SliceClient={constellationSlice:(rootId?:string,signal?:AbortSignal)=>Promise<ConstellationSlice>}

export function ConstellationPage({client,onFocus}:{client:SliceClient;onFocus?:(orgId:string)=>void}){
  const [slice,setSlice]=useState<ConstellationSlice|null>(null)
  const [focus,setFocus]=useState<string>()
  const [error,setError]=useState(false)
  useEffect(()=>{const controller=new AbortController();client.constellationSlice(undefined,controller.signal).then(setSlice).catch(value=>{if(value.name!=="AbortError")setError(true)});return()=>controller.abort()},[client])
  function select(orgId:string){setFocus(orgId);onFocus?.(orgId)}
  if(error)return <section><h2>Government Constellation</h2><p role="status">The visual map is unavailable. Use Organization Walk to continue exploring.</p></section>
  if(!slice)return <p role="status">Loading government map...</p>
  const selected=slice.nodes.find(node=>node.org_id===focus)
  return <section className="constellation-page" id="constellation"><header><h2>Government Constellation</h2><p>Size represents people indexed in each organization branch. Select a system to inspect it.</p></header><Constellation nodes={slice.nodes.map(node=>({id:node.org_id,name:node.name,value:Math.max(1,node.descendant_people_count)}))} focus={focus} onFocus={select}/>{selected&&<aside aria-live="polite"><h3>{selected.name}</h3><p>Matched because this organization is present in the selected government hierarchy slice.</p><dl><div><dt>People indexed</dt><dd>{selected.descendant_people_count.toLocaleString()}</dd></div><div><dt>Child teams</dt><dd>{selected.child_count}</dd></div></dl></aside>}{slice.truncated&&<p role="note">This branch is aggregated to keep the map responsive.</p>}</section>
}

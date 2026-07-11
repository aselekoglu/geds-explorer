import { useEffect, useState } from "react"
import type { TourResult } from "../../api/types"
import type { ExplorerSearch } from "../../state/explorerSearch"
import { listSavedViews, saveView } from "../../state/savedView"

type TourClient={tours:(signal?:AbortSignal)=>Promise<TourResult>}
type TourState={q:string;categories:string[];mode:"constellation";focus?:string}
const queries:Record<string,string>={ai:"AI",software:"software",cybersecurity:"cybersecurity",policy:"policy",data:"data"}

export function SavedMap({client,onOpen,current,lang="en"}:{client:TourClient;onOpen:(state:TourState)=>void;current?:ExplorerSearch;lang?:"en"|"fr"}){
  const [result,setResult]=useState<TourResult|null>(null)
  const [error,setError]=useState(false)
  const [saved,setSaved]=useState(listSavedViews)
  useEffect(()=>{const controller=new AbortController();client.tours(controller.signal).then(setResult).catch(value=>{if(value.name!=="AbortError")setError(true)});return()=>controller.abort()},[client])
  if(error)return <p role="status">Tours are unavailable right now.</p>
  if(!result)return <p role="status">Loading guided tours...</p>
  function saveCurrent(){if(!current)return;saveView({...current,label:current.q?`${current.q} constellation`:"Government map"});setSaved(listSavedViews())}
  return <section className="saved-map" id="tours"><header><div><h2>Guided ways to explore government</h2><p>Start with an interest, then follow snapshot-validated organization references.</p></div>{current&&<button type="button" onClick={saveCurrent}>Save current map</button>}</header><ul className="tour-list">{result.items.map(tour=>{const legacy=tour as typeof tour&{label?:string};const title=tour.title?.[lang]??legacy.label??tour.id;const description=tour.description?.[lang]??"Open this institution in the government map.";const stops=tour.stops??[];return <li key={tour.id}><div><h3>{title}</h3><p>{description}</p><small>{stops.filter(stop=>stop.available).length}/{stops.length} stops available in this snapshot</small></div><button type="button" onClick={()=>onOpen({q:queries[tour.id]??tour.id,categories:tour.categories??[],mode:"constellation",focus:tour.initial_focus})}>{title}</button></li>})}</ul>{saved.length>0&&<section className="saved-views"><h3>Saved locally on this device</h3><ul>{saved.map(view=><li key={view.id}><span>{view.label}</span><button type="button" onClick={()=>onOpen({q:view.q,categories:view.categories,mode:"constellation",focus:view.focus})}>Restore</button></li>)}</ul></section>}</section>
}

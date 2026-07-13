import { useEffect, useState } from "react"
import type { QueryInterpretation, SearchResult } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import type { DiscoverScope } from "./FilterRail"
import { InterpretationChips } from "./InterpretationChips"
import { MatchCard } from "./MatchCard"

type Item=SearchResult["items"][number]
type Client={search:(q:string)=>Promise<{items:Item[];interpretation?:QueryInterpretation}>}
export type SearchKind="all"|"topics"|"teams"|"people"

export function DiscoverPage({search,client,scope={department:""},onScopeChange}:{search:string;client:Client;scope?:DiscoverScope;onScopeChange?:(next:DiscoverScope)=>void}){
  const [items,setItems]=useState<Item[]>([])
  const [interpretation,setInterpretation]=useState<QueryInterpretation|undefined>()
  const [kind,setKind]=useState<SearchKind>("all")
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState("")
  const {t}=useLanguage()
  useEffect(()=>{
    if(!search){setItems([]);return}
    setLoading(true)
    const timer=setTimeout(()=>{setError("");client.search(search).then(result=>{setItems(result.items);setInterpretation(result.interpretation)}).catch(()=>setError(t("discover.error"))).finally(()=>setLoading(false))},250)
    return()=>clearTimeout(timer)
  },[search,client,t])
  const visibleItems=items.filter(item=>(!scope.department||item.department_name===scope.department)&&(kind==="all"||(kind==="teams"&&item.entity_kind==="organization")||(kind==="people"&&item.entity_kind==="person")))
  const showTopics=kind==="all"||kind==="topics"
  const labels:Record<SearchKind,string>={all:t("discover.kindAll"),topics:t("discover.kindTopics"),teams:t("discover.kindTeams"),people:t("discover.kindPeople")}
  return <section aria-label={t("discover.label")} className="discover-results">
    <fieldset className="search-kind"><legend>{t("discover.resultType")}</legend>{(Object.keys(labels) as SearchKind[]).map(value=><label key={value}><input type="radio" name="search-kind" value={value} checked={kind===value} onChange={()=>setKind(value)}/><span>{labels[value]}</span></label>)}</fieldset>
    {showTopics&&<InterpretationChips interpretation={interpretation} scope={scope} onScopeChange={onScopeChange}/>} 
    {loading&&<p aria-live="polite">{t("discover.loading")}</p>}
    {error&&<p role="alert">{error}</p>}
    {!loading&&!error&&search&&!showTopics&&visibleItems.length===0&&<p>{t("discover.noMatch")}</p>}
    <div className="match-grid">{kind!=="topics"&&visibleItems.map(item=><MatchCard key={item.entity_id} item={item}/>)}</div>
  </section>
}

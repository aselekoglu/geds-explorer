import { useEffect, useState } from "react"
import type { QueryInterpretation } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import type { DiscoverScope } from "./FilterRail"
import { InterpretationChips } from "./InterpretationChips"
import { MatchCard } from "./MatchCard"

type Item={entity_id:string;entity_kind:string;title:string;organization_name:string;department_name?:string;score:number;confidence:string;vacancy_signal?:boolean;evidence:Array<{field:string;matched_phrase:string;source_text:string;weight:number;category_id:string}>}
type Client={search:(q:string)=>Promise<{items:Item[];interpretation?:QueryInterpretation}>}

export function DiscoverPage({search,client,scope={department:""},onScopeChange}:{search:string;client:Client;scope?:DiscoverScope;onScopeChange?:(next:DiscoverScope)=>void}){
  const [items,setItems]=useState<Item[]>([])
  const [interpretation,setInterpretation]=useState<QueryInterpretation|undefined>()
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState("")
  const {t}=useLanguage()
  useEffect(()=>{
    if(!search){setItems([]);return}
    setLoading(true)
    const timer=setTimeout(()=>{setError("");client.search(search).then(result=>{setItems(result.items);setInterpretation(result.interpretation)}).catch(()=>setError(t("discover.error"))).finally(()=>setLoading(false))},250)
    return()=>clearTimeout(timer)
  },[search,client,t])
  const visibleItems=items.filter(item=>!scope.department||item.department_name===scope.department)
  return <section aria-label={t("discover.label")} className="discover-results">
    <InterpretationChips interpretation={interpretation} scope={scope} onScopeChange={onScopeChange}/>
    {loading&&<p aria-live="polite">{t("discover.loading")}</p>}
    {error&&<p role="alert">{error}</p>}
    {!loading&&!error&&search&&visibleItems.length===0&&<p>{t("discover.noMatch")}</p>}
    <div className="match-grid">{visibleItems.map(item=><MatchCard key={item.entity_id} item={item}/>)}</div>
  </section>
}

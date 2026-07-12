import { useEffect, useState } from "react"
import type { PeoplePage, PeopleQuery } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"

export type PeopleClient={people:(orgId:string,query?:PeopleQuery,signal?:AbortSignal)=>Promise<PeoplePage>}

export function PeopleInTeam({orgId,client}:{orgId:string;client:PeopleClient}){
  const {t,formatNumber}=useLanguage()
  const [query,setQuery]=useState("")
  const [classification,setClassification]=useState("")
  const [sort,setSort]=useState<"name"|"title">("name")
  const [data,setData]=useState<PeoplePage|null>(null)
  const [availableClassifications,setAvailableClassifications]=useState<string[]>([])
  const [error,setError]=useState(false)
  const [retry,setRetry]=useState(0)
  useEffect(()=>{
    const controller=new AbortController()
    setData(null);setError(false)
    client.people(orgId,{q:query,classification:classification||undefined,sort,limit:50,offset:0},controller.signal).then(result=>{setData(result);setAvailableClassifications(result.available_classifications)}).catch(value=>{if(value?.name!=="AbortError")setError(true)})
    return()=>controller.abort()
  },[client,orgId,query,classification,sort,retry])
  return <section className="people-in-team" aria-labelledby="people-in-team-title">
    <h3 id="people-in-team-title">{t("people.title")}</h3><p>{t("people.intro")}</p>
    <div className="people-controls"><label>{t("people.search")}<input type="search" value={query} onChange={event=>setQuery(event.target.value)}/></label><label>{t("people.classification")}<select value={classification} onChange={event=>setClassification(event.target.value)}><option value="">{t("people.allClassifications")}</option>{availableClassifications.map(value=><option key={value} value={value}>{value}</option>)}</select></label><label>{t("people.sort")}<select value={sort} onChange={event=>setSort(event.target.value as "name"|"title")}><option value="name">{t("people.sortName")}</option><option value="title">{t("people.sortTitle")}</option></select></label></div>
    {error&&<div role="alert"><p>{t("people.error")}</p><button type="button" onClick={()=>setRetry(value=>value+1)}>{t("people.retry")}</button></div>}{!error&&!data&&<p role="status">{t("people.loading")}</p>}
    {data&&<><p className="people-count" role="status">{t("people.count",{count:formatNumber(data.total)})}</p>{data.items.length===0?<p>{t("people.empty")}</p>:<div className="people-table-wrap"><table><thead><tr><th>{t("people.name")}</th><th>{t("people.observedTitle")}</th><th>{t("people.classificationShort")}</th><th><span className="sr-only">{t("people.source")}</span></th></tr></thead><tbody>{data.items.map(person=><tr key={person.person_id}><td data-label={t("people.name")}>{person.display_name}</td><td data-label={t("people.observedTitle")}>{person.observed_title||"—"}</td><td data-label={t("people.classificationShort")}><span className="classification-list">{person.observed_classifications.map(value=><span className="classification-badge" aria-label={t("people.classificationObserved",{value})} title={t("people.classificationHelp")} key={value}>{value}</span>)}</span></td><td data-label={t("people.source")}>{person.source_url?<a href={person.source_url} target="_blank" rel="noopener noreferrer">{t("people.official")}</a>:<span>{t("people.unavailable")}</span>}</td></tr>)}</tbody></table></div>}</>}
  </section>
}

import { useEffect, useMemo, useState } from "react"
import type { PeoplePage, PeopleQuery, PublicPerson } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import { normalizeObservedTitle } from "../profile/titleGroups"

export type PeopleClient={people:(orgId:string,query?:PeopleQuery,signal?:AbortSignal)=>Promise<PeoplePage>}
type PeopleGroup={key:string;label:string;empty:boolean;people:PublicPerson[]}

function groupPeople(items:PublicPerson[]):PeopleGroup[]{
  const groups=new Map<string,PeopleGroup>()
  for(const person of items){
    const label=normalizeObservedTitle(person.observed_title)
    const key=label.toLocaleLowerCase()
    const group=groups.get(key)??{key,label,empty:!label,people:[]}
    group.people.push(person);groups.set(key,group)
  }
  return [...groups.values()].sort((a,b)=>Number(a.empty)-Number(b.empty)||a.label.localeCompare(b.label))
}

export function PeopleInTeam({orgId,client}:{orgId:string;client:PeopleClient}){
  const {t,formatNumber}=useLanguage()
  const [query,setQuery]=useState("")
  const [classification,setClassification]=useState("")
  const [data,setData]=useState<PeoplePage|null>(null)
  const [availableClassifications,setAvailableClassifications]=useState<string[]>([])
  const [error,setError]=useState(false)
  const [retry,setRetry]=useState(0)
  useEffect(()=>{
    const controller=new AbortController();setData(null);setError(false)
    client.people(orgId,{q:query,classification:classification||undefined,sort:"title",limit:200,offset:0},controller.signal).then(result=>{setData(result);setAvailableClassifications(result.available_classifications)}).catch(value=>{if(value?.name!=="AbortError")setError(true)})
    return()=>controller.abort()
  },[client,orgId,query,classification,retry])
  const groups=useMemo(()=>groupPeople(data?.items??[]),[data])
  const personRow=(person:PublicPerson)=><li className="person-row" key={person.person_id}><div><strong>{person.display_name}</strong><span className="classification-list">{person.observed_classifications.map(value=><span className="classification-badge" aria-label={t("people.classificationObserved",{value})} title={t("people.classificationHelp")} key={value}>{value}</span>)}</span></div>{person.source_url?<a href={person.source_url} target="_blank" rel="noopener noreferrer">{t("people.official")}</a>:<span className="source-unavailable">{t("people.unavailable")}</span>}</li>
  return <section className="people-in-team" aria-labelledby="people-in-team-title">
    <h3 id="people-in-team-title">{t("people.title")}</h3><p>{t("people.intro")}</p>
    <div className="people-controls"><label>{t("people.search")}<input type="search" value={query} onChange={event=>setQuery(event.target.value)}/></label><label>{t("people.classification")}<select value={classification} onChange={event=>setClassification(event.target.value)}><option value="">{t("people.allClassifications")}</option>{availableClassifications.map(value=><option key={value} value={value}>{value}</option>)}</select></label></div>
    {error&&<div role="alert"><p>{t("people.error")}</p><button type="button" onClick={()=>setRetry(value=>value+1)}>{t("people.retry")}</button></div>}{!error&&!data&&<p role="status">{t("people.loading")}</p>}
    {data&&<><p className="people-count" role="status">{t("people.count",{count:formatNumber(data.total)})}</p>{groups.length===0?<p>{t("people.empty")}</p>:<div className="people-title-groups">{groups.map(group=>group.empty?<details className="people-title-group people-title-group--empty" key={group.key}><summary>{t("profile.noTitle")} · {group.people.length}</summary><ul>{group.people.map(personRow)}</ul></details>:<section className="people-title-group" key={group.key}><h4><span>{group.label}</span> · {group.people.length}</h4><ul>{group.people.map(personRow)}</ul></section>)}</div>}</>}
  </section>
}

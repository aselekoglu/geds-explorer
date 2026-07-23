import { useState } from "react"
import { useLanguage } from "../../i18n/i18n"
import type { SearchResult } from "../../api/types"
import { BorderGlow } from "../../components/BorderGlow"

type Item=SearchResult["items"][number]

export function MatchCard({item}:{item:Item}){
  const [expanded,setExpanded]=useState(false)
  const {t}=useLanguage()
  const evidence=expanded?item.evidence:item.evidence.slice(0,3)
  const label=item.display_name||item.organization_name||item.title
  return <BorderGlow as="article" aria-label={label} className={`match-card match-card--${item.entity_kind}`} fillOpacity={0.045}>
    <h2>{label}</h2>
    {item.entity_kind==="person"&&item.title&&<p className="match-title">{item.title}</p>}
    {item.department_name&&<p>{item.department_name}</p>}
    <p><strong>{t("common.matchedBecause")}</strong> {evidence.map(record=>t("discover.evidence",{field:record.field,phrase:record.matched_phrase})).join(", ")}</p>
    {item.evidence.length>3&&<button type="button" onClick={()=>setExpanded(value=>!value)}>{expanded?t("discover.showLessEvidence"):t("discover.showAllEvidence")}</button>}
    {item.entity_kind==="person"&&item.source_url&&<a href={item.source_url} target="_blank" rel="noopener noreferrer">{t("people.official")}</a>}
  </BorderGlow>
}

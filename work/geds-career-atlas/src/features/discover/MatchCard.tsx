import { useState } from "react"
import { useLanguage } from "../../i18n/i18n"
import type { SearchResult } from "../../api/types"

type Item=SearchResult["items"][number]

export function MatchCard({item}:{item:Item}){
  const [expanded,setExpanded]=useState(false)
  const {t}=useLanguage()
  const evidence=expanded?item.evidence:item.evidence.slice(0,3)
  return <article aria-label={item.organization_name||item.title} className="match-card">
    <h2>{item.organization_name||item.title}</h2>
    {item.department_name&&<p>{item.department_name}</p>}
    <p>{t("common.confidence",{level:t(`common.${item.confidence}`)})}</p>
    <p><strong>{t("common.matchedBecause")}</strong> {evidence.map(record=>t("discover.evidence",{field:record.field,phrase:record.matched_phrase})).join(", ")}</p>
    {item.evidence.length>3&&<button type="button" onClick={()=>setExpanded(value=>!value)}>{expanded?t("discover.showLessEvidence"):t("discover.showAllEvidence")}</button>}
    {item.vacancy_signal&&<small>{t("discover.vacancy")}</small>}
  </article>
}

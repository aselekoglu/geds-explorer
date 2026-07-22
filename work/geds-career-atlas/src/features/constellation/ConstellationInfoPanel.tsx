import { useEffect } from "react"
import { useLanguage } from "../../i18n/i18n"
import type { ConstellationNode } from "./Constellation"

export function ConstellationInfoPanel({node,onClose,onProfile}:{node:ConstellationNode;onClose:()=>void;onProfile?:(orgId:string)=>void}){
  const {t,formatNumber}=useLanguage()
  useEffect(()=>{const close=(event:KeyboardEvent)=>{if(event.key==="Escape")onClose()};window.addEventListener("keydown",close);return()=>window.removeEventListener("keydown",close)},[onClose])
  return <aside id={`constellation-facts-${node.id}`} className="constellation-info-panel" aria-live="polite" onClick={event=>event.stopPropagation()}>
    <h2>{node.name}</h2><dl><div><dt>{t("constellation.directPeople")}</dt><dd>{formatNumber(node.direct_people_count??0)}</dd></div><div><dt>{t("constellation.branchPeople")}</dt><dd>{formatNumber(node.descendant_people_count??node.value??0)}</dd></div><div><dt>{t("common.childTeams")}</dt><dd>{formatNumber(node.child_count??0)}</dd></div></dl>
    {node.child_count===0&&<p className="constellation-info-panel__leaf">{t("orgWalk.noChildren")}</p>}{onProfile&&<button type="button" onClick={()=>onProfile(node.id)}>{t("orgWalk.openProfile",{name:node.name})}</button>}
  </aside>
}

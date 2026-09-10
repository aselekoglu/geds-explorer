import { useLanguage } from "../../i18n/i18n"
import type { ConstellationNode } from "./Constellation"

export function ConstellationInfoPanel({node,onClose,onProfile}:{node:ConstellationNode;onClose:()=>void;onProfile?:(orgId:string)=>void}){
  const {t,formatNumber}=useLanguage()
  const searchMatch=node.match_count!==undefined
  return <aside id={`constellation-facts-${node.id}`} className="constellation-info-panel" aria-live="polite" tabIndex={-1} onKeyDown={event=>{if(event.key==="Escape")onClose()}} onClick={event=>event.stopPropagation()}>
    <h2>{node.name}</h2><dl>{searchMatch?<><div><dt>{t("constellation.matchRecords")}</dt><dd>{formatNumber(node.match_count ?? 0)}</dd></div><div><dt>{t("constellation.matchScore")}</dt><dd>{formatNumber(node.value ?? 0)}</dd></div></>:<><div><dt>{t("constellation.directPeople")}</dt><dd>{node.direct_people_count===undefined?t("common.unknown"):formatNumber(node.direct_people_count)}</dd></div><div><dt>{t("constellation.branchPeople")}</dt><dd>{node.descendant_people_count===undefined?t("common.unknown"):formatNumber(node.descendant_people_count)}</dd></div><div><dt>{t("common.childTeams")}</dt><dd>{node.child_count===undefined?t("common.unknown"):formatNumber(node.child_count)}</dd></div></>}</dl>
    {node.child_count===0&&<p className="constellation-info-panel__leaf">{t("orgWalk.noChildren")}</p>}{onProfile&&<button type="button" onClick={()=>onProfile(node.id)}>{t("orgWalk.openProfile",{name:node.name})}</button>}
  </aside>
}

import { useLanguage } from "../../i18n/i18n"
import type { ConstellationNode, NodeAnchor } from "./Constellation"

export function ConstellationHoverCard({node,anchor,onProfile}:{node:ConstellationNode;anchor:NodeAnchor;onProfile?:(orgId:string)=>void}){
  const {t,formatNumber}=useLanguage()
  const left=Math.min(70,Math.max(2,(anchor.x/620)*100))
  const top=Math.min(68,Math.max(2,(anchor.y/620)*100))
  return <aside id={`constellation-facts-${node.id}`} className="constellation-hover-card" style={{left:`${left}%`,top:`${top}%`}} aria-live="polite">
    <h2>{node.name}</h2>
    <dl>
      <div><dt>{t("constellation.directPeople")}</dt><dd>{formatNumber(node.direct_people_count??0)}</dd></div>
      <div><dt>{t("constellation.branchPeople")}</dt><dd>{formatNumber(node.descendant_people_count??node.value??0)}</dd></div>
      <div><dt>{t("common.childTeams")}</dt><dd>{formatNumber(node.child_count??0)}</dd></div>
    </dl>
    {node.child_count===0&&<p className="constellation-hover-card__leaf">{t("orgWalk.noChildren")}</p>}
    {onProfile&&<button type="button" onClick={()=>onProfile(node.id)}>{t("orgWalk.openProfile",{name:node.name})}</button>}
  </aside>
}

import type { KeyboardEvent } from "react"
import { useLanguage } from "../../i18n/i18n"
import { buildPackLayout } from "./layout"
import { institutionAbbreviation, wrapBubbleLabel } from "./labels"

export type ConstellationNode = { id: string; name: string; value?: number; child_count?:number; direct_people_count?:number; descendant_people_count?:number; quality_status?: string; vacancy_count?: number; has_more?: boolean }
export type NodeAnchor={x:number;y:number}

export function Constellation({ nodes, focus, onFocus, onDrill, onInspect, topLevel = false }: { nodes: ConstellationNode[]; focus?: string; onFocus?: (id: string) => void; onDrill?:(node:ConstellationNode)=>void;onInspect?:(node:ConstellationNode,anchor:NodeAnchor)=>void; topLevel?: boolean }) {
  const { t } = useLanguage()
  const positioned = buildPackLayout(nodes, 620, 620)
  const details = new Map(nodes.map(node => [node.id, node]))
  function drill(node:ConstellationNode){onDrill?.(node);onFocus?.(node.id)}
  function keySelect(event: KeyboardEvent<SVGGElement>, node: ConstellationNode) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); drill(node) } }
  return <section aria-label={t("constellation.aria")}>
    <svg viewBox="0 0 620 620" role="group" aria-labelledby="constellation-title constellation-description">
      <title id="constellation-title">{t("constellation.graphicTitle")}</title>
      <desc id="constellation-description">{t("constellation.graphicDescription")}</desc>
      {positioned.map(node => {
        const detail = details.get(node.id)
        const classes = [node.id === focus ? "is-selected" : "", detail?.quality_status && detail.quality_status !== "complete" ? "has-quality-warning" : "", detail?.vacancy_count ? "has-vacancy" : ""].filter(Boolean).join(" ")
        const description = [detail?.quality_status ? t("constellation.quality", { status: detail.quality_status.replaceAll("_", " ") }) : "", detail?.vacancy_count ? t("discover.vacancy") : "", detail?.has_more ? t("constellation.moreAvailable") : ""].filter(Boolean).join(". ")
        const displayName = topLevel ? institutionAbbreviation(node.name) : node.name
        const lines = topLevel ? [displayName] : wrapBubbleLabel(displayName, Math.min(22, Math.max(9, Math.floor(node.r / 4.5))), node.r > 100 ? 4 : 3)
        return <g key={node.id} className="constellation-node" data-quality={detail?.quality_status} role="button" tabIndex={0} aria-label={node.name} aria-describedby={`constellation-facts-${node.id}`} onMouseEnter={()=>detail&&onInspect?.(detail,{x:node.x,y:node.y})} onFocus={()=>detail&&onInspect?.(detail,{x:node.x,y:node.y})} onClick={() => detail&&drill(detail)} onKeyDown={event => detail&&keySelect(event, detail)}>
          <title>{[node.name, description].filter(Boolean).join(". ")}</title>
          <circle className={classes || undefined} cx={node.x} cy={node.y} r={Math.max(7, node.r)} />
          {(node.r > 45 || node.id === focus) && <text x={node.x} y={node.y} textAnchor="middle" fill="#f4f8ff" aria-hidden="true">{lines.map((line,index)=><tspan key={`${line}-${index}`} x={node.x} dy={index===0?`${-(lines.length-1)*0.55}em`:"1.1em"}>{line}</tspan>)}</text>}
        </g>
      })}
    </svg>
    <div role="listbox" aria-label={t("constellation.map")}>{nodes.map(node => {const anchor=positioned.find(item=>item.id===node.id)??{x:310,y:310};return <button key={node.id} role="option" aria-label={node.name} aria-selected={node.id === focus} data-quality={node.quality_status} onMouseEnter={()=>onInspect?.(node,anchor)} onFocus={()=>onInspect?.(node,anchor)} onClick={() => drill(node)}><span>{node.name}</span>{node.vacancy_count ? <small>{t("discover.vacancy")}</small> : null}{node.has_more ? <small>{t("constellation.moreAvailable")}</small> : null}</button>})}</div>
    <div className="constellation-info-controls" role="group" aria-label={t("constellation.details")}>{positioned.map(position=>{const node=details.get(position.id);return node?<button key={node.id} type="button" aria-label={t("constellation.showDetails",{name:node.name})} style={{left:`${(position.x/620)*100}%`,top:`${(position.y/620)*100}%`}} onClick={event=>{event.stopPropagation();onInspect?.(node,{x:position.x,y:position.y})}}>i</button>:null})}</div>
  </section>
}

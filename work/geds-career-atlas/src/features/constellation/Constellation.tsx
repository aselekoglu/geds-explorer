import { select, zoom, zoomIdentity, type ZoomBehavior } from "d3"
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react"
import { useLanguage } from "../../i18n/i18n"
import { buildPackLayout } from "./layout"
import { institutionAbbreviation, wrapBubbleLabel } from "./labels"

export type ConstellationNode = { id: string; name: string; value?: number; child_count?:number; direct_people_count?:number; descendant_people_count?:number; quality_status?: string; vacancy_count?: number; has_more?: boolean }

export function Constellation({ nodes, focus, onFocus, onDrill, onSelect, topLevel = false }: { nodes: ConstellationNode[]; focus?: string; onFocus?: (id: string) => void; onDrill?:(node:ConstellationNode)=>void;onSelect?:(node:ConstellationNode)=>void; topLevel?: boolean }) {
  const { t } = useLanguage()
  const svgRef=useRef<SVGSVGElement>(null)
  const viewportRef=useRef<SVGGElement>(null)
  const zoomBehaviorRef=useRef<ZoomBehavior<SVGSVGElement,unknown>|null>(null)
  const [zoomLevel,setZoomLevel]=useState(1)
  const nodeKey=useMemo(()=>nodes.map(node=>node.id).join("|"),[nodes])
  const positioned = buildPackLayout(nodes, 620, 620)
  const details = new Map(nodes.map(node => [node.id, node]))
  useEffect(()=>{
    const svg=svgRef.current
    const viewport=viewportRef.current
    if(!svg||!viewport)return
    const behavior=zoom<SVGSVGElement,unknown>().scaleExtent([.7,8]).on("zoom",event=>{
      select(viewport).attr("transform",event.transform.toString())
    }).on("end",event=>setZoomLevel(event.transform.k))
    zoomBehaviorRef.current=behavior
    select(svg).call(behavior).on("dblclick.zoom",null)
    return()=>{select(svg).on(".zoom",null);zoomBehaviorRef.current=null}
  },[])
  useEffect(()=>{resetView()},[nodeKey])
  function changeZoom(factor:number){const svg=svgRef.current;if(svg&&zoomBehaviorRef.current)zoomBehaviorRef.current.scaleBy(select(svg),factor)}
  function resetView(){const svg=svgRef.current;if(svg&&zoomBehaviorRef.current){zoomBehaviorRef.current.transform(select(svg),zoomIdentity);setZoomLevel(1)}}
  function selectNode(node:ConstellationNode){onSelect?.(node);onFocus?.(node.id)}
  function drill(node:ConstellationNode){onDrill?.(node);onFocus?.(node.id)}
  function keySelect(event: KeyboardEvent<Element>, node: ConstellationNode) {
    if(event.key==="Enter"||event.key===" "){event.preventDefault();selectNode(node)}
    if(event.key==="ArrowRight"){event.preventDefault();drill(node)}
  }
  return <section aria-label={t("constellation.aria")}>
    <div className="constellation-toolbar">
      <p>{t("constellation.zoomHint")}</p>
      <div className="constellation-zoom-controls" role="group" aria-label={t("constellation.map")}>
        <button type="button" aria-label={t("constellation.zoomOut")} onClick={()=>changeZoom(1/1.4)}>−</button>
        <span className="constellation-zoom-level">{Math.round(zoomLevel*100)}%</span>
        <button type="button" aria-label={t("constellation.zoomIn")} onClick={()=>changeZoom(1.4)}>+</button>
        <button type="button" className="constellation-reset" onClick={resetView}>{t("constellation.zoomReset")}</button>
      </div>
    </div>
    <svg ref={svgRef} viewBox="0 0 620 620" role="group" aria-labelledby="constellation-title constellation-description">
      <title id="constellation-title">{t("constellation.graphicTitle")}</title>
      <desc id="constellation-description">{t("constellation.graphicDescription")}</desc>
      <defs>
        <radialGradient id="constellation-bubble-surface" cx="30%" cy="22%" r="92%">
          <stop offset="0%" stopColor="color-mix(in srgb, var(--accent) 86%, white)"/>
          <stop offset="30%" stopColor="var(--bubble-strong)"/>
          <stop offset="76%" stopColor="var(--bubble)"/>
          <stop offset="100%" stopColor="color-mix(in srgb, var(--bubble) 76%, black)"/>
        </radialGradient>
        <radialGradient id="constellation-bubble-surface-selected" cx="28%" cy="20%" r="94%">
          <stop offset="0%" stopColor="color-mix(in srgb, var(--accent) 66%, white)"/>
          <stop offset="44%" stopColor="var(--accent)"/>
          <stop offset="100%" stopColor="color-mix(in srgb, var(--accent-strong) 76%, black)"/>
        </radialGradient>
        <radialGradient id="constellation-bubble-sheen" cx="25%" cy="18%" r="75%">
          <stop offset="0%" stopColor="white" stopOpacity=".52"/>
          <stop offset="22%" stopColor="white" stopOpacity=".1"/>
          <stop offset="64%" stopColor="var(--accent)" stopOpacity=".08"/>
          <stop offset="100%" stopColor="transparent"/>
        </radialGradient>
        <linearGradient id="constellation-bubble-border" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="white" stopOpacity=".78"/>
          <stop offset="42%" stopColor="var(--accent-strong)" stopOpacity=".9"/>
          <stop offset="100%" stopColor="var(--accent)" stopOpacity=".18"/>
        </linearGradient>
      </defs>
      <g ref={viewportRef} className="constellation-viewport">{positioned.map(node => {
        const detail = details.get(node.id)
        const classes = [node.id === focus ? "is-selected" : "", detail?.quality_status && detail.quality_status !== "complete" ? "has-quality-warning" : "", detail?.vacancy_count ? "has-vacancy" : ""].filter(Boolean).join(" ")
        const description = [detail?.quality_status ? t("constellation.quality", { status: detail.quality_status.replaceAll("_", " ") }) : "", detail?.vacancy_count ? t("discover.vacancy") : "", detail?.has_more ? t("constellation.moreAvailable") : ""].filter(Boolean).join(". ")
        const displayName = topLevel ? institutionAbbreviation(node.name) : node.name
        const lines = topLevel ? [displayName] : wrapBubbleLabel(displayName, Math.min(22, Math.max(9, Math.floor(node.r / 4.5))), node.r > 100 ? 4 : 3)
        return <g key={node.id} className="constellation-node" data-quality={detail?.quality_status} role="button" tabIndex={0} aria-label={node.name} aria-keyshortcuts="Enter Space ArrowRight" aria-describedby={node.id===focus?`constellation-facts-${node.id}`:undefined} onClick={() => detail&&selectNode(detail)} onDoubleClick={() => detail&&drill(detail)} onKeyDown={event => detail&&keySelect(event, detail)}>
          <title>{[node.name, description].filter(Boolean).join(". ")}</title>
          <circle className="constellation-hit-target" cx={node.x} cy={node.y} r={Math.max(22,node.r)} />
          <circle className={`constellation-bubble-surface ${classes}`.trim()} cx={node.x} cy={node.y} r={Math.max(7, node.r)} />
          <circle className="constellation-bubble-sheen" cx={node.x} cy={node.y} r={Math.max(7, node.r-1)} />
          <circle className="constellation-bubble-border" cx={node.x} cy={node.y} r={Math.max(7, node.r-1)} />
          {(node.r > 45 || node.id === focus) && <text x={node.x} y={node.y} textAnchor="middle" fill="#f4f8ff" aria-hidden="true">{lines.map((line,index)=><tspan key={`${line}-${index}`} x={node.x} dy={index===0?`${-(lines.length-1)*0.55}em`:"1.1em"}>{line}</tspan>)}</text>}
        </g>
      })}</g>
    </svg>
    <div role="listbox" aria-label={t("constellation.map")}>{nodes.map(node => <button key={node.id} role="option" aria-label={node.name} aria-selected={node.id === focus} data-quality={node.quality_status} onClick={() => selectNode(node)} onDoubleClick={() => drill(node)} onKeyDown={event=>keySelect(event,node)}><span>{node.name}</span>{node.vacancy_count ? <small>{t("discover.vacancy")}</small> : null}{node.has_more ? <small>{t("constellation.moreAvailable")}</small> : null}</button>)}</div>
  </section>
}

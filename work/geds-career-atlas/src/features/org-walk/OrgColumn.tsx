import { useVirtualizer } from "@tanstack/react-virtual"
import { useEffect, useRef } from "react"
import type { OrgNode } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import { BorderGlow } from "../../components/BorderGlow"
import { ProfileInfoIcon } from "./ProfileInfoIcon"

type Props={label:string;items:OrgNode[];columnIndex:number;expandedId?:string;total?:number;hasMore?:boolean;loadingMore?:boolean;focusFirst?:boolean;onLoadMore?:()=>void;onDrill:(node:OrgNode,columnIndex:number)=>void;onProfile:(orgId:string)=>void;onBack:(columnIndex:number)=>void}

export function OrgColumn({label,items,columnIndex,expandedId,total,hasMore,loadingMore,focusFirst,onLoadMore,onDrill,onProfile,onBack}:Props){
  const scrollRef=useRef<HTMLDivElement>(null)
  const {t,formatNumber}=useLanguage()
  const virtualizer=useVirtualizer({count:items.length,getScrollElement:()=>scrollRef.current,estimateSize:()=>74,overscan:6,useFlushSync:false})
  const virtualItems=virtualizer.getVirtualItems().length?virtualizer.getVirtualItems():items.slice(0,60).map((_,index)=>({index,key:index,start:index*74,size:74,end:(index+1)*74,lane:0}))
  useEffect(()=>{if(!focusFirst||!items.length)return;requestAnimationFrame(()=>scrollRef.current?.querySelector<HTMLElement>("[data-org-id]")?.focus())},[focusFirst,items])
  function focusIndex(index:number){const bounded=Math.max(0,Math.min(items.length-1,index));virtualizer.scrollToIndex(bounded);const focus=()=>scrollRef.current?.querySelector<HTMLElement>(`[data-org-id="${CSS.escape(items[bounded].org_id)}"]`)?.focus();focus();requestAnimationFrame(focus)}
  function typeahead(key:string){if(key.length!==1)return;const index=items.findIndex(item=>item.name.toLocaleLowerCase().startsWith(key.toLocaleLowerCase()));if(index>=0)focusIndex(index)}
  return <BorderGlow as="section" className="org-column-shell" aria-label={label} animated={false} borderRadius={0}><header><span>{label}</span><strong>{total!==undefined&&total!==items.length?`${formatNumber(items.length)} / ${formatNumber(total)}`:formatNumber(items.length)}</strong></header><div ref={scrollRef} className="org-root-list" role="list" aria-label={label} onKeyDown={event=>typeahead(event.key)}>
    <div className="org-virtual-space" role="presentation" style={{height:virtualizer.getTotalSize()||Math.min(items.length,60)*74}}>
      {virtualItems.map(item=>{const node=items[item.index];const summary=t("orgWalk.summary",{teams:node.child_count,people:formatNumber(node.descendant_people_count)});return <div className="org-card" role="listitem" key={item.key} style={{position:"absolute",transform:`translateY(${item.start}px)`,height:item.size}}>
        <button className="org-card__primary" data-org-id={node.org_id} aria-label={`${node.name}. ${summary}`} aria-current={expandedId===node.org_id?"true":undefined} aria-expanded={node.child_count>0?expandedId===node.org_id:undefined} onClick={()=>onDrill(node,columnIndex)} onKeyDown={event=>{if(event.key==="ArrowDown"||event.key==="ArrowUp"){event.preventDefault();focusIndex(item.index+(event.key==="ArrowDown"?1:-1))}if(event.key==="ArrowRight"||event.key==="Enter"){event.preventDefault();onDrill(node,columnIndex)}if(event.key==="ArrowLeft"&&columnIndex){event.preventDefault();onBack(columnIndex)}}}><span>{node.name}</span><small>{summary}</small></button>
        <button className="org-card__profile" type="button" aria-label={t("orgWalk.openProfile",{name:node.name})} title={t("orgWalk.openProfile",{name:node.name})} onClick={()=>onProfile(node.org_id)}><ProfileInfoIcon/></button>
      </div>})}
    </div>
  </div>{hasMore&&onLoadMore&&<button type="button" className="org-load-more" onClick={onLoadMore} disabled={loadingMore}>{loadingMore?t("orgWalk.loadingMore"):t("orgWalk.loadMore")}</button>}</BorderGlow>
}

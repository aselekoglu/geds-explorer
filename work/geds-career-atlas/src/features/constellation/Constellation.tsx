import type { KeyboardEvent } from "react"
import { buildPackLayout } from "./layout"

function label(name:string){return name.length<=20?name:`${name.slice(0,17)}...`}

export function Constellation({nodes,focus,onFocus}:{nodes:{id:string;name:string;value?:number}[];focus?:string;onFocus?:(id:string)=>void}){
  const positioned=buildPackLayout(nodes,620,620)
  function keySelect(event:KeyboardEvent<SVGGElement>,id:string){if(event.key==="Enter"||event.key===" "){event.preventDefault();onFocus?.(id)}}
  return <section aria-label="Government constellation"><svg viewBox="0 0 620 620" role="img" aria-labelledby="constellation-title constellation-description"><title id="constellation-title">Government organization constellation</title><desc id="constellation-description">Circle area represents people indexed in each organization branch. Select a circle or use the synchronized list.</desc>{positioned.map(node=><g key={node.id} className="constellation-node" role="button" tabIndex={0} aria-label={node.name} onClick={()=>onFocus?.(node.id)} onKeyDown={event=>keySelect(event,node.id)}><circle className={node.id===focus?"is-selected":undefined} cx={node.x} cy={node.y} r={Math.max(7,node.r)}/>{(node.r>45||node.id===focus)&&<text x={node.x} y={node.y} textAnchor="middle" fill="#f4f8ff">{label(node.name)}</text>}</g>)}</svg><div role="listbox" aria-label="Government map">{nodes.map(node=><button key={node.id} role="option" aria-selected={node.id===focus} onClick={()=>onFocus?.(node.id)}>{node.name}</button>)}</div></section>
}

import { hierarchy, pack } from "d3"

export type PositionedNode={id:string;name:string;x:number;y:number;r:number}
export type PackInput={id:string;name:string;value?:number}
type PackRoot={children:PackInput[]}

export function buildPackLayout(nodes:PackInput[],width=800,height=520):PositionedNode[]{
  if(nodes.length===0)return []
  const sorted=[...nodes].sort((a,b)=>(b.value??1)-(a.value??1)||a.id.localeCompare(b.id))
  const root=hierarchy<PackRoot | PackInput>({children:sorted}).sum(data=>(data as PackInput).value??1).sort((a,b)=>(b.value??0)-(a.value??0)||String((a.data as PackInput).id??"").localeCompare(String((b.data as PackInput).id??"")))
  const packed=pack<PackRoot | PackInput>().size([width,height]).padding(10)(root)
  return packed.leaves().map(leaf=>{const node=leaf.data as PackInput;return{id:node.id,name:node.name,x:leaf.x,y:leaf.y,r:leaf.r}}).sort((a,b)=>a.id.localeCompare(b.id))
}

export function deterministicLayout(nodes:{id:string;name:string}[],width=800,height=520):PositionedNode[]{
  return buildPackLayout(nodes,width,height)
}

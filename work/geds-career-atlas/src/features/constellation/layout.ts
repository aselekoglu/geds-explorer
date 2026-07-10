export type PositionedNode={id:string;name:string;x:number;y:number}
const hash=(value:string)=>[...value].reduce((sum,char)=>((sum*31)+char.charCodeAt(0))>>>0,7)
export function deterministicLayout(nodes:{id:string;name:string}[],width=800,height=520):PositionedNode[]{return [...nodes].sort((a,b)=>a.id.localeCompare(b.id)).map(node=>{const seed=hash(node.id);const angle=(seed%360)*Math.PI/180;const radius=90+(seed%230);return{id:node.id,name:node.name,x:width/2+Math.cos(angle)*radius,y:height/2+Math.sin(angle)*radius}})}

import { expect,it } from "vitest"
import { buildPackLayout, deterministicLayout } from "./layout"
it("keeps node positions stable independent of input order",()=>{const nodes=[{id:"b",name:"B"},{id:"a",name:"A"}];expect(deterministicLayout(nodes)).toEqual(deterministicLayout([...nodes].reverse()))})
it("packs identical inputs identically",()=>{const nodes=[{id:"b",name:"B",value:3},{id:"a",name:"A",value:8}];expect(buildPackLayout(nodes,1200,800)).toEqual(buildPackLayout(nodes,1200,800))})
it("returns no bubbles for an organization without children",()=>{expect(buildPackLayout([])).toEqual([])})
it("keeps every packed bubble positive and non-overlapping",()=>{
  const positioned=buildPackLayout(Array.from({length:80},(_,index)=>({id:`node-${index}`,name:`Node ${index}`,value:index%9===0?0:80-index})),620,620)
  expect(positioned.every(node=>node.r>0)).toBe(true)
  for(let left=0;left<positioned.length;left+=1)for(let right=left+1;right<positioned.length;right+=1){
    const a=positioned[left],b=positioned[right]
    expect(Math.hypot(a.x-b.x,a.y-b.y)+.001).toBeGreaterThanOrEqual(a.r+b.r)
  }
})

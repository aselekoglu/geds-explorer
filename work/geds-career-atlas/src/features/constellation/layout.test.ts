import { expect,it } from "vitest"
import { buildPackLayout, deterministicLayout } from "./layout"
it("keeps node positions stable independent of input order",()=>{const nodes=[{id:"b",name:"B"},{id:"a",name:"A"}];expect(deterministicLayout(nodes)).toEqual(deterministicLayout([...nodes].reverse()))})
it("packs identical inputs identically",()=>{const nodes=[{id:"b",name:"B",value:3},{id:"a",name:"A",value:8}];expect(buildPackLayout(nodes,1200,800)).toEqual(buildPackLayout(nodes,1200,800))})

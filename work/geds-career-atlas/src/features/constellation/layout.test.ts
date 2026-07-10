import { expect,it } from "vitest"
import { deterministicLayout } from "./layout"
it("keeps node positions stable independent of input order",()=>{const nodes=[{id:"b",name:"B"},{id:"a",name:"A"}];expect(deterministicLayout(nodes)).toEqual(deterministicLayout([...nodes].reverse()))})

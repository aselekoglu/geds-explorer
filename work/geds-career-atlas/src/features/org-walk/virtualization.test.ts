import { expect,it } from "vitest"
import { visibleWindow } from "./virtualization"
it("caps a high-fanout rendered window",()=>{expect(visibleWindow(Array.from({length:348},(_,i)=>i),0,60)).toHaveLength(60)})

import { expect,it } from "vitest"
import { loadView,saveView } from "./savedView"
it("stores a local exploration view",()=>{saveView({q:"AI",categories:[],confidence:"exploratory",vacancy:false,lang:"en",mode:"constellation"});expect(loadView()?.q).toBe("AI")})

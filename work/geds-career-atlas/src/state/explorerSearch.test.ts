import { expect, it } from "vitest"
import { explorerSearchSchema } from "./explorerSearch"
it("round-trips shareable explorer state", () => { const state = explorerSearchSchema.parse({ q:"AI",categories:["data-ai-research"],department:"dept-id",org:"org-id",confidence:"medium",vacancy:true,lang:"en",mode:"constellation",focus:"org-id" }); expect(explorerSearchSchema.parse(state)).toEqual(state) })

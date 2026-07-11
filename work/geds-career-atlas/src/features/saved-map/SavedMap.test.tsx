import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { saveView } from "../../state/savedView"
import { SavedMap } from "./SavedMap"

it("opens an AI tour as shareable constellation state", async () => {
  const onOpen=vi.fn()
  const client={tours:async()=>({items:[{id:"ai",title:{en:"Explore AI in government",fr:"Explorer l'IA au gouvernement"},description:{en:"Follow observed teams.",fr:"Suivez les equipes observees."},categories:["data-ai-research"],initial_focus:"ai-org",stops:[{org_id:"ai-org",available:true,note:{en:"Evidence",fr:"Preuve"}}]}],snapshot_id:"snapshot",etag:"etag"})}
  render(<SavedMap client={client} onOpen={onOpen}/>)
  fireEvent.click(await screen.findByRole("button",{name:/Explore AI in government/i}))
  expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({q:"AI",categories:["data-ai-research"],mode:"constellation",focus:"ai-org"}))
})

it("does not persist people or contact fields",()=>{
  saveView({q:"AI",categories:["data-ai-research"],confidence:"high",vacancy:false,lang:"en",mode:"constellation",focus:"ai-org",label:"AI map",note:"email phone person_name source_url"})
  const raw=localStorage.getItem("geds-career-atlas:saved-views:v1")??""
  expect(raw).not.toMatch(/email|phone|person_name|source_url/)
})

it("renders the previous department-tour payload during a rolling server restart",async()=>{
  const client={tours:async()=>({items:[{id:"department:legacy",label:"Legacy Department",kind:"department"}],snapshot_id:"snapshot",etag:"etag"})}
  render(<SavedMap client={client as never} onOpen={()=>undefined}/>)
  expect(await screen.findByRole("heading",{name:"Legacy Department"})).toBeVisible()
})

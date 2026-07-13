import { fireEvent, render, screen } from "@testing-library/react"
import { vi } from "vitest"
import { OrgColumn } from "./OrgColumn"

const items=Array.from({length:348},(_,index)=>({org_id:`org-${index}`,name:`Organization ${index}`,depth:2,child_count:index===42?3:0,direct_people_count:index,descendant_people_count:index}))

it("virtualizes large sibling fanout with accessible tree state",()=>{
  render(<OrgColumn label="Teams" items={items} columnIndex={0} expandedId="org-42" onDrill={vi.fn()} onProfile={vi.fn()} onBack={vi.fn()}/>)
  expect(screen.getByRole("tree",{name:"Teams"})).toBeVisible()
  expect(screen.getAllByRole("treeitem").length).toBeLessThan(80)
})

it("supports typeahead and right-arrow drilling",()=>{
  const onDrill=vi.fn()
  render(<OrgColumn label="Teams" items={items.slice(40,50)} columnIndex={0} onDrill={onDrill} onProfile={vi.fn()} onBack={vi.fn()}/>)
  const tree=screen.getByRole("tree",{name:"Teams"})
  fireEvent.keyDown(tree,{key:"O"})
  const expandable=screen.getByRole("treeitem",{name:/Organization 42/})
  expandable.focus()
  fireEvent.keyDown(expandable,{key:"ArrowDown"})
  expect(screen.getByRole("treeitem",{name:/Organization 43/})).toHaveFocus()
  expandable.focus()
  fireEvent.keyDown(expandable,{key:"ArrowRight"})
  expect(onDrill).toHaveBeenCalledWith(items[42],0)
})

it("keeps drill and profile actions as independent sibling controls",()=>{
  const onDrill=vi.fn()
  const onProfile=vi.fn()
  render(<OrgColumn label="Teams" items={[items[42]]} columnIndex={0} onDrill={onDrill} onProfile={onProfile} onBack={vi.fn()}/>)
  fireEvent.click(screen.getByRole("treeitem",{name:/Organization 42/}))
  expect(onDrill).toHaveBeenCalledWith(items[42],0)
  expect(onProfile).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole("button",{name:"Open Organization 42 profile"}))
  expect(onProfile).toHaveBeenCalledWith("org-42")
  expect(onDrill).toHaveBeenCalledTimes(1)
})

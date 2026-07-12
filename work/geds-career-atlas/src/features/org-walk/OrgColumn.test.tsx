import { fireEvent, render, screen } from "@testing-library/react"
import { vi } from "vitest"
import { OrgColumn } from "./OrgColumn"

const items=Array.from({length:348},(_,index)=>({org_id:`org-${index}`,name:`Organization ${index}`,depth:2,child_count:index===42?3:0,descendant_people_count:index}))

it("virtualizes large sibling fanout with accessible tree state",()=>{
  render(<OrgColumn label="Teams" items={items} columnIndex={0} expandedId="org-42" onOpen={vi.fn()} onBack={vi.fn()}/>)
  expect(screen.getByRole("tree",{name:"Teams"})).toBeVisible()
  expect(screen.getAllByRole("treeitem").length).toBeLessThan(80)
})

it("supports typeahead and right-arrow opening",()=>{
  const onOpen=vi.fn()
  render(<OrgColumn label="Teams" items={items.slice(40,50)} columnIndex={0} onOpen={onOpen} onBack={vi.fn()}/>)
  const tree=screen.getByRole("tree",{name:"Teams"})
  fireEvent.keyDown(tree,{key:"O"})
  const expandable=screen.getByRole("treeitem",{name:/Organization 42/})
  expandable.focus()
  fireEvent.keyDown(expandable,{key:"ArrowDown"})
  expect(screen.getByRole("treeitem",{name:/Organization 43/})).toHaveFocus()
  expandable.focus()
  fireEvent.keyDown(expandable,{key:"ArrowRight"})
  expect(onOpen).toHaveBeenCalledWith(items[42],0)
})

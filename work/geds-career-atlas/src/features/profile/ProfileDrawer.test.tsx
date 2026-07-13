import { fireEvent, render, screen } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { ProfileDrawer } from "./ProfileDrawer"

it("renders nothing while closed and closes on Escape",()=>{
  const onClose=vi.fn()
  const {rerender}=render(<ProfileDrawer open={false} onClose={onClose}>Profile</ProfileDrawer>)
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  rerender(<ProfileDrawer open onClose={onClose}>Profile</ProfileDrawer>)
  fireEvent.keyDown(screen.getByRole("dialog"),{key:"Escape"})
  expect(onClose).toHaveBeenCalled()
})

it("labels the open profile as a modal drawer",()=>{
  render(<ProfileDrawer open onClose={vi.fn()}><h2>Team profile</h2></ProfileDrawer>)
  expect(screen.getByRole("dialog",{name:"Team profile"})).toHaveAttribute("aria-modal","true")
})

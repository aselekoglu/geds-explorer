import { fireEvent, render, screen, within } from "@testing-library/react"
import { BreadcrumbTrail, type BreadcrumbTrailItem } from "./BreadcrumbTrail"

const path: BreadcrumbTrailItem[] = [
  { key: "department", label: "Department" },
  { key: "branch", label: "Branch" },
  { key: "team", label: "Team" },
]

it("renders a named navigation landmark, ordered list, and current page", () => {
  const { container } = render(<BreadcrumbTrail items={path} label="Organization path" />)
  const navigation = screen.getByRole("navigation", { name: "Organization path" })
  const list = within(navigation).getByRole("list")

  expect(within(list).getAllByRole("listitem")).toHaveLength(3)
  expect(within(navigation).queryByRole("button")).not.toBeInTheDocument()
  expect(within(navigation).getByText("Team")).toHaveAttribute("aria-current", "page")

  const separators = container.querySelectorAll("[data-breadcrumb-separator]")
  expect(separators).toHaveLength(2)
  separators.forEach(separator => {
    expect(separator).toHaveAttribute("aria-hidden", "true")
    expect(separator).toHaveAttribute("focusable", "false")
  })
})

it("makes only ancestors actionable and reports their stable index", () => {
  const onSelect = vi.fn()
  render(<BreadcrumbTrail items={path} label="Organization path" onSelect={onSelect} />)

  const department = screen.getByRole("button", { name: "Department" })
  const branch = screen.getByRole("button", { name: "Branch" })
  expect(screen.queryByRole("button", { name: "Team" })).not.toBeInTheDocument()

  fireEvent.click(branch)
  expect(onSelect).toHaveBeenLastCalledWith(1)

  department.focus()
  expect(department).toHaveFocus()
  fireEvent.keyDown(department, { key: "Enter" })
  fireEvent.click(department, { detail: 0 })
  expect(onSelect).toHaveBeenLastCalledWith(0)
})

it("renders nothing for an empty path", () => {
  const { container } = render(<BreadcrumbTrail items={[]} label="Organization path" />)

  expect(container).toBeEmptyDOMElement()
  expect(screen.queryByRole("navigation")).not.toBeInTheDocument()
})

it("renders a single item as the non-interactive current page", () => {
  render(<BreadcrumbTrail items={[path[0]]} label="Organization path" onSelect={vi.fn()} />)

  expect(screen.getByText("Department")).toHaveAttribute("aria-current", "page")
  expect(screen.queryByRole("button")).not.toBeInTheDocument()
  expect(screen.getByRole("list")).toBeInTheDocument()
})

it("supports duplicate labels by using item keys instead of labels", () => {
  render(
    <BreadcrumbTrail
      items={[
        { key: "operations-branch", label: "Operations" },
        { key: "operations-team", label: "Operations" },
      ]}
      label="Organization path"
      onSelect={vi.fn()}
    />,
  )

  expect(screen.getAllByText("Operations")).toHaveLength(2)
  expect(screen.getByRole("button", { name: "Operations" })).toBeInTheDocument()
  expect(screen.getAllByText("Operations")[1]).toHaveAttribute("aria-current", "page")
})

it("keeps every item in a long path available to assistive technology", () => {
  const longPath = Array.from({ length: 12 }, (_, index) => ({
    key: `level-${index}`,
    label: `Organization level ${index + 1}`,
  }))

  render(<BreadcrumbTrail items={longPath} label="Long organization path" />)

  expect(within(screen.getByRole("navigation", { name: "Long organization path" })).getAllByRole("listitem")).toHaveLength(12)
  expect(screen.getByText("Organization level 12")).toHaveAttribute("aria-current", "page")
})

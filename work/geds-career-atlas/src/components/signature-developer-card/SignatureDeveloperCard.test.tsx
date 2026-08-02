import { fireEvent, render, screen } from "@testing-library/react"
import { SignatureDeveloperCard } from "./SignatureDeveloperCard"

const profile = { name: "Ada Lovelace", title: "Developer", href: "https://example.test", portraitSrc: "/portrait.png" }

function mockPointerCapture(card: HTMLElement) {
  Object.defineProperties(card, {
    setPointerCapture: { configurable: true, value: vi.fn() },
    releasePointerCapture: { configurable: true, value: vi.fn() },
    hasPointerCapture: { configurable: true, value: vi.fn(() => true) },
  })
  vi.spyOn(card, "getBoundingClientRect").mockReturnValue({
    x: 0,
    y: 0,
    left: 0,
    top: 0,
    right: 286,
    bottom: 398,
    width: 286,
    height: 398,
    toJSON: () => ({}),
  })
}

it("renders only the approved accessible developer content", () => {
  const { container } = render(<SignatureDeveloperCard profile={profile} />)
  const card = screen.getByRole("link", { name: /visit ada lovelace's website/i })

  expect(card).toHaveAttribute("href", profile.href)
  expect(card).toHaveAttribute("target", "_blank")
  expect(card).toHaveAttribute("rel", "noreferrer")
  expect(card).toHaveAttribute("data-profile-tilt", "disabled")
  expect(screen.getByText("Ada Lovelace")).toBeVisible()
  expect(screen.getByText("Developer")).toBeVisible()
  expect(container.querySelector(".signature-developer-card__portrait img")).toHaveAttribute("src", profile.portraitSrc)
})

it("advertises a non-draggable, scroll-friendly static mode", () => {
  render(<SignatureDeveloperCard profile={profile} interactive={false} />)
  const card = screen.getByRole("link")

  expect(card).toHaveClass("signature-developer-card--static")
  expect(card).toHaveAttribute("data-profile-interactive", "false")
})

it("uses initials when a consumer does not provide a portrait", () => {
  render(<SignatureDeveloperCard profile={{ name: "Grace Hopper", title: "Engineer", href: "https://example.test" }} />)
  expect(screen.getByText("GH")).toBeVisible()
})

it("separates a drag from navigation and allows the next genuine click", () => {
  const onDragStart = vi.fn()
  const onDragMove = vi.fn()
  const onDragEnd = vi.fn()
  render(<SignatureDeveloperCard profile={profile} onDragStart={onDragStart} onDragMove={onDragMove} onDragEnd={onDragEnd} />)
  const card = screen.getByRole("link")
  mockPointerCapture(card)

  fireEvent.pointerDown(card, { button: 0, pointerId: 7, clientX: 80, clientY: 90 })
  fireEvent.pointerMove(card, { pointerId: 7, clientX: 84, clientY: 93 })
  expect(onDragStart).not.toHaveBeenCalled()

  fireEvent.pointerMove(card, { pointerId: 7, clientX: 102, clientY: 110 })
  expect(onDragStart).toHaveBeenCalledWith({ pointerId: 7, clientX: 80, clientY: 90 })
  expect(onDragMove).toHaveBeenLastCalledWith({ pointerId: 7, clientX: 102, clientY: 110 })
  expect(card).toHaveAttribute("data-drag-state", "dragging")

  fireEvent.pointerUp(card, { pointerId: 7, clientX: 102, clientY: 110 })
  expect(onDragEnd).toHaveBeenCalledOnce()
  const dragClick = new MouseEvent("click", { bubbles: true, cancelable: true })
  card.dispatchEvent(dragClick)
  expect(dragClick.defaultPrevented).toBe(true)

  const nextClick = new MouseEvent("click", { bubbles: true, cancelable: true })
  card.dispatchEvent(nextClick)
  expect(nextClick.defaultPrevented).toBe(false)
})

it("cancels an active drag on window blur", () => {
  const onDragCancel = vi.fn()
  render(<SignatureDeveloperCard profile={profile} onDragCancel={onDragCancel} />)
  const card = screen.getByRole("link")
  mockPointerCapture(card)

  fireEvent.pointerDown(card, { button: 0, pointerId: 11, clientX: 40, clientY: 40 })
  fireEvent.pointerMove(card, { pointerId: 11, clientX: 70, clientY: 70 })
  fireEvent.blur(window)

  expect(onDragCancel).toHaveBeenCalledOnce()
  expect(card).toHaveAttribute("data-drag-state", "idle")
  const clickAfterCancel = new MouseEvent("click", { bubbles: true, cancelable: true })
  card.dispatchEvent(clickAfterCancel)
  expect(clickAfterCancel.defaultPrevented).toBe(false)
})

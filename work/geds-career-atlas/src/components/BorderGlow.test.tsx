import { act, render } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { BorderGlow } from "./BorderGlow"

type ObserverHarness = {
  callback?: IntersectionObserverCallback
  disconnect: ReturnType<typeof vi.fn>
  observe: ReturnType<typeof vi.fn>
}

function installMotionPreference(reduced: boolean) {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: reduced,
      media: "(prefers-reduced-motion: reduce)",
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

function installIntersectionObserver(harness: ObserverHarness) {
  class MockIntersectionObserver {
    readonly root = null
    readonly rootMargin = "0px"
    readonly thresholds = [0.01]

    constructor(callback: IntersectionObserverCallback) {
      harness.callback = callback
    }

    observe = harness.observe
    unobserve = vi.fn()
    disconnect = harness.disconnect
    takeRecords = vi.fn(() => [])
  }

  Object.defineProperty(window, "IntersectionObserver", { configurable: true, value: MockIntersectionObserver })
  Object.defineProperty(globalThis, "IntersectionObserver", { configurable: true, value: MockIntersectionObserver })
}

describe("BorderGlow", () => {
  const originalMatchMedia = window.matchMedia
  const originalIntersectionObserver = window.IntersectionObserver
  const originalRequestAnimationFrame = window.requestAnimationFrame
  const originalCancelAnimationFrame = window.cancelAnimationFrame

  beforeEach(() => {
    installMotionPreference(false)
  })

  afterEach(() => {
    Object.defineProperty(window, "matchMedia", { configurable: true, value: originalMatchMedia })
    Object.defineProperty(window, "IntersectionObserver", { configurable: true, value: originalIntersectionObserver })
    Object.defineProperty(globalThis, "IntersectionObserver", { configurable: true, value: originalIntersectionObserver })
    Object.defineProperty(window, "requestAnimationFrame", { configurable: true, value: originalRequestAnimationFrame })
    Object.defineProperty(globalThis, "requestAnimationFrame", { configurable: true, value: originalRequestAnimationFrame })
    Object.defineProperty(window, "cancelAnimationFrame", { configurable: true, value: originalCancelAnimationFrame })
    Object.defineProperty(globalThis, "cancelAnimationFrame", { configurable: true, value: originalCancelAnimationFrame })
    vi.restoreAllMocks()
  })

  it("uses the requested glow defaults and semantic palette", () => {
    const { container } = render(<BorderGlow animated={false}>Content</BorderGlow>)
    const card = container.querySelector<HTMLElement>(".border-glow-card")!

    expect(card.style.getPropertyValue("--edge-sensitivity")).toBe("15")
    expect(card.style.getPropertyValue("--glow-padding")).toBe("56px")
    expect(card.style.getPropertyValue("--cone-spread")).toBe("27")
    expect(card.style.getPropertyValue("--glow-color")).toBe("hsl(176deg 58% 60% / 100%)")
    expect(card.style.getPropertyValue("--glow-color-40")).toBe("hsl(176deg 58% 60% / 76%)")
    expect(card.style.getPropertyValue("--gradient-one")).toContain("var(--glow-gradient-teal)")
    expect(card.style.getPropertyValue("--gradient-two")).toContain("var(--glow-gradient-blue)")
    expect(card.style.getPropertyValue("--gradient-three")).toContain("var(--glow-gradient-amber)")
  })

  it("starts one sweep only after becoming visible and cancels it on cleanup", () => {
    const harness: ObserverHarness = { disconnect: vi.fn(), observe: vi.fn() }
    installIntersectionObserver(harness)
    const requestAnimationFrame = vi.fn(() => 17)
    const cancelAnimationFrame = vi.fn()
    Object.defineProperty(globalThis, "requestAnimationFrame", { configurable: true, value: requestAnimationFrame })
    Object.defineProperty(globalThis, "cancelAnimationFrame", { configurable: true, value: cancelAnimationFrame })

    const { container, unmount } = render(<BorderGlow>Content</BorderGlow>)
    const card = container.querySelector<HTMLElement>(".border-glow-card")!
    expect(harness.observe).toHaveBeenCalledWith(card)
    expect(requestAnimationFrame).not.toHaveBeenCalled()

    act(() => {
      harness.callback?.([{ target: card, isIntersecting: true, intersectionRatio: 1 } as unknown as IntersectionObserverEntry], {} as IntersectionObserver)
    })

    expect(card).toHaveClass("border-glow-card--sweeping")
    expect(requestAnimationFrame).toHaveBeenCalledOnce()
    unmount()
    expect(cancelAnimationFrame).toHaveBeenCalledWith(17)
    expect(harness.disconnect).toHaveBeenCalled()
  })

  it("does not observe or animate when reduced motion is requested", () => {
    installMotionPreference(true)
    const harness: ObserverHarness = { disconnect: vi.fn(), observe: vi.fn() }
    installIntersectionObserver(harness)
    const requestAnimationFrame = vi.fn(() => 17)
    Object.defineProperty(globalThis, "requestAnimationFrame", { configurable: true, value: requestAnimationFrame })

    render(<BorderGlow>Content</BorderGlow>)

    expect(harness.observe).not.toHaveBeenCalled()
    expect(requestAnimationFrame).not.toHaveBeenCalled()
  })
})

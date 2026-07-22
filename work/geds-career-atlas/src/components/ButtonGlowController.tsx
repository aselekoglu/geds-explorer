import { useEffect } from "react"

export function ButtonGlowController() {
  useEffect(() => {
    function updateGlow(event: PointerEvent) {
      const target = event.target instanceof Element ? event.target.closest<HTMLButtonElement>("button") : null
      if (!target || target.disabled) return
      const rect = target.getBoundingClientRect()
      if (!rect.width || !rect.height) return
      target.style.setProperty("--button-glow-x", `${event.clientX - rect.left}px`)
      target.style.setProperty("--button-glow-y", `${event.clientY - rect.top}px`)
    }
    document.addEventListener("pointermove", updateGlow, { passive: true })
    return () => document.removeEventListener("pointermove", updateGlow)
  }, [])
  return null
}

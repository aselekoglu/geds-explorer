import { useEffect, useRef, type KeyboardEvent, type ReactNode, type RefObject } from "react"
import { useLanguage } from "../../i18n/i18n"

type ProfileDrawerProps = {
  open: boolean
  onClose: () => void
  children: ReactNode
  label?: string
  returnFocusRef?: RefObject<HTMLElement | null>
}

export function ProfileDrawer({ open, onClose, children, label = "Team profile", returnFocusRef }: ProfileDrawerProps) {
  const panelRef = useRef<HTMLElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const { t } = useLanguage()

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    return () => { (returnFocusRef?.current ?? previous)?.focus?.() }
  }, [open, returnFocusRef])

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault()
      onClose()
      return
    }
    if (event.key !== "Tab") return
    const focusable = [...(panelRef.current?.querySelectorAll<HTMLElement>('button,a[href],input,select,textarea,[tabindex]:not([tabindex="-1"])') ?? [])]
    if (!focusable.length) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  if (!open) return null
  return <div className="detail-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
    <aside ref={panelRef} className="detail-panel detail-panel--open" role="dialog" aria-modal="true" aria-label={label} onKeyDown={handleKeyDown}>
      <button ref={closeRef} className="close" type="button" aria-label={t("app.close")} onClick={onClose}>×</button>
      {children}
    </aside>
  </div>
}

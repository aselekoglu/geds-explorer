import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react"
import "./SignatureDeveloperCard.css"

export const SIGNATURE_CARD_DRAG_THRESHOLD = 7

export type SignatureDeveloperCardPointer = {
  clientX: number
  clientY: number
  pointerId: number
}

export type SignatureDeveloperProfile = {
  name: string
  title: string
  href: string
  portraitSrc?: string
  portraitAlt?: string
  fallbackInitials?: string
}

export type SignatureDeveloperCardProps = {
  profile: SignatureDeveloperProfile
  className?: string
  interactive?: boolean
  onDragStart?: (pointer: SignatureDeveloperCardPointer) => void
  onDragMove?: (pointer: SignatureDeveloperCardPointer) => void
  onDragEnd?: () => void
  onDragCancel?: () => void
}

type Gesture = SignatureDeveloperCardPointer & { startX: number, startY: number, dragging: boolean }

function pointerFromEvent(event: ReactPointerEvent<HTMLElement>): SignatureDeveloperCardPointer {
  return { clientX: event.clientX, clientY: event.clientY, pointerId: event.pointerId }
}

function releaseCapture(element: HTMLElement, pointerId: number) {
  if (typeof element.hasPointerCapture === "function" && !element.hasPointerCapture(pointerId)) return
  element.releasePointerCapture?.(pointerId)
}

/**
 * An accessible, draggable profile card. It stays an ordinary external link
 * unless a pointer movement crosses the drag threshold.
 */
export function SignatureDeveloperCard({
  profile,
  className = "",
  interactive = true,
  onDragStart,
  onDragMove,
  onDragEnd,
  onDragCancel,
}: SignatureDeveloperCardProps) {
  const cardRef = useRef<HTMLAnchorElement>(null)
  const gestureRef = useRef<Gesture | null>(null)
  const suppressNextClickRef = useRef(false)
  const dragCallbacksRef = useRef({ onDragEnd, onDragCancel })
  const [dragging, setDragging] = useState(false)
  const [imageFailed, setImageFailed] = useState(false)
  dragCallbacksRef.current = { onDragEnd, onDragCancel }

  const resetGesture = useCallback((cancelled: boolean) => {
    const gesture = gestureRef.current
    const card = cardRef.current
    if (!gesture) return
    if (card) releaseCapture(card, gesture.pointerId)
    gestureRef.current = null
    setDragging(false)
    if (!gesture.dragging) return
    if (cancelled) {
      suppressNextClickRef.current = false
      dragCallbacksRef.current.onDragCancel?.()
    } else {
      dragCallbacksRef.current.onDragEnd?.()
    }
  }, [])

  useEffect(() => {
    const handleBlur = () => resetGesture(true)
    window.addEventListener("blur", handleBlur)
    return () => {
      window.removeEventListener("blur", handleBlur)
      resetGesture(true)
    }
  }, [resetGesture])

  const handlePointerDown = (event: ReactPointerEvent<HTMLAnchorElement>) => {
    if (!interactive || event.button !== 0) return
    gestureRef.current = { ...pointerFromEvent(event), startX: event.clientX, startY: event.clientY, dragging: false }
    try { event.currentTarget.setPointerCapture?.(event.pointerId) } catch { /* Transformed hosts can reject capture. */ }
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLAnchorElement>) => {
    const gesture = gestureRef.current
    if (!interactive || !gesture || gesture.pointerId !== event.pointerId) return
    const distance = Math.hypot(event.clientX - gesture.startX, event.clientY - gesture.startY)
    if (!gesture.dragging && distance >= SIGNATURE_CARD_DRAG_THRESHOLD) {
      gesture.dragging = true
      suppressNextClickRef.current = true
      setDragging(true)
      onDragStart?.({ clientX: gesture.startX, clientY: gesture.startY, pointerId: gesture.pointerId })
    }
    if (gesture.dragging) onDragMove?.(pointerFromEvent(event))
  }

  const handleClick = (event: ReactMouseEvent<HTMLAnchorElement>) => {
    if (!suppressNextClickRef.current) return
    suppressNextClickRef.current = false
    event.preventDefault()
    event.stopPropagation()
  }

  const initials = profile.fallbackInitials ?? profile.name.split(/\s+/).map(part => part[0]).join("").slice(0, 2).toUpperCase()
  const classes = ["signature-developer-card", interactive ? "" : "signature-developer-card--static", dragging ? "signature-developer-card--dragging" : "", className].filter(Boolean).join(" ")

  return <a
    ref={cardRef}
    className={classes}
    href={profile.href}
    target="_blank"
    rel="noreferrer"
    aria-label={`Visit ${profile.name}'s website`}
    draggable={false}
    data-drag-state={dragging ? "dragging" : "idle"}
    data-profile-interactive={interactive ? "true" : "false"}
    data-profile-tilt="disabled"
    onClick={handleClick}
    onDragStart={event => event.preventDefault()}
    onPointerDown={handlePointerDown}
    onPointerMove={handlePointerMove}
    onPointerUp={() => resetGesture(false)}
    onPointerCancel={() => resetGesture(true)}
  >
    <span className="signature-developer-card__inside">
      <span className="signature-developer-card__details">
        <span className="signature-developer-card__name">{profile.name}</span>
        <span className="signature-developer-card__title">{profile.title}</span>
      </span>
      <span className="signature-developer-card__portrait" aria-hidden={imageFailed ? undefined : true}>
        {profile.portraitSrc && !imageFailed
          ? <img src={profile.portraitSrc} alt={profile.portraitAlt ?? ""} draggable={false} onError={() => setImageFailed(true)} />
          : <span className="signature-developer-card__initials" aria-label={profile.name}>{initials}</span>}
      </span>
    </span>
  </a>
}

export default SignatureDeveloperCard

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react"
import portrait from "../assets/ata-speaking-2.png"
import "./ProfileCard.css"

export const DEVELOPER_URL = "https://aselekoglu.github.io/?utm_source=geds-career-atlas&utm_medium=profile-card&utm_campaign=about-developer"
export const DEVELOPER_NAME = "Ata Selekoglu"
export const DEVELOPER_TITLE = "Developer"
export const PROFILE_CARD_DRAG_THRESHOLD = 7

export type ProfileCardPointer = {
  clientX: number
  clientY: number
  pointerId: number
}

export type ProfileCardProps = {
  className?: string
  interactive?: boolean
  onDragStart?: (pointer: ProfileCardPointer) => void
  onDragMove?: (pointer: ProfileCardPointer) => void
  onDragEnd?: () => void
  onDragCancel?: () => void
}

type Gesture = ProfileCardPointer & {
  startX: number
  startY: number
  dragging: boolean
}

function pointerFromEvent(event: ReactPointerEvent<HTMLElement>): ProfileCardPointer {
  return { clientX: event.clientX, clientY: event.clientY, pointerId: event.pointerId }
}

function releaseCapture(element: HTMLElement, pointerId: number) {
  if (typeof element.hasPointerCapture === "function" && !element.hasPointerCapture(pointerId)) return
  element.releasePointerCapture?.(pointerId)
}

export function ProfileCard({
  className = "",
  interactive = true,
  onDragStart,
  onDragMove,
  onDragEnd,
  onDragCancel,
}: ProfileCardProps) {
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
    gestureRef.current = {
      ...pointerFromEvent(event),
      startX: event.clientX,
      startY: event.clientY,
      dragging: false,
    }
    try {
      event.currentTarget.setPointerCapture?.(event.pointerId)
    } catch {
      // The gesture still works while the pointer remains over the transformed HTML host.
    }
  }

  const handlePointerMove = (event: ReactPointerEvent<HTMLAnchorElement>) => {
    const gesture = gestureRef.current
    if (!interactive || !gesture || gesture.pointerId !== event.pointerId) return

    const distance = Math.hypot(event.clientX - gesture.startX, event.clientY - gesture.startY)
    if (!gesture.dragging && distance >= PROFILE_CARD_DRAG_THRESHOLD) {
      gesture.dragging = true
      suppressNextClickRef.current = true
      setDragging(true)
      onDragStart?.({
        clientX: gesture.startX,
        clientY: gesture.startY,
        pointerId: gesture.pointerId,
      })
    }
    if (gesture.dragging) onDragMove?.(pointerFromEvent(event))
  }

  const handleClick = (event: ReactMouseEvent<HTMLAnchorElement>) => {
    if (!suppressNextClickRef.current) return
    suppressNextClickRef.current = false
    event.preventDefault()
    event.stopPropagation()
  }

  const classes = [
    "profile-card",
    interactive ? "" : "profile-card--static",
    dragging ? "profile-card--dragging" : "",
    className,
  ].filter(Boolean).join(" ")

  return <a
    ref={cardRef}
    className={classes}
    href={DEVELOPER_URL}
    target="_blank"
    rel="noreferrer"
    aria-label={`Visit ${DEVELOPER_NAME}'s website`}
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
    <span className="profile-card__inside">
      <span className="profile-card__shine" aria-hidden="true" />
      <span className="profile-card__glare" aria-hidden="true" />
      <span className="profile-card__details">
        <span className="profile-card__name">{DEVELOPER_NAME}</span>
        <span className="profile-card__title">{DEVELOPER_TITLE}</span>
      </span>
      <span className="profile-card__portrait" aria-hidden={imageFailed ? undefined : true}>
        {imageFailed
          ? <span className="profile-card__initials" aria-label={DEVELOPER_NAME}>AS</span>
          : <img src={portrait} alt="" draggable={false} onError={() => setImageFailed(true)} />}
      </span>
    </span>
  </a>
}

export default ProfileCard

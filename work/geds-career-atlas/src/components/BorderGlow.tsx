import { useCallback, useRef, type CSSProperties, type FocusEvent, type HTMLAttributes, type PointerEvent } from "react"

type BorderGlowElement = "article" | "aside" | "div" | "section"

type BorderGlowProps = Omit<HTMLAttributes<HTMLElement>, "children"> & {
  as?: BorderGlowElement
  children: React.ReactNode
  edgeSensitivity?: number
  glowColor?: string
  backgroundColor?: string
  borderRadius?: number
  glowRadius?: number
  glowIntensity?: number
  coneSpread?: number
  colors?: string[]
  fillOpacity?: number
}

const gradientPositions = ["80% 55%", "69% 34%", "8% 6%", "41% 38%", "86% 85%", "82% 18%", "51% 4%"]
const gradientKeys = ["--gradient-one", "--gradient-two", "--gradient-three", "--gradient-four", "--gradient-five", "--gradient-six", "--gradient-seven"]
const colorMap = [0, 1, 2, 0, 1, 2, 1]

function parseHsl(value: string) {
  const match = value.match(/([\d.]+)\s*([\d.]+)%?\s*([\d.]+)%?/)
  return match ? { h: Number(match[1]), s: Number(match[2]), l: Number(match[3]) } : { h: 176, s: 58, l: 60 }
}

function buildGlowVars(glowColor: string, intensity: number) {
  const { h, s, l } = parseHsl(glowColor)
  const base = `${h}deg ${s}% ${l}%`
  const opacities = [100, 60, 50, 40, 30, 20, 10]
  const keys = ["", "-60", "-50", "-40", "-30", "-20", "-10"]
  return Object.fromEntries(opacities.map((opacity, index) => [`--glow-color${keys[index]}`, `hsl(${base} / ${Math.min(opacity * intensity, 100)}%)`]))
}

function buildGradientVars(colors: string[]) {
  const palette = colors.length ? colors : ["#62d8ce"]
  const variables = Object.fromEntries(gradientKeys.map((key, index) => {
    const color = palette[Math.min(colorMap[index], palette.length - 1)]
    return [key, `radial-gradient(at ${gradientPositions[index]}, ${color} 0px, transparent 50%)`]
  }))
  return { ...variables, "--gradient-base": `linear-gradient(${palette[0]} 0 100%)` }
}

export function BorderGlow({
  as = "div",
  children,
  className = "",
  edgeSensitivity = 34,
  glowColor = "176 58 60",
  backgroundColor = "var(--surface)",
  borderRadius = 18,
  glowRadius = 32,
  glowIntensity = 0.72,
  coneSpread = 25,
  colors = ["#52cfc4", "#86bdb8", "#b8eee8"],
  fillOpacity = 0.12,
  style,
  onPointerMove,
  onFocusCapture,
  onBlurCapture,
  ...elementProps
}: BorderGlowProps) {
  const cardRef = useRef<HTMLElement>(null)
  const Tag = as

  const updateGlow = useCallback((x: number, y: number) => {
    const card = cardRef.current
    if (!card) return
    const { width, height } = card.getBoundingClientRect()
    if (!width || !height) return
    const centerX = width / 2
    const centerY = height / 2
    const deltaX = x - centerX
    const deltaY = y - centerY
    const scaleX = deltaX === 0 ? Number.POSITIVE_INFINITY : centerX / Math.abs(deltaX)
    const scaleY = deltaY === 0 ? Number.POSITIVE_INFINITY : centerY / Math.abs(deltaY)
    const proximity = Math.min(Math.max(1 / Math.min(scaleX, scaleY), 0), 1)
    let angle = Math.atan2(deltaY, deltaX) * (180 / Math.PI) + 90
    if (angle < 0) angle += 360
    card.style.setProperty("--edge-proximity", (proximity * 100).toFixed(3))
    card.style.setProperty("--cursor-angle", `${angle.toFixed(3)}deg`)
  }, [])

  function handlePointerMove(event: PointerEvent<HTMLElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    updateGlow(event.clientX - rect.left, event.clientY - rect.top)
    onPointerMove?.(event)
  }

  function handleFocus(event: FocusEvent<HTMLElement>) {
    const card = cardRef.current
    card?.style.setProperty("--edge-proximity", "100")
    card?.style.setProperty("--cursor-angle", "45deg")
    onFocusCapture?.(event)
  }

  function handleBlur(event: FocusEvent<HTMLElement>) {
    if (!event.currentTarget.contains(event.relatedTarget)) cardRef.current?.style.setProperty("--edge-proximity", "0")
    onBlurCapture?.(event)
  }

  const glowStyle = {
    ...style,
    "--card-bg": backgroundColor,
    "--edge-sensitivity": edgeSensitivity,
    "--border-radius": `${borderRadius}px`,
    "--glow-padding": `${glowRadius}px`,
    "--cone-spread": coneSpread,
    "--fill-opacity": fillOpacity,
    ...buildGlowVars(glowColor, glowIntensity),
    ...buildGradientVars(colors),
  } as CSSProperties

  return <Tag
    ref={cardRef as never}
    className={`border-glow-card ${className}`.trim()}
    style={glowStyle}
    onPointerMove={handlePointerMove}
    onFocusCapture={handleFocus}
    onBlurCapture={handleBlur}
    {...elementProps}
  >
    <span className="edge-light" aria-hidden="true" />
    <div className="border-glow-inner">{children}</div>
  </Tag>
}

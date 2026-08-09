import type { CSSProperties, HTMLAttributes } from "react"

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
  animated?: boolean
}

/**
 * A compatibility surface for the original premium card API.
 *
 * The pointer-following glow was intentionally retired for the GC service
 * redesign. Keeping this wrapper lets data-heavy features share one semantic
 * surface without carrying decorative animation or layout-specific markup.
 */
export function BorderGlow({
  as = "div",
  children,
  className = "",
  backgroundColor = "var(--surface)",
  borderRadius = 4,
  style,
  edgeSensitivity: _edgeSensitivity,
  glowColor: _glowColor,
  glowRadius: _glowRadius,
  glowIntensity: _glowIntensity,
  coneSpread: _coneSpread,
  colors: _colors,
  fillOpacity: _fillOpacity,
  animated: _animated = false,
  ...elementProps
}: BorderGlowProps) {
  const Tag = as
  const surfaceStyle = {
    ...style,
    "--card-bg": backgroundColor,
    "--border-radius": `${borderRadius}px`,
  } as CSSProperties

  return <Tag className={`border-glow-card ${className}`.trim()} style={surfaceStyle} {...elementProps}>
    <div className="border-glow-inner">{children}</div>
  </Tag>
}

import { useVirtualizer } from "@tanstack/react-virtual"
import { useRef, useState } from "react"

type OrgWalkProps = { path: string[] }

export function OrgWalk({ path }: OrgWalkProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [active, setActive] = useState(Math.max(0, Math.min(path.length - 1, 59)))
  const virtualizer = useVirtualizer({
    count: path.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => 36,
    overscan: 6,
  })
  const items = virtualizer.getVirtualItems().length ? virtualizer.getVirtualItems() : path.slice(0, 60).map((_, index) => ({ index, key: index, start: index * 36, size: 36 }))

  return <section className="org-walk">
    <nav aria-label="Organization path">{path.join(" / ")}</nav>
    <p className="org-walk-count">{path.length} organizations</p>
    <div ref={scrollRef} className="org-walk-scroll" role="tree" aria-label="Organization hierarchy" onKeyDown={event => {
      if (event.key === "ArrowDown") { event.preventDefault(); setActive(value => Math.min(value + 1, path.length - 1)) }
      if (event.key === "ArrowUp") { event.preventDefault(); setActive(value => Math.max(value - 1, 0)) }
    }}>
      <div style={{ height: virtualizer.getTotalSize() || Math.min(path.length, 60) * 36, position: "relative" }}>
        {items.map(item => <button key={item.key} role="treeitem" tabIndex={item.index === active ? 0 : -1} aria-level={item.index + 1} aria-current={item.index === path.length - 1 ? "true" : undefined} style={{ position: "absolute", transform: `translateY(${item.start}px)`, height: item.size }} onFocus={() => setActive(item.index)}>{path[item.index]}</button>)}
      </div>
    </div>
  </section>
}

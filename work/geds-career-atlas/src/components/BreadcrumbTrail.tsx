export type BreadcrumbTrailItem = {
  key: string
  label: string
}

export interface BreadcrumbTrailProps {
  items: readonly BreadcrumbTrailItem[]
  label: string
  onSelect?: (index: number) => void
}

function BreadcrumbSeparator() {
  return (
    <svg
      className="breadcrumb-trail__separator"
      data-breadcrumb-separator
      viewBox="0 0 16 16"
      width="16"
      height="16"
      aria-hidden="true"
      focusable="false"
    >
      <path d="m6 3.5 4.5 4.5L6 12.5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function BreadcrumbTrail({ items, label, onSelect }: BreadcrumbTrailProps) {
  if (items.length === 0) return null

  return (
    <nav className="breadcrumb-trail" aria-label={label}>
      <ol className="breadcrumb-trail__list">
        {items.map((item, index) => {
          const isCurrent = index === items.length - 1

          return (
            <li className="breadcrumb-trail__item" key={item.key}>
              {index > 0 && <BreadcrumbSeparator />}
              {isCurrent ? (
                <span className="breadcrumb-trail__current" aria-current="page">{item.label}</span>
              ) : onSelect ? (
                <button className="breadcrumb-trail__button" type="button" onClick={() => onSelect(index)}>
                  {item.label}
                </button>
              ) : (
                <span className="breadcrumb-trail__ancestor">{item.label}</span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

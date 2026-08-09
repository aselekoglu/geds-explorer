import { useState, type ReactNode } from "react"
import type { SearchResult } from "../../api/types"
import { BorderGlow } from "../../components/BorderGlow"
import { useLanguage } from "../../i18n/i18n"
import { localizeEvidenceField } from "../../i18n/labels"

type Item = SearchResult["items"][number]

function HighlightedText({ children, query }: { children: string; query: string }): ReactNode {
  const value = query.trim()
  if (!value) return children
  const escaped = value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  const pieces = children.split(new RegExp(`(${escaped})`, "ig"))
  return pieces.map((piece, index) => piece.toLocaleLowerCase() === value.toLocaleLowerCase() ? <mark key={`${piece}-${index}`}>{piece}</mark> : piece)
}

export function MatchCard({ item, query, onProfile }: { item: Item; query: string; onProfile?: (orgId: string) => void }) {
  const [expanded, setExpanded] = useState(false)
  const { t } = useLanguage()
  const evidence = expanded ? item.evidence : item.evidence.slice(0, 3)
  const label = item.display_name || item.organization_name || item.title
  const isPerson = item.entity_kind === "person"
  const context = [item.department_name, isPerson ? item.organization_name : undefined].filter(Boolean)

  return <BorderGlow as="article" aria-label={label} className={`match-card match-card--${item.entity_kind}`} animated={false} borderRadius={0}>
    <div className="match-card__body">
      <p className="match-card__kind">{isPerson ? t("discover.personResult") : t("discover.teamResult")}</p>
      <h3><HighlightedText query={query}>{label}</HighlightedText></h3>
      {isPerson && item.title && <p className="match-title"><HighlightedText query={query}>{item.title}</HighlightedText></p>}
      {context.length > 0 && <p className="match-card__path">{context.map((value, index) => <span key={value}>{index > 0 && <i aria-hidden="true">›</i>}{value}</span>)}</p>}
      {evidence.length > 0 && <ul className="match-card__evidence" aria-label={t("discover.evidenceLabel")}>{evidence.map((record, index) => <li key={`${record.field}-${record.matched_phrase}-${index}`}><span>{localizeEvidenceField(record.field,t)}</span><mark>{record.matched_phrase}</mark></li>)}</ul>}
      {item.evidence.length > 3 && <button className="match-card__more" type="button" onClick={() => setExpanded(value => !value)}>{expanded ? t("discover.showLessEvidence") : t("discover.showAllEvidence")}</button>}
    </div>
    <div className="match-card__actions">
      {!isPerson && item.org_id && onProfile && <button type="button" onClick={() => onProfile(item.org_id!)}>{t("discover.openTeamProfile")}</button>}
      {isPerson && item.source_url && <a href={item.source_url} target="_blank" rel="noopener noreferrer">{t("people.official")}</a>}
    </div>
  </BorderGlow>
}

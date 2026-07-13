import { useEffect, useMemo, useState } from "react"
import type { ConstellationSlice, SearchResult } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import { Constellation } from "./Constellation"
import { ConstellationBoundary } from "./ConstellationBoundary"
import type { DiscoverScope } from "../discover/FilterRail"

type SliceClient = { constellationSlice: (rootId?: string, signal?: AbortSignal) => Promise<ConstellationSlice>; constellation?: (query: string, signal?: AbortSignal) => Promise<SearchResult> }

export function ConstellationPage({ client, query = "", focus, onFocus, scope={department:""} }: { client: SliceClient; query?: string; focus?: string; onFocus?: (orgId: string) => void;scope?:DiscoverScope }) {
  const [slice, setSlice] = useState<ConstellationSlice | null>(null)
  const [matches, setMatches] = useState<SearchResult | null>(null)
  const [rootId, setRootId] = useState<string | undefined>(focus)
  const [localFocus, setLocalFocus] = useState<string | undefined>(focus)
  const [error, setError] = useState(false)
  const { t, formatNumber } = useLanguage()
  const activeFocus = focus ?? localFocus
  useEffect(() => { const controller = new AbortController(); setError(false); client.constellationSlice(rootId, controller.signal).then(setSlice).catch(value => { if (value.name !== "AbortError") setError(true) }); return () => controller.abort() }, [client, rootId])
  useEffect(() => { const controller = new AbortController(); if (query.trim() && client.constellation) client.constellation(query, controller.signal).then(setMatches).catch(value => { if (value.name !== "AbortError") setMatches(null) }); else setMatches(null); return () => controller.abort() }, [client, query])
  const interestNodes = useMemo(() => {
    const grouped = new Map<string, { id: string; name: string; value: number; vacancy_count: number }>()
    for (const item of matches?.items ?? []) { if (!item.org_id) continue;if(scope.department&&item.department_name!==scope.department)continue; const current = grouped.get(item.org_id); if (current) { current.value += Math.max(1, item.score); if (item.vacancy_signal) current.vacancy_count += 1 } else grouped.set(item.org_id, { id: item.org_id, name: item.organization_name, value: Math.max(1, item.score), vacancy_count: item.vacancy_signal ? 1 : 0 }) }
    return [...grouped.values()]
  }, [scope,matches])
  const visualNodes = query.trim() && interestNodes.length ? interestNodes : (slice?.nodes.map(node => ({ id: node.org_id, name: node.name, value: Math.max(1, node.descendant_people_count), quality_status: node.quality_status, vacancy_count: node.vacancy_count, has_more: node.has_more })) ?? [])
  useEffect(() => { if (visualNodes.length && !visualNodes.some(node => node.id === activeFocus)) { const first = [...visualNodes].sort((a, b) => b.value - a.value || a.id.localeCompare(b.id))[0]; setLocalFocus(first.id) } }, [activeFocus, visualNodes])
  function select(orgId: string) { setLocalFocus(orgId); onFocus?.(orgId) }
  function reset() { setRootId(undefined); setLocalFocus(undefined) }
  if (error) return <section className="constellation-page"><h1>{t("constellation.title")}</h1><p role="status">{t("constellation.unavailable")}</p></section>
  if (!slice) return <p role="status" className="constellation-loading">{t("constellation.loading")}</p>
  const selected = slice.nodes.find(node => node.org_id === activeFocus)
  const selectedMatch = matches?.items.find(item => item.org_id === activeFocus)
  return <section className="constellation-page" id="constellation">
    <header className="constellation-heading"><div><h1>{query.trim() ? t("constellation.queryTitle", { query: query.trim() }) : t("constellation.title")}</h1><p>{query.trim() ? t("constellation.queryIntro", { count: formatNumber(interestNodes.length) }) : t("constellation.intro")}</p></div>{rootId && <button type="button" onClick={reset}>{t("constellation.all")}</button>}</header>
    <div className="constellation-stage"><ConstellationBoundary nodes={visualNodes} label={t("constellation.map")} focus={activeFocus} onFocus={select}><Constellation nodes={visualNodes} focus={activeFocus} onFocus={select} /></ConstellationBoundary>{(selected || selectedMatch) && <aside className="constellation-evidence" aria-live="polite"><h2>{selected?.name ?? selectedMatch?.organization_name}</h2><p><strong>{t("common.matchedBecause")}</strong> {selectedMatch?.evidence[0]?.source_text ?? t("constellation.hierarchyEvidence")}</p>{selected && <dl><div><dt>{t("common.peopleIndexed")}</dt><dd>{formatNumber(selected.descendant_people_count)}</dd></div><div><dt>{t("common.childTeams")}</dt><dd>{formatNumber(selected.child_count)}</dd></div></dl>}{selected?.child_count ? <button type="button" onClick={() => setRootId(selected.org_id)}>{t("constellation.explore")}</button> : null}</aside>}</div>
    <footer className="constellation-legend"><span><i className="legend-dot legend-dot--selected" />{t("constellation.selected")}</span><span><i className="legend-dot" />{query.trim() ? t("constellation.matchingTeam") : t("constellation.organization")}</span><span>{t("constellation.area", { measure: query.trim() ? t("constellation.matchStrength") : t("constellation.peopleMeasure") })}</span>{slice.truncated && <span>{t("constellation.aggregated")}</span>}</footer>
  </section>
}

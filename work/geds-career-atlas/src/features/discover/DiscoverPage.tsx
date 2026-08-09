import { useEffect, useState } from "react"
import type { QueryInterpretation, SearchResult } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import type { DiscoverScope } from "./FilterRail"
import { InterpretationChips } from "./InterpretationChips"
import { MatchCard } from "./MatchCard"

type Item = SearchResult["items"][number]
type Client = { search: (q: string, signal?: AbortSignal) => Promise<{ items: Item[]; interpretation?: QueryInterpretation }> }
export type SearchKind = "all" | "topics" | "teams" | "people"

export function DiscoverPage({ search, client, scope = { department: "" }, onScopeChange, onProfile }: {
  search: string
  client: Client
  scope?: DiscoverScope
  onScopeChange?: (next: DiscoverScope) => void
  onProfile?: (orgId: string) => void
}) {
  const [items, setItems] = useState<Item[]>([])
  const [interpretation, setInterpretation] = useState<QueryInterpretation | undefined>()
  const [kind, setKind] = useState<SearchKind>("all")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const { t, formatNumber } = useLanguage()

  useEffect(() => {
    const controller = new AbortController()
    if (!search) {
      setItems([])
      setInterpretation(undefined)
      setLoading(false)
      return () => controller.abort()
    }
    setItems([])
    setInterpretation(undefined)
    setLoading(true)
    const timer = setTimeout(() => {
      setError("")
      client.search(search, controller.signal).then(result => {
        setItems(result.items)
        setInterpretation(result.interpretation)
      }).catch(value => {
        if (value?.name !== "AbortError") setError(t("discover.error"))
      }).finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    }, 250)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [search, client, t])

  const visibleItems = items.filter(item =>
    (!scope.department || item.department_name === scope.department) &&
    (kind === "all" || (kind === "teams" && item.entity_kind === "organization") || (kind === "people" && item.entity_kind === "person"))
  )
  const showTopics = kind === "all" || kind === "topics"
  const topicCount = interpretation?.category_ids.length ?? 0
  const labels: Record<SearchKind, string> = {
    all: t("discover.kindAll"),
    topics: t("discover.kindTopics"),
    teams: t("discover.kindTeams"),
    people: t("discover.kindPeople"),
  }
  const resultSummary = kind === "topics"
    ? t("discover.topicCount", { count: formatNumber(topicCount) })
    : t("discover.resultsCount", { count: formatNumber(visibleItems.length) })
  const showNoMatch = !loading && !error && search && visibleItems.length === 0 && (!showTopics || topicCount === 0)

  return <section aria-labelledby="discover-results-title" className="discover-results">
    <header className="discover-results__header">
      <div>
        <p className="service-kicker">{t("discover.results")}</p>
        <h2 id="discover-results-title">{t("discover.resultsFor", { query: search })}</h2>
        <p className="discover-results__count" aria-live="polite">{loading ? t("discover.loading") : resultSummary}</p>
      </div>
      <fieldset className="search-kind"><legend>{t("discover.resultType")}</legend>{(Object.keys(labels) as SearchKind[]).map(value => <label key={value}><input type="radio" name="search-kind" value={value} checked={kind === value} onChange={() => setKind(value)}/><span>{labels[value]}</span></label>)}</fieldset>
    </header>
    {showTopics && <InterpretationChips interpretation={interpretation} scope={scope} onScopeChange={onScopeChange}/>}
    {loading && items.length === 0 && <div className="result-skeletons" aria-hidden="true"><span/><span/><span/></div>}
    {error && <div className="inline-state inline-state--error" role="alert"><strong>{t("discover.error")}</strong></div>}
    {showNoMatch && <div className="inline-state"><strong>{t("discover.noMatch")}</strong></div>}
    <div className="match-grid">{!error && kind !== "topics" && visibleItems.map(item => <MatchCard key={item.entity_id} item={item} query={search} onProfile={onProfile}/>)}</div>
  </section>
}

import { useEffect, useState } from "react"
import { useLanguage } from "../../i18n/i18n"

type Item = { entity_id: string; entity_kind: string; title: string; organization_name: string; score: number; confidence: string; evidence: Array<{ field: string; matched_phrase: string; source_text: string; weight: number; category_id: string }> }
type Client = { search: (q: string) => Promise<{ items: Item[] }> }

export function DiscoverPage({ search, client }: { search: string; client: Client }) {
  const [items, setItems] = useState<Item[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const { t } = useLanguage()
  useEffect(() => {
    if (!search) { setItems([]); return }
    const timer = setTimeout(() => {
      setLoading(true); setError("")
      client.search(search).then(result => setItems(result.items)).catch(() => setError(t("discover.error"))).finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(timer)
  }, [search, client, t])
  return <section aria-label={t("discover.label")}>
    <p className="interpretation">{t("discover.interpretation")}</p>
    {loading && <p aria-live="polite">{t("discover.loading")}</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !error && search && items.length === 0 && <p>{t("discover.noMatch")}</p>}
    <div>{items.map(item => <article key={item.entity_id} aria-label={item.organization_name || item.title}><h2>{item.organization_name || item.title}</h2><p>{t("common.confidence", { level: t(`common.${item.confidence}`) })}</p><p>{t("common.matchedBecause")} {item.evidence.slice(0, 3).map(evidence => t("discover.evidence", { field: evidence.field, phrase: evidence.matched_phrase })).join(", ")}</p><small>{t("discover.vacancy")}</small></article>)}</div>
  </section>
}

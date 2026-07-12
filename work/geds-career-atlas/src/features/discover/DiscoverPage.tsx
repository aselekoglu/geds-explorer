import { useEffect, useState } from "react"
import { useLanguage } from "../../i18n/i18n"
import type { QueryInterpretation } from "../../api/types"
import type { DiscoverFilters } from "./FilterRail"
import { InterpretationChips } from "./InterpretationChips"
import { MatchCard } from "./MatchCard"

type Item = { entity_id: string; entity_kind: string; title: string; organization_name: string; department_name?: string; score: number; confidence: string; vacancy_signal?: boolean; evidence: Array<{ field: string; matched_phrase: string; source_text: string; weight: number; category_id: string }> }
type Client = { search: (q: string) => Promise<{ items: Item[]; interpretation?:QueryInterpretation }> }

const ranks:Record<string,number>={none:0,exploratory:1,medium:2,high:3}
export function DiscoverPage({ search, client, filters={domain:"",department:"",confidence:"exploratory",vacancy:false},onFiltersChange }: { search: string; client: Client; filters?:DiscoverFilters;onFiltersChange?:(next:DiscoverFilters)=>void }) {
  const [items, setItems] = useState<Item[]>([])
  const [interpretation,setInterpretation]=useState<QueryInterpretation|undefined>()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const { t } = useLanguage()
  useEffect(() => {
    if (!search) { setItems([]); return }
    setLoading(true)
    const timer = setTimeout(() => {
      setError("")
      client.search(search).then(result => {setItems(result.items);setInterpretation(result.interpretation)}).catch(() => setError(t("discover.error"))).finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(timer)
  }, [search, client, t])
  const visibleItems=items.filter(item=>(ranks[item.confidence]??0)>=ranks[filters.confidence]&&(!filters.domain||item.evidence.some(record=>record.category_id===filters.domain))&&(!filters.department||item.department_name===filters.department)&&(!filters.vacancy||item.vacancy_signal))
  return <section aria-label={t("discover.label")} className="discover-results">
    <InterpretationChips interpretation={interpretation} filters={filters} onFiltersChange={onFiltersChange}/>
    {loading && <p aria-live="polite">{t("discover.loading")}</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !error && search && visibleItems.length === 0 && <p>{t("discover.noMatch")}</p>}
    <div className="match-grid">{visibleItems.map(item => <MatchCard key={item.entity_id} item={item}/>)}</div>
  </section>
}

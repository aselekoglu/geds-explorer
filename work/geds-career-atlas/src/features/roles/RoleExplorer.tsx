import { useMemo, useState } from "react"
import type { SearchResult } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"

type RoleItem = SearchResult["items"][number]
const confidenceRank: Record<string, number> = { none: 0, exploratory: 1, medium: 2, high: 3 }
const categoryLabel = (category: string) => category.split(/[-_]/).map(word => word.toLowerCase() === "ai" ? "AI" : word ? `${word[0].toUpperCase()}${word.slice(1)}` : "").join(" ")

export function RoleExplorer({ items }: { items: RoleItem[] }) {
  const { t } = useLanguage()
  const [confidence, setConfidence] = useState("exploratory")
  const [institution, setInstitution] = useState("")
  const [subtree,setSubtree]=useState("")
  const [vacancyOnly, setVacancyOnly] = useState(false)
  const institutions = useMemo(() => [...new Set(items.map(item => item.department_name).filter((name):name is string=>Boolean(name)))].sort(), [items])
  const subtrees=useMemo(()=>[...new Set(items.map(item=>item.organization_name))].sort(),[items])
  const grouped = useMemo(() => {
    const groups = new Map<string, RoleItem[]>()
    for (const item of items) {
      if ((confidenceRank[item.confidence] ?? 0) < confidenceRank[confidence]) continue
      if (institution && item.department_name !== institution) continue
      if(subtree&&item.organization_name!==subtree)continue
      if (vacancyOnly && !item.vacancy_signal) continue
      const categories = [...new Set(item.evidence.map(evidence => evidence.category_id))]
      for (const category of categories.length ? categories : ["uncategorized"]) groups.set(category, [...(groups.get(category) ?? []), item])
    }
    return [...groups].sort(([a], [b]) => a.localeCompare(b))
  }, [confidence, institution, items, subtree,vacancyOnly])
  return <section className="role-explorer" aria-labelledby="role-explorer-title">
    <h3 id="role-explorer-title">{t("roles.title")}</h3>
    <div className="role-filters"><label>{t("roles.confidence")}<select value={confidence} onChange={event => setConfidence(event.target.value)}><option value="exploratory">{t("common.exploratory")}</option><option value="medium">{t("common.medium")}</option><option value="high">{t("common.high")}</option></select></label><label>{t("roles.institution")}<select value={institution} onChange={event => setInstitution(event.target.value)}><option value="">{t("roles.allInstitutions")}</option>{institutions.map(name => <option key={name}>{name}</option>)}</select></label><label>{t("roles.subtree")}<select value={subtree} onChange={event=>setSubtree(event.target.value)}><option value="">{t("roles.allSubtrees")}</option>{subtrees.map(name=><option key={name}>{name}</option>)}</select></label><label className="role-checkbox"><input type="checkbox" checked={vacancyOnly} onChange={event => setVacancyOnly(event.target.checked)} />{t("roles.vacancyOnly")}</label></div>
    {grouped.length === 0 ? <p>{t("roles.noRoles")}</p> : grouped.map(([category, roles]) => <section key={category}><h4>{categoryLabel(category)}</h4><ul>{roles.map(role => <li key={`${category}:${role.entity_id}`}><span>{role.title}</span>{role.org_id && <a href={`?focus=${encodeURIComponent(role.org_id)}`}>{role.organization_name}</a>}</li>)}</ul></section>)}
  </section>
}

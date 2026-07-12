import { useLanguage } from "../../i18n/i18n"
import type { QueryInterpretation } from "../../api/types"
import type { DiscoverFilters } from "./FilterRail"

export function InterpretationChips({interpretation,filters,onFiltersChange}:{interpretation?:QueryInterpretation;filters:DiscoverFilters;onFiltersChange?:(next:DiscoverFilters)=>void}){
  const {t}=useLanguage()
  const terms=(interpretation?.expanded_terms??[]).slice(0,6)
  return <div className="interpretation-panel" aria-label={t("discover.interpretedAs")}>
    <p className="interpretation">{interpretation?.category_ids.length ? interpretation.category_ids.map(id=>t(`domains.${id}`)).join(", ") : t("discover.interpretation")}</p>
    {terms.length>0&&<p className="expanded-terms"><strong>{t("discover.relatedTerms")}</strong> {terms.join(" · ")}</p>}
    {onFiltersChange&&<div className="active-constraints">
      {filters.domain&&<button type="button" onClick={()=>onFiltersChange({...filters,domain:""})} aria-label={t("discover.removeDomain")}>{t(`domains.${filters.domain}`)} ×</button>}
      {filters.department&&<button type="button" onClick={()=>onFiltersChange({...filters,department:""})} aria-label={t("discover.removeInstitution")}>{filters.department} ×</button>}
      {filters.confidence!=="exploratory"&&<button type="button" onClick={()=>onFiltersChange({...filters,confidence:"exploratory"})} aria-label={t("discover.removeConfidence")}>{t(`common.${filters.confidence}`)} ×</button>}
      {filters.vacancy&&<button type="button" onClick={()=>onFiltersChange({...filters,vacancy:false})} aria-label={t("discover.removeVacancy")}>{t("discover.vacancyFilter")} ×</button>}
    </div>}
  </div>
}

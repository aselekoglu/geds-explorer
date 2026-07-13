import type { QueryInterpretation } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import type { DiscoverScope } from "./FilterRail"

export function InterpretationChips({interpretation,scope,onScopeChange}:{interpretation?:QueryInterpretation;scope:DiscoverScope;onScopeChange?:(next:DiscoverScope)=>void}){
  const {t}=useLanguage()
  const terms=(interpretation?.expanded_terms??[]).slice(0,6)
  return <div className="interpretation-panel" aria-label={t("discover.interpretedAs")}>
    <p className="interpretation">{interpretation?.category_ids.length?interpretation.category_ids.map(id=>t(`domains.${id}`)).join(", "):t("discover.interpretation")}</p>
    {terms.length>0&&<p className="expanded-terms"><strong>{t("discover.relatedTerms")}</strong> {terms.join(" · ")}</p>}
    {onScopeChange&&scope.department&&<div className="active-constraints"><button type="button" onClick={()=>onScopeChange({department:""})} aria-label={t("discover.removeInstitution")}>{scope.department} ×</button></div>}
  </div>
}

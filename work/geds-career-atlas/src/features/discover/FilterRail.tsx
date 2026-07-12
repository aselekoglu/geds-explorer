import type { DepartmentPage } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"

export type DiscoverFilters={domain:string;department:string;confidence:"exploratory"|"medium"|"high";vacancy:boolean}

export function FilterRail({departments,value,qualityStatus,onChange}:{departments:DepartmentPage["items"];value:DiscoverFilters;qualityStatus:string;onChange:(value:DiscoverFilters)=>void}){
  const {t}=useLanguage()
  return <div className="filter-rail filter-rail--functional">
    <label>{t("discover.domain")}<select value={value.domain} onChange={event=>onChange({...value,domain:event.target.value})}><option value="">{t("discover.allDomains")}</option><option value="data-ai-research">{t("domains.data-ai-research")}</option><option value="software-digital">{t("domains.software-digital")}</option><option value="cybersecurity">{t("domains.cybersecurity")}</option><option value="policy-programs">{t("domains.policy-programs")}</option></select></label>
    <label>{t("roles.institution")}<select value={value.department} onChange={event=>onChange({...value,department:event.target.value})}><option value="">{t("roles.allInstitutions")}</option>{departments.map(department=><option key={department.department_id} value={department.name}>{department.name}</option>)}</select></label>
    <label>{t("roles.confidence")}<select value={value.confidence} onChange={event=>onChange({...value,confidence:event.target.value as DiscoverFilters["confidence"]})}><option value="exploratory">{t("common.exploratory")}</option><option value="medium">{t("common.medium")}</option><option value="high">{t("common.high")}</option></select></label>
    <label className="filter-check"><input type="checkbox" checked={value.vacancy} onChange={event=>onChange({...value,vacancy:event.target.checked})}/>{t("discover.vacancyFilter")}</label>
    <span className="quality-chip">{t("discover.quality",{status:qualityStatus.replaceAll("_"," ")})}</span>
  </div>
}

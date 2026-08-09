import type { DepartmentPage } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"
import { localizeQualityStatus } from "../../i18n/labels"

export type DiscoverScope={department:string}

export function FilterRail({departments,value,qualityStatus,onChange}:{departments:DepartmentPage["items"];value:DiscoverScope;qualityStatus:string;onChange:(value:DiscoverScope)=>void}){
  const {t}=useLanguage()
  return <div className="filter-rail institution-scope" aria-label={t("app.filters")}>
    <label><span>{t("roles.institution")}</span><select value={value.department} onChange={event=>onChange({department:event.target.value})}><option value="">{t("roles.allInstitutions")}</option>{departments.map(department=><option key={department.department_id} value={department.name}>{department.name}</option>)}</select></label>
    <span className="quality-chip" role="status"><i aria-hidden="true"/>{t("discover.quality",{status:localizeQualityStatus(qualityStatus,t)})}</span>
  </div>
}

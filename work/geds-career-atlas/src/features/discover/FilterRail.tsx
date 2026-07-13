import type { DepartmentPage } from "../../api/types"
import { useLanguage } from "../../i18n/i18n"

export type DiscoverScope={department:string}

export function FilterRail({departments,value,qualityStatus,onChange}:{departments:DepartmentPage["items"];value:DiscoverScope;qualityStatus:string;onChange:(value:DiscoverScope)=>void}){
  const {t}=useLanguage()
  return <div className="filter-rail institution-scope">
    <label>{t("roles.institution")}<select value={value.department} onChange={event=>onChange({department:event.target.value})}><option value="">{t("roles.allInstitutions")}</option>{departments.map(department=><option key={department.department_id} value={department.name}>{department.name}</option>)}</select></label>
    <span className="quality-chip">{t("discover.quality",{status:qualityStatus.replaceAll("_"," ")})}</span>
  </div>
}

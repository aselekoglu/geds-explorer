import { useLanguage } from "../../i18n/i18n"
import { groupObservedTitles } from "./titleGroups"

export function GroupedRoles({titles,onRoleQuery}:{titles:string[];onRoleQuery?:(title:string)=>void}){
  const {t}=useLanguage()
  const groups=groupObservedTitles(titles)
  const roles=groups.filter(group=>!group.empty)
  const missing=groups.find(group=>group.empty)
  if(!groups.length)return <p className="title-groups__empty">{t("profile.rolesEmpty")}</p>
  return <div className="title-groups">
    <p className="title-groups__summary">{t("profile.rolesSummary",{records:titles.length,roles:roles.length})}</p>
    {roles.length>0&&<table className="title-groups__table">
      <thead><tr><th scope="col">{t("profile.roleColumn")}</th><th scope="col">{t("profile.recordsColumn")}</th></tr></thead>
      <tbody>{roles.map(group=><tr key={group.key}><th scope="row"><button type="button" aria-label={t("profile.filterByRole",{title:group.label})} onClick={()=>onRoleQuery?.(group.label)}>{group.label}</button></th><td>{group.count}</td></tr>)}</tbody>
    </table>}
    {missing&&<details className="title-groups__missing"><summary><span>{t("profile.noTitle")}</span><strong>{missing.count}</strong></summary><p>{t("profile.noTitleHelp")}</p></details>}
  </div>
}

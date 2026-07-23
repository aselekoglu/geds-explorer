import { BreadcrumbTrail, type BreadcrumbTrailItem } from "../../components/BreadcrumbTrail"

export function OrgBreadcrumb({path,onBack,onSelect,label}:{path:string[];onBack:()=>void;onSelect:(index:number)=>void;label:string}){
  if(!path.length)return null
  const items:BreadcrumbTrailItem[]=path.map((itemLabel,index)=>({key:`${index}:${itemLabel}`,label:itemLabel}))
  return <div className="org-breadcrumb"><button type="button" className="org-breadcrumb__back" onClick={onBack} aria-label="Back one organization level">←</button><BreadcrumbTrail items={items} label={label} onSelect={onSelect}/></div>
}

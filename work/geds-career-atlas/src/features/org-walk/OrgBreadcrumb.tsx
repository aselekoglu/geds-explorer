export function OrgBreadcrumb({path,onBack,label}:{path:string[];onBack:()=>void;label:string}){
  if(!path.length)return null
  return <div className="org-breadcrumb"><button type="button" onClick={onBack} aria-label="Back one organization level">←</button><nav aria-label={label}>{path.join(" / ")}</nav></div>
}

export type Evidence={field:string;matched_phrase:string;source_text:string;weight:number;category_id:string}
export type SearchResult={items:Array<{entity_id:string;entity_kind:string;org_id?:string;title:string;organization_name:string;score:number;confidence:string;evidence:Evidence[]}>;snapshot_id:string;etag:string}
export type OrgNode={org_id:string;name:string;parent_id?:string;depth:number;child_count:number;descendant_people_count:number}
export type OrgPage={items:OrgNode[];snapshot_id:string;etag:string}
export type DepartmentPage={items:Array<{department_id:string;name:string}>;snapshot_id:string;etag:string}
export type TeamProfile={org_id:string;name:string;department_name:string;canonical_path:string[];direct_people_count:number;descendant_people_count:number;child_count:number;snapshot_id:string}

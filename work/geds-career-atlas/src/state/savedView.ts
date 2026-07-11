import type { ExplorerSearch } from "./explorerSearch"

const key="geds-career-atlas:saved-views:v1"
export type SavedView=ExplorerSearch&{id:string;label:string;note:string;comparisons:string[];created_at:string}
export type SavedViewInput=ExplorerSearch&{label?:string;note?:string;comparisons?:string[]}

function cleanText(value:string,limit:number){return value.slice(0,limit).replace(/email|phone|person_name|source_url/gi,"[redacted]")}
export function listSavedViews():SavedView[]{try{const value=JSON.parse(localStorage.getItem(key)??"[]");return Array.isArray(value)?value as SavedView[]:[]}catch{return[]}}
export function saveView(view:SavedViewInput){const saved:SavedView={q:view.q,categories:[...view.categories],department:view.department,org:view.org,confidence:view.confidence,vacancy:view.vacancy,lang:view.lang,mode:view.mode,focus:view.focus,id:crypto.randomUUID(),label:cleanText((view.label??view.q)||"Saved exploration",120),note:cleanText(view.note??"",2000),comparisons:(view.comparisons??[]).slice(0,4),created_at:new Date().toISOString()};localStorage.setItem(key,JSON.stringify([...listSavedViews(),saved]));return saved}
export function loadView():SavedView|undefined{return listSavedViews().at(-1)}

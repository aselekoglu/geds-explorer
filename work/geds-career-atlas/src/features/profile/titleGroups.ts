export type TitleGroup={key:string;label:string;count:number;empty:boolean}

export const normalizeObservedTitle=(title?:string|null)=>(title??"").trim().replace(/\s+/g," ")

export function groupObservedTitles(titles:string[]):TitleGroup[]{
  const groups=new Map<string,TitleGroup>()
  for(const raw of titles){
    const normalized=normalizeObservedTitle(raw)
    const key=normalized.toLocaleLowerCase()
    const current=groups.get(key)
    if(current)current.count+=1
    else groups.set(key,{key,label:normalized||"No title recorded",count:1,empty:!normalized})
  }
  return [...groups.values()].sort((a,b)=>Number(a.empty)-Number(b.empty)||a.label.localeCompare(b.label))
}

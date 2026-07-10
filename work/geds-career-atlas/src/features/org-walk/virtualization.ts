export function visibleWindow<T>(items:T[],start:number,size:number){return items.slice(Math.max(0,start),Math.max(0,start)+size)}

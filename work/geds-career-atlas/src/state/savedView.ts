import type { ExplorerSearch } from "./explorerSearch"
const key="geds-career-atlas:saved-view"
export function saveView(view:ExplorerSearch){localStorage.setItem(key,JSON.stringify(view))}
export function loadView():ExplorerSearch|undefined{const value=localStorage.getItem(key);return value?JSON.parse(value) as ExplorerSearch:undefined}

import { productCopy } from "../../copy/product"
export function VacancyNotice({lang="en"}:{lang?:"en"|"fr"}){return <p role="note">{productCopy[lang].vacancy}</p>}

import { productCopy } from "../../copy/product"
export function TeamProfile({name,roles}:{name:string;roles:string[]}){return <section aria-label={`${name} team profile`}><h2>{name}</h2><p>Explore the hierarchy, work context, and recorded roles.</p><h3>Current roles</h3><ul>{roles.map(role=><li key={role}>{role}</li>)}</ul><footer>{productCopy.en.vacancy}</footer></section>}

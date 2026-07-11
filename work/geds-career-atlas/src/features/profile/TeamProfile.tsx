import { productCopy } from "../../copy/product"

type ProfileFacts = { org_id: string; department_name: string; canonical_path: string[]; direct_people_count: number; descendant_people_count: number; child_count: number; snapshot_id: string }

export function TeamProfile({ name, roles, profile }: { name: string; roles: string[]; profile?: ProfileFacts }) {
  return <section aria-label={`${name} team profile`}>
    <p className="eyebrow">TEAM PROFILE</p><h2>{name}</h2>
    {profile && <><p>{profile.canonical_path.join(" / ")}</p><dl><div><dt>Observed people</dt><dd>{profile.direct_people_count.toLocaleString()}</dd></div><div><dt>People in this branch</dt><dd>{profile.descendant_people_count.toLocaleString()}</dd></div><div><dt>Child teams</dt><dd>{profile.child_count}</dd></div></dl></>}
    <h3>Observed roles</h3><p>These are title records observed in the current GEDS snapshot, not open jobs.</p><ul>{roles.map(role => <li key={role}>{role}</li>)}</ul>
    <h3>Matched because</h3><p>Inferred from observed organization and role names. Validate details through the official source before acting.</p>
    <p role="note">{productCopy.en.vacancy}</p>
  </section>
}

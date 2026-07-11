import { expect, type APIRequestContext, type Page } from "@playwright/test"

export async function waitForAtlas(page: Page) {
  await expect(page).toHaveTitle("GEDS Career Atlas")
  await expect(page.getByRole("heading", { name: /Government at a glance|Where .* appears/ })).toBeVisible()
}

export async function findProfile(
  request: APIRequestContext,
  predicate: (profile: Record<string, unknown>) => boolean,
) {
  const roots = (await (await request.get("/api/orgs/root/children?limit=200")).json()).items as Array<{ org_id: string }>
  const queue = [...roots]
  let inspected = 0
  while (queue.length && inspected < 600) {
    const org = queue.shift()!
    const profile = await (await request.get(`/api/orgs/${org.org_id}/profile`)).json()
    inspected += 1
    if (predicate(profile)) return profile as Record<string, unknown> & { org_id: string; name: string }
    if ((profile.child_count as number) > 0 && inspected < 400) {
      const children = (await (await request.get(`/api/orgs/${org.org_id}/children?limit=200`)).json()).items as Array<{ org_id: string }>
      queue.push(...children)
    }
  }
  throw new Error(`No matching real-data profile found after ${inspected} bounded reads`)
}

export async function findProfileFromInterestResults(
  request: APIRequestContext,
  predicate: (profile: Record<string, unknown>) => boolean,
) {
  const orgIds = new Set<string>()
  for (const query of ["AI", "software", "cybersecurity", "policy", "data"]) {
    const result = await (await request.get(`/api/search?q=${encodeURIComponent(query)}&limit=200`)).json()
    for (const item of result.items as Array<{ org_id?: string }>) if (item.org_id) orgIds.add(item.org_id)
  }
  const ids = [...orgIds]
  for (let offset = 0; offset < ids.length; offset += 25) {
    const profiles = await Promise.all(ids.slice(offset, offset + 25).map(async orgId =>
      (await (await request.get(`/api/orgs/${orgId}/profile`)).json()) as Record<string, unknown> & { org_id: string; name: string },
    ))
    const found = profiles.find(predicate)
    if (found) return found
  }
  throw new Error(`No matching profile found in ${ids.length} bounded interest-result organizations`)
}

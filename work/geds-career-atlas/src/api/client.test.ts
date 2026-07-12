import { expect, it, vi } from "vitest"
import { CareerApiClient, CareerApiError } from "./client"
it("raises typed API errors", async () => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:"index stale"}),{status:409}))); await expect(new CareerApiClient().meta()).rejects.toMatchObject({status:409} satisfies Partial<CareerApiError>) })

it("requests direct team people with encoded public filters", async () => {
  const fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify({items:[],total:0,limit:25,offset:0,available_classifications:[],snapshot_id:"snapshot",quality_status:"complete",etag:"etag"}),{status:200}))
  vi.stubGlobal("fetch",fetchMock)

  await new CareerApiClient().people("team/id",{q:"Ada Lovelace",classification:"IT-02",sort:"title",limit:25,offset:0})

  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/orgs/team%2Fid/people?"),expect.any(Object))
  expect(fetchMock.mock.calls[0][0]).toContain("q=Ada+Lovelace")
  expect(fetchMock.mock.calls[0][0]).toContain("classification=IT-02")
  expect(fetchMock.mock.calls[0][0]).toContain("sort=title")
})

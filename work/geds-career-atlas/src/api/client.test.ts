import { expect, it, vi } from "vitest"
import { CareerApiClient, CareerApiError } from "./client"
it("raises typed API errors", async () => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({detail:"index stale"}),{status:409}))); await expect(new CareerApiClient().meta()).rejects.toMatchObject({status:409} satisfies Partial<CareerApiError>) })

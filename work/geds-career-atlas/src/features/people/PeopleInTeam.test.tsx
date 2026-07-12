import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { expect, it, vi } from "vitest"
import { PeopleInTeam } from "./PeopleInTeam"

const officialUrl="https://geds-sage.gc.ca/en/GEDS?pgid=015&dn=ada"

function page() {
  return {
    items:[{
      person_id:"person-1",
      display_name:"Ada Lovelace",
      observed_title:"IT02 Support Analyst",
      observed_classifications:["IT-02"],
      org_id:"ai",
      organization_name:"AI Centre",
      snapshot_id:"snapshot",
      snapshot_as_of:"2026-07-09T00:00:00Z",
      source_url:officialUrl,
    }],
    total:1,
    limit:50,
    offset:0,
    available_classifications:["IT-02","EC-04"],
    snapshot_id:"snapshot",
    quality_status:"complete",
    etag:"etag",
  }
}

it("shows observed people, classifications, and official GEDS links without contact fields",async()=>{
  const client={people:vi.fn().mockResolvedValue(page())}
  render(<PeopleInTeam orgId="ai" client={client}/>)

  expect(await screen.findByText("Ada Lovelace")).toBeVisible()
  expect(screen.getByText("IT02 Support Analyst")).toBeVisible()
  expect(screen.getByLabelText("Classification observed in title: IT-02")).toHaveTextContent("IT-02")
  expect(screen.getByRole("link",{name:/View in official GEDS/i})).toHaveAttribute("href",officialUrl)
  expect(screen.queryByText(/email|phone/i)).not.toBeInTheDocument()
})

it("refetches with search and classification filters",async()=>{
  const client={people:vi.fn().mockResolvedValue(page())}
  render(<PeopleInTeam orgId="ai" client={client}/>)
  await screen.findByText("Ada Lovelace")

  fireEvent.change(screen.getByRole("searchbox",{name:/Search people/i}),{target:{value:"Ada"}})
  fireEvent.change(screen.getByRole("combobox",{name:/Observed classification/i}),{target:{value:"IT-02"}})

  await waitFor(()=>expect(client.people).toHaveBeenLastCalledWith("ai",expect.objectContaining({q:"Ada",classification:"IT-02"}),expect.any(AbortSignal)))
})

it("does not render a guessed link when the official source is unavailable",async()=>{
  const unavailable=page()
  unavailable.items[0]={...unavailable.items[0],source_url:""}
  render(<PeopleInTeam orgId="ai" client={{people:vi.fn().mockResolvedValue(unavailable)}}/>)

  expect(await screen.findByText("Official GEDS record unavailable")).toBeVisible()
  expect(screen.queryByRole("link",{name:/View in official GEDS/i})).not.toBeInTheDocument()
})

import { render, screen } from "@testing-library/react"
import { DEVELOPER_URL, DeveloperProfileCard, PROFILE_CARD_OPTIONS } from "./DeveloperProfileCard"

it("makes the developer card an accessible tracked external link", () => {
  render(<DeveloperProfileCard />)
  const card = screen.getByRole("link", { name: /visit ata selekoglu's website/i })
  expect(card).toHaveAttribute("href", DEVELOPER_URL)
  expect(card).toHaveAttribute("data-profile-tilt", PROFILE_CARD_OPTIONS.enableTilt ? "enabled" : "disabled")
  expect(screen.getByText("Ata Selekoglu")).toBeVisible()
  expect(screen.getByText("Developer")).toBeVisible()
})

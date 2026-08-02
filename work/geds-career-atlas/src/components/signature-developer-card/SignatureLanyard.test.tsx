import { render, screen } from "@testing-library/react"
import { SignatureDeveloperCard } from "./SignatureDeveloperCard"
import { SignatureLanyard } from "./SignatureLanyard"

it("keeps the camera contract and shows the real profile card when WebGL is unavailable", () => {
  render(<SignatureLanyard position={[0, 0, 45]} renderCard={props => <SignatureDeveloperCard profile={{ name: "Ada Lovelace", title: "Developer", href: "https://example.test" }} {...props} />} />)

  expect(screen.getByRole("link", { name: /visit ada lovelace's website/i })).toBeVisible()
  expect(screen.getByRole("link")).toHaveAttribute("data-profile-tilt", "disabled")
  expect(document.querySelector('[data-camera-distance="45"]')).toHaveAttribute("data-render-mode", "webgl-fallback")
  expect(document.querySelector("canvas")).toBeNull()
})

import { render, screen } from "@testing-library/react"
import Lanyard from "./Lanyard"

it("keeps the camera contract and shows the real profile card when WebGL is unavailable", () => {
  render(<Lanyard position={[0, 0, 45]} />)

  expect(screen.getByRole("link", { name: /visit ata selekoglu's website/i })).toBeVisible()
  expect(screen.getByRole("link")).toHaveAttribute("data-profile-tilt", "disabled")
  expect(document.querySelector('[data-camera-distance="45"]')).toHaveAttribute("data-render-mode", "webgl-fallback")
  expect(document.querySelector("canvas")).toBeNull()
})

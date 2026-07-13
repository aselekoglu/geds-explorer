import { expect, it } from "vitest"
import { publicViewHash, readPublicView } from "./publicView"

it("maps only supported public hashes to primary views", () => {
  expect(readPublicView("#explorer")).toBe("explorer")
  expect(readPublicView("#about")).toBe("about")
  expect(readPublicView("#tours")).toBe("discover")
  expect(publicViewHash("discover")).toBe("#discover")
})

import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { TeamProfile } from "./TeamProfile"
it("uses non-claiming vacancy language",()=>{render(<TeamProfile name="AI Centre" roles={["Data Scientist"]} />);expect(screen.getByText("Recorded as vacant in GEDS — unverified")).toBeVisible();expect(screen.queryByRole("link",{name:/apply/i})).not.toBeInTheDocument()})

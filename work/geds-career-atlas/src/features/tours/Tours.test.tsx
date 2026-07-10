import { render, screen } from "@testing-library/react"
import { expect,it } from "vitest"
import { Tours } from "./Tours"
it("renders a privacy-safe curated tour",()=>{render(<Tours/>);expect(screen.getByRole("link",{name:/AI across government/i})).toBeVisible();expect(screen.queryByText(/email|phone/i)).not.toBeInTheDocument()})

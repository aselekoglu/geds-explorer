import { render,screen } from "@testing-library/react"
import { expect,it } from "vitest"
import { VacancyNotice } from "./VacancyNotice"
it("never presents a vacancy as an application action",()=>{render(<VacancyNotice lang="fr"/>);expect(screen.getByText(/non vérifié/i)).toBeVisible();expect(screen.queryByRole("link",{name:/apply|postuler/i})).not.toBeInTheDocument()})

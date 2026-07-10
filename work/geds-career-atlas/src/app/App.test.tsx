import { render, screen } from "@testing-library/react"
import { App } from "./App"
it("renders public navigation without crawler actions", () => { render(<App />); expect(screen.getByRole("link", { name: /discover/i })).toBeVisible(); expect(screen.getByRole("link", { name: /constellation/i })).toBeVisible(); expect(screen.queryByText(/start crawler/i)).not.toBeInTheDocument() })

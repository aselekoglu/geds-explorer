import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { Constellation } from "./Constellation"
it("synchronizes selected focus with accessible list",()=>{render(<Constellation nodes={[{id:"a",name:"AI Centre"}]} focus="a"/>);expect(screen.getByRole("option",{name:"AI Centre"})).toHaveAttribute("aria-selected","true")})

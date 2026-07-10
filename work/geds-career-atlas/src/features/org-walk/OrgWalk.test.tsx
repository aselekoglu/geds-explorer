import { render, screen } from "@testing-library/react"
import { expect, it } from "vitest"
import { OrgWalk } from "./OrgWalk"
it("reveals a shared deep path",()=>{render(<OrgWalk path={["Department","Branch","Directorate","Team"]} />);expect(screen.getByLabelText("Organization path")).toHaveTextContent("Department / Branch / Directorate / Team");expect(screen.getByRole("treeitem",{name:"Team"})).toHaveAttribute("aria-current","true")})

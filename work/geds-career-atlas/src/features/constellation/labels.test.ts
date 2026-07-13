import { describe, expect, it } from "vitest"
import { institutionAbbreviation, wrapBubbleLabel } from "./labels"

describe("institutionAbbreviation", () => {
  it("uses reviewed Government of Canada abbreviations", () => {
    expect(institutionAbbreviation("Canadian Radio-television and Telecommunications Commission")).toBe("CRTC")
    expect(institutionAbbreviation("Employment and Social Development Canada")).toBe("ESDC")
    expect(institutionAbbreviation("CANADA REVENUE AGENCY")).toBe("CRA")
  })

  it("derives compact initials when no reviewed abbreviation exists", () => {
    expect(institutionAbbreviation("Example Office for Public Programs")).toBe("EOPP")
    expect(institutionAbbreviation("Office of Extremely Long Specialized Administrative Programs and Services")).toHaveLength(6)
  })
})

describe("wrapBubbleLabel", () => {
  it("wraps whole words without adding an ellipsis", () => {
    expect(wrapBubbleLabel("Chairperson's Office", 12)).toEqual(["Chairperson's", "Office"])
    expect(wrapBubbleLabel("Dispute Resolution and Regulatory Implementation", 18, 3).join(" ")).not.toContain("...")
  })
})

import { expect, it } from "vitest"
import { groupObservedTitles, normalizeObservedTitle } from "./titleGroups"

it("normalizes whitespace without inventing a title",()=>{
  expect(normalizeObservedTitle("  Senior   Analyst ")).toBe("Senior Analyst")
  expect(normalizeObservedTitle("   ")).toBe("")
})

it("groups case and whitespace variants and sorts empty last",()=>{
  expect(groupObservedTitles([" Senior  Analyst ","senior analyst","", "   "])).toEqual([
    {key:"senior analyst",label:"Senior Analyst",count:2,empty:false},
    {key:"",label:"No title recorded",count:2,empty:true},
  ])
})

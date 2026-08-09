import { expect, it } from "vitest"
import { localizeEvidenceField, localizeQualityStatus } from "./labels"

const messages: Record<string, string> = {
  "qualityStatus.partialOverlay": "couverture partielle",
  "evidenceField.displayName": "nom affiché",
}
const t = (key: string) => messages[key] ?? key

it("localizes known data labels without changing unknown contract values", () => {
  expect(localizeQualityStatus("partial_overlay", t)).toBe("couverture partielle")
  expect(localizeEvidenceField("display_name", t)).toBe("nom affiché")
  expect(localizeQualityStatus("future_status", t)).toBe("future status")
  expect(localizeEvidenceField("future_field", t)).toBe("future field")
})

import { z } from "zod"
export const explorerSearchSchema = z.object({q:z.string().catch(""),categories:z.array(z.string()).catch([]),department:z.string().optional(),org:z.string().optional(),confidence:z.enum(["high","medium","exploratory"]).catch("exploratory"),vacancy:z.boolean().catch(false),lang:z.enum(["en","fr"]).catch("en"),mode:z.enum(["list","org-walk","constellation"]).catch("list"),focus:z.string().optional()})
export type ExplorerSearch = z.infer<typeof explorerSearchSchema>

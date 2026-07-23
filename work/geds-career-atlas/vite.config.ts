import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
export default defineConfig({ assetsInclude: ["**/*.glb"], plugins: [react()], test: { environment: "jsdom", globals: true, setupFiles: "./src/test/setup.ts", include: ["src/**/*.test.{ts,tsx}"] } })

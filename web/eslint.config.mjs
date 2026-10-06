import { defineConfig, globalIgnores } from "eslint/config";
import js from "@eslint/js";
import ts from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

export default defineConfig([
  js.configs.recommended,
  ...ts.configs.recommended,
  { files: ["**/*.{ts,tsx}"], ...reactHooks.configs.flat.recommended },
  { files: ["**/*.{ts,tsx,mjs}"], languageOptions: { globals: {
    process: "readonly", console: "readonly", setTimeout: "readonly", clearTimeout: "readonly",
    window: "readonly", document: "readonly", URL: "readonly", AbortController: "readonly", fetch: "readonly",
  } }, rules: { "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_", ignoreRestSiblings: true }] } },
  globalIgnores([".next/**", ".next-e2e/**", ".npm-cache/**", ".playwright/**", "node_modules/**", "playwright-report/**", "test-results/**", "next-env.d.ts"]),
]);

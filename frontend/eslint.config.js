import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";

export default [
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  {
    files: ["**/*.{js,jsx,mjs}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.es2025 },
    },
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      ...js.configs.recommended.rules,
      ...reactHooks.configs.flat.recommended.rules,
      "no-unused-vars": ["warn", { varsIgnorePattern: "^_", argsIgnorePattern: "^_" }],
      "no-undef": "error",
      "react-hooks/set-state-in-effect": "off",
    },
  },
];

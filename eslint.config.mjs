// Flat ESLint config. The point of interest is eslint-plugin-no-unsanitized,
// which flags raw innerHTML / insertAdjacentHTML sinks so a future regression of
// JV-01 (the attribute-context XSS) is caught at lint time, not in production.
import noUnsanitized from "eslint-plugin-no-unsanitized";

export default [
  {
    files: ["**/*.js"],
    ignores: ["node_modules/**", "backend/**", "icons/**"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        chrome: "readonly",
        document: "readonly",
        window: "readonly",
        self: "readonly",
        fetch: "readonly",
        JV: "readonly",
        console: "readonly",
      },
    },
    plugins: { "no-unsanitized": noUnsanitized },
    rules: {
      "no-unsanitized/property": "error",
      "no-unsanitized/method": "error",
    },
  },
];

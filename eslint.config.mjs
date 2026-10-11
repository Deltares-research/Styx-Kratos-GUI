// ESLint settings for the frontend (the eslint job in .github/workflows/lint.yml, run
// there through npx; the frontend is build-free and has no package.json).
//
// Only rules that point at a likely bug, not at style. The files are plain browser
// scripts sharing globals through `App`, so no-undef and no-unused-vars would mostly
// report the design, and stay off.

export default [
  {
    ignores: [
      "frontend/vendor/",   // three.js, minified and not ours to fix
      "frontend/base/",     // the frozen mockup, loaded verbatim
    ],
  },
  {
    files: ["frontend/**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
    },
    rules: {
      "for-direction": "error",
      "getter-return": "error",
      "no-compare-neg-zero": "error",
      "no-cond-assign": ["error", "except-parens"],
      "no-const-assign": "error",
      "no-constant-binary-expression": "error",
      "no-debugger": "error",
      "no-dupe-args": "error",
      "no-dupe-class-members": "error",
      "no-dupe-else-if": "error",
      "no-dupe-keys": "error",
      "no-duplicate-case": "error",
      "no-empty-character-class": "error",
      "no-ex-assign": "error",
      "no-func-assign": "error",
      "no-invalid-regexp": "error",
      "no-loss-of-precision": "error",
      "no-obj-calls": "error",
      "no-self-assign": "error",
      "no-self-compare": "error",
      "no-setter-return": "error",
      "no-sparse-arrays": "error",
      "no-unreachable": "error",
      "no-unsafe-finally": "error",
      "no-unsafe-negation": "error",
      "no-unsafe-optional-chaining": "error",
      "use-isnan": "error",
      "valid-typeof": "error",
    },
  },
];

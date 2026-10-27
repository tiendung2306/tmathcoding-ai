# Math rendering verification

The submission detail modal now renders problem statements and Code Doctor advice with the same Markdown and KaTeX pipeline used by the skill problem dialog. These captures show the `SubmissionDetailModal` using a local mock adapter and fixture text transcribed from the user-provided Rock Paper Scissors / `TIME_LIMIT_EXCEEDED` screenshots. They are illustrative test data, not production records.

## Captures

- [Problem statement, desktop](submission-problem-desktop.png)
- [Code Doctor diagnosis, desktop](submission-diagnosis-desktop.png)
- [Problem statement, 375 px viewport](submission-problem-mobile.png)
- [Code Doctor diagnosis, 375 px viewport](submission-diagnosis-mobile.png)

## Verification

- `npm run build` passes TypeScript and Vite production bundling. Vite reports the existing large-chunk advisory.
- `node --test tests/markdown-math.test.mjs` passes. It checks inline and block KaTeX, inline/fenced code preservation, ignored raw HTML, safe external-link attributes, and invalid LaTeX handling.
- `npm test` runs 35 tests: 33 pass and 2 unrelated existing navigation cases fail. The failures are the roster context test (`null` instead of `7d`) and shared roster/student context request reuse. The repository's unmodified main checkout reproduces these baseline failures.
- At a 375 × 812 viewport, the document width remains 375 px and the modal has matching 354 px client and scroll widths. Long math is contained in horizontally scrollable KaTeX wrappers.

The screenshot harness was removed after capture; only the report and images remain in this folder.

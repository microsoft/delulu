# Changelog

## v1.1.0 — 2026-05-06

- Refreshed dataset to v3 license-tagged release: **1,947 samples** (947 unique FIM contexts) drawn from 319 public GitHub repositories.
- Added `license` column with SPDX identifier per row (collection-of-licenses model). Rows without any detected license string have been removed.
- All `prompt` / `suffix` / `repo_url` `NaN` values replaced with empty strings; the previously-empty `rust-import-58a1608eb036` row recovered from enriched metadata.
- Hugging Face dataset mirror published at `microsoft/delulu-fim-benchmark`.

## v1.0.0 — 2026-04-30

Initial public release.

- 1,951 manually-reviewed Fill-in-the-Middle samples across 7 languages
  (C++, C#, Go, Java, Python, Rust, TypeScript).
- 4 hallucination types: `import`, `method`, `parameter`, `undefinedvariable`.
- Per-language execution-based Docker verifiers.
- LLM-as-judge evaluation harness with cached, resumable runs.

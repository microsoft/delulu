# Changelog

## v1.0.0 — 2026-05-06

Initial public release.

- **1,947** manually-reviewed Fill-in-the-Middle samples (947 unique FIM contexts) drawn from 319 public GitHub repositories across 7 languages (C++, C#, Go, Java, Python, Rust, TypeScript).
- 4 hallucination types: `import`, `method`, `parameter`, `undefinedvariable`.
- Per-row `license` column with SPDX identifier (collection-of-licenses model); see `DATA_LICENSE.md`.
- Per-language execution-based Docker verifiers.
- LLM-as-judge evaluation harness with cached, resumable runs.
- Hugging Face dataset mirror at <https://huggingface.co/datasets/microsoft/delulu-fim-benchmark>.

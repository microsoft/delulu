# Datasheet — Delulu v1

Following the *Datasheets for Datasets* template (Gebru et al., 2018).

## Motivation

**Why was the dataset created?** To measure how often modern code LLMs
"hallucinate" plausible-looking but provably wrong tokens during Fill-in-the-Middle
(FIM) code completion in real codebases — focusing on four high-frequency,
verifiable failure modes: undefined variables, missing imports, non-existent
methods, and wrong parameter names.

**Who funded the creation?** See the accompanying paper.

## Composition

- **Instances**: 1,961 FIM samples drawn from public GitHub repositories.
- **Languages**: C++, C#, Go, Java, Python, Rust, TypeScript.
- **Hallucination types**: `import`, `method`, `parameter`, `undefinedvariable`.
- **Per-instance fields**: see [README.md](README.md) for the schema.
- **Targets / labels**: each row contains both a `golden_completion` (verified
  correct) and a `hallucinated_completion` (verified to fail with the labelled
  error category).

## Collection process

1. **Sourcing**: code files mined from public GitHub repositories with
   permissive or weak-copyleft licenses.
2. **FIM extraction**: candidate completions selected at AST-meaningful
   boundaries (call sites, identifiers, imports).
3. **Hallucination synthesis**: each candidate is paired with a synthetically
   modified completion that introduces a hallucination of the target type.
4. **Execution-based filtering**: every (golden, hallucinated) pair is run
   through the matching language verifier inside a Docker sandbox. Only pairs
   where the golden compiles/runs AND the hallucinated fails with the
   *expected* error category are retained.
5. **Manual review**: a human reviewer inspected every retained pair, fixing
   or discarding edge cases (false-friend errors, contextually-valid
   hallucinations, license-incompatible snippets).
6. **Balancing**: a final pass reduces over-represented (language, type)
   strata.

The full curation pipeline used at construction time is **not** included in
this v1 release; it depends on private mirrors and is described in the paper.

## Preprocessing / cleaning

- Trailing whitespace normalised on `prompt`/`suffix`.
- Files larger than the LLM context window of typical code models are excluded.
- License metadata joined from GitHub's License API at the commit pinned in
  `metadata`.

## Uses

**Intended uses**:
- Evaluating LLM-as-judge accuracy at detecting code hallucinations.
- Evaluating raw FIM code-completion models (use the docker verifiers to
  score model patches).
- Studying per-language and per-hallucination-type failure modes.

**Out-of-scope uses**:
- Training: while the data is public-license, **we do not recommend training
  on Delulu** — this is an evaluation-only benchmark and contamination would
  invalidate future leaderboard numbers.
- Deciding production code-quality at the per-snippet level.

## Distribution

- License: each row inherits its source repository's license; see
  [DATA_LICENSE.md](../DATA_LICENSE.md).
- Format: CSV in this repo; HuggingFace mirror TBA.

## Maintenance

- Issues + PRs welcome on GitHub.
- Removal requests for individual snippets: open an issue with the
  `benchmark_id`.

## Known limitations

- English-only repository metadata.
- Coverage tilt toward TypeScript / Python.
- The `hallucinated_completion` is one of many plausible hallucinations; a
  judge that scores 1 here is *necessary* but not *sufficient* for being
  hallucination-free in practice.

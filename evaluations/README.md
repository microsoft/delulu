# Evaluations

Two tools for scoring a model on Delulu. Both are stand-alone scripts —
no shared framework, just a thin CLI over the dataset.

## 1. `run_delulu_judges.py` — *judge mode*

LLM-as-judge harness. For each sample the judge is shown the prefix, suffix,
and a candidate completion (golden or hallucinated) and asked to score `0`
or `1`. A judge is **correct** on a sample only when it scores the golden
completion `1` AND the hallucinated completion `0` (`both_correct`).

```bash
cp ../.env.example ../.env   # at least one provider's API key
pip install -e "..[eval]"
python run_delulu_judges.py                                # all default models
python run_delulu_judges.py --models GPT-5.5 Claude-4.5-Sonnet
python run_delulu_judges.py --models GPT-5.5 --limit 20    # smoke test
```

Outputs:

- `results/<Model>_cache.json` — per-(model, sample) judgements (resumable).
- `results/judge_report.json` — overall / per-language / per-type summary.

### Provider matrix

| Provider | API kind | Required env vars |
| --- | --- | --- |
| Azure OpenAI (chat completions) | `chat` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` |
| Azure OpenAI (responses API) | `responses` | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_RESPONSES_API_VERSION` |
| Anthropic Claude | `claude` | `ANTHROPIC_API_KEY` |
| Google Gemini | `gemini` | `GOOGLE_API_KEY` |

The default model registry in the script is a starting point — edit
`DEFAULT_MODELS` to point deployment names at your own resource.

## 2. `run_completion_metrics.py` — *metrics mode*

Given a CSV of model predictions (columns `benchmark_id`, `model_completion`),
this computes per-row:

- **pass@1** — execution-based, via the per-sample Docker verifier image
  (`docker run -i <image> verify patch < completion.txt`).
- **exact_match** — strict equality with the golden completion.
- **edit_similarity** — char-level normalised Levenshtein vs. golden.
- **hallucination_rate** — `1` if the completion is closer (by edit
  similarity) to the *hallucinated* variant than to the golden, else `0`.

```bash
# 2 samples per language (14 total) — smoke test
python run_completion_metrics.py \
    --predictions my_model.csv \
    --model-name my-model \
    --smoke-test

# Full run
python run_completion_metrics.py \
    --predictions my_model.csv \
    --model-name my-model
```

Outputs:

- `results/<model>_metrics.json` — per-sample cache (resumable).
- `results/<model>_metrics_report.json` — overall / per-language / per-type
  aggregate.

### Predictions CSV format

Two required columns; everything else is ignored:

```csv
benchmark_id,model_completion
go-method-e9ac561d7779,"some.completion()"
python-undefinedvariable-681700c5cbff,"x = some_var"
...
```

Use `tools/slice.py` to produce a sliced CSV (e.g. just Python rows) before
running inference if you want to evaluate on a subset.

### Registry

The script pulls `<registry>/<image_tag>` for each row. `image_tag` is the
column in `delulu.csv`; `registry` defaults to the value of
`DELULU_REGISTRY` (a pre-release registry until publication). Override with
`--registry` or the env var, e.g. `--registry delulubench` once images are
mirrored to Docker Hub.

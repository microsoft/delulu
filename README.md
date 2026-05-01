# Delulu

**Delulu** is a multilingual benchmark for measuring **code-completion hallucinations** in modern code LLMs.

Each sample is a real-world Fill-in-the-Middle (FIM) snippet annotated with:

- a **golden** completion that compiles / runs in the original repository, and
- a **hallucinated** completion that *looks* plausible but is provably wrong (uses an undefined symbol, a non-existent method/parameter, or a missing import).

Every sample also ships as a self-contained Docker image that can run
`verify golden` / `verify hallucinated` / `verify patch <your-completion>`,
so any score on Delulu is execution-grounded.

## Stats

| Languages | Samples | Hallucination types |
| --- | --- | --- |
| C++, C#, Go, Java, JavaScript / TypeScript, Python, Rust | **1,961** | `import`, `method`, `parameter`, `undefinedvariable` |

| Language | Count | | Type | Count |
| --- | ---: | --- | --- | ---: |
| TypeScript | 420 | | undefinedvariable | 579 |
| Python | 383 | | import | 483 |
| Go | 291 | | method | 463 |
| Rust | 253 | | parameter | 436 |
| C# | 246 | | | |
| Java | 243 | | | |
| C++ | 125 | | | |

## What's in the repo

```
data/                # delulu.csv + datasheet
tools/
  load.py / stats.py / slice.py / inspect.py    # CLIs for working with the dataset
  viewer/                                       # browser UI (also a Docker image)
evaluations/
  run_delulu_judges.py        # LLM-as-judge harness (the "judge" tool)
  run_completion_metrics.py   # pass@1 + offline metrics (the "metrics" tool)
examples/            # 5-minute walkthrough on a 14-sample mini set
```

## The two evaluation tools

### 1. Judge — *Can a foundation model tell which completion is hallucinated?*

`evaluations/run_delulu_judges.py` shows a judge model the prefix, suffix, and
a candidate completion, asks it to score `0` or `1`, and counts a sample as
correct only when the judge scores **golden=1** AND **hallucinated=0**.

```bash
cp .env.example .env
pip install -e ".[eval]"
python evaluations/run_delulu_judges.py --models GPT-5.5 Claude-4.5-Sonnet
```

Per-model caches are written under `evaluations/results/`, so runs are
resumable. See [evaluations/README.md](evaluations/README.md).

### 2. Metrics — *Do the model's completions actually run? How close are they to the truth?*

`evaluations/run_completion_metrics.py` takes a CSV of model predictions
(columns: `benchmark_id`, `model_completion`) and computes:

- **pass@1** — execution-based, by piping each completion into the
  per-sample Docker verifier image (`docker run -i <image> verify patch`).
- **exact_match** — strict equality with the golden completion.
- **edit_similarity** — char-level normalised Levenshtein vs. golden.
- **hallucination_rate** — share of completions closer to the *hallucinated*
  variant than to the golden one.

```bash
# Fast smoke-test: 2 samples per language (14 total)
python evaluations/run_completion_metrics.py \
    --predictions my_model.csv \
    --model-name my-model \
    --smoke-test

# Full run
python evaluations/run_completion_metrics.py \
    --predictions my_model.csv \
    --model-name my-model
```

Verifier images are pulled from `${DELULU_REGISTRY}` (defaults to a
pre-release registry; the public Docker Hub mirror is TBA). See
[evaluations/README.md](evaluations/README.md).

## Viewer

A browsable UI for the dataset is shipped as a Docker image — see
[tools/viewer/README.md](tools/viewer/README.md):

```bash
docker run --rm -p 8000:8000 \
    -v /var/run/docker.sock:/var/run/docker.sock \
    delulubench/delulu-viewer:v1
```

## Quickstart

```python
from tools.load import load_delulu
df = load_delulu()
print(df.shape, df["language"].value_counts())
```

A HuggingFace mirror is also available (TBA):

```python
from datasets import load_dataset
ds = load_dataset("delulu-bench/delulu", split="test")
```

For an end-to-end 5-minute walkthrough, see [examples/quickstart.md](examples/quickstart.md).

## Citation

```bibtex
@article{delulu2026,
  title  = {Delulu: A Multilingual Benchmark for Code Completion Hallucinations},
  author = {TBD},
  year   = {2026},
  eprint = {arXiv:TBD}
}
```

A machine-readable citation is in [CITATION.cff](CITATION.cff).

## License

- **Code** in this repository: MIT (see [LICENSE](LICENSE)).
- **Data**: each sample inherits the license of its source repository,
  recorded in the `license` and `repo_url` columns. See
  [DATA_LICENSE.md](DATA_LICENSE.md).

## Links

- Paper (arXiv): _TBA_
- HuggingFace dataset: _TBA_
- Docker Hub: _TBA_

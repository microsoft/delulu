# Delulu Dataset

`delulu.csv` — 1,961 rows, UTF-8, comma-separated, header row included.

## Schema

| Column | Type | Description |
| --- | --- | --- |
| `benchmark_id` | string | Stable unique identifier for the sample. |
| `image_tag` | string | Tag of the per-sample Docker verifier image, e.g. `delulu-python-undefinedvariable-681700c5cbff:v1`. Combine with the public registry to pull: `${REGISTRY:-delulubench}/<image_tag>`. |
| `language` | string | One of `cpp`, `csharp`, `go`, `java`, `python`, `rust`, `typescript`. |
| `file_path` | string | Original path of the file inside the source repository. |
| `hallucination_type` | string | One of `import`, `method`, `parameter`, `undefinedvariable`. |
| `prompt` | string | Code that appears **before** the FIM cursor (the *prefix*). |
| `suffix` | string | Code that appears **after** the FIM cursor. |
| `golden_completion` | string | Original code at the cursor; verified to compile / run. |
| `hallucinated_completion` | string | Plausible-looking but provably wrong completion. |
| `error_message` | string | Error category / message produced by the language toolchain when running the hallucinated completion. |
| `metadata` | JSON string | Extra per-sample metadata (e.g. cluster id, hallucination target). |
| `license` | string | SPDX identifier of the source repository's license. |
| `repo_url` | string | Public GitHub URL of the source repository. |

## Quick stats

| Language | Samples | | Hallucination type | Samples |
| --- | ---: | --- | --- | ---: |
| typescript | 420 | | undefinedvariable | 579 |
| python | 383 | | import | 483 |
| go | 291 | | method | 463 |
| rust | 253 | | parameter | 436 |
| csharp | 246 | | | |
| java | 243 | | | |
| cpp | 125 | | | |
| **Total** | **1,961** | | **Total** | **1,961** |

## Loading

### Plain pandas

```python
import pandas as pd
df = pd.read_csv("data/delulu.csv")
```

### HuggingFace Datasets (mirror, TBA)

```python
from datasets import load_dataset
ds = load_dataset("delulu-bench/delulu", split="test")
```

### Helper

```python
from tools.load import load_delulu
df = load_delulu()
```

See [DATASHEET.md](DATASHEET.md) for a datasheet-for-datasets style description
of how the benchmark was constructed, intended uses, and known limitations.

# Delulu Dataset

`delulu.csv` — 1,947 rows, UTF-8, comma-separated, header row included.

## Schema

| Column | Type | Description |
| --- | --- | --- |
| `benchmark_id` | string | Stable unique identifier for the sample (`<lang>-<type>-<12-hex-hash>`). |
| `image_tag` | string | Tag of the per-sample Docker verifier image, e.g. `delulu-python-undefinedvariable-681700c5cbff:v1`. Combine with the public registry to pull: `${REGISTRY:-delulubench}/<image_tag>`. |
| `language` | string | One of `cpp`, `csharp`, `go`, `java`, `python`, `rust`, `typescript`. |
| `file_path` | string | Original path of the file inside the source repository. |
| `hallucination_type` | string | One of `import`, `method`, `parameter`, `undefinedvariable`. |
| `prompt` | string | Code that appears **before** the FIM cursor (the *prefix*). |
| `suffix` | string | Code that appears **after** the FIM cursor. |
| `golden_completion` | string | Original code at the cursor; verified to compile / run. |
| `hallucinated_completion` | string | Plausible-looking but provably wrong completion. |
| `error_message` | string | Error category / message produced by the language toolchain when running the hallucinated completion (Python-style label, see note below). |
| `metadata` | JSON string | Extra per-sample metadata (e.g. cluster id, hallucination target). |
| `license` | string | SPDX identifier of the source repository's license. |
| `repo_url` | string | Public GitHub URL of the source repository. |

> The `error_message` / hallucination-type column uses Python-style category labels (`ImportError`, `AttributeError`, `TypeError`, `NameError`) as a *shared category* across all seven languages; each language raises its own concrete equivalent.

## Quick stats

### By language × hallucination type

| Language     | `import` | `method` | `parameter` | `undefinedvariable` | Total |
|--------------|---:|---:|---:|---:|---:|
| TypeScript   | 111 | 100 |  86 | 123 |  420 |
| Python       | 164 |  77 |  22 | 107 |  370 |
| Go           |  50 |  81 |  79 |  81 |  291 |
| Rust         |  57 |  60 |  66 |  69 |  252 |
| C#           |  26 |  51 |  82 |  87 |  246 |
| Java         |  44 |  59 |  65 |  75 |  243 |
| C++          |  24 |  32 |  35 |  34 |  125 |
| **Total**    | **476** | **460** | **435** | **576** | **1,947** |

### Samples vs. unique FIM contexts

The 1,947 samples cover **947 unique FIM contexts** (`prompt` + `suffix` + `golden_completion`). The same FIM context can appear multiple times paired with different hallucinated variants (e.g. a single function call can be turned into a `method`, `parameter`, and `undefinedvariable` hallucination using the same prefix/suffix/golden). When evaluating per-context model behavior, deduplicate by `(prompt, suffix, golden_completion)`.

### Source repositories and licenses

The 1,947 samples are drawn from **319 public GitHub repositories**. Every row preserves its source repository's SPDX identifier in the `license` column. Top licenses:

| License | Count |
| --- | ---: |
| MIT | 818 |
| Apache-2.0 | 594 |
| UNLICENSED\* | 104 |
| EPL-2.0 | 93 |
| GPL-3.0 | 71 |
| MPL-2.0 | 43 |
| AGPL-3.0 | 42 |
| BSD-3-Clause | 42 |
| Zlib | 19 |
| GPL-2.0 | 12 |
| BSD-2-Clause | 12 |
| MIT-0 | 11 |
| CC0-1.0 | 11 |
| MIT OR Apache-2.0 | 10 |
| OFL-1.1 | 9 |
| EUPL-1.2 | 7 |
| CC-BY-NC-4.0 | 7 |
| LicenseRef-scancode-unknown-license-reference | 7 |
| MS-PL | 6 |
| AGPL-3.0-or-later | 6 |
| UPL-1.0 | 5 |
| GPL-3.0-only | 4 |
| LGPL-3.0 | 4 |
| LicenseRef-scancode-proprietary-license | 4 |
| BSD-3-Clause-Clear | 3 |
| GPL-2.0-only | 2 |
| CC-BY-NC-SA-4.0 | 1 |

\* `UNLICENSED` is the npm convention for "proprietary, all rights reserved"; rows so labelled are not offered under an open-source license by their upstream authors and are retained for evaluation completeness only. Downstream users who plan to redistribute these rows must obtain permission from the original copyright holder.

Delulu follows the *collection-of-licenses* model: see [DATA_LICENSE.md](../DATA_LICENSE.md) for full per-license obligations.

## Loading

### Plain pandas

```python
import pandas as pd
df = pd.read_csv("data/delulu.csv")
```

### Hugging Face Datasets

```python
from datasets import load_dataset
ds = load_dataset("microsoft/delulu-fim-benchmark", split="test")
```

### Helper

```python
from tools.load import load_delulu
df = load_delulu()
```

See [DATASHEET.md](DATASHEET.md) for a datasheet-for-datasets style description
of how the benchmark was constructed, intended uses, and known limitations.

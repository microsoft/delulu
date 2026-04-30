# Data License

The **code in this repository** (everything outside `data/`) is released under
the MIT license — see [LICENSE](LICENSE).

The **dataset** (`data/delulu.csv`) is a curated collection of code snippets
extracted from public open-source repositories on GitHub. **Each row is
governed by the license of its source repository**, recorded in two columns:

- `license` — SPDX-style identifier (e.g. `MIT`, `Apache-2.0`, `BSD-3-Clause`).
- `repo_url` — the upstream repository URL.

When you redistribute, fine-tune on, or otherwise reuse a sample you must
comply with that sample's upstream license, including any attribution,
copyleft, or share-alike requirements.

## Filtering

Samples are restricted to repositories with permissive or weak-copyleft
open-source licenses. Repositories with no detected license, with
non-open-source licenses, or that explicitly forbid AI / training reuse are
**excluded**.

## Removal requests

If you are a rights-holder for a snippet you believe should not be in this
benchmark, please open an issue with the `benchmark_id` and we will remove the
sample from the next release.

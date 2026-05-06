# Data License

The **code in this repository** (everything outside `data/`) is released under
the MIT license — see [LICENSE](LICENSE).

The **dataset** (`data/delulu.csv`) is a curated collection of code snippets
extracted from public open-source repositories on GitHub. **Each row is
governed by the license of its source repository**, recorded in two columns:

- `license` — SPDX-style identifier (e.g. `MIT`, `Apache-2.0`, `BSD-3-Clause`,
  or non-open-source markers such as `UNLICENSED` and
  `LicenseRef-scancode-proprietary-license`).
- `repo_url` — the upstream repository URL (may be empty for a small number of
  rows where the URL was not captured during mining; consult `file_path` for
  provenance in those cases).

Delulu follows the *collection-of-licenses* model used by The Stack v2,
BigCodeBench, and CodeSearchNet. When you redistribute, fine-tune on, or
otherwise reuse a sample you must comply with that sample's upstream license,
including any attribution, copyleft, or share-alike requirements.

## Per-license obligations (informational, not legal advice)

- **Permissive** (`MIT`, `MIT-0`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`,
  `BSD-3-Clause-Clear`, `MS-PL`, `UPL-1.0`, `CC0-1.0`, `Zlib`, `OFL-1.1`,
  `MIT OR Apache-2.0`). Redistributing snippets is allowed. Apache-2.0 also
  requires noting modifications (the `hallucinated_completion` is one);
  `MIT-0` / `CC0-1.0` carry no obligations.
- **Weak / file-level copyleft** (`MPL-2.0`, `EPL-2.0`, `EUPL-1.2`, `LGPL-3.0`).
  Snippets may be redistributed but each snippet *remains* under its original
  license; downstream users must keep the SPDX identifier intact and not
  relicense the snippet itself.
- **Strong copyleft** (`GPL-2.0`, `GPL-2.0-only`, `GPL-3.0`, `GPL-3.0-only`,
  `AGPL-3.0`, `AGPL-3.0-or-later`). Snippets are included for evaluation
  completeness. They remain under their respective licenses; any work that
  *combines* them with other code may itself need to be released under the
  same license. Users who plan to redistribute Delulu rows as part of a larger
  artifact should assess GPL/AGPL applicability for their specific use case,
  or filter to the permissive subset before redistribution.
- **Non-commercial** (`CC-BY-NC-4.0`, `CC-BY-NC-SA-4.0`). Redistribution and
  reuse is restricted to non-commercial purposes; users intending commercial
  use should filter these rows out.
- **Non-open-source** (`UNLICENSED`,
  `LicenseRef-scancode-proprietary-license`,
  `LicenseRef-scancode-unknown-license-reference`). The upstream authors did
  not grant any open-source license. These rows are retained for evaluation
  completeness only; users who plan to redistribute them must obtain
  permission from the original copyright holder.

## Filtering to a permissive subset

Users who only want snippets under permissive licenses can filter the dataset
programmatically:

```python
import pandas as pd

PERMISSIVE = {
    "MIT", "MIT-0", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause",
    "BSD-3-Clause-Clear", "CC0-1.0", "UPL-1.0", "MS-PL", "Zlib", "OFL-1.1",
    "MIT OR Apache-2.0",
}
df = pd.read_csv("data/delulu.csv")
df_permissive = df[df["license"].isin(PERMISSIVE)]
print(len(df_permissive))
```

## Removal requests

If you are a rights-holder for a snippet you believe should not be in this
benchmark, please open an issue with the `benchmark_id` and we will remove the
sample from the next release.

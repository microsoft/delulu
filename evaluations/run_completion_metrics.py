"""
Run model-completion metrics on the Delulu benchmark.

Given an input CSV with an extra ``model_completion`` column (one row per
``benchmark_id`` from ``data/delulu.csv``), this script computes per-row:

    * pass@1  — execution-based, via the per-sample Docker verifier image
                (mode ``verify patch``).
    * exact_match            — ``model_completion == golden_completion``.
    * edit_similarity        — char-level normalised Levenshtein vs. golden.
    * hallucination_rate     — 1 if completion is closer to the *hallucinated*
                               variant than to the golden variant, else 0.

Aggregate scores are written to ``<cache-dir>/metrics_report.json``.
Per-(model, sample) results are cached so re-runs are resumable.

Usage
-----
    # Apply the model_completion column from a predictions CSV produced by
    # your inference pipeline; rows must have benchmark_id + model_completion.
    python run_completion_metrics.py \\
        --predictions predictions.csv \\
        --model-name qwen2.5-coder-32b \\
        --cache-dir results/metrics

    # Smoke test on 14 rows (2 per language)
    python run_completion_metrics.py \\
        --predictions predictions.csv \\
        --model-name qwen2.5-coder-32b \\
        --smoke-test
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from tqdm import tqdm


# A sentinel value that obviously isn't a real registry; we error out with a
# clear message instead of silently failing on `docker pull`.
_REGISTRY_UNSET = "<unset>"

DEFAULT_REGISTRY = os.environ.get("DELULU_REGISTRY", _REGISTRY_UNSET)
DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "delulu.csv"
VERIFY_TIMEOUT = 240
PULL_TIMEOUT = 600


# ── Offline metrics ────────────────────────────────────────────────

def levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        cur = [i + 1]
        for j, c2 in enumerate(s2):
            cur.append(min(prev[j + 1] + 1, cur[j] + 1, prev[j] + (c1 != c2)))
        prev = cur
    return prev[-1]


def edit_similarity(a: str, b: str) -> float:
    a = a or ""
    b = b or ""
    if not a and not b:
        return 1.0
    m = max(len(a), len(b))
    return 1.0 - levenshtein(a, b) / m


def is_hallucinated_aligned(completion: str, golden: str, hallucinated: str) -> Optional[float]:
    """Hallucination-alignment score in {0.0, 0.5, 1.0} (or None when both
    references are missing).

    - 1.0 if the completion is closer to the hallucinated variant than to the
      golden one (a model-emitted hallucination).
    - 0.0 if it's strictly closer to the golden completion.
    - 0.5 on a tie, including the degenerate case where both candidates have
      the same edit similarity (common for very short completions).
    The mean of this column over the dataset is the dataset-level
    hallucination rate.
    """
    if not (golden or hallucinated):
        return None
    g = edit_similarity(completion, golden or "")
    h = edit_similarity(completion, hallucinated or "")
    if h > g:
        return 1.0
    if h < g:
        return 0.0
    return 0.5


# ── Docker verifier ────────────────────────────────────────────────

@dataclass
class VerifyResult:
    is_valid: Optional[bool]
    exit_code: int
    error_message: str
    raw_stdout: str


def _run(cmd: list[str], *, stdin_data: Optional[str] = None,
         timeout: int = VERIFY_TIMEOUT) -> tuple[int, str, str]:
    try:
        r = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", f"timeout after {timeout}s"
    except FileNotFoundError:
        return -2, "", "docker executable not found"


def docker_pull(image: str) -> tuple[bool, str]:
    rc, _, _ = _run(["docker", "image", "inspect", image], timeout=15)
    if rc == 0:
        return True, "cached"
    rc, _, err = _run(["docker", "pull", image], timeout=PULL_TIMEOUT)
    return rc == 0, ("pulled" if rc == 0 else err[:300])


def verify_patch(image: str, completion: str) -> VerifyResult:
    rc, stdout, stderr = _run(
        ["docker", "run", "--rm", "-i", image, "verify", "patch"],
        stdin_data=completion,
        timeout=VERIFY_TIMEOUT,
    )
    parsed: dict = {}
    if stdout.strip():
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            pass
    is_valid = parsed.get("is_valid")
    if is_valid is None:
        # Fall back to exit code: 0=valid, 1=invalid, others=error/unknown
        if rc == 0:
            is_valid = True
        elif rc == 1:
            is_valid = False
    return VerifyResult(
        is_valid=is_valid,
        exit_code=rc,
        error_message=parsed.get("error_message", "") or stderr[:200],
        raw_stdout=stdout[:500],
    )


# ── Sample loading & merging ──────────────────────────────────────

def load_benchmark(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with open(path, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["benchmark_id"]] = r
    return rows


def load_predictions(path: Path) -> dict[str, str]:
    preds: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        if "benchmark_id" not in rdr.fieldnames or "model_completion" not in rdr.fieldnames:
            raise SystemExit(
                "predictions CSV must have columns: benchmark_id, model_completion"
            )
        for r in rdr:
            preds[r["benchmark_id"]] = r["model_completion"]
    return preds


def smoke_test_sample(bench: dict[str, dict], n_per_lang: int = 2) -> list[str]:
    by_lang: dict[str, list[str]] = {}
    for bid, r in bench.items():
        by_lang.setdefault(r["language"], []).append(bid)
    chosen: list[str] = []
    for lang in sorted(by_lang):
        chosen.extend(by_lang[lang][:n_per_lang])
    return chosen


# ── Cache ──────────────────────────────────────────────────────────

def cache_path(cache_dir: Path, model_name: str) -> Path:
    safe = model_name.replace("/", "_").replace(" ", "_")
    return cache_dir / f"{safe}_metrics.json"


def load_cache(cache_dir: Path, model_name: str) -> dict:
    p = cache_path(cache_dir, model_name)
    return json.loads(p.read_text()) if p.exists() else {}


def save_cache(cache_dir: Path, model_name: str, cache: dict) -> None:
    cache_path(cache_dir, model_name).write_text(json.dumps(cache, indent=2))


# ── Per-sample evaluation ──────────────────────────────────────────

def evaluate_one(bid: str, row: dict, completion: str, registry: str) -> dict:
    if registry == _REGISTRY_UNSET:
        raise SystemExit(
            "No Docker registry configured. Set --registry or the "
            "DELULU_REGISTRY environment variable to the public Delulu "
            "image registry (e.g. 'delulubench' once published) before "
            "running execution-based evaluation."
        )
    image = f"{registry.rstrip('/')}/{row['image_tag']}"

    em = completion.strip() == (row["golden_completion"] or "").strip()
    es = edit_similarity(completion, row["golden_completion"] or "")
    hr = is_hallucinated_aligned(
        completion, row["golden_completion"] or "", row["hallucinated_completion"] or ""
    )

    base = {
        "benchmark_id": bid,
        "language": row["language"],
        "hallucination_type": row["hallucination_type"],
        "exact_match": em,
        "edit_similarity": es,
        "hallucination_aligned": hr,
        "pass_at_1": None,
        "verify_exit_code": None,
        "verify_error": None,
        "error": None,
    }

    pulled, pull_msg = docker_pull(image)
    if not pulled:
        return {**base, "error": f"pull failed: {pull_msg}"}

    res = verify_patch(image, completion)
    return {
        **base,
        "pass_at_1": bool(res.is_valid) if res.is_valid is not None else None,
        "verify_exit_code": res.exit_code,
        "verify_error": res.error_message,
    }


# ── Reporting ──────────────────────────────────────────────────────

def summarize(model_name: str, cache: dict, cache_dir: Path) -> dict:
    import pandas as pd
    df = pd.DataFrame(cache.values())
    if df.empty:
        return {}

    def _mean(col):
        s = df[col].dropna()
        return float(s.mean()) if len(s) else None

    overall = {
        "model": model_name,
        "n": int(len(df)),
        "n_pass_at_1_evaluated": int(df["pass_at_1"].notna().sum()),
        "pass_at_1": _mean("pass_at_1"),
        "exact_match": _mean("exact_match"),
        "edit_similarity": _mean("edit_similarity"),
        "hallucination_rate": _mean("hallucination_aligned"),
    }
    by_lang = (
        df.groupby("language")
          .agg(n=("benchmark_id", "count"),
               pass_at_1=("pass_at_1", "mean"),
               edit_similarity=("edit_similarity", "mean"),
               hallucination_rate=("hallucination_aligned", "mean"))
          .round(4)
          .reset_index()
          .to_dict(orient="records")
    )
    by_type = (
        df.groupby("hallucination_type")
          .agg(n=("benchmark_id", "count"),
               pass_at_1=("pass_at_1", "mean"),
               hallucination_rate=("hallucination_aligned", "mean"))
          .round(4)
          .reset_index()
          .to_dict(orient="records")
    )

    report = {"overall": overall, "by_language": by_lang, "by_type": by_type}
    out = cache_dir / f"{model_name.replace('/', '_').replace(' ', '_')}_metrics_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"\nReport: {out}")
    print(json.dumps(overall, indent=2))
    return report


# ── CLI ────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--predictions", type=Path, required=True,
                   help="CSV with columns benchmark_id, model_completion")
    p.add_argument("--model-name", required=True,
                   help="Display name for caching / report filenames")
    p.add_argument("--data", type=Path, default=DEFAULT_DATA,
                   help="Path to delulu.csv (default: ../data/delulu.csv)")
    p.add_argument("--cache-dir", type=Path, default=Path("results"),
                   help="Output directory")
    p.add_argument("--registry", default=DEFAULT_REGISTRY,
                   help=("Docker registry to pull verifier images from. "
                         "Defaults to the DELULU_REGISTRY environment "
                         "variable; set it to the public Delulu registry "
                         "(TBA on Docker Hub) or override per-invocation."))
    p.add_argument("--workers", type=int, default=4,
                   help="Parallel docker workers (default: 4)")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap number of samples (debug)")
    p.add_argument("--smoke-test", action="store_true",
                   help="Evaluate only 2 samples per language (14 total)")
    args = p.parse_args()

    args.cache_dir.mkdir(parents=True, exist_ok=True)

    bench = load_benchmark(args.data)
    preds = load_predictions(args.predictions)
    print(f"Loaded {len(bench)} benchmark rows, {len(preds)} predictions")

    if args.smoke_test:
        ids = smoke_test_sample(bench, n_per_lang=2)
        print(f"Smoke test: {len(ids)} samples (2 per language)")
    else:
        ids = list(preds.keys())
    if args.limit:
        ids = ids[:args.limit]

    missing_pred = [bid for bid in ids if bid not in preds]
    if missing_pred:
        print(f"Warning: {len(missing_pred)} samples missing model_completion; skipping")
        ids = [bid for bid in ids if bid in preds]
    missing_bench = [bid for bid in ids if bid not in bench]
    if missing_bench:
        print(f"Warning: {len(missing_bench)} benchmark_ids not found in {args.data}; skipping")
        ids = [bid for bid in ids if bid in bench]

    cache = load_cache(args.cache_dir, args.model_name)
    todo = [bid for bid in ids if bid not in cache]
    print(f"Cached: {len(set(cache) & set(ids))}, To run: {len(todo)}")

    if todo:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {
                ex.submit(evaluate_one, bid, bench[bid], preds[bid], args.registry): bid
                for bid in todo
            }
            with tqdm(total=len(futures), desc=args.model_name, unit="sample") as pbar:
                done = 0
                for fut in as_completed(futures):
                    bid = futures[fut]
                    try:
                        cache[bid] = fut.result()
                    except Exception as e:
                        cache[bid] = {"benchmark_id": bid, "error": str(e)[:200]}
                    done += 1
                    if done % 5 == 0:
                        save_cache(args.cache_dir, args.model_name, cache)
                    pbar.update(1)

        save_cache(args.cache_dir, args.model_name, cache)

    # Restrict cache view to the requested subset for the report
    subset = {bid: cache[bid] for bid in ids if bid in cache}
    summarize(args.model_name, subset, args.cache_dir)


if __name__ == "__main__":
    main()

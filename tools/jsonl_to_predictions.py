"""Convert a Qwen FIM-inference JSONL dump to a Delulu predictions CSV.

Input JSONL (one object per line) must have keys: ``hash_id``, ``prompt``,
``predict``, ``label``. The ``prompt`` is expected to end with the
``<|fim_middle|>`` token; everything before it is the concatenation of the
benchmark prefix + suffix (Qwen's no-token FIM convention used in our
inference dumps).

Each input row is matched to a Delulu sample by looking up
``(prompt + suffix, golden_completion)`` against ``data/delulu.csv``.

Output CSV has columns ``benchmark_id, model_completion`` ready to feed into
``evaluations/run_completion_metrics.py``.

Usage
-----
    python tools/jsonl_to_predictions.py \\
        --input run.jsonl --output predictions.csv \\
        [--data data/delulu.csv] [--limit 50] [--per-language 0]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

import pandas as pd

FIM_MIDDLE = "<|fim_middle|>"


def build_index(df: pd.DataFrame) -> dict:
    """Map (combined prefix+suffix, golden_completion) -> list of benchmark_ids."""
    df = df.fillna("")
    idx: dict = defaultdict(list)
    for r in df.itertuples(index=False):
        combined = (r.prompt or "") + (r.suffix or "")
        idx[(combined, r.golden_completion)].append(r.benchmark_id)
    return idx


def iter_jsonl(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--input", type=Path, required=True, help="Input JSONL")
    p.add_argument("--output", type=Path, required=True, help="Output predictions CSV")
    p.add_argument("--data", type=Path,
                   default=Path(__file__).resolve().parent.parent / "data" / "delulu.csv")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap total predictions written (after matching)")
    p.add_argument("--per-language", type=int, default=0,
                   help="If >0, balance the output to N rows per language")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    df = pd.read_csv(args.data).fillna("")
    bid_to_lang = dict(zip(df["benchmark_id"], df["language"]))
    idx = build_index(df)

    matched: list[dict] = []
    n_total = n_unique = n_multi = n_miss = 0

    for d in iter_jsonl(args.input):
        n_total += 1
        prompt = d.get("prompt", "")
        if prompt.endswith(FIM_MIDDLE):
            prompt = prompt[: -len(FIM_MIDDLE)]
        ids = idx.get((prompt, d.get("label", "")), [])
        if len(ids) == 1:
            n_unique += 1
            matched.append({"benchmark_id": ids[0], "model_completion": d.get("predict", "")})
        elif len(ids) > 1:
            n_multi += 1
        else:
            n_miss += 1

    print(f"input rows: {n_total}")
    print(f"  unique-match: {n_unique}")
    print(f"  multi-match (skipped): {n_multi}")
    print(f"  no-match (skipped):   {n_miss}")

    rng = random.Random(args.seed)
    if args.per_language > 0:
        by_lang: dict = defaultdict(list)
        for row in matched:
            by_lang[bid_to_lang.get(row["benchmark_id"], "?")].append(row)
        chosen = []
        for lang in sorted(by_lang):
            rng.shuffle(by_lang[lang])
            chosen.extend(by_lang[lang][: args.per_language])
        rng.shuffle(chosen)
        matched = chosen
        print(f"  balanced to {args.per_language}/lang -> {len(matched)} rows")

    if args.limit:
        rng.shuffle(matched)
        matched = matched[: args.limit]
        print(f"  limited to {len(matched)} rows")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["benchmark_id", "model_completion"])
        w.writeheader()
        w.writerows(matched)
    print(f"wrote {len(matched)} rows -> {args.output}")


if __name__ == "__main__":
    main()

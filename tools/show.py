"""Pretty-print a single sample by ``benchmark_id``."""
from __future__ import annotations

import argparse

from .load import load_delulu


def _hr(label: str) -> str:
    return f"\n{'─' * 6} {label} {'─' * (60 - len(label))}\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", default=None, help="Path to delulu.csv")
    p.add_argument("--id", required=True, dest="bid", help="benchmark_id to inspect")
    args = p.parse_args()

    df = load_delulu(args.data)
    rows = df[df["benchmark_id"] == args.bid]
    if rows.empty:
        raise SystemExit(f"benchmark_id not found: {args.bid}")
    r = rows.iloc[0]

    print(f"benchmark_id:       {r['benchmark_id']}")
    print(f"language:           {r['language']}")
    print(f"hallucination_type: {r['hallucination_type']}")
    print(f"file_path:          {r['file_path']}")
    print(f"image_tag:          {r['image_tag']}")
    print(f"license:            {r['license']}")
    print(f"repo_url:           {r['repo_url']}")
    print(_hr("PROMPT (prefix)"))
    print(r["prompt"])
    print(_hr("GOLDEN COMPLETION"))
    print(r["golden_completion"])
    print(_hr("HALLUCINATED COMPLETION"))
    print(r["hallucinated_completion"])
    print(_hr("SUFFIX"))
    print(r["suffix"])
    print(_hr("EXPECTED ERROR (hallucinated)"))
    print(r["error_message"])


if __name__ == "__main__":
    main()

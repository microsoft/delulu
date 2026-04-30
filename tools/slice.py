"""Filter Delulu by language / hallucination type and write a sliced CSV."""
from __future__ import annotations

import argparse
from pathlib import Path

from .load import load_delulu


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", default=None, help="Path to delulu.csv")
    p.add_argument("--language", action="append", help="Filter by language (repeatable)")
    p.add_argument("--type", action="append", dest="halluc_type",
                   help="Filter by hallucination type (repeatable)")
    p.add_argument("-o", "--output", required=True, type=Path, help="Output CSV path")
    args = p.parse_args()

    df = load_delulu(args.data)
    if args.language:
        df = df[df["language"].isin(args.language)]
    if args.halluc_type:
        df = df[df["hallucination_type"].isin(args.halluc_type)]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote {len(df)} rows -> {args.output}")


if __name__ == "__main__":
    main()

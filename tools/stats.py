"""Print per-language and per-hallucination-type stats."""
from __future__ import annotations

import argparse

from .load import load_delulu


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", default=None, help="Path to delulu.csv")
    args = p.parse_args()

    df = load_delulu(args.data)
    print(f"Total samples: {len(df)}\n")

    print("By language:")
    print(df["language"].value_counts().to_string())
    print()

    print("By hallucination type:")
    print(df["hallucination_type"].value_counts().to_string())
    print()

    print("Language x Type:")
    print(df.groupby(["language", "hallucination_type"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()

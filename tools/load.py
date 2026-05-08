"""Load the Delulu benchmark as a pandas DataFrame."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import pandas as pd

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "delulu.csv"


def load_delulu(path: Optional[Union[str, Path]] = None) -> pd.DataFrame:
    """Return the benchmark as a DataFrame.

    Parameters
    ----------
    path : str or Path, optional
        Path to ``delulu.csv``. Defaults to ``data/delulu.csv`` relative to
        this repository.
    """
    return pd.read_csv(path or DEFAULT_PATH)


if __name__ == "__main__":
    df = load_delulu()
    print(df.shape)
    print(df.columns.tolist())

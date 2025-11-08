from pathlib import Path
from typing import List

import pandas as pd

from ...logging_utils import get_logger

log = get_logger(__name__)


def compare_excels(left: str, right: str, key_column: str) -> pd.DataFrame:
    """Compare two Excel/CSV files on a key column.

    Returns a DataFrame that shows:
    - rows only in left
    - rows only in right
    - rows in both but with differences
    """
    left_df = _read_any(left)
    right_df = _read_any(right)

    if key_column not in left_df.columns:
        raise KeyError(f"{key_column!r} not found in left file columns: {list(left_df.columns)}")
    if key_column not in right_df.columns:
        raise KeyError(f"{key_column!r} not found in right file columns: {list(right_df.columns)}")

    left_df = left_df.set_index(key_column)
    right_df = right_df.set_index(key_column)

    # Outer join to spot differences
    merged = left_df.merge(
        right_df,
        how="outer",
        left_index=True,
        right_index=True,
        suffixes=("_left", "_right"),
        indicator=True,
    )

    return merged


def _read_any(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if p.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(p)
    if p.suffix.lower() in {".csv", ".txt"}:
        return pd.read_csv(p)
    raise ValueError(f"Unsupported file extension: {p.suffix}")


def excel_compare_cli(args) -> int:
    df = compare_excels(args.left, args.right, args.column)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path)
    print(f"[excel-compare] Wrote diff to {args.output}")
    return 0

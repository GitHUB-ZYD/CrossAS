from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pandas as pd


def read_table(path: str) -> pd.DataFrame:
    path_obj = Path(path)
    suffix = path_obj.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path_obj)
    if suffix in {".tsv", ".txt", ".bed"}:
        return pd.read_csv(path_obj, sep="\t")
    raise ValueError("Unsupported input format. Use .tsv, .txt, .bed, or .csv.")


def write_table(df: pd.DataFrame, path: str):
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    suffix = path_obj.suffix.lower()
    if suffix == ".csv":
        df.to_csv(path_obj, index=False, float_format="%.6f")
    elif suffix in {".tsv", ".txt", ".bed"}:
        df.to_csv(path_obj, sep="\t", index=False, float_format="%.6f")
    else:
        raise ValueError("Unsupported output format. Use .tsv or .csv.")


def default_output_path(result_dir: Path, model_id: str, prefix: str = "prediction") -> Path:
    result_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return result_dir / f"crossas_{prefix}_{model_id}_{stamp}.tsv"

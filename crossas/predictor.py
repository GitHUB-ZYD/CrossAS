from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
import pysam

from .as_pred import (
    get_snp_sequence,
    load_finetuned_model,
    load_tokenizer,
    predict_sequences,
    resolve_device,
)
from .config import COLUMN_ALIASES, CrossASSettings, load_settings, resolve_model


def _find_column(columns: Iterable[str], canonical_name: str) -> Optional[str]:
    lower_to_original = {str(col).lower(): col for col in columns}
    for alias in COLUMN_ALIASES[canonical_name]:
        if alias.lower() in lower_to_original:
            return lower_to_original[alias.lower()]
    return None


def normalize_variant_dataframe(
    df: pd.DataFrame,
    settings: CrossASSettings,
    default_genome: Optional[str] = None,
) -> pd.DataFrame:
    if df.empty:
        raise ValueError("Input table is empty.")

    chrom_col = _find_column(df.columns, "chrom")
    start_col = _find_column(df.columns, "start")
    end_col = _find_column(df.columns, "end")
    genome_col = _find_column(df.columns, "genome")
    id_col = _find_column(df.columns, "id")

    if chrom_col is None:
        raise ValueError("Missing chromosome column. Accepted names include chrom, chr, chromosome, snp_chr.")
    if start_col is None:
        raise ValueError("Missing start column. Accepted names include start, start_0, snp_start_0, snp_0_base.")
    if genome_col is None and default_genome is None:
        raise ValueError("No genome column was found and no --genome value was supplied.")

    out = df.copy()
    out["chrom"] = out[chrom_col].astype(str)
    out["start"] = pd.to_numeric(out[start_col], errors="raise").astype("int64")
    out["end"] = (
        out["start"] + 1
        if end_col is None
        else pd.to_numeric(out[end_col], errors="raise").astype("int64")
    )

    if genome_col is None:
        out["genome"] = str(default_genome).lower()
    else:
        out["genome"] = out[genome_col].astype(str).str.strip().str.lower()
        if default_genome is not None:
            out["genome"] = out["genome"].replace({"": default_genome, "nan": default_genome})

    if id_col is None:
        out["id"] = [f"variant_{i + 1}" for i in range(len(out))]
    else:
        out["id"] = out[id_col].astype(str)

    invalid_genomes = sorted(set(out["genome"]) - set(settings.genomes))
    if invalid_genomes:
        available = ", ".join(sorted(settings.genomes))
        raise ValueError(
            f"Unsupported reference genome value(s): {', '.join(invalid_genomes)}. "
            f"Available genomes: {available}."
        )

    invalid_intervals = out[out["end"] != out["start"] + 1]
    if not invalid_intervals.empty:
        raise ValueError(
            "CrossAS expects one-base SNP intervals: end must equal start + 1. "
            f"Found {len(invalid_intervals)} invalid row(s)."
        )

    return out


def _ordered_columns(df: pd.DataFrame) -> list[str]:
    preferred = [
        "id", "genome", "chrom", "start", "end", "model",
        "model_species", "element_type",
        "as_probability", "non_as_probability", "prediction", "status", "error",
    ]
    first = [c for c in preferred if c in df.columns]
    remaining = [c for c in df.columns if c not in first]
    return first + remaining


class CrossASPredictor:
    def __init__(
        self,
        device: str = "auto",
        extend_len: int = 512,
        config_path: Optional[str] = None,
    ):
        self.settings = load_settings(config_path)
        self.device = resolve_device(device)
        self.extend_len = int(extend_len)
        self._tokenizer = None
        self._genome_cache = {}
        self._model_cache = {}

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            self._tokenizer = load_tokenizer(self.extend_len)
        return self._tokenizer

    def get_genome(self, genome_name: str):
        key = str(genome_name).lower()
        if key not in self.settings.genomes:
            available = ", ".join(sorted(self.settings.genomes))
            raise ValueError(f"Unknown reference genome '{genome_name}'. Available genomes: {available}")

        if key not in self._genome_cache:
            genome_path = Path(self.settings.genomes[key])
            if not genome_path.exists() or genome_path.stat().st_size == 0:
                raise FileNotFoundError(
                    f"Reference genome not found or empty for '{key}': {genome_path}\n"
                    f"Edit [genomes] in {self.settings.config_path}."
                )
            self._genome_cache[key] = pysam.FastaFile(str(genome_path))
        return self._genome_cache[key]

    def get_model(self, model_id: str):
        key = str(model_id).lower()
        if key in self._model_cache:
            return self._model_cache[key]

        model_cfg = resolve_model(self.settings, key)
        checkpoint = Path(model_cfg.checkpoint_file)
        if not checkpoint.exists() or checkpoint.stat().st_size == 0:
            raise FileNotFoundError(
                f"Fine-tuned checkpoint not found or empty for '{key}': {checkpoint}\n"
                f"Edit [models] in {self.settings.config_path}."
            )

        model = load_finetuned_model(checkpoint_file=checkpoint, device=self.device)
        self._model_cache[key] = model
        return model

    def get_sequence(self, genome_name: str, chrom: str, start: int, end: Optional[int] = None) -> str:
        start = int(start)
        end = start + 1 if end is None else int(end)
        return get_snp_sequence(
            genome=self.get_genome(genome_name),
            chrom=str(chrom),
            start=start,
            end=end,
            extend_len=self.extend_len,
        )

    def _predict_sequences(self, sequences, model_id: str, batch_size: int = 32):
        return predict_sequences(
            sequences=sequences,
            tokenizer=self.tokenizer,
            model=self.get_model(model_id),
            device=self.device,
            batch_size=int(batch_size),
        )

    def predict_one(
        self,
        genome_name: str,
        chrom: str,
        start: int,
        end: Optional[int],
        model_id: str,
    ) -> dict:
        model_cfg = resolve_model(self.settings, model_id)
        start = int(start)
        end = start + 1 if end is None else int(end)
        sequence = self.get_sequence(genome_name, chrom, start, end)
        non_as, as_prob, predictions = self._predict_sequences([sequence], model_id=model_id, batch_size=1)
        return {
            "genome": str(genome_name).lower(),
            "chrom": str(chrom),
            "start": start,
            "end": end,
            "model": model_cfg.model_id,
            "model_species": model_cfg.species,
            "element_type": model_cfg.element_type,
            "as_probability": float(as_prob[0]),
            "non_as_probability": float(non_as[0]),
            "prediction": predictions[0],
        }

    def predict_dataframe(
        self,
        df: pd.DataFrame,
        model_id: str,
        default_genome: Optional[str] = None,
        batch_size: int = 32,
        continue_on_error: bool = True,
    ) -> pd.DataFrame:
        model_cfg = resolve_model(self.settings, model_id)
        result = normalize_variant_dataframe(df, self.settings, default_genome=default_genome)
        result["model"] = model_cfg.model_id
        result["model_species"] = model_cfg.species
        result["element_type"] = model_cfg.element_type
        result["as_probability"] = pd.NA
        result["non_as_probability"] = pd.NA
        result["prediction"] = pd.NA
        result["status"] = "pending"
        result["error"] = ""

        valid_indices = []
        valid_sequences = []
        for idx, row in result.iterrows():
            try:
                sequence = self.get_sequence(row["genome"], row["chrom"], row["start"], row["end"])
                valid_indices.append(idx)
                valid_sequences.append(sequence)
            except Exception as exc:
                if not continue_on_error:
                    raise
                result.at[idx, "status"] = "error"
                result.at[idx, "error"] = str(exc)

        if valid_sequences:
            non_as, as_prob, predictions = self._predict_sequences(
                valid_sequences,
                model_id=model_cfg.model_id,
                batch_size=int(batch_size),
            )
            for idx, p_non, p_as, prediction in zip(valid_indices, non_as, as_prob, predictions):
                result.at[idx, "as_probability"] = float(p_as)
                result.at[idx, "non_as_probability"] = float(p_non)
                result.at[idx, "prediction"] = prediction
                result.at[idx, "status"] = "ok"

        return result[_ordered_columns(result)]

    def close(self):
        for genome in self._genome_cache.values():
            genome.close()
        self._genome_cache.clear()

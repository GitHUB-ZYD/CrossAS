from __future__ import annotations

# CrossAS uses bundled local tokenizer/model-structure resources only.
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import json
from pathlib import Path
import warnings
from typing import Iterable, Tuple

import pysam
import torch
import torch.nn.functional as F
from transformers import PreTrainedTokenizerFast
from transformers.models.bert.configuration_bert import BertConfig

from .backbones.dnabert2.bert_layers import BertForSequenceClassification
from .config import BACKBONE_DIR


def resolve_device(device: str) -> torch.device:
    name = str(device).lower()
    if name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is False.")
    if name not in {"cpu", "cuda"}:
        raise ValueError("device must be one of: auto, cpu, cuda")
    return torch.device(name)


def load_tokenizer(extend_len: int = 512):
    max_seq_length = int(0.25 * (extend_len * 2 + 1)) + 1
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_file=str(BACKBONE_DIR / "tokenizer.json"),
        unk_token="[UNK]",
        cls_token="[CLS]",
        sep_token="[SEP]",
        pad_token="[PAD]",
        mask_token="[MASK]",
    )
    tokenizer.model_max_length = max_seq_length
    tokenizer.padding_side = "right"
    return tokenizer


def _build_model_config() -> BertConfig:
    config_file = BACKBONE_DIR / "config.json"
    with config_file.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    # Hub-specific metadata is irrelevant for the bundled local backbone.
    data.pop("auto_map", None)
    data.pop("_name_or_path", None)
    data["num_labels"] = 2

    config = BertConfig(**data)
    # MosaicBERT/DNABERT-2-specific attribute used by the bundled model code.
    config.alibi_starting_size = int(data.get("alibi_starting_size", 512))
    return config


def load_finetuned_model(checkpoint_file: Path, device: torch.device):
    """Create the bundled DNABERT-2 classifier and load a complete fine-tuned state dict.

    DNABERT-2 base/pretraining weights are not loaded. The architecture is bundled
    inside CrossAS; only the selected CrossAS fine-tuned checkpoint is read.
    """
    config = _build_model_config()
    model = BertForSequenceClassification(config)

    try:
        state_dict = torch.load(str(checkpoint_file), map_location="cpu", weights_only=True)
    except TypeError:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=FutureWarning,
                message=r".*torch\.load.*weights_only=False.*",
            )
            state_dict = torch.load(str(checkpoint_file), map_location="cpu")

    # Also accept a conventional wrapper object if a checkpoint was saved that way.
    if isinstance(state_dict, dict) and "state_dict" in state_dict and isinstance(state_dict["state_dict"], dict):
        state_dict = state_dict["state_dict"]

    model.load_state_dict(state_dict, strict=True)
    del state_dict
    model.to(device)
    model.eval()
    return model


def get_snp_sequence(
    genome: pysam.FastaFile,
    chrom: str,
    start: int,
    end: int,
    extend_len: int = 512,
) -> str:
    start = int(start)
    end = int(end)
    if end != start + 1:
        raise ValueError("Only one-base SNP intervals are supported: end must equal start + 1.")
    if start < 0:
        raise ValueError("start must be >= 0.")
    if chrom not in genome.references:
        example = ", ".join(genome.references[:8])
        raise ValueError(
            f"Chromosome '{chrom}' is not present in the reference genome. "
            f"Example reference names: {example}"
        )

    chrom_len = genome.get_reference_length(chrom)
    left = start - int(extend_len)
    right = end + int(extend_len)
    if left < 0 or right > chrom_len:
        raise ValueError(
            f"Variant {chrom}:{start}-{end} is too close to a chromosome boundary "
            f"for extend_len={extend_len}. Chromosome length={chrom_len}."
        )
    return genome.fetch(chrom, left, right).upper()


def predict_sequences(
    sequences: Iterable[str],
    tokenizer,
    model,
    device: torch.device,
    batch_size: int = 32,
) -> Tuple[list, list, list]:
    sequences = list(sequences)
    non_as_values = []
    as_values = []
    predictions = []

    with torch.no_grad():
        for offset in range(0, len(sequences), int(batch_size)):
            batch = sequences[offset : offset + int(batch_size)]
            encoded = tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                max_length=tokenizer.model_max_length,
                truncation=True,
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            outputs = model(**encoded)
            probabilities = F.softmax(outputs.logits, dim=1).detach().cpu()
            labels = torch.argmax(probabilities, dim=1)

            non_as_values.extend(probabilities[:, 0].tolist())
            as_values.extend(probabilities[:, 1].tolist())
            predictions.extend(
                ["Allele-Specific" if int(label) == 1 else "Non-Allele-Specific" for label in labels]
            )

    return non_as_values, as_values, predictions

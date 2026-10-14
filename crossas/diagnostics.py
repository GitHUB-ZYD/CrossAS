from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import BACKBONE_DIR, load_settings


def run_checks(config_path: Optional[str] = None) -> list[dict]:
    settings = load_settings(config_path)
    rows = []

    def add(kind: str, name: str, path: Path, required: bool = True):
        exists = path.exists()
        size = path.stat().st_size if exists and path.is_file() else None
        ok = exists and (size is None or size > 0)
        rows.append(
            {
                "kind": kind,
                "name": name,
                "path": str(path),
                "required": required,
                "ok": bool(ok),
                "size_bytes": size,
            }
        )

    add("backbone", "DNABERT-2 model structure", BACKBONE_DIR / "bert_layers.py")
    add("backbone", "DNABERT-2 tokenizer", BACKBONE_DIR / "tokenizer.json")
    add("backbone", "DNABERT-2 config", BACKBONE_DIR / "config.json")

    for genome_name, path in sorted(settings.genomes.items()):
        add("genome", genome_name, Path(path))

    for model_id, model_cfg in sorted(settings.models.items()):
        add("model", model_id, Path(model_cfg.checkpoint_file))

    return rows

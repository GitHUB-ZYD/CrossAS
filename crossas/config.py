from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
import os
from typing import Dict, Optional

PACKAGE_DIR = Path(__file__).resolve().parent
BACKBONE_DIR = PACKAGE_DIR / "backbones" / "dnabert2"
DEFAULT_CONFIG_NAME = "crossas.ini"


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    checkpoint_file: Path
    species: str
    element_type: str

    @property
    def display_name(self) -> str:
        return f"{self.species.capitalize()} {self.element_type.capitalize()}"


@dataclass(frozen=True)
class CrossASSettings:
    config_path: Path
    resource_dir: Path
    result_dir: Path
    genomes: Dict[str, Path]
    models: Dict[str, ModelConfig]


def _resolve_path(value: str, config_dir: Path) -> Path:
    path = Path(os.path.expandvars(os.path.expanduser(value.strip())))
    if not path.is_absolute():
        path = config_dir / path
    return path.resolve()


def find_config_path(explicit_path: Optional[str] = None) -> Path:
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))

    env_config = os.environ.get("CROSSAS_CONFIG")
    if env_config:
        candidates.append(Path(env_config))

    env_home = os.environ.get("CROSSAS_HOME")
    if env_home:
        candidates.append(Path(env_home) / DEFAULT_CONFIG_NAME)

    cwd = Path.cwd().resolve()
    candidates.extend(parent / DEFAULT_CONFIG_NAME for parent in [cwd, *cwd.parents])

    # Useful for editable/source installs.
    candidates.append(PACKAGE_DIR.parent / DEFAULT_CONFIG_NAME)
    candidates.append(Path.home() / ".config" / "crossas" / DEFAULT_CONFIG_NAME)

    seen = []
    for candidate in candidates:
        candidate = candidate.expanduser().resolve()
        if candidate in seen:
            continue
        seen.append(candidate)
        if candidate.is_file():
            return candidate

    searched = "\n  - ".join(str(p) for p in seen)
    raise FileNotFoundError(
        "CrossAS configuration file was not found.\n"
        "Run CrossAS from the project directory, pass --config, or set CROSSAS_CONFIG.\n"
        f"Searched:\n  - {searched}"
    )


def load_settings(config_path: Optional[str] = None) -> CrossASSettings:
    path = find_config_path(config_path)
    parser = ConfigParser()
    parser.optionxform = str.lower
    parser.read(path)
    config_dir = path.parent

    for section in ("paths", "genomes", "models"):
        if section not in parser:
            raise ValueError(f"Missing [{section}] section in {path}")

    resource_dir = _resolve_path(parser["paths"].get("resource_dir", "./resources"), config_dir)
    result_dir = _resolve_path(parser["paths"].get("result_dir", "./results"), config_dir)

    genomes = {
        species.strip().lower(): _resolve_path(value, config_dir)
        for species, value in parser["genomes"].items()
    }

    models: Dict[str, ModelConfig] = {}
    for model_id, value in parser["models"].items():
        key = model_id.strip().lower()
        parts = key.split("-", 1)
        if len(parts) != 2 or parts[0] not in {"human", "pig"} or parts[1] not in {"promoter", "enhancer"}:
            raise ValueError(
                f"Invalid model ID '{model_id}' in {path}. "
                "Expected one of human-promoter, human-enhancer, pig-promoter, pig-enhancer."
            )
        models[key] = ModelConfig(
            model_id=key,
            checkpoint_file=_resolve_path(value, config_dir),
            species=parts[0],
            element_type=parts[1],
        )

    return CrossASSettings(
        config_path=path,
        resource_dir=resource_dir,
        result_dir=result_dir,
        genomes=genomes,
        models=models,
    )


def resolve_model(settings: CrossASSettings, model_id: str) -> ModelConfig:
    key = model_id.strip().lower()
    if key not in settings.models:
        available = ", ".join(sorted(settings.models)) or "none"
        raise ValueError(f"Unknown model '{model_id}'. Available models: {available}")
    return settings.models[key]


COLUMN_ALIASES = {
    "id": ["id", "variant_id", "snp_id", "name"],
    "genome": ["genome", "species", "reference_genome", "snp_species", "sequence_species"],
    "chrom": ["chrom", "chr", "chromosome", "snp_chr"],
    "start": ["start", "start_0", "snp_start_0", "snp_0_base", "pos_0", "position_0"],
    "end": ["end", "end_1", "snp_end_1", "snp_start_1", "pos_1", "position_1"],
}

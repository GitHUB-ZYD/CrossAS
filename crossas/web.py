from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Optional

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory

from .config import PACKAGE_DIR
from .predictor import CrossASPredictor


def _read_uploaded_table(file_storage):
    filename = (file_storage.filename or "").lower()
    raw = file_storage.read()
    if not raw:
        raise ValueError("Uploaded variant file is empty.")
    buffer = io.BytesIO(raw)
    if filename.endswith(".csv"):
        return pd.read_csv(buffer)
    return pd.read_csv(buffer, sep="\t")


def create_app(device: str = "auto", config_path: Optional[str] = None):
    static_dir = Path(PACKAGE_DIR) / "static"
    if not static_dir.exists():
        raise FileNotFoundError(f"CrossAS packaged static directory not found: {static_dir}")

    app = Flask(__name__, static_folder=str(static_dir), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

    # One predictor per web process. Tokenizer, genomes, and requested models are cached.
    predictor = CrossASPredictor(device=device, config_path=config_path)

    @app.route("/")
    def index():
        return send_from_directory(str(static_dir / "html"), "as_pred.html")

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify(
            {
                "status": "ok",
                "device": str(predictor.device),
                "config": str(predictor.settings.config_path),
            }
        )

    @app.route("/meta", methods=["GET"])
    def meta():
        models = [
            {
                "id": model_id,
                "display_name": cfg.display_name,
                "species": cfg.species,
                "element_type": cfg.element_type,
            }
            for model_id, cfg in sorted(predictor.settings.models.items())
        ]
        genomes = sorted(predictor.settings.genomes)
        return jsonify({"models": models, "genomes": genomes})

    @app.route("/as_pred", methods=["POST"])
    def process_as_pred():
        try:
            data = request.get_json(force=True)
            genome_name = str(data["genome"]).lower()
            chrom = str(data["chrom"])
            start = int(data["start"])
            end = int(data.get("end", start + 1))
            model_id = str(data["model"]).lower()

            result = predictor.predict_one(
                genome_name=genome_name,
                chrom=chrom,
                start=start,
                end=end,
                model_id=model_id,
            )
            return jsonify(result)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.route("/as_pred_batch", methods=["POST"])
    def process_as_pred_batch():
        try:
            if "file" not in request.files:
                raise ValueError("Missing uploaded variant file.")

            input_df = _read_uploaded_table(request.files["file"])
            model_id = str(request.form["model"]).lower()
            default_genome = request.form.get("genome") or None
            batch_size = int(request.form.get("batch_size", 32))

            result_df = predictor.predict_dataframe(
                input_df,
                model_id=model_id,
                default_genome=default_genome,
                batch_size=batch_size,
                continue_on_error=True,
            )

            records = json.loads(result_df.to_json(orient="records"))
            ok_count = int((result_df["status"] == "ok").sum())
            error_count = int((result_df["status"] == "error").sum())
            return jsonify(
                {
                    "summary": {"rows": len(result_df), "ok": ok_count, "error": error_count},
                    "results": records,
                }
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    return app

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from . import __version__


MODEL_IDS = ["human-promoter", "human-enhancer", "pig-promoter", "pig-enhancer"]
GENOME_IDS = ["human", "pig"]


def _formatter(prog):
    return argparse.RawDescriptionHelpFormatter(prog)


def _add_config_arg(parser):
    parser.add_argument(
        "-c", "--config",
        metavar="FILE",
        help="CrossAS configuration file. Default: locate crossas.ini from the current project or CROSSAS_CONFIG.",
    )


def _add_device_arg(parser):
    parser.add_argument(
        "-d", "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help="Inference device. 'auto' uses CUDA when available, otherwise CPU. Default: auto.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crossas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "CrossAS V1.0\n"
            "Cross-species allele-specific variant prediction using fine-tuned genomic language models."
        ),
        epilog=(
            "Examples:\n"
            "  crossas predict -m pig-promoter -g pig chr1 130071886 130071887\n"
            "  crossas predict -m human-promoter -g pig chr1 130071886 130071887 -o results/result.tsv\n"
            "  crossas batch -m pig-enhancer -g pig -i example/batch_variants.tsv -o results/batch.tsv\n"
            "  crossas models\n"
            "  crossas check\n"
            "  crossas serve --host 0.0.0.0 --port 5000 --device cpu"
        ),
    )
    parser.add_argument("--version", action="version", version=f"CrossAS {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True, title="commands")

    predict = subparsers.add_parser(
        "predict",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Predict one variant.",
        description="Predict allele-specific activity for a single one-base variant.",
        epilog=(
            "Examples:\n"
            "  crossas predict -m pig-promoter -g pig chr1 130071886 130071887\n"
            "  crossas predict -m human-enhancer -g pig chr2 2000000 2000001 --json"
        ),
    )
    predict.add_argument(
        "-m", "--model", required=True, choices=MODEL_IDS, metavar="MODEL",
        help="Prediction model: human-promoter, human-enhancer, pig-promoter, or pig-enhancer.",
    )
    predict.add_argument(
        "-g", "--genome", required=True, choices=GENOME_IDS, metavar="GENOME",
        help="Reference genome used to extract the input sequence: human or pig.",
    )
    predict.add_argument("chrom", help="Chromosome name, for example chr1.")
    predict.add_argument("start", type=int, help="0-based variant start coordinate.")
    predict.add_argument(
        "end", type=int, nargs="?",
        help="0-based exclusive end coordinate. For a SNP, end = start + 1. Default: start + 1.",
    )
    predict.add_argument(
        "-o", "--output", metavar="FILE",
        help="Optional output TSV/CSV path. If omitted, a formatted result is printed to stdout.",
    )
    predict.add_argument(
        "--json", action="store_true",
        help="Print the single-variant result as JSON instead of formatted text.",
    )
    _add_device_arg(predict)
    _add_config_arg(predict)

    batch = subparsers.add_parser(
        "batch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Predict variants from a TSV/CSV file.",
        description=(
            "Batch prediction from a table. Required columns are chromosome and start.\n"
            "End is optional and defaults to start + 1. A genome column can be supplied per row;\n"
            "otherwise use --genome to define the reference genome for the batch."
        ),
        epilog=(
            "Examples:\n"
            "  crossas batch -m pig-promoter -g pig -i example/batch_variants.tsv\n"
            "  crossas batch -m human-enhancer -i example/mixed_genomes.tsv -o results/mixed.tsv -b 64"
        ),
    )
    batch.add_argument(
        "-m", "--model", required=True, choices=MODEL_IDS, metavar="MODEL",
        help="Prediction model: human-promoter, human-enhancer, pig-promoter, or pig-enhancer.",
    )
    batch.add_argument(
        "-g", "--genome", choices=GENOME_IDS, metavar="GENOME",
        help="Reference genome for rows without a genome column: human or pig.",
    )
    batch.add_argument("-i", "--input", required=True, metavar="FILE", help="Input TSV/CSV/BED-like table.")
    batch.add_argument(
        "-o", "--output", metavar="FILE",
        help="Output TSV/CSV path. Default: automatically create a timestamped file in results/.",
    )
    batch.add_argument(
        "-b", "--batch-size", type=int, default=32, metavar="N",
        help="Model inference batch size. Default: 32.",
    )
    batch.add_argument(
        "--fail-fast", action="store_true",
        help="Stop immediately on the first invalid row instead of recording row-level errors.",
    )
    _add_device_arg(batch)
    _add_config_arg(batch)

    models = subparsers.add_parser("models", help="List configured prediction models.")
    _add_config_arg(models)

    check = subparsers.add_parser("check", help="Check configuration and required local resources.")
    _add_config_arg(check)

    serve = subparsers.add_parser(
        "serve",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Start the CrossAS web application.",
        description="Start the local CrossAS web server. Models are loaded lazily and cached in memory.",
        epilog="Example:\n  crossas serve --host 0.0.0.0 --port 5000 --device cpu",
    )
    serve.add_argument("--host", default="0.0.0.0", help="Bind host. Default: 0.0.0.0.")
    serve.add_argument("--port", type=int, default=5000, help="Bind port. Default: 5000.")
    serve.add_argument("--debug", action="store_true", help="Enable Flask debug mode.")
    _add_device_arg(serve)
    _add_config_arg(serve)

    return parser


def _round_result(result: dict) -> dict:
    out = dict(result)
    for key in ("as_probability", "non_as_probability"):
        if key in out and out[key] is not None:
            out[key] = round(float(out[key]), 6)
    return out


def _print_single_result(result: dict):
    print(f"Reference genome:              {result['genome']}")
    print(f"Variant:                       {result['chrom']}:{result['start']}-{result['end']}")
    print(f"Prediction model:              {result['model']}")
    print(f"Allele-Specific Probability:   {float(result['as_probability']):.6f}")
    print(f"Non-Allele-Specific Probability: {float(result['non_as_probability']):.6f}")
    print(f"Prediction:                    {result['prediction']}")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.command == "models":
        from .config import load_settings
        settings = load_settings(args.config)
        print("Model\tSpecies\tRegulatory region\tCheckpoint")
        for model_id, cfg in sorted(settings.models.items()):
            print(f"{model_id}\t{cfg.species}\t{cfg.element_type}\t{cfg.checkpoint_file}")
        return 0

    if args.command == "check":
        from .diagnostics import run_checks
        rows = run_checks(args.config)
        failed = 0
        print("Status\tType\tName\tPath")
        for row in rows:
            status = "OK" if row["ok"] else "MISSING"
            if not row["ok"] and row["required"]:
                failed += 1
            print(f"{status}\t{row['kind']}\t{row['name']}\t{row['path']}")
        return 1 if failed else 0

    if args.command == "serve":
        from .web import create_app
        app = create_app(device=args.device, config_path=args.config)
        app.run(host=args.host, port=args.port, debug=args.debug)
        return 0

    from .predictor import CrossASPredictor
    from .io import default_output_path, read_table, write_table
    predictor = CrossASPredictor(device=args.device, config_path=args.config)

    try:
        if args.command == "predict":
            end = args.start + 1 if args.end is None else args.end
            result = predictor.predict_one(
                genome_name=args.genome,
                chrom=args.chrom,
                start=args.start,
                end=end,
                model_id=args.model,
            )
            if args.output:
                import pandas as pd
                write_table(pd.DataFrame([result]), args.output)
                print(str(Path(args.output).resolve()))
            elif args.json:
                print(json.dumps(_round_result(result), indent=2))
            else:
                _print_single_result(result)
            return 0

        if args.command == "batch":
            input_df = read_table(args.input)
            result_df = predictor.predict_dataframe(
                input_df,
                model_id=args.model,
                default_genome=args.genome,
                batch_size=args.batch_size,
                continue_on_error=not args.fail_fast,
            )
            output = Path(args.output) if args.output else default_output_path(
                predictor.settings.result_dir, args.model, prefix="batch"
            )
            write_table(result_df, str(output))
            ok_count = int((result_df["status"] == "ok").sum())
            error_count = int((result_df["status"] == "error").sum())
            print(f"Output: {output.resolve()}")
            print(f"Rows: {len(result_df)}; OK: {ok_count}; Error: {error_count}")
            return 0
    finally:
        predictor.close()

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

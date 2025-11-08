import argparse
import sys

from .logging_utils import setup_logging
from .modules.template_engine.engine import render_template_cli
from .modules.tools.excel_compare import excel_compare_cli
from .modules.akamai_engine.client import akamai_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devsecops-assistant",
        description="DevSecOps Assistant multi-module CLI",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # Template engine
    tmpl = subparsers.add_parser("template", help="Render templates (Jinja2 + YAML)")
    tmpl.add_argument("--template", required=True, help="Path to template file (.j2)")
    tmpl.add_argument("--values", required=True, help="Path to YAML/JSON values file")
    tmpl.add_argument("--output", required=True, help="Output file path")
    tmpl.set_defaults(func=render_template_cli)

    # Excel compare
    exc = subparsers.add_parser("excel-compare", help="Compare two Excel/CSV files") 
    exc.add_argument("--left", required=True, help="Left Excel/CSV file") 
    exc.add_argument("--right", required=True, help="Right Excel/CSV file") 
    exc.add_argument("--column", required=True, help="Column name to join on") 
    exc.add_argument("--output", required=True, help="Path to output CSV with diff") 
    exc.set_defaults(func=excel_compare_cli)

    # Akamai engine
    aka = subparsers.add_parser("akamai", help="Akamai DevOps engine commands")
    aka.set_defaults(func=akamai_cli)

    return parser


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(level=args.log_level)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

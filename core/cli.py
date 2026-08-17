import argparse
import sys

from .logging_utils import setup_logging
from .modules.template_engine.engine import render_template_cli
from .modules.tools.excel_compare import excel_compare_cli
from .modules.akamai_engine.client import akamai_cli
from .modules.ci_onboard.onboard import onboard_cli, list_supported_tools
from .modules.containerize.containerize import containerize_cli
from .modules.containerize.k8s import k8s_cli, DEFAULT_REPLICAS as K8S_DEFAULT_REPLICAS
from .modules.automation.automate import automate_cli, ALL_TARGETS as AUTOMATION_TARGETS
from .modules.security_scan.remediation import security_scan_cli
from .modules.exceptions.cli_entry import exceptions_cli
from .agents.coordinator import repl as chat_repl


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

    # CI onboarding
    onboard = subparsers.add_parser(
        "onboard",
        help="Auto-detect a project and generate a CI/CD pipeline",
    )
    onboard.add_argument(
        "--project", default=".", help="Path to the project to onboard (default: current directory)"
    )
    onboard.add_argument(
        "--ci", required=True, choices=list_supported_tools(), help="Target CI tool"
    )
    onboard.add_argument(
        "--deploy-branch", default="main", help="Branch to deploy from (default: main)"
    )
    onboard.add_argument(
        "--output", default=None, help="Output file path (default: the CI tool's conventional path)"
    )
    onboard.add_argument(
        "--dry-run", action="store_true", help="Print the rendered pipeline instead of writing it"
    )
    onboard.set_defaults(func=onboard_cli)

    # Containerization
    ctr = subparsers.add_parser(
        "containerize",
        help="Auto-detect a project and generate a Dockerfile (+ .dockerignore, optional compose)",
    )
    ctr.add_argument(
        "--project", default=".", help="Path to the project to containerize (default: current directory)"
    )
    ctr.add_argument(
        "--port", type=int, default=None, help="Port the app listens on (default: framework convention)"
    )
    ctr.add_argument(
        "--output", default=None, help="Dockerfile output path (default: <project>/Dockerfile)"
    )
    ctr.add_argument(
        "--compose", action="store_true", help="Also generate a docker-compose.yml"
    )
    ctr.add_argument(
        "--dry-run", action="store_true", help="Print the rendered files instead of writing them"
    )
    ctr.set_defaults(func=containerize_cli)

    # Kubernetes manifests / Helm chart
    k8s = subparsers.add_parser(
        "k8s",
        help="Auto-detect a project and generate Kubernetes manifests or a Helm chart",
    )
    k8s.add_argument(
        "--project", default=".", help="Path to the project (default: current directory)"
    )
    k8s.add_argument(
        "--helm", action="store_true", help="Generate a Helm chart instead of plain manifests"
    )
    k8s.add_argument(
        "--port", type=int, default=None, help="Port the app listens on (default: framework convention)"
    )
    k8s.add_argument(
        "--replicas", type=int, default=K8S_DEFAULT_REPLICAS, help=f"Pod replica count (default: {K8S_DEFAULT_REPLICAS})"
    )
    k8s.add_argument(
        "--image", default=None, help="Container image reference (plain manifests only; default: <service-name>:latest)"
    )
    k8s.add_argument(
        "--output-dir", default=None, help="Output directory (default: <project>/k8s or <project>/chart)"
    )
    k8s.add_argument(
        "--dry-run", action="store_true", help="Print the rendered files instead of writing them"
    )
    k8s.set_defaults(func=k8s_cli)

    # Automation frameworks
    auto = subparsers.add_parser(
        "automate",
        help="Auto-detect a project and generate dev-workflow automation (Makefile, Dependabot, pre-commit)",
    )
    auto.add_argument(
        "--project", default=".", help="Path to the project (default: current directory)"
    )
    auto.add_argument(
        "--targets",
        nargs="+",
        choices=list(AUTOMATION_TARGETS),
        default=None,
        help="Which artifacts to generate (default: all of them)",
    )
    auto.add_argument(
        "--dry-run", action="store_true", help="Print the rendered files instead of writing them"
    )
    auto.set_defaults(func=automate_cli)

    # Security scanning
    sec = subparsers.add_parser(
        "security-scan",
        help="Scan a project for secrets, risky code patterns, and vulnerable dependencies",
    )
    sec.add_argument(
        "--project", default=".", help="Path to the project to scan (default: current directory)"
    )
    sec.add_argument(
        "--no-secrets", action="store_true", help="Skip the secret scanner"
    )
    sec.add_argument(
        "--no-patterns", action="store_true", help="Skip the risky-pattern scanner"
    )
    sec.add_argument(
        "--no-dependencies", action="store_true", help="Skip the dependency vulnerability scanner"
    )
    sec.add_argument(
        "--output", default=None, help="Findings report path (default: <project>/SECURITY_FINDINGS.md)"
    )
    sec.add_argument(
        "--dry-run", action="store_true", help="Print a findings summary instead of writing the report"
    )
    sec.set_defaults(func=security_scan_cli)

    # Exceptions tracking (accepted-risk waivers)
    exc = subparsers.add_parser(
        "exceptions",
        help="Track accepted security risks (waivers) — create, list, revoke, or check expiry",
    )
    exc_sub = exc.add_subparsers(dest="exceptions_command", metavar="<action>")

    exc_create = exc_sub.add_parser("create", help="Record a new exception")
    exc_create.add_argument("--project", default=".", help="Path to the project (default: current directory)")
    exc_create.add_argument("--description", required=True, help="What is being accepted")
    exc_create.add_argument("--justification", required=True, help="Why it's acceptable")
    exc_create.add_argument("--approved-by", required=True, help="Who approved it")
    exc_create.add_argument("--expires-at", required=True, help="ISO date/datetime this exception expires, e.g. 2026-12-01")
    exc_create.add_argument("--finding-id", default=None, help="The Security Scanning finding_id this waives, if any")

    exc_list = exc_sub.add_parser("list", help="List recorded exceptions")
    exc_list.add_argument("--project", default=".", help="Path to the project (default: current directory)")
    exc_list.add_argument("--status", choices=["active", "expired", "revoked"], default=None, help="Filter by status")

    exc_revoke = exc_sub.add_parser("revoke", help="Revoke an exception before its expiry")
    exc_revoke.add_argument("--project", default=".", help="Path to the project (default: current directory)")
    exc_revoke.add_argument("--waiver-id", required=True, help="The exception's id")
    exc_revoke.add_argument("--reason", required=True, help="Why it's being revoked")

    exc_expiring = exc_sub.add_parser("expiring", help="List active exceptions expiring soon")
    exc_expiring.add_argument("--project", default=".", help="Path to the project (default: current directory)")
    exc_expiring.add_argument("--within-days", type=int, default=7, help="How many days ahead to check (default: 7)")

    exc.set_defaults(func=exceptions_cli)

    # Chat — the coordinator agent
    chat = subparsers.add_parser(
        "chat",
        help="Start an interactive chat session with the DevSecOps Assistant coordinator",
    )
    chat.set_defaults(func=lambda args: chat_repl())

    return parser


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Some commands print emoji/box-drawing characters; Windows consoles
    # often default to a non-UTF-8 codepage (e.g. cp1252) that can't encode
    # them, which would otherwise crash the process mid-output.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(level=args.log_level)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""CLI entry point for the `exceptions` subcommand and its nested actions."""

from __future__ import annotations

from ..registry.store import app_id_for
from .store import create_exception, expiring_within, list_exceptions, revoke_exception


def _print_waiver(w) -> None:
    finding_part = f", finding {w.finding_id}" if w.finding_id else ""
    print(f"[{w.status()}] {w.waiver_id}{finding_part}")
    print(f"  {w.description}")
    print(f"  Justification : {w.justification}")
    print(f"  Approved by   : {w.approved_by}")
    print(f"  Created       : {w.created_at}")
    print(f"  Expires       : {w.expires_at}")
    if w.revoked_at:
        print(f"  Revoked       : {w.revoked_at} ({w.revoked_reason})")
    print()


def exceptions_cli(args) -> int:
    action = getattr(args, "exceptions_command", None)
    if action is None:
        print("Specify an action: create, list, revoke, or expiring. See --help.")
        return 1

    try:
        if action == "create":
            waiver = create_exception(
                args.project,
                app_id=app_id_for(args.project),
                description=args.description,
                justification=args.justification,
                approved_by=args.approved_by,
                expires_at=args.expires_at,
                finding_id=args.finding_id,
            )
            print(f"Recorded exception {waiver.waiver_id} (expires {waiver.expires_at}).")
            return 0

        if action == "list":
            waivers = list_exceptions(args.project, app_id=app_id_for(args.project), status=args.status)
            if not waivers:
                print("No exceptions recorded.")
                return 0
            for w in waivers:
                _print_waiver(w)
            return 0

        if action == "revoke":
            waiver = revoke_exception(args.project, args.waiver_id, args.reason)
            print(f"Revoked exception {waiver.waiver_id}.")
            return 0

        if action == "expiring":
            waivers = expiring_within(args.project, days=args.within_days, app_id=app_id_for(args.project))
            if not waivers:
                print(f"No active exceptions expiring within {args.within_days} day(s).")
                return 0
            for w in waivers:
                _print_waiver(w)
            return 0

        print(f"Unknown action: {action}")
        return 1
    except (KeyError, ValueError) as exc:
        print(f"\n❌ Error: {exc}")
        return 1

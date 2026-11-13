"""플래그를 켜고 끄는 CLI.

python -m app.flagctl list
python -m app.flagctl set <name> on [--percent 10]
python -m app.flagctl set <name> off
"""

import argparse
import sys

from app import db
from app.config import load_settings
from app.flags import load_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flagctl")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    set_parser = sub.add_parser("set")
    set_parser.add_argument("name")
    set_parser.add_argument("state", choices=["on", "off"])
    set_parser.add_argument("--percent", type=int, default=100)
    args = parser.parse_args(argv)

    settings = load_settings()
    registry = load_registry()

    with db.connect(settings.database_url) as conn:
        if args.command == "set":
            if args.name not in registry:
                print(f"flags.json에 없는 플래그: {args.name}", file=sys.stderr)
                return 1
            if not 0 <= args.percent <= 100:
                print("--percent는 0~100", file=sys.stderr)
                return 1
            conn.execute(
                """
                INSERT INTO feature_flags (name, enabled, rollout_percent)
                VALUES (%s, %s, %s)
                ON CONFLICT (name) DO UPDATE
                SET enabled = EXCLUDED.enabled,
                    rollout_percent = EXCLUDED.rollout_percent,
                    updated_at = now()
                """,
                (args.name, args.state == "on", args.percent),
            )

        rows = conn.execute(
            "SELECT name, enabled, rollout_percent, updated_at FROM feature_flags"
        ).fetchall()
        states = {row["name"]: row for row in rows}

    print(f"[{settings.app_env}] feature flags")
    if not registry:
        print("  (flags.json에 등록된 플래그가 없다)")
    for name, spec in registry.items():
        row = states.get(name)
        if row is None:
            status = f"기본값({'on' if spec['default'] else 'off'})"
        elif row["enabled"]:
            status = f"on {row['rollout_percent']}%"
        else:
            status = "off"
        print(f"  {name:<28} {status:<14} 만료 {spec['expires']}  담당 {spec['owner']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

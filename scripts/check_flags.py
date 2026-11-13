#!/usr/bin/env python3
"""feature flag가 빚으로 쌓이지 않게 CI에서 검사한다.

    python3 scripts/check_flags.py
    python3 scripts/check_flags.py --today 2027-01-15

실패하는 경우:
  - 필수 항목(description, owner, expires, default)이 빠진 플래그
  - 만료일이 지난 플래그
  - 코드에서 쓰는데 flags.json에 없는 플래그
  - flags.json에 있는데 코드에서 더는 쓰지 않는 플래그
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_FIELDS = ("description", "owner", "expires", "default")
USAGE_PATTERN = re.compile(r"""is_enabled\(\s*["']([a-z0-9_]+)["']""")


def flags_used_in_code() -> set[str]:
    used: set[str] = set()
    for path in (ROOT / "app").rglob("*"):
        if path.suffix in (".py", ".html"):
            used.update(USAGE_PATTERN.findall(path.read_text(encoding="utf-8")))
    return used


def check(registry: dict, used: set[str], today: datetime.date) -> list[str]:
    problems = []
    for name, spec in registry.items():
        missing = [key for key in REQUIRED_FIELDS if key not in spec]
        if missing:
            problems.append(f"{name}: 필수 항목 누락 ({', '.join(missing)})")
            continue
        expires = datetime.date.fromisoformat(spec["expires"])
        if expires < today:
            problems.append(
                f"{name}: 만료일({expires})이 지났다. "
                f"플래그와 분기 코드를 지우거나, 이유를 적고 만료일을 늘린다 (담당 {spec['owner']})"
            )
        if name not in used:
            problems.append(f"{name}: 코드에서 쓰지 않는다. flags.json에서 지운다")
    for name in sorted(used - set(registry)):
        problems.append(f"{name}: 코드에서 쓰는데 flags.json에 없다")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--today", type=datetime.date.fromisoformat, default=datetime.date.today())
    args = parser.parse_args()

    registry = json.loads((ROOT / "flags.json").read_text(encoding="utf-8"))
    problems = check(registry, flags_used_in_code(), args.today)

    if problems:
        print("feature flag 검사 실패:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"feature flag {len(registry)}개 이상 없음 (기준일 {args.today})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

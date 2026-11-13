"""마이그레이션 실행기.

python -m app.migrate status
python -m app.migrate up
python -m app.migrate up --allow-contract

파일 이름은 NNNN_expand_*.sql 또는 NNNN_contract_*.sql 이다.
expand는 옛 버전 코드가 계속 동작하는 변경이라 배포 때 자동으로 적용한다.
contract는 옛 버전 코드를 깨뜨릴 수 있어 사람이 --allow-contract로 따로 적용한다.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

from app.config import load_settings

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

# 두 배포가 동시에 마이그레이션을 돌리지 못하게 잡는 advisory lock 번호.
LOCK_ID = 20261112


@dataclass(frozen=True)
class Migration:
    version: str
    phase: str
    name: str
    path: Path


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        version, phase, _ = path.stem.split("_", 2)
        if phase not in ("expand", "contract"):
            raise ValueError(f"{path.name}: 단계는 expand 또는 contract여야 한다")
        migrations.append(Migration(version, phase, path.stem, path))
    return migrations


def plan(
    available: list[Migration], applied: set[str], *, allow_contract: bool
) -> tuple[list[Migration], Migration | None]:
    """적용할 목록과, contract라서 멈춘 지점을 돌려준다."""
    to_apply: list[Migration] = []
    for migration in available:
        if migration.version in applied:
            continue
        if migration.phase == "contract" and not allow_contract:
            # 순서를 건너뛰지 않는다.
            # contract에서 멈추면 그 뒤 마이그레이션도 적용하지 않는다.
            return to_apply, migration
        to_apply.append(migration)
    return to_apply, None


def _applied_versions(conn: psycopg.Connection) -> set[str]:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    TEXT        PRIMARY KEY,
            name       TEXT        NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}


def up(database_url: str, *, allow_contract: bool = False, out=print) -> None:
    available = discover()
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        applied = _applied_versions(conn)

        # 롤백으로 옛 이미지가 올라오면 DB가 코드보다 앞서 있다.
        # expand만 적용돼 있다면 옛 코드도 동작하므로 그대로 둔다.
        ahead = sorted(applied - {m.version for m in available})
        if ahead:
            out(f"DB가 이 이미지보다 앞서 있다 (이 이미지가 모르는 버전: {', '.join(ahead)})")

        to_apply, blocked = plan(available, applied, allow_contract=allow_contract)
        for migration in to_apply:
            out(f"적용: {migration.name}")
            # 파일 하나가 한 트랜잭션이다.
            # 중간에 실패하면 그 파일의 변경은 전부 취소된다.
            with conn.transaction():
                conn.execute(migration.path.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
                    (migration.version, migration.name),
                )
        if not to_apply:
            out("적용할 마이그레이션이 없다")
        if blocked:
            out(f"보류: {blocked.name} (contract 단계는 --allow-contract로 따로 적용한다)")


def status(database_url: str, out=print) -> None:
    available = discover()
    with psycopg.connect(database_url, autocommit=True) as conn:
        applied = _applied_versions(conn)
    for migration in available:
        mark = "적용됨" if migration.version in applied else "대기  "
        out(f"  [{mark}] {migration.phase:<8} {migration.name}")
    for version in sorted(applied - {m.version for m in available}):
        out(f"  [적용됨] ?        {version} (이 이미지에는 없는 마이그레이션)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="migrate")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    up_parser = sub.add_parser("up")
    up_parser.add_argument("--allow-contract", action="store_true")
    args = parser.parse_args(argv)

    database_url = load_settings().database_url
    try:
        if args.command == "status":
            status(database_url)
        else:
            up(database_url, allow_contract=args.allow_contract)
    except psycopg.Error as error:
        # 실패한 파일의 변경은 트랜잭션과 함께 취소됐다.
        print(f"마이그레이션 실패: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

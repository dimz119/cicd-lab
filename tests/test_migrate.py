from pathlib import Path

import pytest

from app.migrate import Migration, discover, plan


def migration(version: str, phase: str) -> Migration:
    return Migration(version, phase, f"{version}_{phase}_x", Path(f"{version}_{phase}_x.sql"))


EXPAND_1 = migration("0001", "expand")
EXPAND_2 = migration("0002", "expand")
CONTRACT_3 = migration("0003", "contract")
EXPAND_4 = migration("0004", "expand")


def test_applies_only_pending_migrations():
    to_apply, blocked = plan([EXPAND_1, EXPAND_2], {"0001"}, allow_contract=False)

    assert to_apply == [EXPAND_2]
    assert blocked is None


def test_stops_at_contract_and_does_not_skip_ahead():
    to_apply, blocked = plan(
        [EXPAND_1, EXPAND_2, CONTRACT_3, EXPAND_4], {"0001"}, allow_contract=False
    )

    assert to_apply == [EXPAND_2]
    assert blocked == CONTRACT_3


def test_applies_contract_when_explicitly_allowed():
    to_apply, blocked = plan(
        [EXPAND_1, EXPAND_2, CONTRACT_3, EXPAND_4], {"0001", "0002"}, allow_contract=True
    )

    assert to_apply == [CONTRACT_3, EXPAND_4]
    assert blocked is None


def test_ignores_applied_versions_this_image_does_not_know():
    to_apply, blocked = plan([EXPAND_1], {"0001", "0002", "0003"}, allow_contract=False)

    assert to_apply == []
    assert blocked is None


def test_discovers_repo_migrations_in_order():
    versions = [m.version for m in discover()]

    assert versions == sorted(versions)
    assert len(versions) == len(set(versions))


def test_rejects_file_without_phase(tmp_path):
    (tmp_path / "0001_add_column.sql").write_text("SELECT 1;")

    with pytest.raises(ValueError, match="expand 또는 contract"):
        discover(tmp_path)

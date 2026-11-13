import pytest

from app.flags import FlagService, UnknownFlagError, bucket

REGISTRY = {
    "new_checkout": {"default": False},
    "legacy_banner": {"default": True},
}


def service(states, **kwargs) -> FlagService:
    return FlagService(registry=REGISTRY, fetch_states=lambda: states, ttl_seconds=0, **kwargs)


def test_unregistered_flag_is_an_error():
    with pytest.raises(UnknownFlagError):
        service({}).is_enabled("typo_flag", "user-1")


def test_uses_registry_default_when_no_state_is_stored():
    flags = service({})

    assert flags.is_enabled("new_checkout", "user-1") is False
    assert flags.is_enabled("legacy_banner", "user-1") is True


def test_off_wins_over_rollout_percent():
    assert service({"new_checkout": (False, 100)}).is_enabled("new_checkout", "user-1") is False


def test_full_rollout_enables_everyone():
    flags = service({"new_checkout": (True, 100)})

    assert all(flags.is_enabled("new_checkout", f"user-{i}") for i in range(200))


def test_partial_rollout_is_stable_per_user_and_roughly_sized():
    flags = service({"new_checkout": (True, 10)})
    users = [f"user-{i}" for i in range(2000)]

    first = [flags.is_enabled("new_checkout", user) for user in users]
    second = [flags.is_enabled("new_checkout", user) for user in users]

    assert first == second
    assert 0.07 < sum(first) / len(users) < 0.13


def test_raising_percent_keeps_already_enabled_users():
    users = [f"user-{i}" for i in range(500)]

    def enabled_at(percent: int) -> set[str]:
        flags = service({"new_checkout": (True, percent)})
        return {user for user in users if flags.is_enabled("new_checkout", user)}

    assert enabled_at(10) <= enabled_at(50)


def test_bucket_differs_between_flags():
    users = [f"user-{i}" for i in range(200)]

    assert [bucket("a", u) for u in users] != [bucket("b", u) for u in users]


def test_caches_states_within_ttl():
    calls = []
    now = [0.0]

    def fetch():
        calls.append(1)
        return {"new_checkout": (True, 100)}

    flags = FlagService(
        registry=REGISTRY, fetch_states=fetch, ttl_seconds=5, clock=lambda: now[0]
    )
    flags.is_enabled("new_checkout", "user-1")
    now[0] = 4.9
    flags.is_enabled("new_checkout", "user-1")
    assert len(calls) == 1

    now[0] = 5.1
    flags.is_enabled("new_checkout", "user-1")
    assert len(calls) == 2


def test_keeps_last_known_state_when_store_fails():
    healthy = [True]

    def fetch():
        if not healthy[0]:
            raise ConnectionError("db down")
        return {"new_checkout": (True, 100)}

    flags = FlagService(registry=REGISTRY, fetch_states=fetch, ttl_seconds=0)
    assert flags.is_enabled("new_checkout", "user-1") is True

    healthy[0] = False
    assert flags.is_enabled("new_checkout", "user-1") is True


def test_falls_back_to_default_when_store_never_answered():
    def fetch():
        raise ConnectionError("db down")

    flags = FlagService(registry=REGISTRY, fetch_states=fetch, ttl_seconds=0)

    assert flags.is_enabled("new_checkout", "user-1") is False

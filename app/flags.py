"""feature flag.

정의는 리포의 flags.json에 있다 (설명, 담당자, 만료일, 기본값).
상태는 각 환경의 DB에 있다 (켜짐/꺼짐, 비율).
그래서 배포 없이 켜고 끌 수 있고, staging에서만 먼저 켤 수 있다.
"""

import hashlib
import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "flags.json"

log = logging.getLogger("orders.flags")

FlagStates = dict[str, tuple[bool, int]]


class UnknownFlagError(KeyError):
    pass


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def bucket(flag_name: str, user_id: str) -> int:
    """사용자를 0~99 중 한 칸에 넣는다.

    같은 사용자는 항상 같은 칸에 들어간다.
    그래서 10%로 켜면 새로고침할 때마다 화면이 바뀌지 않는다.
    플래그 이름을 섞어서 플래그마다 다른 10%가 뽑힌다.
    """
    digest = hashlib.sha256(f"{flag_name}:{user_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % 100


class FlagService:
    def __init__(
        self,
        *,
        registry: dict[str, dict],
        fetch_states: Callable[[], FlagStates],
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._registry = registry
        self._fetch_states = fetch_states
        self._ttl = ttl_seconds
        self._clock = clock
        self._cache: FlagStates = {}
        self._fetched_at: float | None = None

    def is_enabled(self, name: str, user_id: str) -> bool:
        # flags.json에 없는 플래그는 쓸 수 없다.
        spec = self._registry.get(name)
        if spec is None:
            raise UnknownFlagError(name)

        state = self._states().get(name)
        # DB에 상태가 없으면 flags.json의 기본값을 쓴다.
        if state is None:
            return bool(spec["default"])

        enabled, rollout_percent = state
        if not enabled:
            return False
        return bucket(name, user_id) < rollout_percent

    def _states(self) -> FlagStates:
        now = self._clock()
        if self._fetched_at is not None and now - self._fetched_at < self._ttl:
            return self._cache
        try:
            self._cache = self._fetch_states()
        except Exception:
            # 플래그 저장소가 죽어도 주문은 받아야 한다.
            # 마지막으로 읽은 값(없으면 기본값)으로 계속 동작한다.
            log.warning("플래그 상태를 읽지 못해 마지막 값을 쓴다", exc_info=True)
        self._fetched_at = now
        return self._cache

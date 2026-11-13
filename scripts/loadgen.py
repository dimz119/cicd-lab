#!/usr/bin/env python3
"""주문 트래픽을 만들고, 응답을 색(blue / green)별로 집계한다.

    python3 scripts/loadgen.py --url http://localhost:8080 --requests 400
    python3 scripts/loadgen.py --url http://localhost:8080 --watch
    python3 scripts/loadgen.py --url http://localhost:8080 --watch --csv canary.csv

표준 라이브러리만 쓴다.
실제 서비스라면 이 숫자는 모니터링 시스템에서 가져온다.
"""

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

BOOKS = ["파이프라인 설계 입문", "무중단 배포", "데이터베이스 마이그레이션", "feature flag 실전"]


@dataclass
class Stats:
    version: str = "?"
    latencies_ms: list[float] = field(default_factory=list)
    errors: int = 0

    @property
    def count(self) -> int:
        return len(self.latencies_ms)

    @property
    def error_rate(self) -> float:
        return self.errors / self.count if self.count else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        return ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]


def send(base_url: str, rng: random.Random, order_ids: list[int]) -> tuple[str, str, bool, float]:
    """요청 하나를 보내고 (색, 버전, 성공 여부, 지연 ms)를 돌려준다."""
    # 주문 생성과 주문 완료 화면 조회를 반반 섞는다.
    if not order_ids or rng.random() < 0.5:
        body = {
            "user_id": f"user-{rng.randint(1, 500)}",
            "book_title": rng.choice(BOOKS),
            "quantity": rng.randint(1, 3),
            # 빠른 배송이 30%.
            "shipping_method": "express" if rng.random() < 0.3 else "standard",
        }
        request = urllib.request.Request(
            f"{base_url}/orders",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    else:
        request = urllib.request.Request(f"{base_url}/orders/{rng.choice(order_ids)}/complete")

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            headers, status, payload = response.headers, response.status, response.read()
    except urllib.error.HTTPError as error:
        headers, status, payload = error.headers, error.code, b""
    except OSError:
        # 연결 자체가 실패하면 어느 색인지 알 수 없다.
        return "router", "?", False, (time.perf_counter() - started) * 1000
    elapsed_ms = (time.perf_counter() - started) * 1000

    if request.get_method() == "POST" and status == 201:
        order_ids.append(json.loads(payload)["id"])
        del order_ids[:-200]

    color = headers.get("X-App-Color", "router")
    version = headers.get("X-App-Version", "?")
    # 5xx만 서버 오류로 센다.
    return color, version, status < 500, elapsed_ms


def record(stats: dict[str, Stats], sample: tuple[str, str, bool, float]) -> None:
    color, version, succeeded, elapsed_ms = sample
    entry = stats.setdefault(color, Stats())
    entry.version = version
    entry.latencies_ms.append(elapsed_ms)
    if not succeeded:
        entry.errors += 1


def collect(base_url: str, requests: int, rng: random.Random | None = None) -> dict[str, Stats]:
    rng = rng or random.Random()
    stats: dict[str, Stats] = {}
    order_ids: list[int] = []
    for _ in range(requests):
        record(stats, send(base_url, rng, order_ids))
    return stats


def format_table(stats: dict[str, Stats]) -> str:
    total = sum(entry.count for entry in stats.values()) or 1
    lines = [f"  {'색':<7} {'버전':<22} {'요청':>5} {'비율':>6} {'에러율':>7} {'p95':>8}"]
    for color in sorted(stats):
        entry = stats[color]
        lines.append(
            f"  {color:<8} {entry.version:<24} {entry.count:>6} "
            f"{entry.count / total:>7.1%} {entry.error_rate:>9.1%} {entry.p95_ms:>7.0f}ms"
        )
    return "\n".join(lines)


def watch(base_url: str, rps: float, csv_path: str | None = None) -> None:
    rng = random.Random()
    order_ids: list[int] = []
    print(f"{base_url} 로 초당 약 {rps:.0f}건을 보낸다. Ctrl-C로 멈춘다.")
    while True:
        # 5초 단위로 끊어서 본다.
        # 누적 평균이 아니라 '지금'의 에러율이 보여야 변화가 눈에 띈다.
        stats: dict[str, Stats] = {}
        window_end = time.monotonic() + 5
        while time.monotonic() < window_end:
            record(stats, send(base_url, rng, order_ids))
            time.sleep(1 / rps)
        print(f"\n{time.strftime('%H:%M:%S')}  최근 5초")
        print(format_table(stats), flush=True)
        if csv_path:
            # 그래프를 그릴 수 있게 5초 구간마다 한 줄씩 남긴다.
            with open(csv_path, "a", encoding="utf-8") as file:
                if file.tell() == 0:
                    file.write("time,color,version,requests,error_rate,p95_ms\n")
                for color, entry in sorted(stats.items()):
                    file.write(
                        f"{time.strftime('%H:%M:%S')},{color},{entry.version},"
                        f"{entry.count},{entry.error_rate:.4f},{entry.p95_ms:.1f}\n"
                    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=400)
    parser.add_argument("--watch", action="store_true", help="멈출 때까지 5초마다 집계를 출력")
    parser.add_argument("--rps", type=float, default=20)
    parser.add_argument("--csv", help="--watch의 구간별 집계를 이 파일에 CSV로 덧붙인다")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    if args.watch:
        try:
            watch(base_url, args.rps, args.csv)
        except KeyboardInterrupt:
            print()
        return 0

    print(format_table(collect(base_url, args.requests)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

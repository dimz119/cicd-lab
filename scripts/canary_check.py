#!/usr/bin/env python3
"""canary를 계속 진행할지, 중단할지 판단한다.

    python3 scripts/canary_check.py --url http://localhost:8080 \\
        --canary-color green --baseline-color blue

판단 기준은 "같은 시간에 같은 트래픽을 받은 기존 버전(baseline)과 비교"다.
절대값만 보면 원래 느린 시간대인지, 새 버전이 느린 것인지 구분할 수 없다.

종료 코드: 0이면 진행, 1이면 중단.
"""

import argparse
import sys

from loadgen import Stats, collect, format_table


def judge(
    canary: Stats,
    baseline: Stats | None,
    *,
    min_samples: int,
    error_margin: float,
    latency_factor: float,
    latency_floor_ms: float,
) -> list[str]:
    """기준을 넘은 항목을 돌려준다. 비어 있으면 통과다."""
    # 표본이 너무 적으면 "문제없음"이 아니라 "모름"이다.
    # 모르면 진행하지 않는다.
    if canary.count < min_samples:
        return [f"canary 표본 부족: {canary.count}건 (최소 {min_samples}건)"]

    problems = []
    baseline_error_rate = baseline.error_rate if baseline else 0.0
    error_limit = baseline_error_rate + error_margin
    if canary.error_rate > error_limit:
        problems.append(f"에러율 {canary.error_rate:.1%} > 허용 {error_limit:.1%}")

    if baseline and baseline.count:
        # 아주 빠른 응답끼리는 배수 비교가 의미 없어 하한을 둔다.
        latency_limit = max(baseline.p95_ms * latency_factor, latency_floor_ms)
        if canary.p95_ms > latency_limit:
            problems.append(f"p95 {canary.p95_ms:.0f}ms > 허용 {latency_limit:.0f}ms")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True)
    parser.add_argument("--canary-color", required=True)
    # 100% 단계에서는 비교할 기존 버전이 없어 생략한다.
    parser.add_argument("--baseline-color")
    parser.add_argument("--requests", type=int, default=400)
    parser.add_argument("--min-samples", type=int, default=20)
    # 에러율은 baseline 에러율 + error-margin 까지 허용한다.
    parser.add_argument("--error-margin", type=float, default=0.02)
    # p95는 baseline p95의 latency-factor 배까지 허용한다.
    parser.add_argument("--latency-factor", type=float, default=2.0)
    parser.add_argument("--latency-floor-ms", type=float, default=200.0)
    args = parser.parse_args()

    stats = collect(args.url.rstrip("/"), args.requests)
    print(format_table(stats))

    canary = stats.get(args.canary_color, Stats())
    baseline = stats.get(args.baseline_color) if args.baseline_color else None
    problems = judge(
        canary,
        baseline,
        min_samples=args.min_samples,
        error_margin=args.error_margin,
        latency_factor=args.latency_factor,
        latency_floor_ms=args.latency_floor_ms,
    )
    # 라우터가 직접 낸 오류(502 등)는 어느 색 탓인지 알 수 없다.
    # 이것도 진행을 멈출 이유다.
    router = stats.get("router")
    if router and router.count:
        problems.append(f"라우터 오류 {router.count}건")

    if problems:
        print("  판정: 중단 — " + "; ".join(problems))
        return 1
    print("  판정: 진행")
    return 0


if __name__ == "__main__":
    sys.exit(main())

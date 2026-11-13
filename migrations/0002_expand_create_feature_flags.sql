-- feature flag의 런타임 상태.
-- 플래그의 정의(설명, 담당자, 만료일)는 리포의 flags.json에 있다.
-- 켜짐/꺼짐과 비율은 환경마다 다르므로 각 환경의 DB에 둔다.
CREATE TABLE feature_flags (
    name            TEXT        PRIMARY KEY,
    enabled         BOOLEAN     NOT NULL DEFAULT false,
    rollout_percent INTEGER     NOT NULL DEFAULT 100 CHECK (rollout_percent BETWEEN 0 AND 100),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

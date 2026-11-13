-- 주문 테이블.
CREATE TABLE orders (
    id              BIGSERIAL PRIMARY KEY,
    user_id         TEXT        NOT NULL,
    book_title      TEXT        NOT NULL,
    quantity        INTEGER     NOT NULL CHECK (quantity > 0),
    shipping_method TEXT        NOT NULL DEFAULT 'standard',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

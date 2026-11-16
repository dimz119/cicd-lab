-- 컬럼 이름을 book_title에서 title로 바꾼다.
SET LOCAL lock_timeout = '5s';

ALTER TABLE orders RENAME COLUMN book_title TO title;

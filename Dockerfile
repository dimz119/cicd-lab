FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# 의존성 레이어를 먼저 만들어 코드만 바뀐 빌드는 캐시를 탄다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 마이그레이션과 플래그 목록도 아티팩트의 일부다.
COPY app ./app
COPY migrations ./migrations
COPY flags.json .

# 버전은 빌드할 때 한 번 박힌다.
# 환경마다 달라지는 값(DATABASE_URL 등)은 이미지에 넣지 않는다.
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

RUN useradd --system --no-create-home app
USER app

EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "app.wsgi:app"]

import json
import logging
import time

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

from app import db, store
from app.config import Settings, load_settings
from app.flags import FlagService, load_registry

SHIPPING_METHODS = ("standard", "express")

log = logging.getLogger("orders")


class ValidationError(Exception):
    pass


def parse_order(data: dict) -> dict:
    user_id = str(data.get("user_id", "")).strip()
    book_title = str(data.get("book_title", "")).strip()
    shipping_method = str(data.get("shipping_method", "standard")).strip()
    try:
        quantity = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        raise ValidationError("quantity는 정수여야 한다") from None

    if not user_id:
        raise ValidationError("user_id가 없다")
    if not book_title:
        raise ValidationError("book_title이 없다")
    if not 1 <= quantity <= 99:
        raise ValidationError("quantity는 1~99")
    if shipping_method not in SHIPPING_METHODS:
        raise ValidationError(f"shipping_method는 {SHIPPING_METHODS} 중 하나")
    return {
        "user_id": user_id,
        "book_title": book_title,
        "quantity": quantity,
        "shipping_method": shipping_method,
    }


def serialize_order(order: dict) -> dict:
    return {
        "id": order["id"],
        "user_id": order["user_id"],
        "book_title": order["book_title"],
        "quantity": order["quantity"],
        "shipping_method": order["shipping_method"],
        "created_at": order["created_at"].isoformat(),
    }


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or load_settings()
    logging.basicConfig(level=settings.log_level, format="%(message)s")

    app = Flask(__name__)

    def fetch_flag_states():
        with db.connect(settings.database_url) as conn:
            return store.fetch_flag_states(conn)

    flags = FlagService(
        registry=load_registry(),
        fetch_states=fetch_flag_states,
        ttl_seconds=settings.flag_cache_ttl_seconds,
    )
    app.extensions["flags"] = flags

    @app.before_request
    def start_timer():
        g.started = time.perf_counter()

    @app.after_request
    def tag_and_log(response):
        # 어느 버전, 어느 색이 응답했는지 헤더로 알려 준다.
        # canary 지표를 버전별로 나눠 볼 때 이 헤더를 쓴다.
        response.headers["X-App-Version"] = settings.app_version
        response.headers["X-App-Color"] = settings.app_color
        record = {
            "env": settings.app_env,
            "version": settings.app_version,
            "color": settings.app_color,
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "ms": round((time.perf_counter() - g.started) * 1000, 1),
        }
        # health check 로그는 DEBUG로 낮춰 운영 로그를 덮지 않게 한다.
        level = logging.DEBUG if request.path in ("/healthz", "/readyz") else logging.INFO
        log.log(level, json.dumps(record, ensure_ascii=False))
        return response

    @app.context_processor
    def inject_settings():
        return {"settings": settings}

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return jsonify(error=str(error)), 400

    @app.get("/healthz")
    def healthz():
        # 프로세스가 살아 있는지만 본다.
        return jsonify(status="ok")

    @app.get("/readyz")
    def readyz():
        # 트래픽을 받을 준비가 됐는지 본다.
        # DB에 붙지 못하면 준비되지 않은 것이다.
        try:
            with db.connect(settings.database_url) as conn:
                conn.execute("SELECT 1")
        except Exception as error:
            return jsonify(status="unavailable", reason=type(error).__name__), 503
        return jsonify(status="ready")

    @app.get("/info")
    def info():
        # 비밀 값(DATABASE_URL)은 내보내지 않는다.
        return jsonify(
            env=settings.app_env,
            version=settings.app_version,
            color=settings.app_color,
            log_level=settings.log_level,
            payment_api_url=settings.payment_api_url,
            flag_cache_ttl_seconds=settings.flag_cache_ttl_seconds,
        )

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/orders")
    def create_order():
        payload = request.get_json(silent=True)
        data = parse_order(payload if payload is not None else request.form)
        log.debug(json.dumps({"event": "create_order", **data}, ensure_ascii=False))

        with db.connect(settings.database_url) as conn:
            order = store.create_order(conn, **data)

        if payload is not None:
            return jsonify(serialize_order(order)), 201
        # 화면에서 주문하면 주문 완료 화면으로 보낸다.
        return redirect(url_for("order_complete", order_id=order["id"]), code=303)

    @app.get("/orders/<int:order_id>")
    def get_order(order_id: int):
        with db.connect(settings.database_url) as conn:
            order = store.get_order(conn, order_id)
        if order is None:
            return jsonify(error="주문을 찾을 수 없다"), 404
        return jsonify(serialize_order(order))

    @app.get("/orders/<int:order_id>/complete")
    def order_complete(order_id: int):
        with db.connect(settings.database_url) as conn:
            order = store.get_order(conn, order_id)
        if order is None:
            return jsonify(error="주문을 찾을 수 없다"), 404
        return render_template("complete.html", order=order)

    return app

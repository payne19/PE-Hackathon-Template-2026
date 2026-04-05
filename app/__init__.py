import logging
import time

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request

from app.database import init_db
from app.routes import register_routes

logger = logging.getLogger(__name__)


def create_app(test_config=None):
    load_dotenv()

    app = Flask(__name__)

    if test_config:
        app.config.update(test_config)

    _configure_logging(app)
    _configure_metrics(app)

    from app.cache import init_cache
    init_cache(app)

    init_db(app)

    from app.models import User, URL, Event  # noqa: F401 - registers models with Peewee
    from app.database import db as _db
    with app.app_context():
        _db.connect(reuse_if_open=True)
        _db.create_tables([User, URL, Event], safe=True)
        if not _db.is_closed():
            _db.close()

    register_routes(app)

    @app.before_request
    def _start_timer():
        g.start_time = time.monotonic()

    @app.after_request
    def _log_request(response):
        duration_ms = round((time.monotonic() - g.start_time) * 1000, 2)
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "latency_ms": duration_ms,
                "remote_addr": request.remote_addr,
            },
        )
        return response

    @app.route("/health")
    def health():
        return jsonify(status="ok")

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error="Bad request", detail=str(e)), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Resource not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(409)
    def conflict(e):
        return jsonify(error="Conflict", detail=str(e)), 409

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.exception("Unhandled exception")
        return jsonify(error="Internal server error"), 500

    return app


def _configure_metrics(app):
    try:
        from prometheus_flask_exporter import PrometheusMetrics

        metrics = PrometheusMetrics(app)
        metrics.info("app_info", "URL Shortener", version="1.0.0")
    except ImportError:
        pass


def _configure_logging(app):
    try:
        from pythonjsonlogger import jsonlogger

        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
        handler.setFormatter(formatter)
        root = logging.getLogger()
        root.handlers = [handler]
        root.setLevel(logging.WARNING)
    except ImportError:
        logging.basicConfig(level=logging.INFO)

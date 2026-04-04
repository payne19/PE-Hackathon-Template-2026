"""Unit tests — pure Python, no database or HTTP required."""
import sys
import string
from unittest.mock import MagicMock, patch

import pytest


class TestGenerateShortCode:
    def _fn(self):
        from app.routes.urls import _generate_short_code
        return _generate_short_code

    def test_default_length(self):
        code = self._fn()()
        assert len(code) == 6

    def test_custom_length(self):
        code = self._fn()(length=10)
        assert len(code) == 10

    def test_characters_are_alphanumeric(self):
        allowed = set(string.ascii_letters + string.digits)
        for _ in range(20):
            code = self._fn()()
            assert set(code).issubset(allowed)

    def test_codes_are_random(self):
        codes = {self._fn()() for _ in range(50)}
        assert len(codes) > 1


class TestUrlToDict:
    def test_returns_dict_without_user_key(self, app):
        from app.models.url import URL
        from app.models.user import User
        from app.routes.urls import _url_to_dict

        with app.app_context():
            user = User.create(username="testuser", email="t@t.com")
            url = URL.create(
                short_code="abc123",
                original_url="https://example.com",
                user=user,
                is_active=True,
            )
            result = _url_to_dict(url)
            assert "user" not in result
            assert result["short_code"] == "abc123"
            assert result["original_url"] == "https://example.com"


class TestUrlValidation:
    """Test URL validation logic via the route."""

    def test_valid_http_url(self, client):
        rv = client.post("/shorten", json={"original_url": "http://example.com"})
        assert rv.status_code == 201

    def test_valid_https_url(self, client):
        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        assert rv.status_code == 201

    def test_invalid_url_no_scheme(self, client):
        rv = client.post("/shorten", json={"original_url": "example.com"})
        assert rv.status_code == 422
        data = rv.get_json()
        assert "error" in data

    def test_empty_url(self, client):
        rv = client.post("/shorten", json={"original_url": ""})
        assert rv.status_code == 422

    def test_missing_url_field(self, client):
        rv = client.post("/shorten", json={"title": "no url"})
        assert rv.status_code == 422

    def test_no_json_body(self, client):
        rv = client.post("/shorten", data="not json", content_type="text/plain")
        assert rv.status_code == 400


class TestErrorHandlers:
    def test_404_returns_json(self, client):
        rv = client.get("/nonexistent-route-xyz")
        assert rv.status_code == 404
        data = rv.get_json()
        assert "error" in data

    def test_405_returns_json(self, client):
        rv = client.delete("/health")
        assert rv.status_code == 405
        data = rv.get_json()
        assert "error" in data

    def test_404_handler_via_multi_segment_path(self, client):
        rv = client.get("/no/such/path")
        assert rv.status_code == 404
        assert "error" in rv.get_json()

    def test_400_handler_via_http_exception(self, app):
        from werkzeug.exceptions import BadRequest
        with app.test_request_context("/"):
            rv = app.handle_http_exception(BadRequest())
        assert rv.status_code == 400
        assert "error" in rv.get_json()

    def test_409_handler_via_http_exception(self, app):
        from werkzeug.exceptions import Conflict
        with app.test_request_context("/"):
            rv = app.handle_http_exception(Conflict())
        assert rv.status_code == 409
        assert "error" in rv.get_json()

    def test_500_handler_via_http_exception(self, app):
        from werkzeug.exceptions import InternalServerError
        with app.test_request_context("/"):
            rv = app.handle_http_exception(InternalServerError())
        assert rv.status_code == 500
        assert "error" in rv.get_json()


class TestCacheInit:
    def test_redis_config_set_when_no_cache_type(self):
        from flask import Flask
        from app.cache import cache, init_cache
        test_app = Flask(__name__)
        with patch.object(cache, "init_app", return_value=None):
            init_cache(test_app)
        assert test_app.config["CACHE_TYPE"] == "RedisCache"

    def test_cache_falls_back_to_simplecache_on_error(self):
        from flask import Flask
        from app.cache import cache, init_cache
        test_app = Flask(__name__)
        test_app.config["CACHE_TYPE"] = "RedisCache"
        call_count = {"n": 0}

        def _fail_first(app):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise Exception("Redis unavailable")

        with patch.object(cache, "init_app", side_effect=_fail_first):
            init_cache(test_app)
        assert test_app.config["CACHE_TYPE"] == "SimpleCache"


class TestConfigureImportErrors:
    def test_metrics_import_error_is_silenced(self, app):
        from app import _configure_metrics
        with patch.dict(sys.modules, {"prometheus_flask_exporter": None}):
            _configure_metrics(app)

    def test_logging_falls_back_to_basicconfig(self, app):
        from app import _configure_logging
        with patch.dict(
            sys.modules,
            {"pythonjsonlogger": None, "pythonjsonlogger.jsonlogger": None},
        ):
            with patch("logging.basicConfig") as mock_basic:
                _configure_logging(app)
            mock_basic.assert_called_once()


class TestGetCachedUrl:
    def test_returns_dict_when_url_exists(self, app):
        from app.models.url import URL
        from app.routes.urls import _get_cached_url
        with app.app_context():
            URL.create(short_code="gctest1", original_url="https://example.com", is_active=True)
            result = _get_cached_url("gctest1")
        assert result is not None
        assert result["original_url"] == "https://example.com"
        assert result["is_active"] is True

    def test_returns_none_when_url_missing(self, app):
        from app.routes.urls import _get_cached_url
        with app.app_context():
            result = _get_cached_url("zzz_no_exist_999")
        assert result is None


class TestShortenExhaustedCodes:
    def test_returns_500_when_all_candidates_taken(self, client):
        from app.routes import urls as urls_module
        mock_qs = MagicMock()
        mock_qs.where.return_value.exists.return_value = True
        with patch.object(urls_module.URL, "select", return_value=mock_qs):
            rv = client.post("/shorten", json={"original_url": "https://example.com"})
        assert rv.status_code == 500
        assert "error" in rv.get_json()

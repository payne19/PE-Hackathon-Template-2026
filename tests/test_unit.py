"""Unit tests — pure Python, no database or HTTP required."""
import string

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

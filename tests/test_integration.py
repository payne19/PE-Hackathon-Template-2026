"""Integration tests — hit the API and check DB state."""
import pytest


class TestHealth:
    def test_health_returns_200(self, client):
        rv = client.get("/health")
        assert rv.status_code == 200
        assert rv.get_json() == {"status": "ok"}

    def test_health_content_type(self, client):
        rv = client.get("/health")
        assert "application/json" in rv.content_type


class TestMetrics:
    def test_metrics_endpoint_exists(self, client):
        rv = client.get("/metrics")
        assert rv.status_code == 200

    def test_metrics_contains_flask_data(self, client):
        rv = client.get("/metrics")
        assert b"flask" in rv.data.lower() or b"http" in rv.data.lower()


class TestShorten:
    def test_shorten_valid_url_returns_201(self, client):
        rv = client.post("/shorten", json={"original_url": "https://google.com"})
        assert rv.status_code == 201
        data = rv.get_json()
        assert "short_code" in data
        assert data["original_url"] == "https://google.com"
        assert data["is_active"] is True

    def test_shorten_creates_db_record(self, client, app):
        from app.models.url import URL

        rv = client.post("/shorten", json={"original_url": "https://github.com"})
        assert rv.status_code == 201
        code = rv.get_json()["short_code"]

        with app.app_context():
            url = URL.get(URL.short_code == code)
            assert url.original_url == "https://github.com"

    def test_shorten_with_title(self, client):
        rv = client.post(
            "/shorten",
            json={"original_url": "https://example.com", "title": "My Link"},
        )
        assert rv.status_code == 201
        assert rv.get_json()["title"] == "My Link"

    def test_shorten_with_custom_code(self, client):
        rv = client.post(
            "/shorten",
            json={"original_url": "https://example.com", "short_code": "mycode"},
        )
        assert rv.status_code == 201
        assert rv.get_json()["short_code"] == "mycode"

    def test_shorten_duplicate_custom_code_returns_409(self, client):
        client.post(
            "/shorten",
            json={"original_url": "https://example.com", "short_code": "dup"},
        )
        rv = client.post(
            "/shorten",
            json={"original_url": "https://other.com", "short_code": "dup"},
        )
        assert rv.status_code == 409
        assert "error" in rv.get_json()

    def test_shorten_invalid_url_no_scheme_returns_422(self, client):
        rv = client.post("/shorten", json={"original_url": "notaurl.com"})
        assert rv.status_code == 422

    def test_shorten_empty_body_returns_400(self, client):
        rv = client.post("/shorten", content_type="application/json", data="{}")
        assert rv.status_code == 422

    def test_shorten_non_json_returns_400(self, client):
        rv = client.post("/shorten", data="garbage", content_type="text/plain")
        assert rv.status_code == 400

    def test_shorten_creates_event_record(self, client, app):
        from app.models.event import Event

        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        assert rv.status_code == 201
        url_id = rv.get_json()["id"]

        with app.app_context():
            events = list(Event.select().where(Event.url_id == url_id))
            assert any(e.event_type == "created" for e in events)


class TestRedirect:
    def test_redirect_valid_code(self, client):
        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        code = rv.get_json()["short_code"]
        rv2 = client.get(f"/{code}")
        assert rv2.status_code == 302
        assert rv2.headers["Location"] == "https://example.com"

    def test_redirect_unknown_code_returns_404(self, client):
        rv = client.get("/zzzzzzzzzzz")
        assert rv.status_code == 404
        assert "error" in rv.get_json()

    def test_redirect_inactive_url_returns_410(self, client, app):
        rv = client.post(
            "/shorten",
            json={"original_url": "https://example.com", "short_code": "gone1"},
        )
        url_id = rv.get_json()["id"]
        client.delete(f"/urls/{url_id}")

        rv2 = client.get("/gone1")
        assert rv2.status_code == 410
        assert "error" in rv2.get_json()

    def test_redirect_records_click_event(self, client, app):
        from app.models.event import Event

        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        code = rv.get_json()["short_code"]
        url_id = rv.get_json()["id"]

        client.get(f"/{code}")

        with app.app_context():
            clicks = Event.select().where(
                (Event.url_id == url_id) & (Event.event_type == "click")
            ).count()
            assert clicks == 1


class TestListUrls:
    def test_list_urls_returns_200(self, client):
        rv = client.get("/urls")
        assert rv.status_code == 200
        data = rv.get_json()
        assert isinstance(data, list)

    def test_list_urls_includes_all(self, client, app):
        client.post("/shorten", json={"original_url": "https://active.com", "short_code": "act1"})
        rv2 = client.post("/shorten", json={"original_url": "https://inactive.com", "short_code": "ina1"})
        url_id = rv2.get_json()["id"]
        client.delete(f"/urls/{url_id}")

        rv = client.get("/urls")
        codes = [u["short_code"] for u in rv.get_json()]
        assert "act1" in codes
        assert "ina1" in codes

    def test_list_urls_pagination(self, client):
        rv = client.get("/urls?page=1&per_page=5")
        assert rv.status_code == 200
        data = rv.get_json()
        assert isinstance(data, list)


class TestGetUrl:
    def test_get_existing_url(self, client):
        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        url_id = rv.get_json()["id"]
        rv2 = client.get(f"/urls/{url_id}")
        assert rv2.status_code == 200
        assert rv2.get_json()["id"] == url_id

    def test_get_nonexistent_url_returns_404(self, client):
        rv = client.get("/urls/999999")
        assert rv.status_code == 404
        assert "error" in rv.get_json()


class TestDeactivateUrl:
    def test_deactivate_url(self, client, app):
        from app.models.url import URL

        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        url_id = rv.get_json()["id"]
        code = rv.get_json()["short_code"]

        rv2 = client.delete(f"/urls/{url_id}")
        assert rv2.status_code == 200

        with app.app_context():
            url = URL.get_by_id(url_id)
            assert url.is_active is False

    def test_deactivate_nonexistent_url_returns_404(self, client):
        rv = client.delete("/urls/999999")
        assert rv.status_code == 404
        assert "error" in rv.get_json()


class TestStats:
    def test_stats_returns_data(self, client):
        rv = client.post(
            "/shorten",
            json={"original_url": "https://example.com", "short_code": "stat1"},
        )
        rv2 = client.get("/stats/stat1")
        assert rv2.status_code == 200
        data = rv2.get_json()
        assert data["short_code"] == "stat1"
        assert "click_count" in data

    def test_stats_click_count_increments(self, client):
        client.post(
            "/shorten",
            json={"original_url": "https://example.com", "short_code": "clk1"},
        )
        client.get("/clk1")
        client.get("/clk1")

        rv = client.get("/stats/clk1")
        assert rv.get_json()["click_count"] == 2

    def test_stats_unknown_code_returns_404(self, client):
        rv = client.get("/stats/zzznone")
        assert rv.status_code == 404
        assert "error" in rv.get_json()

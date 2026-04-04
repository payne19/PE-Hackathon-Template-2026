"""Gold tier tests — graceful failure, events, URL CRUD, and chaos coverage."""
import pytest


class TestEventsEndpoint:
    def test_events_returns_200(self, client):
        rv = client.get("/events")
        assert rv.status_code == 200
        assert isinstance(rv.get_json(), list)

    def test_events_filter_by_url_id(self, client):
        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        url_id = rv.get_json()["id"]

        rv2 = client.get(f"/events?url_id={url_id}")
        assert rv2.status_code == 200
        data = rv2.get_json()
        assert isinstance(data, list)
        assert all(e["url_id"] == url_id for e in data)

    def test_events_filter_by_user_id(self, client):
        user = client.post("/users", json={"username": "evtuser", "email": "evtuser@example.com"})
        user_id = user.get_json()["id"]

        rv = client.get(f"/events?user_id={user_id}")
        assert rv.status_code == 200
        assert isinstance(rv.get_json(), list)

    def test_events_ordered_by_timestamp_desc(self, client):
        client.post("/shorten", json={"original_url": "https://first.com"})
        client.post("/shorten", json={"original_url": "https://second.com"})
        rv = client.get("/events")
        data = rv.get_json()
        if len(data) >= 2:
            assert data[0]["timestamp"] >= data[1]["timestamp"]

    def test_event_has_required_fields(self, client):
        client.post("/shorten", json={"original_url": "https://example.com"})
        rv = client.get("/events")
        data = rv.get_json()
        assert len(data) > 0
        event = data[0]
        assert "id" in event
        assert "url_id" in event
        assert "event_type" in event
        assert "timestamp" in event


class TestUrlCrudEndpoints:
    def test_post_urls_creates_url(self, client):
        rv = client.post("/urls", json={"original_url": "https://example.com"})
        assert rv.status_code == 201
        data = rv.get_json()
        assert "short_code" in data
        assert data["original_url"] == "https://example.com"

    def test_post_urls_with_user_id(self, client):
        user = client.post("/users", json={"username": "urlowner", "email": "urlowner@example.com"})
        user_id = user.get_json()["id"]
        rv = client.post("/urls", json={"original_url": "https://example.com", "user_id": user_id})
        assert rv.status_code == 201

    def test_post_urls_invalid_user_returns_404(self, client):
        rv = client.post("/urls", json={"original_url": "https://example.com", "user_id": 999999})
        assert rv.status_code == 404
        assert "error" in rv.get_json()

    def test_post_urls_missing_url_returns_422(self, client):
        rv = client.post("/urls", json={"title": "no url"})
        assert rv.status_code == 422
        assert "error" in rv.get_json()

    def test_post_urls_no_json_returns_400(self, client):
        rv = client.post("/urls", data="garbage", content_type="text/plain")
        assert rv.status_code == 400
        assert "error" in rv.get_json()

    def test_post_urls_duplicate_short_code_returns_409(self, client):
        client.post("/urls", json={"original_url": "https://example.com", "short_code": "dupurl"})
        rv = client.post("/urls", json={"original_url": "https://other.com", "short_code": "dupurl"})
        assert rv.status_code == 409
        assert "error" in rv.get_json()

    def test_put_url_updates_title(self, client):
        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        url_id = rv.get_json()["id"]
        rv2 = client.put(f"/urls/{url_id}", json={"title": "Updated Title"})
        assert rv2.status_code == 200
        assert rv2.get_json()["title"] == "Updated Title"

    def test_put_url_deactivates(self, client):
        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        url_id = rv.get_json()["id"]
        rv2 = client.put(f"/urls/{url_id}", json={"is_active": False})
        assert rv2.status_code == 200
        assert rv2.get_json()["is_active"] is False

    def test_put_url_updates_original_url(self, client):
        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        url_id = rv.get_json()["id"]
        rv2 = client.put(f"/urls/{url_id}", json={"original_url": "https://updated.com"})
        assert rv2.status_code == 200
        assert rv2.get_json()["original_url"] == "https://updated.com"

    def test_put_url_nonexistent_returns_404(self, client):
        rv = client.put("/urls/999999", json={"title": "x"})
        assert rv.status_code == 404
        assert "error" in rv.get_json()

    def test_put_url_no_json_returns_400(self, client):
        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        url_id = rv.get_json()["id"]
        rv2 = client.put(f"/urls/{url_id}", data="bad", content_type="text/plain")
        assert rv2.status_code == 400
        assert "error" in rv2.get_json()

    def test_put_url_creates_updated_event(self, client, app):
        from app.models.event import Event
        rv = client.post("/shorten", json={"original_url": "https://example.com"})
        url_id = rv.get_json()["id"]
        client.put(f"/urls/{url_id}", json={"title": "new title"})
        with app.app_context():
            events = list(Event.select().where(
                (Event.url_id == url_id) & (Event.event_type == "updated")
            ))
            assert len(events) == 1

    def test_post_urls_with_filter_by_user(self, client):
        user = client.post("/users", json={"username": "filteruser", "email": "filter@example.com"})
        user_id = user.get_json()["id"]
        client.post("/urls", json={"original_url": "https://example.com", "user_id": user_id})
        rv = client.get(f"/urls?user_id={user_id}")
        assert rv.status_code == 200
        data = rv.get_json()
        assert len(data) >= 1


class TestGracefulFailure:
    """Verify all endpoints return clean JSON errors, never stack traces."""

    def test_500_is_json_not_html(self, app):
        from werkzeug.exceptions import InternalServerError
        with app.test_request_context("/"):
            rv, status = app.handle_http_exception(InternalServerError())
        assert status == 500
        data = rv.get_json()
        assert data is not None, "500 response must be JSON"
        assert "error" in data

    def test_404_is_json_not_html(self, client):
        rv = client.get("/this-does-not-exist-at-all")
        assert rv.status_code == 404
        assert "application/json" in rv.content_type
        assert "error" in rv.get_json()

    def test_405_is_json_not_html(self, client):
        rv = client.delete("/health")
        assert rv.status_code == 405
        assert "application/json" in rv.content_type
        assert "error" in rv.get_json()

    def test_shorten_with_integer_url_returns_clean_error(self, client):
        rv = client.post("/shorten", json={"original_url": 12345})
        assert rv.status_code == 422
        data = rv.get_json()
        assert data is not None
        assert "error" in data

    def test_shorten_with_null_url_returns_clean_error(self, client):
        rv = client.post("/shorten", json={"original_url": None})
        assert rv.status_code == 422
        data = rv.get_json()
        assert data is not None
        assert "error" in data

    def test_shorten_with_url_missing_scheme_returns_clean_error(self, client):
        rv = client.post("/shorten", json={"original_url": "notaurl"})
        assert rv.status_code == 422
        data = rv.get_json()
        assert "error" in data

    def test_redirect_unknown_code_is_json(self, client):
        rv = client.get("/zzzthiscodedoesnotexist999")
        assert rv.status_code == 404
        assert "application/json" in rv.content_type
        assert "error" in rv.get_json()

    def test_stats_unknown_code_is_json(self, client):
        rv = client.get("/stats/zzz_no_such_code")
        assert rv.status_code == 404
        assert "application/json" in rv.content_type
        assert "error" in rv.get_json()

    def test_get_nonexistent_url_is_json(self, client):
        rv = client.get("/urls/999999")
        assert rv.status_code == 404
        assert "application/json" in rv.content_type
        assert "error" in rv.get_json()

    def test_delete_nonexistent_url_is_json(self, client):
        rv = client.delete("/urls/999999")
        assert rv.status_code == 404
        assert "application/json" in rv.content_type
        assert "error" in rv.get_json()

    def test_create_user_with_garbage_body_is_json(self, client):
        rv = client.post("/users", data="}{garbage", content_type="application/json")
        assert rv.status_code == 400
        data = rv.get_json()
        assert data is not None
        assert "error" in data

    def test_get_nonexistent_user_is_json(self, client):
        rv = client.get("/users/999999")
        assert rv.status_code == 404
        assert "application/json" in rv.content_type
        assert "error" in rv.get_json()

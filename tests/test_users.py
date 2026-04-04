"""Tests for the /users endpoints."""
import pytest


class TestListUsers:
    def test_list_users_returns_200(self, client):
        rv = client.get("/users")
        assert rv.status_code == 200
        assert isinstance(rv.get_json(), list)

    def test_list_users_empty_initially(self, client):
        rv = client.get("/users")
        assert rv.get_json() == []

    def test_list_users_returns_created_user(self, client):
        client.post("/users", json={"username": "alice", "email": "alice@example.com"})
        rv = client.get("/users")
        data = rv.get_json()
        assert len(data) == 1
        assert data[0]["username"] == "alice"


class TestGetUser:
    def test_get_existing_user(self, client):
        rv = client.post("/users", json={"username": "bob", "email": "bob@example.com"})
        user_id = rv.get_json()["id"]
        rv2 = client.get(f"/users/{user_id}")
        assert rv2.status_code == 200
        assert rv2.get_json()["email"] == "bob@example.com"

    def test_get_nonexistent_user_returns_404(self, client):
        rv = client.get("/users/999999")
        assert rv.status_code == 404
        assert "error" in rv.get_json()


class TestCreateUser:
    def test_create_user_returns_201(self, client):
        rv = client.post("/users", json={"username": "carol", "email": "carol@example.com"})
        assert rv.status_code == 201
        data = rv.get_json()
        assert data["username"] == "carol"
        assert data["email"] == "carol@example.com"
        assert "id" in data

    def test_create_user_missing_username_returns_400(self, client):
        rv = client.post("/users", json={"email": "x@example.com"})
        assert rv.status_code == 400
        assert "error" in rv.get_json()

    def test_create_user_missing_email_returns_400(self, client):
        rv = client.post("/users", json={"username": "x"})
        assert rv.status_code == 400
        assert "error" in rv.get_json()

    def test_create_user_no_json_returns_400(self, client):
        rv = client.post("/users", data="not json", content_type="text/plain")
        assert rv.status_code == 400
        assert "error" in rv.get_json()

    def test_create_user_duplicate_email_returns_409(self, client):
        client.post("/users", json={"username": "dave", "email": "dave@example.com"})
        rv = client.post("/users", json={"username": "dave2", "email": "dave@example.com"})
        assert rv.status_code == 409
        assert "error" in rv.get_json()

    def test_create_user_empty_username_returns_400(self, client):
        rv = client.post("/users", json={"username": "  ", "email": "x@example.com"})
        assert rv.status_code == 400

    def test_create_user_empty_email_returns_400(self, client):
        rv = client.post("/users", json={"username": "x", "email": "  "})
        assert rv.status_code == 400

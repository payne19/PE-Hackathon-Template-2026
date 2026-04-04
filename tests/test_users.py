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
        assert rv.status_code in (400, 422)
        assert "error" in rv.get_json()

    def test_create_user_missing_email_returns_400(self, client):
        rv = client.post("/users", json={"username": "x"})
        assert rv.status_code in (400, 422)
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

    def test_create_user_non_string_username_returns_422(self, client):
        rv = client.post("/users", json={"username": 123, "email": "x@example.com"})
        assert rv.status_code == 422
        assert "error" in rv.get_json()

    def test_create_user_non_string_email_returns_422(self, client):
        rv = client.post("/users", json={"username": "x", "email": 999})
        assert rv.status_code == 422
        assert "error" in rv.get_json()


class TestUpdateUser:
    def test_update_username(self, client):
        rv = client.post("/users", json={"username": "orig", "email": "orig@example.com"})
        user_id = rv.get_json()["id"]
        rv2 = client.put(f"/users/{user_id}", json={"username": "updated"})
        assert rv2.status_code == 200
        assert rv2.get_json()["username"] == "updated"

    def test_update_email(self, client):
        rv = client.post("/users", json={"username": "u1", "email": "u1@example.com"})
        user_id = rv.get_json()["id"]
        rv2 = client.put(f"/users/{user_id}", json={"email": "new@example.com"})
        assert rv2.status_code == 200
        assert rv2.get_json()["email"] == "new@example.com"

    def test_update_nonexistent_user_returns_404(self, client):
        rv = client.put("/users/999999", json={"username": "x"})
        assert rv.status_code == 404
        assert "error" in rv.get_json()

    def test_update_no_json_returns_400(self, client):
        rv = client.post("/users", json={"username": "u2", "email": "u2@example.com"})
        user_id = rv.get_json()["id"]
        rv2 = client.put(f"/users/{user_id}", data="bad", content_type="text/plain")
        assert rv2.status_code == 400
        assert "error" in rv2.get_json()

    def test_update_duplicate_email_returns_409(self, client):
        client.post("/users", json={"username": "a", "email": "a@example.com"})
        rv = client.post("/users", json={"username": "b", "email": "b@example.com"})
        user_id = rv.get_json()["id"]
        rv2 = client.put(f"/users/{user_id}", json={"email": "a@example.com"})
        assert rv2.status_code == 409
        assert "error" in rv2.get_json()

    def test_update_non_string_username_returns_422(self, client):
        rv = client.post("/users", json={"username": "u3", "email": "u3@example.com"})
        user_id = rv.get_json()["id"]
        rv2 = client.put(f"/users/{user_id}", json={"username": 42})
        assert rv2.status_code == 422
        assert "error" in rv2.get_json()


class TestBulkImportUsers:
    def test_bulk_import_csv(self, client):
        import io
        csv_data = "username,email\nfoo,foo@example.com\nbar,bar@example.com\n"
        rv = client.post(
            "/users/bulk",
            data={"file": (io.BytesIO(csv_data.encode()), "users.csv")},
            content_type="multipart/form-data",
        )
        assert rv.status_code == 201
        data = rv.get_json()
        assert data["imported"] == 2

    def test_bulk_import_no_file_returns_400(self, client):
        rv = client.post("/users/bulk", json={})
        assert rv.status_code == 400
        assert "error" in rv.get_json()

    def test_bulk_import_upserts_duplicates(self, client):
        import io
        client.post("/users", json={"username": "existing", "email": "exist@example.com"})
        csv_data = "username,email\nexisting,exist@example.com\nnew,new@example.com\n"
        rv = client.post(
            "/users/bulk",
            data={"file": (io.BytesIO(csv_data.encode()), "users.csv")},
            content_type="multipart/form-data",
        )
        assert rv.status_code == 201
        assert rv.get_json()["imported"] == 2


class TestListUsersPagination:
    def test_list_users_pagination(self, client):
        for i in range(3):
            client.post("/users", json={"username": f"pg{i}", "email": f"pg{i}@example.com"})
        rv = client.get("/users?page=1&per_page=2")
        assert rv.status_code == 200
        data = rv.get_json()
        assert isinstance(data, list)
        assert len(data) == 2

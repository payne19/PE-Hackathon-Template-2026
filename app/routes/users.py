import csv
import io
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.models.user import User

users_bp = Blueprint("users", __name__, url_prefix="/users")


def _user_dict(user):
    ca = user.created_at
    if ca and hasattr(ca, "strftime"):
        ca = ca.strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "created_at": ca,
    }


@users_bp.route("", methods=["GET"])
def list_users():
    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", 20, type=int)
    query = User.select()
    if page:
        users = list(query.paginate(page, per_page))
        return jsonify([_user_dict(u) for u in users])
    return jsonify([_user_dict(u) for u in query])


@users_bp.route("/<int:user_id>", methods=["GET"])
def get_user(user_id):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        return jsonify(error="User not found"), 404
    return jsonify(_user_dict(user))


@users_bp.route("", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    username = data.get("username")
    email = data.get("email")

    if username is None or not isinstance(username, str):
        return jsonify(error="username must be a non-empty string"), 422
    if email is None or not isinstance(email, str):
        return jsonify(error="email must be a non-empty string"), 422

    username = username.strip()
    email = email.strip()

    if not username:
        return jsonify(error="username is required"), 400
    if not email:
        return jsonify(error="email is required"), 400

    try:
        user = User.create(username=username, email=email, created_at=datetime.now(timezone.utc))
    except IntegrityError:
        return jsonify(error="Email already exists"), 409

    return jsonify(_user_dict(user)), 201


@users_bp.route("/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        return jsonify(error="User not found"), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    if "username" in data:
        if not isinstance(data["username"], str):
            return jsonify(error="username must be a string"), 422
        user.username = data["username"].strip()
    if "email" in data:
        if not isinstance(data["email"], str):
            return jsonify(error="email must be a string"), 422
        user.email = data["email"].strip()

    try:
        user.save()
    except IntegrityError:
        return jsonify(error="Email already exists"), 409

    return jsonify(_user_dict(user))


@users_bp.route("/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        return jsonify(error="User not found"), 404
    user.delete_instance(recursive=True)
    return jsonify(message="User deleted", id=user_id)


@users_bp.route("/bulk", methods=["POST"])
def bulk_import_users():
    if "file" not in request.files:
        return jsonify(error="file field is required"), 400

    f = request.files["file"]
    stream = io.StringIO(f.stream.read().decode("utf-8"))
    reader = csv.DictReader(stream)

    rows = list(reader)
    imported = 0
    for row in rows:
        try:
            _, created = User.get_or_create(
                username=row["username"],
                defaults={
                    "email": row["email"],
                    "created_at": row.get("created_at") or datetime.now(timezone.utc),
                },
            )
            if created:
                imported += 1
        except IntegrityError:
            pass

    return jsonify(imported=imported, count=len(rows)), 201

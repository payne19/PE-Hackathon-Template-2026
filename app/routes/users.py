from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.models.user import User

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("", methods=["GET"])
def list_users():
    users = list(User.select().dicts())
    return jsonify(users)


@users_bp.route("/<int:user_id>", methods=["GET"])
def get_user(user_id):
    user = User.get_or_none(User.id == user_id)
    if user is None:
        return jsonify(error="User not found"), 404
    return jsonify({"id": user.id, "username": user.username, "email": user.email, "created_at": str(user.created_at)})


@users_bp.route("", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    username = data.get("username", "").strip()
    email = data.get("email", "").strip()

    if not username:
        return jsonify(error="username is required"), 400
    if not email:
        return jsonify(error="email is required"), 400

    from datetime import datetime, timezone
    try:
        user = User.create(username=username, email=email, created_at=datetime.now(timezone.utc))
    except IntegrityError:
        return jsonify(error="Email already exists"), 409

    return jsonify({"id": user.id, "username": user.username, "email": user.email, "created_at": str(user.created_at)}), 201

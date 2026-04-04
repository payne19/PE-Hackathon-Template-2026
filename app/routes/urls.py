import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from peewee import IntegrityError

from app.models.event import Event
from app.models.url import Url
from app.models.user import User

urls_bp = Blueprint("urls", __name__, url_prefix="/urls")


def _url_dict(url):
    return {
        "id": url.id,
        "user_id": url.user_id,
        "short_code": url.short_code,
        "original_url": url.original_url,
        "title": url.title,
        "is_active": url.is_active,
        "created_at": str(url.created_at),
        "updated_at": str(url.updated_at),
    }


def _log_event(url, user_id, event_type, details=None):
    Event.create(
        url=url,
        user_id=user_id,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        details=json.dumps(details) if details else None,
    )


@urls_bp.route("", methods=["GET"])
def list_urls():
    urls = [_url_dict(u) for u in Url.select().where(Url.is_active == True)]
    return jsonify(urls)


@urls_bp.route("", methods=["POST"])
def create_url():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    short_code = data.get("short_code", "").strip()
    original_url = data.get("original_url", "").strip()
    user_id = data.get("user_id")
    title = data.get("title", "").strip() or None

    if not short_code:
        return jsonify(error="short_code is required"), 400
    if not original_url:
        return jsonify(error="original_url is required"), 400
    if not user_id:
        return jsonify(error="user_id is required"), 400

    user = User.get_or_none(User.id == user_id)
    if user is None:
        return jsonify(error="User not found"), 404

    now = datetime.now(timezone.utc)
    try:
        url = Url.create(
            user=user,
            short_code=short_code,
            original_url=original_url,
            title=title,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    except IntegrityError:
        return jsonify(error="short_code already exists"), 409

    _log_event(url, user_id, "created", {"short_code": short_code, "original_url": original_url})
    return jsonify(_url_dict(url)), 201


@urls_bp.route("/<string:short_code>", methods=["GET"])
def get_url(short_code):
    url = Url.get_or_none(Url.short_code == short_code)
    if url is None:
        return jsonify(error="URL not found"), 404
    if not url.is_active:
        return jsonify(error="URL is inactive"), 410
    return jsonify(_url_dict(url))


@urls_bp.route("/<string:short_code>", methods=["PATCH"])
def update_url(short_code):
    url = Url.get_or_none(Url.short_code == short_code)
    if url is None:
        return jsonify(error="URL not found"), 404
    if not url.is_active:
        return jsonify(error="URL is inactive"), 410

    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    changes = {}
    if "original_url" in data:
        url.original_url = data["original_url"].strip()
        changes["original_url"] = url.original_url
    if "title" in data:
        url.title = data["title"].strip() or None
        changes["title"] = url.title

    url.updated_at = datetime.now(timezone.utc)
    url.save()

    _log_event(url, url.user_id, "updated", changes)
    return jsonify(_url_dict(url))


@urls_bp.route("/<string:short_code>", methods=["DELETE"])
def delete_url(short_code):
    url = Url.get_or_none(Url.short_code == short_code)
    if url is None:
        return jsonify(error="URL not found"), 404
    if not url.is_active:
        return jsonify(error="URL already inactive"), 410

    url.is_active = False
    url.updated_at = datetime.now(timezone.utc)
    url.save()

    _log_event(url, url.user_id, "deleted", {"short_code": short_code})
    return jsonify({"message": "URL deactivated", "short_code": short_code})

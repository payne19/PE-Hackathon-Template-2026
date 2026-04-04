import random
import string
from datetime import datetime, timezone

from flask import Blueprint, jsonify, redirect, request
from playhouse.shortcuts import model_to_dict

from app.cache import cache
from app.models.event import Event
from app.models.url import URL

urls_bp = Blueprint("urls", __name__)


def _generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def _url_to_dict(url_obj):
    d = model_to_dict(url_obj, recurse=False)
    d["user_id"] = url_obj.user_id
    d.pop("user", None)
    return d


@urls_bp.route("/shorten", methods=["POST"])
def shorten():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="Request body must be JSON"), 400

    raw_url = data.get("original_url")
    if not isinstance(raw_url, str) or not raw_url.strip():
        return jsonify(error="original_url is required and must be a string"), 422

    original_url = raw_url.strip()
    if not original_url.startswith(("http://", "https://")):
        return jsonify(error="original_url must start with http:// or https://"), 422

    title = data.get("title") or None
    if isinstance(title, str):
        title = title.strip() or None
    user_id = data.get("user_id") or None

    short_code = data.get("short_code") or None
    if isinstance(short_code, str):
        short_code = short_code.strip() or None
    if short_code:
        if URL.select().where(URL.short_code == short_code).exists():
            return jsonify(error="short_code already in use"), 409
    else:
        for _ in range(10):
            candidate = _generate_short_code()
            if not URL.select().where(URL.short_code == candidate).exists():
                short_code = candidate
                break
        else:
            return jsonify(error="Could not generate unique short code"), 500

    now = datetime.now(timezone.utc)
    url = URL.create(
        short_code=short_code,
        original_url=original_url,
        title=title,
        user_id=user_id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    Event.create(
        url=url,
        user_id=user_id,
        event_type="created",
        timestamp=now,
        details=None,
    )

    return jsonify(_url_to_dict(url)), 201


def _get_cached_url(code):
    """Cacheable helper — returns (original_url, is_active) or None."""
    try:
        url = URL.get(URL.short_code == code)
        return {"id": url.id, "original_url": url.original_url, "is_active": url.is_active}
    except URL.DoesNotExist:
        return None


@urls_bp.route("/<string:code>", methods=["GET"])
def redirect_short(code):
    try:
        cached = cache.get(f"url:{code}")
    except Exception:
        cached = None
    if cached is None:
        try:
            url_obj = URL.get(URL.short_code == code)
            cached = {
                "id": url_obj.id,
                "original_url": url_obj.original_url,
                "is_active": url_obj.is_active,
            }
            try:
                cache.set(f"url:{code}", cached, timeout=300)
            except Exception:
                pass
        except URL.DoesNotExist:
            return jsonify(error="Short code not found"), 404

    if not cached["is_active"]:
        return jsonify(error="This link is no longer active"), 410

    Event.create(
        url_id=cached["id"],
        user_id=None,
        event_type="click",
        timestamp=datetime.now(timezone.utc),
        details=None,
    )

    return redirect(cached["original_url"], code=302)


@urls_bp.route("/urls/<string:code>/redirect", methods=["GET"])
def redirect_by_url_path(code):
    return redirect_short(code)


@urls_bp.route("/urls", methods=["GET"])
def list_urls():
    user_id = request.args.get("user_id", type=int)
    page = request.args.get("page", type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    query = URL.select()
    if user_id:
        query = query.where(URL.user_id == user_id)
    query = query.order_by(URL.created_at.desc())

    if page:
        query = query.paginate(page, per_page)

    return jsonify([_url_to_dict(u) for u in query])


@urls_bp.route("/urls", methods=["POST"])
def create_url():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="Request body must be JSON"), 400

    raw_url = data.get("original_url")
    if not isinstance(raw_url, str) or not raw_url.strip():
        return jsonify(error="original_url is required and must be a string"), 422

    original_url = raw_url.strip()
    if not original_url.startswith(("http://", "https://")):
        return jsonify(error="original_url must start with http:// or https://"), 422

    user_id = data.get("user_id")
    title = data.get("title") or None
    if isinstance(title, str):
        title = title.strip() or None
    short_code = data.get("short_code") or None
    if isinstance(short_code, str):
        short_code = short_code.strip() or None

    if user_id is not None:
        from app.models.user import User
        if User.get_or_none(User.id == user_id) is None:
            return jsonify(error="User not found"), 404

    if short_code:
        if URL.select().where(URL.short_code == short_code).exists():
            return jsonify(error="short_code already in use"), 409
    else:
        for _ in range(10):
            candidate = _generate_short_code()
            if not URL.select().where(URL.short_code == candidate).exists():
                short_code = candidate
                break
        else:
            return jsonify(error="Could not generate unique short code"), 500

    now = datetime.now(timezone.utc)
    url = URL.create(
        short_code=short_code,
        original_url=original_url,
        title=title,
        user_id=user_id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    Event.create(
        url=url,
        user_id=user_id,
        event_type="created",
        timestamp=now,
        details=None,
    )

    return jsonify(_url_to_dict(url)), 201


@urls_bp.route("/urls/<int:url_id>", methods=["GET"])
def get_url(url_id):
    try:
        url = URL.get_by_id(url_id)
    except URL.DoesNotExist:
        return jsonify(error="URL not found"), 404
    return jsonify(_url_to_dict(url))


@urls_bp.route("/urls/<int:url_id>", methods=["PUT"])
def update_url(url_id):
    try:
        url = URL.get_by_id(url_id)
    except URL.DoesNotExist:
        return jsonify(error="URL not found"), 404

    data = request.get_json(silent=True)
    if data is None:
        return jsonify(error="Request body must be JSON"), 400

    if "title" in data:
        url.title = data["title"]
    if "original_url" in data:
        new_url = data["original_url"]
        if not isinstance(new_url, str) or not new_url.strip():
            return jsonify(error="original_url must be a non-empty string"), 422
        new_url = new_url.strip()
        if not new_url.startswith(("http://", "https://")):
            return jsonify(error="original_url must start with http:// or https://"), 422
        url.original_url = new_url
    if "is_active" in data:
        url.is_active = bool(data["is_active"])
        if not url.is_active:
            cache.delete(f"url:{url.short_code}")

    url.updated_at = datetime.now(timezone.utc)
    url.save()

    Event.create(
        url=url,
        user_id=None,
        event_type="updated",
        timestamp=datetime.now(timezone.utc),
        details=None,
    )

    return jsonify(_url_to_dict(url))


@urls_bp.route("/urls/<int:url_id>", methods=["DELETE"])
def deactivate_url(url_id):
    try:
        url = URL.get_by_id(url_id)
    except URL.DoesNotExist:
        return jsonify(error="URL not found"), 404

    url.is_active = False
    url.updated_at = datetime.now(timezone.utc)
    url.save()

    try:
        cache.delete(f"url:{url.short_code}")
    except Exception:
        pass

    Event.create(
        url=url,
        user_id=None,
        event_type="deactivated",
        timestamp=datetime.now(timezone.utc),
        details=None,
    )

    return jsonify(message="URL deactivated", id=url_id)


@urls_bp.route("/stats/<string:code>", methods=["GET"])
def stats(code):
    try:
        url = URL.get(URL.short_code == code)
    except URL.DoesNotExist:
        return jsonify(error="Short code not found"), 404

    click_count = Event.select().where(
        (Event.url == url) & (Event.event_type == "click")
    ).count()

    return jsonify(
        short_code=code,
        original_url=url.original_url,
        title=url.title,
        is_active=url.is_active,
        click_count=click_count,
        created_at=str(url.created_at),
    )

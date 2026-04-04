from flask import Blueprint, jsonify, redirect, request

from app.models.url import URL
from app.services.url_service import (
    CodeGenerationError,
    URLInactiveError,
    URLNotFoundError,
    deactivate,
    resolve,
    shorten,
)

urls_bp = Blueprint("urls", __name__)


@urls_bp.post("/urls")
def shorten_url():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    original_url = data.get("original_url", "").strip()
    if not original_url:
        return jsonify(error="original_url is required"), 400
    if not original_url.startswith(("http://", "https://")):
        return jsonify(error="original_url must start with http:// or https://"), 400
    if len(original_url) > 2048:
        return jsonify(error="original_url must be 2048 characters or fewer"), 400

    # allow_duplicate=True → each call gets its own code even for identical URLs
    allow_duplicate = bool(data.get("allow_duplicate", False))

    try:
        result = shorten(
            original_url=original_url,
            user_id=data.get("user_id"),
            allow_duplicate=allow_duplicate,
        )
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except CodeGenerationError as exc:
        return jsonify(error=str(exc)), 500

    return jsonify(
        short_code=result.short_code,
        original_url=result.original_url,
        click_count=result.click_count,
        is_active=result.is_active,
        created_at=result.created_at,
        is_new=result.is_new,
    ), 201



@urls_bp.get("/urls")
def list_urls():
    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify(error="limit and offset must be integers"), 400

    if not (1 <= limit <= 100):
        return jsonify(error="limit must be between 1 and 100"), 400
    if offset < 0:
        return jsonify(error="offset must be 0 or greater"), 400

    query = URL.select().where(URL.is_active == True)
    total = query.count()
    rows = query.order_by(URL.created_at.desc()).limit(limit).offset(offset)

    return jsonify(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            {
                "short_code": u.short_code,
                "original_url": u.original_url,
                "click_count": u.click_count,
                "created_at": u.created_at.isoformat(),
            }
            for u in rows
        ],
    )



@urls_bp.get("/urls/<short_code>")
def get_url(short_code: str):
    try:
        url = URL.get(URL.short_code == short_code)
    except URL.DoesNotExist:
        return jsonify(error="Short URL not found"), 404
    return jsonify(
        short_code=url.short_code,
        original_url=url.original_url,
        click_count=url.click_count,
        is_active=url.is_active,
        created_at=url.created_at.isoformat(),
    )



@urls_bp.delete("/urls/<short_code>")
def delete_url(short_code: str):
    try:
        deactivate(short_code)
    except URLNotFoundError:
        return jsonify(error="Short URL not found"), 404
    return "", 204


@urls_bp.get("/r/<short_code>")
def redirect_url(short_code: str):
    try:
        original_url = resolve(short_code)
    except URLNotFoundError:
        return jsonify(error="Short URL not found"), 404
    except URLInactiveError:
        return jsonify(error="This short URL has been deactivated"), 410
    return redirect(original_url, code=302)

import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.models.event import Event

events_bp = Blueprint("events", __name__, url_prefix="/events")


def _event_dict(event):
    details = event.details
    if details:
        try:
            details = json.loads(details)
        except (ValueError, TypeError):
            pass

    return {
        "id": event.id,
        "url_id": event.url_id,
        "user_id": event.user_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp.strftime("%Y-%m-%dT%H:%M:%S") if event.timestamp else None,
        "details": details,
    }


@events_bp.route("", methods=["GET"])
def list_events():
    url_id = request.args.get("url_id", type=int)
    user_id = request.args.get("user_id", type=int)
    event_type = request.args.get("event_type")
    page = request.args.get("page", type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    query = Event.select()
    if url_id:
        query = query.where(Event.url_id == url_id)
    if user_id:
        query = query.where(Event.user_id == user_id)
    if event_type:
        query = query.where(Event.event_type == event_type)

    query = query.order_by(Event.timestamp.desc())

    if page:
        query = query.paginate(page, per_page)

    return jsonify([_event_dict(e) for e in query])


@events_bp.route("/<int:event_id>", methods=["GET"])
def get_event(event_id):
    event = Event.get_or_none(Event.id == event_id)
    if event is None:
        return jsonify(error="Event not found"), 404
    return jsonify(_event_dict(event))


@events_bp.route("/<int:event_id>", methods=["PUT"])
def update_event(event_id):
    event = Event.get_or_none(Event.id == event_id)
    if event is None:
        return jsonify(error="Event not found"), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    if "event_type" in data:
        event.event_type = data["event_type"]
    if "details" in data:
        details = data["details"]
        if details and not isinstance(details, str):
            details = json.dumps(details)
        event.details = details
    if "url_id" in data:
        event.url_id = data["url_id"]
    if "user_id" in data:
        event.user_id = data["user_id"]

    event.save()
    return jsonify(_event_dict(event))


@events_bp.route("/<int:event_id>", methods=["DELETE"])
def delete_event(event_id):
    event = Event.get_or_none(Event.id == event_id)
    if event is None:
        return jsonify(error="Event not found"), 404
    event.delete_instance()
    return jsonify(message="Event deleted", id=event_id)


@events_bp.route("", methods=["POST"])
def create_event():
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="Request body must be JSON"), 400

    url_id = data.get("url_id")
    user_id = data.get("user_id")
    event_type = data.get("event_type")

    if not event_type:
        return jsonify(error="event_type is required"), 422

    details = data.get("details")
    if details and not isinstance(details, str):
        details = json.dumps(details)

    event = Event.create(
        url_id=url_id,
        user_id=user_id,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        details=details,
    )

    return jsonify(_event_dict(event)), 201

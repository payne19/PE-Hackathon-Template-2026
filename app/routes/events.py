import json

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

    query = Event.select()
    if url_id:
        query = query.where(Event.url_id == url_id)
    if user_id:
        query = query.where(Event.user_id == user_id)

    query = query.order_by(Event.timestamp.desc())
    return jsonify([_event_dict(e) for e in query])

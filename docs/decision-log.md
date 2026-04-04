# Decision Log

## Why Redis for Caching?

**Options considered:** In-process dict, Memcached, Redis  
**Choice:** Redis

Redis is the standard choice for distributed caching because it's shared across all app instances (in-process caching would give each container its own stale copy), supports TTL natively, and doubles as a message broker if needed later. The `flask-caching` library has first-class Redis support.

---

## Why Nginx as Load Balancer?

**Options considered:** HAProxy, Traefik, Nginx  
**Choice:** Nginx

Nginx is battle-tested, has near-zero overhead for reverse proxying, and the config is simple to understand and demo. HAProxy is marginally faster but harder to configure. Traefik auto-discovers Docker containers but adds operational complexity we don't need for this demo.

---

## Why Gunicorn (not Flask dev server)?

Flask's built-in server is single-threaded and not safe for production. Gunicorn forks multiple worker processes (`--workers 4`), allowing true parallelism even on a single container. Each worker handles one request at a time but 4 workers handle 4 concurrent requests per container, giving 8 concurrent request capacity across 2 containers before queuing.

---

## Why Locust (not k6)?

**Options considered:** k6, Locust, Apache JMeter  
**Choice:** Locust

Locust is pure Python — no separate binary install, easy to read, and integrates naturally into the Python project. k6 uses JavaScript and requires a separate install. For a hackathon demo, Locust's web UI also gives a visual real-time graph that's easy to screenshot.

---

## Why Prometheus + Grafana (not Datadog)?

Prometheus + Grafana is fully open-source, runs in Docker Compose alongside the app with zero external accounts, and `prometheus-flask-exporter` auto-instruments all Flask routes. Datadog requires an agent, API key, and internet connectivity — too much friction for a hackathon.

---

## Why 2 App Replicas (not 3)?

Two replicas demonstrate horizontal scaling clearly in `docker ps` while keeping resource usage low on a laptop. The Nginx upstream round-robins between them. Adding a 3rd replica is a one-line change to `docker-compose.yml`.

---

## Why Peewee (not SQLAlchemy)?

The template came with Peewee. It's lighter-weight, has a simpler API for CRUD, and the `DatabaseProxy` pattern makes it easy to swap to SQLite for testing. SQLAlchemy would be the choice for a production app at scale.

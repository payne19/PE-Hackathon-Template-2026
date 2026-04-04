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

## Why 3 App Replicas?

Three replicas provide higher throughput and fault tolerance — losing one still leaves two healthy instances behind Nginx's `least_conn` balancer. Combined with PgBouncer connection pooling, this setup handled 1000 concurrent users at a 0.05% error rate in load testing.

---

## Why Peewee (not SQLAlchemy)?

The template came with Peewee. It's lighter-weight, has a simpler API for CRUD, and the `DatabaseProxy` pattern makes it easy to swap to SQLite for testing. SQLAlchemy would be the choice for a production app at scale.

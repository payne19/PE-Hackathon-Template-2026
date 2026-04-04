import os

from flask_caching import Cache

cache = Cache()


def init_cache(app):
    if not app.config.get("CACHE_TYPE"):
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        app.config["CACHE_TYPE"] = "RedisCache"
        app.config["CACHE_REDIS_URL"] = redis_url
    app.config.setdefault("CACHE_DEFAULT_TIMEOUT", 300)
    try:
        cache.init_app(app)
    except Exception:
        app.config["CACHE_TYPE"] = "SimpleCache"
        cache.init_app(app)

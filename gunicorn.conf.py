import os

bind = "0.0.0.0:5000"
workers = int(os.environ.get("GUNICORN_WORKERS", 4))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", 8))
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "warning"

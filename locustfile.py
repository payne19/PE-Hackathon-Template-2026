"""
Load test for the URL Shortener service.

Run:
    locust -f locustfile.py --host http://localhost
    # or against Docker Compose:
    locust -f locustfile.py --host http://localhost:80

Targets:
  - Bronze:  50 concurrent users
  - Silver: 200 concurrent users (all requests <3s)
  - Gold:   500 concurrent users (<5% error rate)
"""
import random
import string

from locust import HttpUser, between, task

SEED_CODES = []


def _random_url():
    slug = "".join(random.choices(string.ascii_lowercase, k=8))
    return f"https://example-{slug}.com/path"


class UrlShortenerUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        rv = self.client.post(
            "/shorten",
            json={"original_url": _random_url()},
            name="/shorten [setup]",
        )
        if rv.status_code == 201:
            SEED_CODES.append(rv.json()["short_code"])

    @task(6)
    def redirect(self):
        if not SEED_CODES:
            return
        code = random.choice(SEED_CODES)
        with self.client.get(
            f"/{code}",
            name="/<code> [redirect]",
            allow_redirects=False,
            catch_response=True,
        ) as resp:
            if resp.status_code in (302, 200, 404, 410):
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(2)
    def shorten(self):
        rv = self.client.post(
            "/shorten",
            json={"original_url": _random_url()},
            name="/shorten",
        )
        if rv.status_code == 201:
            SEED_CODES.append(rv.json()["short_code"])

    @task(1)
    def list_urls(self):
        self.client.get("/urls?page=1&per_page=10", name="/urls")

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")

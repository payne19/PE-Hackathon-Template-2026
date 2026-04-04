# URL Shortener — MLH PE Hackathon 2026

A production-grade URL shortener built for the MLH Production Engineering Hackathon.

**Stack:** Flask · Peewee ORM · PostgreSQL · Redis · Nginx · PgBouncer · Docker Compose

## Architecture

```
                        ┌──────────────────────────────┐
Internet ──▶ Nginx :80  │  least_conn load balancer    │
                        └───┬───────────┬──────────┬───┘
                            │           │          │
                       app1:5000   app2:5000   app3:5000
                       (gthread)   (gthread)   (gthread)
                            │           │          │
                        ┌───▼───────────▼──────────▼───┐
                        │   PgBouncer (conn pool)      │
                        │   PostgreSQL :5432            │
                        └──────────────────────────────┘
                        ┌──────────────────────────────┐
                        │   Redis :6379  (URL cache)   │
                        └──────────────────────────────┘
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check → `{"status":"ok"}` |
| POST | `/shorten` | Create a short URL |
| GET | `/<code>` | Redirect (cached in Redis) |
| GET | `/urls` | List active URLs (paginated) |
| GET | `/urls/<id>` | Get URL by ID |
| DELETE | `/urls/<id>` | Deactivate URL |
| GET | `/stats/<code>` | Click stats for a short code |

See [`docs/api.md`](docs/api.md) for full request/response details.

## **Important**

You need to work with around the seed files that you can find in [MLH PE Hackathon](https://mlh-pe-hackathon.com) platform. This will help you build the schema for the database and have some data to do some testing and submit your project for judging. If you need help with this, reach out on Discord or on the Q&A tab on the platform.

## Prerequisites

- **uv** — a fast Python package manager that handles Python versions, virtual environments, and dependencies automatically.
  Install it with:
  ```bash
  # macOS / Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Windows (PowerShell)
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
  For other methods see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/).
- PostgreSQL running locally (you can use Docker or a local instance)

## uv Basics

`uv` manages your Python version, virtual environment, and dependencies automatically — no manual `python -m venv` needed.

| Command | What it does |
|---------|--------------|
| `uv sync` | Install all dependencies (creates `.venv` automatically) |
| `uv run <script>` | Run a script using the project's virtual environment |
| `uv add <package>` | Add a new dependency |
| `uv remove <package>` | Remove a dependency |

## Quick Start (Docker — recommended)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
# 1. Clone & configure
git clone <repo-url> && cd PE-Hackathon-Template-2026
cp .env.example .env          # edit DATABASE_PASSWORD if needed

# 2. Build and start everything
docker compose up --build -d

# 3. Seed the database from CSVs
docker compose exec app1 uv run load_data.py

# 4. Verify
curl http://localhost/health
# → {"status":"ok"}

```

### Chaos Demo (Reliability Gold)
```bash
# Kill one instance — watch the other keep serving
docker stop pe-hackathon-template-2026-app1-1
curl http://localhost/health   # still 200 ✅
docker compose up -d app1      # resurrects automatically
```

### Load Test (Scalability Gold)
```bash
uv add --dev locust
uv run locust -f locustfile.py --host http://localhost \
  --headless -u 500 -r 50 --run-time 2m
```

## Quick Start (Local dev)

```bash
# 1. Install dependencies
uv sync --extra dev

# 2. Create the database
createdb hackathon_db

# 3. Configure environment
cp .env.example .env

# 4. Run the server
uv run run.py

# 5. Seed data (optional)
uv run load_data.py

# 6. Verify
curl http://localhost:5000/health
# → {"status":"ok"}
```

## Project Structure

```
mlh-pe-hackathon/
├── app/
│   ├── __init__.py          # App factory (create_app)
│   ├── database.py          # DatabaseProxy, BaseModel, connection hooks
│   ├── models/
│   │   └── __init__.py      # Import your models here
│   └── routes/
│       └── __init__.py      # register_routes() — add blueprints here
├── .env.example             # DB connection template
├── .gitignore               # Python + uv gitignore
├── .python-version          # Pin Python version for uv
├── pyproject.toml           # Project metadata + dependencies
├── run.py                   # Entry point: uv run run.py
└── README.md
```

## How to Add a Model

1. Create a file in `app/models/`, e.g. `app/models/product.py`:

```python
from peewee import CharField, DecimalField, IntegerField

from app.database import BaseModel


class Product(BaseModel):
    name = CharField()
    category = CharField()
    price = DecimalField(decimal_places=2)
    stock = IntegerField()
```

2. Import it in `app/models/__init__.py`:

```python
from app.models.product import Product
```

3. Create the table (run once in a Python shell or a setup script):

```python
from app.database import db
from app.models.product import Product

db.create_tables([Product])
```

## How to Add Routes

1. Create a blueprint in `app/routes/`, e.g. `app/routes/products.py`:

```python
from flask import Blueprint, jsonify
from playhouse.shortcuts import model_to_dict

from app.models.product import Product

products_bp = Blueprint("products", __name__)


@products_bp.route("/products")
def list_products():
    products = Product.select()
    return jsonify([model_to_dict(p) for p in products])
```

2. Register it in `app/routes/__init__.py`:

```python
def register_routes(app):
    from app.routes.products import products_bp
    app.register_blueprint(products_bp)
```

## How to Load CSV Data

```python
import csv
from peewee import chunked
from app.database import db
from app.models.product import Product

def load_csv(filepath):
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    with db.atomic():
        for batch in chunked(rows, 100):
            Product.insert_many(batch).execute()
```

## Useful Peewee Patterns

```python
from peewee import fn
from playhouse.shortcuts import model_to_dict

# Select all
products = Product.select()

# Filter
cheap = Product.select().where(Product.price < 10)

# Get by ID
p = Product.get_by_id(1)

# Create
Product.create(name="Widget", category="Tools", price=9.99, stock=50)

# Convert to dict (great for JSON responses)
model_to_dict(p)

# Aggregations
avg_price = Product.select(fn.AVG(Product.price)).scalar()
total = Product.select(fn.SUM(Product.stock)).scalar()

# Group by
from peewee import fn
query = (Product
         .select(Product.category, fn.COUNT(Product.id).alias("count"))
         .group_by(Product.category))
```

## Tips

- Use `model_to_dict` from `playhouse.shortcuts` to convert model instances to dictionaries for JSON responses.
- Wrap bulk inserts in `db.atomic()` for transactional safety and performance.
- The template uses `teardown_appcontext` for connection cleanup, so connections are closed even when requests fail.
- Check `.env.example` for all available configuration options.
